package repository

import (
	"context"

	"github.com/oklog/ulid/v2"
	"github.com/takeuchi-shogo/ai-slack-bot/slack_bot/pkg/domain/di"
	"github.com/takeuchi-shogo/ai-slack-bot/slack_bot/pkg/infra/entity"
	"github.com/uptrace/bun"
)

type SlackMentionRepository struct {
	db *bun.DB
}

func NewSlackMentionRepository(db *bun.DB) di.SlackMentionRepository {
	return &SlackMentionRepository{db: db}
}

func (r *SlackMentionRepository) FindByID(ctx context.Context, id ulid.ULID) (*entity.SlackMention, error) {
	var mention entity.SlackMention
	err := r.db.NewSelect().Model(&mention).Where("id = ?", id).Scan(ctx)
	return &mention, err
}

func (r *SlackMentionRepository) Create(ctx context.Context, mention *entity.SlackMention) error {
	if _, err := r.db.NewInsert().Model(mention).Exec(ctx); err != nil {
		return err
	}
	return nil
}
