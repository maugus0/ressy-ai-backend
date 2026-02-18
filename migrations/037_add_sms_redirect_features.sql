-- Migration: Add SMS Redirect fields to Restaurant_Features table
-- Description: Extends restaurant features to support SMS redirect for orders and reservations
-- When SMS redirect is enabled for orders/reservations, the agent sends an SMS with a link
-- instead of processing the request directly. Requires the corresponding capability to be disabled.
--
-- Idempotent: safe to run multiple times (MySQL 5.7+).

-- Add columns only if they do not exist (uses INFORMATION_SCHEMA check)
SET @db = DATABASE();

SET @add_orders_sms_redirect_enabled = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
     WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'Restaurant_Features'
     AND COLUMN_NAME = 'orders_sms_redirect_enabled') > 0,
    'DO 1',
    'ALTER TABLE Restaurant_Features ADD COLUMN orders_sms_redirect_enabled BOOLEAN NOT NULL DEFAULT FALSE'
));
PREPARE stmt FROM @add_orders_sms_redirect_enabled;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_orders_redirect_url = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
     WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'Restaurant_Features'
     AND COLUMN_NAME = 'orders_redirect_url') > 0,
    'DO 1',
    'ALTER TABLE Restaurant_Features ADD COLUMN orders_redirect_url VARCHAR(512) DEFAULT NULL'
));
PREPARE stmt FROM @add_orders_redirect_url;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_orders_redirect_message = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
     WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'Restaurant_Features'
     AND COLUMN_NAME = 'orders_redirect_message') > 0,
    'DO 1',
    'ALTER TABLE Restaurant_Features ADD COLUMN orders_redirect_message TEXT DEFAULT NULL'
));
PREPARE stmt FROM @add_orders_redirect_message;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_reservations_sms_redirect_enabled = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
     WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'Restaurant_Features'
     AND COLUMN_NAME = 'reservations_sms_redirect_enabled') > 0,
    'DO 1',
    'ALTER TABLE Restaurant_Features ADD COLUMN reservations_sms_redirect_enabled BOOLEAN NOT NULL DEFAULT FALSE'
));
PREPARE stmt FROM @add_reservations_sms_redirect_enabled;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_reservations_redirect_url = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
     WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'Restaurant_Features'
     AND COLUMN_NAME = 'reservations_redirect_url') > 0,
    'DO 1',
    'ALTER TABLE Restaurant_Features ADD COLUMN reservations_redirect_url VARCHAR(512) DEFAULT NULL'
));
PREPARE stmt FROM @add_reservations_redirect_url;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @add_reservations_redirect_message = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
     WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'Restaurant_Features'
     AND COLUMN_NAME = 'reservations_redirect_message') > 0,
    'DO 1',
    'ALTER TABLE Restaurant_Features ADD COLUMN reservations_redirect_message TEXT DEFAULT NULL'
));
PREPARE stmt FROM @add_reservations_redirect_message;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Note: We intentionally do not create standalone indexes on the
-- orders_sms_redirect_enabled and reservations_sms_redirect_enabled
-- boolean columns. These columns have very low cardinality (only true/false),
-- so dedicated indexes are unlikely to provide meaningful performance
-- benefits and would add unnecessary write overhead.

-- Business Rules (enforced at application level):
-- 1. orders_sms_redirect_enabled = TRUE requires orders_enabled = FALSE
-- 2. reservations_sms_redirect_enabled = TRUE requires reservations_enabled = FALSE
-- 3. URL is required when SMS redirect is enabled
-- 4. Default messages are used when custom message is NULL
