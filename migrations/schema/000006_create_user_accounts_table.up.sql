-- Create user_accounts table
CREATE TABLE IF NOT EXISTS `user_accounts` (
  `id` CHAR(26) NOT NULL COMMENT 'ULID primary key',
  `user_id` CHAR(26) NOT NULL COMMENT 'Reference to users.id',
  `password` VARCHAR(255) NOT NULL COMMENT 'User password',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  `deleted_at` DATETIME NULL DEFAULT NULL COMMENT 'Soft delete time',
  PRIMARY KEY (`id`),
  INDEX `idx_user_accounts_user_id` (`user_id`),
  INDEX `idx_user_accounts_created_at` (`created_at`),
  CONSTRAINT `fk_user_accounts_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='User accounts table';

