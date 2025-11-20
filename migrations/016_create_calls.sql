-- Migration: Create Calls table
-- Description: Stores call session information

CREATE TABLE IF NOT EXISTS Calls (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL COMMENT 'User identifier',
    restaurant_id VARCHAR(255) COMMENT 'Restaurant identifier',
    twilio_call_sid VARCHAR(255) COMMENT 'Twilio call SID',
    deepgram_request_id VARCHAR(255) COMMENT 'Deepgram session ID',
    call_status VARCHAR(50) DEFAULT 'in_progress' COMMENT 'Call status (in_progress, completed, failed)',
    call_direction VARCHAR(50) DEFAULT 'inbound' COMMENT 'Call direction',
    call_duration INT DEFAULT 0 COMMENT 'Call duration in seconds',
    cost DECIMAL(10, 6) DEFAULT 0.000000 COMMENT 'Call cost',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_restaurant_id (restaurant_id),
    INDEX idx_call_status (call_status),
    INDEX idx_started_at (started_at),
    INDEX idx_user_started (user_id, started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

