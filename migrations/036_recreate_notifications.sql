-- Migration: Recreate Notifications table for persistent notification system
-- Description: Drops legacy order-only Notifications table ONLY when legacy schema
-- is detected; then creates unified notification table (idempotent).
-- Depends on: 004_create_restaurants.sql (application-layer restaurant scoping; no FK)
--
-- CRITICAL: Migration runner runs ALL migrations every time (no tracking). We must
-- NOT unconditionally DROP TABLE or every deployment would wipe production data.
-- Legacy table (009) had: order_id, status. New table has: type, subtype, etc.

-- Only drop if the legacy schema exists (has order_id column, lacks type column)
SET @has_legacy_schema = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'Notifications'
    AND COLUMN_NAME = 'order_id'
);

SET @has_new_schema = (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'Notifications'
    AND COLUMN_NAME = 'type'
);

-- Drop only if legacy schema detected (order_id exists, type does not)
SET @should_drop = IF(@has_legacy_schema > 0 AND @has_new_schema = 0, 1, 0);

-- Conditional drop via prepared statement (no-op SELECT 1 when not dropping)
SET @drop_sql = IF(@should_drop = 1, 'DROP TABLE IF EXISTS Notifications', 'DO 0');
PREPARE stmt FROM @drop_sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Create only if not exists (idempotent; safe on every run)
CREATE TABLE IF NOT EXISTS Notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id INT NOT NULL COMMENT 'Restaurant this notification belongs to',
    type VARCHAR(50) NOT NULL COMMENT 'Event type: order, reservation, escalation',
    subtype VARCHAR(50) NOT NULL COMMENT 'Event subtype: new_order, order_updated, order_cancelled, new_reservation, reservation_updated, reservation_cancelled, user_requested, internal_server_error, suspected_spam',
    title VARCHAR(255) NOT NULL COMMENT 'Human-readable notification title',
    message TEXT COMMENT 'Human-readable notification message/body',
    data JSON COMMENT 'Full event payload as JSON for frontend rendering',
    entity_id INT COMMENT 'ID of the related entity (order_id, reservation_id, or escalation call_id)',
    is_read BOOLEAN DEFAULT FALSE COMMENT 'Whether the notification has been read',
    read_at TIMESTAMP NULL COMMENT 'When the notification was marked as read',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_restaurant_id (restaurant_id),
    INDEX idx_restaurant_read (restaurant_id, is_read),
    INDEX idx_type (type),
    INDEX idx_type_subtype (type, subtype),
    INDEX idx_entity (type, entity_id),
    INDEX idx_created_at (created_at),
    INDEX idx_restaurant_created (restaurant_id, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
