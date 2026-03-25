-- Migration: Add POS webhook tracking and provider account metadata
-- Description: Adds generic external account routing to POS integrations and a persisted webhook event log
--              for idempotent provider webhook processing and internal retries.

SET @sql = IF(
    EXISTS (
        SELECT 1
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'POS_Integrations'
          AND COLUMN_NAME = 'external_account_id'
    ),
    'DO 0',
    'ALTER TABLE POS_Integrations ADD COLUMN external_account_id VARCHAR(255) NULL AFTER location_id'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1
        FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'POS_Integrations'
          AND INDEX_NAME = 'idx_pos_type_account'
    ),
    'DO 0',
    'ALTER TABLE POS_Integrations ADD INDEX idx_pos_type_account (pos_type, external_account_id)'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS POS_Webhook_Events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pos_type VARCHAR(32) NOT NULL,
    provider_event_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    external_account_id VARCHAR(255) DEFAULT NULL,
    location_id VARCHAR(255) DEFAULT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    delivery_count INT NOT NULL DEFAULT 1,
    processing_attempts INT NOT NULL DEFAULT 0,
    last_retry_number INT DEFAULT NULL,
    last_retry_reason VARCHAR(255) DEFAULT NULL,
    next_retry_at TIMESTAMP NULL,
    processed_at TIMESTAMP NULL,
    last_error TEXT DEFAULT NULL,
    payload JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_pos_webhook_provider_event (pos_type, provider_event_id),
    INDEX idx_pos_webhook_status_retry (status, next_retry_at),
    INDEX idx_pos_webhook_type_account (pos_type, event_type, external_account_id),
    INDEX idx_pos_webhook_location (pos_type, location_id),
    INDEX idx_pos_webhook_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
