-- One-off update for existing databases to add session tracking columns.
-- Run manually on environments that already have Ressy_Administrator and Restaurant_Administrators.

-- NOTE: This file may be executed automatically at container startup.
-- Make it idempotent so restarts don't crash with "Duplicate column" errors.

-- Important: This file is executed by a simple Python runner that executes
-- statements one-by-one without fetching result sets. Avoid standalone statements
-- that return rows to the client (e.g., top-level `SELECT ...`), or mysql-connector
-- may raise "Unread result found". It is safe to use SELECT subqueries inside
-- expressions such as SET/IF, since they do not return result sets to the client.
-- MySQL doesn't support `ADD COLUMN IF NOT EXISTS` in all environments.
-- Use dynamic SQL + information_schema checks (via SET subqueries) instead.

-- Ressy_Administrator.last_login
SET @col_exists := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'Ressy_Administrator'
      AND COLUMN_NAME = 'last_login'
);
SET @sql := IF(
    @col_exists > 0,
    'DO 0',
    'ALTER TABLE Ressy_Administrator ADD COLUMN last_login TIMESTAMP NULL DEFAULT NULL AFTER updated_at'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Ressy_Administrator.last_active
SET @col_exists := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'Ressy_Administrator'
      AND COLUMN_NAME = 'last_active'
);
SET @sql := IF(
    @col_exists > 0,
    'DO 0',
    'ALTER TABLE Ressy_Administrator ADD COLUMN last_active TIMESTAMP NULL DEFAULT NULL AFTER last_login'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Restaurant_Administrators.last_login
SET @col_exists := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'Restaurant_Administrators'
      AND COLUMN_NAME = 'last_login'
);
SET @sql := IF(
    @col_exists > 0,
    'DO 0',
    'ALTER TABLE Restaurant_Administrators ADD COLUMN last_login TIMESTAMP NULL DEFAULT NULL AFTER updated_at'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Restaurant_Administrators.last_active
SET @col_exists := (
    SELECT COUNT(*)
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'Restaurant_Administrators'
      AND COLUMN_NAME = 'last_active'
);
SET @sql := IF(
    @col_exists > 0,
    'DO 0',
    'ALTER TABLE Restaurant_Administrators ADD COLUMN last_active TIMESTAMP NULL DEFAULT NULL AFTER last_login'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
