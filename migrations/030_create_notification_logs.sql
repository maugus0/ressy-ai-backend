-- Migration: Create Notification_Logs table
-- Description: Stores SMS notification logs for order and reservation status changes

CREATE TABLE IF NOT EXISTS Notification_Logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id INT NOT NULL,
    entity_type ENUM('order', 'reservation') NOT NULL COMMENT 'Type of entity (order or reservation)',
    entity_id INT NOT NULL COMMENT 'ID of the order or reservation',
    recipient_phone VARCHAR(20) NOT NULL COMMENT 'Customer phone number',
    message_content TEXT NOT NULL COMMENT 'The message content sent',
    status ENUM('pending', 'sent', 'delivered', 'failed') NOT NULL DEFAULT 'pending',
    twilio_message_sid VARCHAR(50) COMMENT 'Twilio message SID for tracking',
    error_message TEXT COMMENT 'Error message if failed',
    retry_count INT NOT NULL DEFAULT 0 COMMENT 'Number of retry attempts',
    sent_at TIMESTAMP NULL COMMENT 'When the message was sent',
    delivered_at TIMESTAMP NULL COMMENT 'When delivery was confirmed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_restaurant_id (restaurant_id),
    INDEX idx_entity (entity_type, entity_id),
    INDEX idx_status (status),
    INDEX idx_twilio_sid (twilio_message_sid),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
