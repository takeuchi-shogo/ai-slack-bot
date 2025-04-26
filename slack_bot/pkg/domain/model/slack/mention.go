package slack

import (
	"errors"
	"math/rand"
	"time"

	"github.com/oklog/ulid/v2"
)

type (
	Mention struct {
		ID        MentionID
		UserID    UserID
		ChannelID ChannelID
		Text      Text
		Timestamp Timestamp
		EventTime EventTime
	}
	MentionID ulid.ULID
	ChannelID string
	UserID    string
	Text      string
	Timestamp time.Time
	EventTime time.Time
)

func NewMention(
	userID UserID,
	channelID ChannelID,
	text Text,
	timestamp Timestamp,
	eventTime EventTime,
) (*Mention, error) {
	id, err := ulid.New(ulid.Timestamp(time.Now()), ulid.Monotonic(rand.New(rand.NewSource(time.Now().UnixNano())), 0))
	if err != nil {
		return nil, err
	}
	m, err := newMention(MentionID(id), userID, channelID, text, timestamp, eventTime)
	if err != nil {
		return nil, err
	}

	return m, nil
}

func newMention(
	id MentionID,
	userID UserID,
	channelID ChannelID,
	text Text,
	timestamp Timestamp,
	eventTime EventTime,
) (*Mention, error) {
	m := &Mention{
		ID:        id,
		UserID:    userID,
		ChannelID: channelID,
		Text:      text,
		Timestamp: timestamp,
		EventTime: eventTime,
	}

	if err := m.validate(); err != nil {
		return nil, err
	}

	return m, nil
}

func (m Mention) validate() error {
	if m.UserID == "" {
		return errors.New("userID is required")
	}
	if m.ChannelID == "" {
		return errors.New("channelID is required")
	}
	if m.Text == "" {
		return errors.New("text is required")
	}
	return nil
}
