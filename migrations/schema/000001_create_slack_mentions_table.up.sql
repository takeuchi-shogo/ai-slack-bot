-- Create slack_mentions table
CREATE TABLE IF NOT EXISTS `slack_mentions` (
  `id` CHAR(26) NOT NULL COMMENT 'ULID primary key',
  `type` VARCHAR(255) NOT NULL COMMENT 'Mention type',
  `user_id` VARCHAR(255) NOT NULL COMMENT 'Slack user ID',
  `channel_id` VARCHAR(255) NOT NULL COMMENT 'Slack channel ID',
  `text` TEXT NOT NULL COMMENT 'Mention text content',
  `timestamp` DATETIME NOT NULL COMMENT 'Slack event timestamp',
  `event_time` DATETIME NOT NULL COMMENT 'Slack event time',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  `deleted_at` DATETIME NULL DEFAULT NULL COMMENT 'Soft delete time',
  PRIMARY KEY (`id`),
  INDEX `idx_slack_mentions_user_id` (`user_id`),
  INDEX `idx_slack_mentions_channel_id` (`channel_id`),
  INDEX `idx_slack_mentions_timestamp` (`timestamp`),
  INDEX `idx_slack_mentions_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;