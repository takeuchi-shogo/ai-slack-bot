package di

import (
	"context"

	"github.com/oklog/ulid/v2"
	"github.com/takeuchi-shogo/ai-slack-bot/slack_bot/pkg/infra/entity"
)

type SlackMentionRepository interface {
	Create(context.Context, *entity.SlackMention) error
	FindByID(context.Context, ulid.ULID) (*entity.SlackMention, error)
}
