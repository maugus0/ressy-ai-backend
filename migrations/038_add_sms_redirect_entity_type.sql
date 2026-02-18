-- Migration: 038_add_sms_redirect_entity_type.sql
-- Description: Add 'sms_redirect' to entity_type ENUM in Notification_Logs table
-- This allows logging SMS redirect notifications sent during calls
--
-- Idempotent: safe to run multiple times (MySQL 5.7+).

-- Check if 'sms_redirect' already exists in the ENUM before altering
-- MySQL doesn't have a direct way to check ENUM values, so we use INFORMATION_SCHEMA
SET @db = DATABASE();

SET @alter_entity_type = (SELECT IF(
    (SELECT COLUMN_TYPE FROM INFORMATION_SCHEMA.COLUMNS
     WHERE TABLE_SCHEMA = @db AND TABLE_NAME = 'Notification_Logs'
     AND COLUMN_NAME = 'entity_type') LIKE '%sms_redirect%',
    'DO 1',
    'ALTER TABLE Notification_Logs MODIFY COLUMN entity_type ENUM(''order'', ''reservation'', ''sms_redirect'') NOT NULL COMMENT ''Type of entity (order, reservation, or sms_redirect)'''
));
PREPARE stmt FROM @alter_entity_type;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
