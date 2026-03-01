-- Migration: Allow Notifications.restaurant_id to be NULL
-- Description: Enables admin-global system notifications (e.g., kill_switch_bulk_updated).
-- Constraint that NULL restaurant_id is only for type='system' is enforced in application logic.
-- Idempotent: safe to run multiple times.

SET @db = DATABASE();

SET @is_nullable = (
    SELECT IS_NULLABLE
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = @db
      AND TABLE_NAME = 'Notifications'
      AND COLUMN_NAME = 'restaurant_id'
    LIMIT 1
);

SET @alter_sql = IF(
    @is_nullable = 'YES',
    'DO 1',
    'ALTER TABLE Notifications MODIFY COLUMN restaurant_id INT NULL COMMENT ''Restaurant this notification belongs to'''
);

PREPARE stmt FROM @alter_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

