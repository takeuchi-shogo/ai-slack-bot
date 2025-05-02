package config

import (
	"fmt"

	"github.com/spf13/viper"
	"go.uber.org/fx"
)

var Module = fx.Options(
	fx.Provide(NewAppConfig),
)

type AppConfig struct {
	SlackBot  SlackBotConfig  `mapstructure:"slack_bot"`
	ElasticMQ ElasticMQConfig `mapstructure:"elasticmq"`
}

type SlackBotConfig struct {
	BotToken string `mapstructure:"bot_token"`
	AppToken string `mapstructure:"app_token"`
}

type ElasticMQConfig struct {
	Endpoint  string `mapstructure:"endpoint"`
	QueueName string `mapstructure:"queue_name"`
	Region    string `mapstructure:"region"`
	AccessKey string `mapstructure:"access_key"`
	SecretKey string `mapstructure:"secret_key"`
}

func NewAppConfig() (*AppConfig, error) {
	v := viper.New()
	v.SetConfigName("config")
	v.SetConfigType("yml")
	v.AddConfigPath("./config")
	v.AddConfigPath("./slack_bot/config")

	if err := v.ReadInConfig(); err != nil {
		return nil, fmt.Errorf("設定ファイルの読み込みに失敗しました: %w", err)
	}

	var config AppConfig
	if err := v.Unmarshal(&config); err != nil {
		return nil, fmt.Errorf("設定ファイルのパースに失敗しました: %w", err)
	}

	// 必須項目の検証
	if config.SlackBot.BotToken == "" {
		return nil, fmt.Errorf("Slack Bot Token (slack_bot.bot_token) が設定されていません")
	}
	if config.SlackBot.AppToken == "" {
		return nil, fmt.Errorf("Slack App Token (slack_bot.app_token) が設定されていません")
	}

	return &config, nil
}
