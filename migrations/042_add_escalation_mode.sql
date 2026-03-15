-- Migration: 042_add_escalation_mode.sql
-- Description: Add escalation_mode column to Restaurants table.
-- Controls when escalation transfers are allowed:
--   'always'          — current default; transfer any time escalation is triggered.
--   'open_hours_only' — only transfer during operating hours; inform caller otherwise.
-- Idempotent: safe to run multiple times.

SET @db = DATABASE();

SET @add_escalation_mode = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
     WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'Restaurants'
     AND COLUMN_NAME = 'escalation_mode') > 0,
    'DO 1',
    'ALTER TABLE Restaurants ADD COLUMN escalation_mode VARCHAR(20) NOT NULL DEFAULT ''always'' COMMENT ''Controls when escalation transfers are allowed: always | open_hours_only'''
));
PREPARE stmt FROM @add_escalation_mode;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
