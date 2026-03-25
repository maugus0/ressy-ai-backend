-- Migration: Create POS integration foundation tables
-- Description: Introduces generic POS integration and order sync tables after upstream migration 042.

CREATE TABLE IF NOT EXISTS POS_Integrations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id INT NOT NULL,
    pos_type VARCHAR(32) NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    credentials JSON,
    location_id VARCHAR(255),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    default_order_options JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(id) ON DELETE CASCADE ON UPDATE CASCADE,
    UNIQUE KEY unique_restaurant_pos (restaurant_id, pos_type),
    INDEX idx_restaurant_pos (restaurant_id, pos_type),
    INDEX idx_enabled (enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE POS_Integrations
MODIFY COLUMN pos_type VARCHAR(32) NOT NULL;

SET @sql = IF(
    EXISTS (
        SELECT 1
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'POS_Integrations'
          AND COLUMN_NAME = 'currency'
    ),
    'DO 0',
    'ALTER TABLE POS_Integrations ADD COLUMN currency VARCHAR(3) NOT NULL DEFAULT ''USD'' AFTER location_id'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS Order_POS_Sync (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    restaurant_id INT NOT NULL,
    pos_integration_id INT NOT NULL,
    external_order_id VARCHAR(255),
    idempotency_key VARCHAR(255) UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    last_error TEXT,
    attempts INT NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMP NULL,
    request_payload JSON,
    response_payload JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES Orders(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (pos_integration_id) REFERENCES POS_Integrations(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_order_pos (order_id, pos_integration_id),
    INDEX idx_restaurant_status (restaurant_id, status),
    INDEX idx_next_retry (next_retry_at),
    INDEX idx_idempotency (idempotency_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE Order_POS_Sync
MODIFY COLUMN status VARCHAR(20) NOT NULL DEFAULT 'PENDING';
