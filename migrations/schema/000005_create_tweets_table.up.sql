-- Create tweets table
CREATE TABLE IF NOT EXISTS `tweets` (
  `id` CHAR(26) NOT NULL COMMENT 'ULID primary key',
  `user_id` CHAR(26) NOT NULL COMMENT 'Reference to users.id',
  `content` TEXT NOT NULL COMMENT 'Tweet content',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  `deleted_at` DATETIME NULL DEFAULT NULL COMMENT 'Soft delete time',
  PRIMARY KEY (`id`),
  INDEX `idx_tweets_user_id` (`user_id`),
  INDEX `idx_tweets_created_at` (`created_at`),
  CONSTRAINT `fk_tweets_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Tweets table';
