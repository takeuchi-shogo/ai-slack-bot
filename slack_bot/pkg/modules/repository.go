package modules

import (
	"github.com/takeuchi-shogo/ai-slack-bot/slack_bot/pkg/infra/repository"
	"go.uber.org/fx"
)

var RepositoryModule = fx.Options(
	fx.Provide(repository.NewSlackMentionRepository),
)
