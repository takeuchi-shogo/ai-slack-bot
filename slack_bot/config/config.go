package config

import "github.com/spf13/viper"

type AppConfig struct {
	SlackBot struct {
		BotToken string `mapstructure:"bot_token"`
		AppToken string `mapstructure:"app_token"`
	} `mapstructure:"slack_bot"`
}

func NewAppConfig() (*AppConfig, error) {
	viper.SetConfigName("config")
	viper.SetConfigType("yml")
	// viper.AddConfigPath(".")
	viper.AddConfigPath("./config")

	if err := viper.ReadInConfig(); err != nil {
		return nil, err
	}

	cfg := &AppConfig{}
	if err := viper.Unmarshal(cfg); err != nil {
		return nil, err
	}

	return cfg, nil
}
