package query

import (
	"context"

	"github.com/takeuchi-shogo/ai-slack-bot/slack_bot/pkg/domain/model/slack"
	"github.com/takeuchi-shogo/ai-slack-bot/slack_bot/pkg/infra/entity"
)

type SlackMentionQuery interface {
	FindByID(context.Context, slack.MentionID) (*entity.SlackMention, error)
}
