-- Migration 024: Create User_Activity_History table
-- Description: Stores audit logs for order and reservation changes
-- This table tracks all updates to orders and reservations for history/audit purposes

CREATE TABLE IF NOT EXISTS User_Activity_History (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL COMMENT 'User who performed the action (from Users table)',
    activity_type ENUM('order', 'reservation') NOT NULL COMMENT 'Type of activity being tracked',
    order_id INT NULL COMMENT 'Associated order ID (if activity_type = order)',
    reservation_id INT NULL COMMENT 'Associated reservation ID (if activity_type = reservation)',
    action VARCHAR(50) NOT NULL COMMENT 'Action performed: created, updated, cancelled, status_changed, etc.',
    previous_value JSON COMMENT 'Previous state before the change (serialized JSON)',
    new_value JSON COMMENT 'New state after the change (serialized JSON)',
    change_summary VARCHAR(500) COMMENT 'Human-readable summary of the change',
    restaurant_id INT NOT NULL COMMENT 'Restaurant ID for RBAC access control',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign keys
    FOREIGN KEY (order_id) REFERENCES Orders(id) ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (reservation_id) REFERENCES Reservations(id) ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(id) ON DELETE CASCADE ON UPDATE CASCADE,
    
    -- Indexes for common query patterns
    INDEX idx_user_id (user_id),
    INDEX idx_activity_type (activity_type),
    INDEX idx_order_id (order_id),
    INDEX idx_reservation_id (reservation_id),
    INDEX idx_restaurant_id (restaurant_id),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at),
    INDEX idx_restaurant_created (restaurant_id, created_at DESC),
    INDEX idx_order_created (order_id, created_at DESC),
    INDEX idx_reservation_created (reservation_id, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
