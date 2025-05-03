-- Create slack_mention_responses table
CREATE TABLE IF NOT EXISTS `slack_mention_responses` (
  `id` CHAR(26) NOT NULL COMMENT 'ULID primary key',
  `mention_id` CHAR(26) NOT NULL COMMENT 'Reference to slack_mentions.id',
  `content` TEXT NOT NULL COMMENT 'Response content',
  `status` VARCHAR(50) NOT NULL DEFAULT 'pending' COMMENT 'Status of the response (pending, sent, failed)',
  `sent_at` DATETIME NULL DEFAULT NULL COMMENT 'Time when the response was sent',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  `deleted_at` DATETIME NULL DEFAULT NULL COMMENT 'Soft delete time',
  PRIMARY KEY (`id`),
  INDEX `idx_slack_mention_responses_mention_id` (`mention_id`),
  INDEX `idx_slack_mention_responses_status` (`status`),
  INDEX `idx_slack_mention_responses_created_at` (`created_at`),
  CONSTRAINT `fk_mention_responses_mention_id` FOREIGN KEY (`mention_id`) REFERENCES `slack_mentions` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;