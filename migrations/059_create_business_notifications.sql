-- Migration: Create Business_Notifications table
-- Description: Stores notifications for businesses (generalized from Notifications)

CREATE TABLE IF NOT EXISTS Business_Notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL COMMENT 'Business this notification belongs to',
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
    INDEX idx_business_id (business_id),
    INDEX idx_business_read (business_id, is_read),
    INDEX idx_type (type),
    INDEX idx_type_subtype (type, subtype),
    INDEX idx_entity (type, entity_id),
    INDEX idx_created_at (created_at),
    INDEX idx_business_created (business_id, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
