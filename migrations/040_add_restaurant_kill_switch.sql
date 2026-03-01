-- Migration: Add kill switch setting to Restaurants
-- Description: Adds kill_switch_enabled flag for routing inbound calls directly to escalation phone
-- Idempotent: safe to run multiple times (MySQL 5.7+)

SET @db = DATABASE();

SET @add_kill_switch_enabled = (
    SELECT IF(
        (SELECT COUNT(*)
         FROM INFORMATION_SCHEMA.COLUMNS
         WHERE TABLE_SCHEMA = @db
           AND TABLE_NAME = 'Restaurants'
           AND COLUMN_NAME = 'kill_switch_enabled') > 0,
        'DO 1',
        'ALTER TABLE Restaurants ADD COLUMN kill_switch_enabled BOOLEAN NOT NULL DEFAULT FALSE'
    )
);

PREPARE stmt FROM @add_kill_switch_enabled;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
