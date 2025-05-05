-- Create user_emails table
CREATE TABLE IF NOT EXISTS `user_emails` (
  `id` CHAR(26) NOT NULL COMMENT 'ULID primary key',
  `user_id` CHAR(26) NOT NULL COMMENT 'Reference to users.id',
  `email` VARCHAR(255) NOT NULL COMMENT 'User email',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  `deleted_at` DATETIME NULL DEFAULT NULL COMMENT 'Soft delete time',
  PRIMARY KEY (`id`),
  INDEX `idx_user_emails_user_id` (`user_id`),
  INDEX `idx_user_emails_created_at` (`created_at`),
  CONSTRAINT `fk_user_emails_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='User emails table';
