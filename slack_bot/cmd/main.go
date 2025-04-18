package main

import (
	"fmt"
	"log"
	"os"

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

	// スレッドに返信
	_, _, err := client.PostMessage(evt.Channel,
		slack.MsgOptionText(fmt.Sprintf("<@%s> メンションを受け取りました！", evt.User), false),
		slack.MsgOptionTS(evt.ThreadTimeStamp),
	)

	if err != nil {
		fmt.Printf("返信エラー: %v\n", err)
	}
}
