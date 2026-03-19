-- Migration: Create Business_User_Activity_History table
-- Description: Stores audit logs for business order and booking changes (generalized from User_Activity_History)
-- This table tracks all updates to orders and bookings for history/audit purposes

CREATE TABLE IF NOT EXISTS Business_User_Activity_History (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL COMMENT 'User who performed the action (from Users table)',
    activity_type ENUM('order', 'reservation') NOT NULL COMMENT 'Type of activity being tracked',
    order_id INT NULL COMMENT 'Associated order ID (if activity_type = order)',
    booking_id INT NULL COMMENT 'Associated booking ID (if activity_type = reservation)',
    action VARCHAR(50) NOT NULL COMMENT 'Action performed: created, updated, cancelled, status_changed, etc.',
    previous_value JSON COMMENT 'Previous state before the change (serialized JSON)',
    new_value JSON COMMENT 'New state after the change (serialized JSON)',
    change_summary VARCHAR(1000) COMMENT 'Human-readable summary of the change',
    business_id INT NOT NULL COMMENT 'Business ID for RBAC access control',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign keys
    FOREIGN KEY (order_id) REFERENCES Business_Orders(id) ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (booking_id) REFERENCES Bookings(id) ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE ON UPDATE CASCADE,
    
    -- Indexes for common query patterns
    INDEX idx_user_id (user_id),
    INDEX idx_activity_type (activity_type),
    INDEX idx_order_id (order_id),
    INDEX idx_booking_id (booking_id),
    INDEX idx_business_id (business_id),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at),
    INDEX idx_business_created (business_id, created_at DESC),
    INDEX idx_order_created (order_id, created_at DESC),
    INDEX idx_booking_created (booking_id, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
