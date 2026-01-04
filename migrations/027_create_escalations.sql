-- Migration: Create Escalations table
-- Description: Stores escalation events for calls

CREATE TABLE IF NOT EXISTS Escalations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    call_id INT NOT NULL COMMENT 'Calls.id for this escalation',
    user_id VARCHAR(255) NOT NULL COMMENT 'User identifier (from call context)',
    restaurant_id VARCHAR(255) NOT NULL COMMENT 'Restaurant identifier (from call context)',
    twilio_call_sid VARCHAR(255) COMMENT 'Twilio call SID',
    caller_phone VARCHAR(20) COMMENT 'Caller phone at time of escalation',
    escalation_phone_number VARCHAR(20) COMMENT 'Escalation forwarding number at time of escalation',
    urgency VARCHAR(50) COMMENT 'Urgency provided by agent',
    reason VARCHAR(255) COMMENT 'Reason provided by agent',
    status VARCHAR(50) DEFAULT 'raised' COMMENT 'raised, forwarded, failed, resolved',
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    forwarded_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_call_id (call_id),
    INDEX idx_restaurant_id (restaurant_id),
    INDEX idx_user_id (user_id),
    INDEX idx_twilio_call_sid (twilio_call_sid),
    INDEX idx_status (status),
    INDEX idx_requested_at (requested_at),
    INDEX idx_call_requested (call_id, requested_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
