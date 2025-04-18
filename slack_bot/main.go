package main

import (
	"fmt"
	"log"
	"os"

	"github.com/slack-go/slack"
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
			}
		}
	}()

	err = client.Run()
	if err != nil {
		log.Fatal(err)
	}
}
