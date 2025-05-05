-- Create users table
CREATE TABLE IF NOT EXISTS `users` (
  `id` CHAR(26) NOT NULL COMMENT 'ULID primary key',
  `name` VARCHAR(255) NOT NULL COMMENT 'User name',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation time',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update time',
  `deleted_at` DATETIME NULL DEFAULT NULL COMMENT 'Soft delete time',
  PRIMARY KEY (`id`),
  INDEX `idx_users_created_at` (`created_at`),
  INDEX `idx_users_updated_at` (`updated_at`),
  INDEX `idx_users_deleted_at` (`deleted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Users table';
