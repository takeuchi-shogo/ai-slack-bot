package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"

	"github.com/aws/aws-sdk-go/aws"
	"github.com/aws/aws-sdk-go/aws/credentials"
	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/aws/aws-sdk-go/service/sqs"
	"github.com/slack-go/slack"
	"github.com/slack-go/slack/slackevents"
	"github.com/slack-go/slack/socketmode"
	"github.com/takeuchi-shogo/ai-slack-bot/slack_bot/config"
)

func main() {
	cfg, err := config.NewAppConfig()
	if err != nil {
		log.Fatal(err)
	}

	api := slack.New(
		cfg.SlackBot.BotToken,
		slack.OptionDebug(true),
		slack.OptionLog(log.New(os.Stdout, "slack-bot: ", log.Lshortfile|log.LstdFlags)),
		slack.OptionAppLevelToken(cfg.SlackBot.AppToken),
	)

	// イベントハンドラを登録
	client := socketmode.New(
		api,
		socketmode.OptionDebug(true),
		socketmode.OptionLog(log.New(os.Stdout, "slack-bot: ", log.Lshortfile|log.LstdFlags)),
	)

	go func() {
		for evt := range client.Events {
			switch evt.Type {
			case socketmode.EventTypeConnecting:
				fmt.Println("Connecting to Slack...")
			case socketmode.EventTypeConnected:
				fmt.Println("Connected to Slack!")
			case socketmode.EventTypeEventsAPI:
				log.Println("EventsAPI")
				eventsAPIEvent, ok := evt.Data.(slackevents.EventsAPIEvent)
				if !ok {
					log.Printf("Could not type assert to EventsAPIEvent: %v", evt)
					continue
				}
				log.Printf("Received event: %+v", eventsAPIEvent)

				switch eventsAPIEvent.Type {
				case slackevents.CallbackEvent:
					innerEvent := eventsAPIEvent.InnerEvent
					switch ev := innerEvent.Data.(type) {
					case *slackevents.AppMentionEvent:
						fmt.Println("AppMentionEvent")
						handleAppMention(ev, api)
					}
				}
			}
		}
	}()

	err = client.Run()
	if err != nil {
		log.Fatal(err)
	}
}

func handleAppMention(evt *slackevents.AppMentionEvent, client *slack.Client) {
	// メッセージのメタデータとコンテンツを表示
	fmt.Printf("メンション情報:\n")
	fmt.Printf("  チャンネル: %s\n", evt.Channel)
	fmt.Printf("  ユーザー: %s\n", evt.User)
	fmt.Printf("  タイムスタンプ: %s\n", evt.TimeStamp)
	fmt.Printf("  スレッドタイムスタンプ: %s\n", evt.ThreadTimeStamp)
	fmt.Printf("  メッセージテキスト: %s\n", evt.Text)

	// ElasticMQにメッセージを送信
	err := sendToElasticMQ(evt)
	if err != nil {
		fmt.Printf("ElasticMQへの送信エラー: %v\n", err)
	}

	// スレッドに初期返信
	_, _, err = client.PostMessage(evt.Channel,
		slack.MsgOptionText(fmt.Sprintf("<@%s> メンションを受け取りました。処理中です...", evt.User), false),
		slack.MsgOptionTS(evt.ThreadTimeStamp),
	)

	if err != nil {
		fmt.Printf("返信エラー: %v\n", err)
	}
}

// ElasticMQにメッセージを送信する関数
func sendToElasticMQ(evt *slackevents.AppMentionEvent) error {
	// 設定を取得
	cfg, err := config.NewAppConfig()
	if err != nil {
		return fmt.Errorf("設定読み込みエラー: %w", err)
	}

	// AWS SDKの設定
	sess, err := session.NewSession(&aws.Config{
		Region:   aws.String(cfg.ElasticMQ.Region),
		Endpoint: aws.String(cfg.ElasticMQ.Endpoint),
		Credentials: credentials.NewStaticCredentials(
			cfg.ElasticMQ.AccessKey,
			cfg.ElasticMQ.SecretKey,
			"", // トークン
		),
	})
	if err != nil {
		return fmt.Errorf("AWSセッション作成エラー: %w", err)
	}

	// SQSクライアントの作成
	svc := sqs.New(sess)

	// メッセージ内容の作成
	messageBody, err := json.Marshal(map[string]string{
		"text":       evt.Text,
		"user":       evt.User,
		"channel":    evt.Channel,
		"ts":         evt.TimeStamp,
		"thread_ts":  evt.ThreadTimeStamp,
		"source":     "slack",
	})
	if err != nil {
		return fmt.Errorf("JSONエンコードエラー: %w", err)
	}

	// キューURLの構築
	queueURL := fmt.Sprintf("%s/queue/%s", cfg.ElasticMQ.Endpoint, cfg.ElasticMQ.QueueName)

	// メッセージ送信
	_, err = svc.SendMessage(&sqs.SendMessageInput{
		QueueUrl:    aws.String(queueURL),
		MessageBody: aws.String(string(messageBody)),
	})
	if err != nil {
		return fmt.Errorf("SQS送信エラー: %w", err)
	}

	fmt.Printf("メッセージを%sのキュー%sに送信しました\n", cfg.ElasticMQ.Endpoint, cfg.ElasticMQ.QueueName)
	return nil
}
