package bootstrap

import (
	"github.com/takeuchi-shogo/ai-slack-bot/slack_bot/config"
	"github.com/takeuchi-shogo/ai-slack-bot/slack_bot/pkg/modules"
	"go.uber.org/fx"
)

var CommandModule = fx.Options(
	config.Module,
	modules.RepositoryModule,
)
