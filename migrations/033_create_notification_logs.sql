-- Migration: 033_create_notification_logs.sql
-- Description: Create Notification_Logs table for SMS notification tracking
-- Depends on: 004_create_restaurants.sql (Restaurants table must exist for FK)
--
-- PII Note: recipient_phone stores customer phone numbers in plain text.
-- Recommended: Implement data retention policy to delete logs older than 90 days.
-- Future: Consider application-level encryption for recipient_phone column.

CREATE TABLE IF NOT EXISTS Notification_Logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id INT NOT NULL,
    entity_type ENUM('order', 'reservation') NOT NULL COMMENT 'Type of entity (order or reservation)',
    entity_id INT NOT NULL COMMENT 'ID of the order or reservation',
    recipient_phone VARCHAR(30) NOT NULL COMMENT 'Customer phone number (E.164 format) - PII, see retention policy',
    message_content TEXT NOT NULL COMMENT 'The message content sent',
    status ENUM('pending', 'sent', 'delivered', 'failed') NOT NULL DEFAULT 'pending',
    twilio_message_sid VARCHAR(100) COMMENT 'Twilio message SID for tracking',
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
    INDEX idx_created_at (created_at),
    CONSTRAINT fk_notification_logs_restaurant
        FOREIGN KEY (restaurant_id) REFERENCES Restaurants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
