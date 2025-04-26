package entity

import (
	"time"

	"github.com/oklog/ulid/v2"
	"github.com/takeuchi-shogo/ai-slack-bot/slack_bot/pkg/domain/model/slack"
)

type SlackMention struct {
	ID        ulid.ULID `bun:"id,pk,type:ulid"`
	Type      string    `bun:"type"`
	UserID    string    `bun:"user_id"`
	ChannelID string    `bun:"channel_id"`
	Text      string    `bun:"text"`
	Timestamp time.Time `bun:"timestamp"`
	EventTime time.Time `bun:"event_time"`
	CreatedAt time.Time `bun:"created_at"`
	UpdatedAt time.Time `bun:"updated_at"`
	DeletedAt time.Time `bun:"deleted_at"`
}

func NewSlackMention(mention *slack.Mention) (*SlackMention, error) {
	return &SlackMention{
		ID:        ulid.ULID(mention.ID),
		Type:      "mention",
		UserID:    string(mention.UserID),
		ChannelID: string(mention.ChannelID),
		Text:      string(mention.Text),
		Timestamp: time.Time(mention.Timestamp),
		EventTime: time.Time(mention.EventTime),
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
		DeletedAt: time.Time{},
	}, nil
}

func (m *SlackMention) ToModel() *slack.Mention {
	return &slack.Mention{
		ID:        slack.MentionID(m.ID),
		UserID:    slack.UserID(m.UserID),
		ChannelID: slack.ChannelID(m.ChannelID),
		Text:      slack.Text(m.Text),
		Timestamp: slack.Timestamp(m.Timestamp),
		EventTime: slack.EventTime(m.EventTime),
	}
}
