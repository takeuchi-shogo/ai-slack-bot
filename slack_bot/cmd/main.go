package main

import (
	"context"
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
	"github.com/takeuchi-shogo/ai-slack-bot/slack_bot/bootstrap"
	"github.com/takeuchi-shogo/ai-slack-bot/slack_bot/config"
	"go.uber.org/fx"
)

type SlackBotApp struct {
	SlackClient      *slack.Client
	SocketModeClient *socketmode.Client
	AppConfig        *config.AppConfig
}

func main() {
	fx.New(
		bootstrap.CommandModule,
		fx.Provide(NewSlackBotApp),
		fx.Invoke(func(app *SlackBotApp) {
			// 依存性の注入が完了したことを確認するだけ
			fmt.Println("Slack Bot Application started")
		}),
	).Run()
}

func NewSlackBotApp(lc fx.Lifecycle, cfg *config.AppConfig) *SlackBotApp {
	fmt.Println("AppConfig: ", cfg)

	// Slackクライアントを作成
	api := slack.New(
		cfg.SlackBot.BotToken,
		slack.OptionAppLevelToken(cfg.SlackBot.AppToken), // Socketモードに必要なAppトークンを設定
		slack.OptionDebug(true),
		slack.OptionLog(log.New(os.Stdout, "slack-bot: ", log.Lshortfile|log.LstdFlags)),
	)

	// SocketModeクライアントを作成
	socketClient := socketmode.New(
		api,
		socketmode.OptionDebug(true),
		socketmode.OptionLog(log.New(os.Stdout, "socketmode: ", log.Lshortfile|log.LstdFlags)),
	)

	app := &SlackBotApp{
		SlackClient:      api,
		SocketModeClient: socketClient,
		AppConfig:        cfg,
	}

	// イベントハンドラを設定
	go app.handleEvents()

	// ライフサイクルフックを追加
	lc.Append(fx.Hook{
		OnStart: func(ctx context.Context) error {
			fmt.Println("Starting SocketMode client...")
			// 非同期でSocketModeクライアントを起動
			go func() {
				err := app.SocketModeClient.Run()
				if err != nil {
					log.Printf("SocketMode実行エラー: %v", err)
					// エラーが致命的な場合はプロセスを終了
					os.Exit(1)
				}
			}()
			return nil
		},
		OnStop: func(ctx context.Context) error {
			fmt.Println("Stopping Slack Bot Application...")
			// 必要なクリーンアップ処理をここに記述
			return nil
		},
	})

	return app
}

// イベント処理を行うメソッド
func (app *SlackBotApp) handleEvents() {
	for evt := range app.SocketModeClient.Events {
		switch evt.Type {
		case socketmode.EventTypeConnecting:
			fmt.Println("Connecting to Slack...")
		case socketmode.EventTypeConnectionError:
			fmt.Printf("Connection error: %v\n", evt.Data)
		case socketmode.EventTypeConnected:
			fmt.Println("Connected to Slack!")
		case socketmode.EventTypeEventsAPI:
			// イベントを確認してACK（応答）を返す
			app.SocketModeClient.Ack(*evt.Request)

			eventsAPIEvent, ok := evt.Data.(slackevents.EventsAPIEvent)
			if !ok {
				log.Printf("Type assertion error: %v", evt.Data)
				continue
			}

			switch eventsAPIEvent.Type {
			case slackevents.CallbackEvent:
				innerEvent := eventsAPIEvent.InnerEvent
				switch ev := innerEvent.Data.(type) {
				case *slackevents.AppMentionEvent:
					fmt.Println("AppMentionEvent")
					app.handleAppMention(ev)
				}
			}
		}
	}
}

// メンション処理メソッド
func (app *SlackBotApp) handleAppMention(evt *slackevents.AppMentionEvent) {
	// メッセージのメタデータとコンテンツを表示
	fmt.Printf("メンション情報: %+v\n", evt)
	fmt.Printf("メンション詳細:\n")
	fmt.Printf("  チャンネル: %s\n", evt.Channel)
	fmt.Printf("  ユーザー: %s\n", evt.User)
	fmt.Printf("  タイムスタンプ: %s\n", evt.TimeStamp)
	fmt.Printf("  スレッドタイムスタンプ: %s\n", evt.ThreadTimeStamp)
	fmt.Printf("  メッセージテキスト: %s\n", evt.Text)

	// ElasticMQにメッセージを送信
	err := app.sendToElasticMQ(evt)
	if err != nil {
		fmt.Printf("ElasticMQへの送信エラー: %v\n", err)

		// エラーが発生した場合のみSlackに返信
		_, _, err = app.SlackClient.PostMessage(evt.Channel,
			slack.MsgOptionText(fmt.Sprintf("<@%s> メッセージキューへの送信中にエラーが発生しました。", evt.User), false),
			slack.MsgOptionTS(evt.ThreadTimeStamp),
		)
		if err != nil {
			fmt.Printf("返信エラー: %v\n", err)
		}
		return
	}

	// キューに正常に送信できた場合は返信しない（Pythonが処理する）
	log.Printf("メッセージをキューに送信しました。処理はPythonに委譲します。")
}

// ElasticMQにメッセージを送信するメソッド
func (app *SlackBotApp) sendToElasticMQ(evt *slackevents.AppMentionEvent) error {
	// AWS SDKの設定
	sess, err := session.NewSession(&aws.Config{
		Region:   aws.String(app.AppConfig.ElasticMQ.Region),
		Endpoint: aws.String(app.AppConfig.ElasticMQ.Endpoint),
		Credentials: credentials.NewStaticCredentials(
			app.AppConfig.ElasticMQ.AccessKey,
			app.AppConfig.ElasticMQ.SecretKey,
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
		"text":      evt.Text,
		"user":      evt.User,
		"channel":   evt.Channel,
		"ts":        evt.TimeStamp,
		"thread_ts": evt.ThreadTimeStamp,
		"source":    "slack",
	})
	if err != nil {
		return fmt.Errorf("JSONエンコードエラー: %w", err)
	}

	// キューURLの構築
	queueURL := fmt.Sprintf("%s/queue/%s", app.AppConfig.ElasticMQ.Endpoint, app.AppConfig.ElasticMQ.QueueName)

	// メッセージ送信
	_, err = svc.SendMessage(&sqs.SendMessageInput{
		QueueUrl:    aws.String(queueURL),
		MessageBody: aws.String(string(messageBody)),
	})
	if err != nil {
		return fmt.Errorf("SQS送信エラー: %w", err)
	}

	fmt.Printf("メッセージを%sのキュー%sに送信しました\n", app.AppConfig.ElasticMQ.Endpoint, app.AppConfig.ElasticMQ.QueueName)
	return nil
}
