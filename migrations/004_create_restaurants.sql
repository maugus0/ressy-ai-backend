-- Migration: Create Restaurants table
-- Description: Stores restaurant information and integration details

CREATE TABLE IF NOT EXISTS Restaurants (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    phone_number VARCHAR(20),
    twilio_phone_number VARCHAR(20),
    twilio_details JSON COMMENT 'Twilio configuration and settings',
    deepgram_details JSON COMMENT 'Deepgram configuration and settings',
    open_table_details JSON COMMENT 'OpenTable integration details',
    forward_minutes INT DEFAULT 0 COMMENT 'Forward booking window in minutes',
    backward_minutes INT DEFAULT 0 COMMENT 'Backward booking window in minutes',
    is_credit_card_required_for_reservation BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_name (name),
    INDEX idx_phone_number (phone_number),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

