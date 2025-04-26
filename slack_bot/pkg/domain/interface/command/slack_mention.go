package command

import (
	"context"

	"github.com/takeuchi-shogo/ai-slack-bot/slack_bot/pkg/infra/entity"
)

type SlackMentionCommand interface {
	Create(context.Context, *entity.SlackMention) error
}
