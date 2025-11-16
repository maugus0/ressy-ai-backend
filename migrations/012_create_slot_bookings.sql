-- Migration: Create Slot_Bookings table
-- Description: Stores available booking slots

CREATE TABLE IF NOT EXISTS Slot_Bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id INT NOT NULL,
    date_time DATETIME NOT NULL,
    expires_at DATETIME NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'available' COMMENT 'Status: available, reserved, expired, cancelled',
    reservation_token VARCHAR(255) UNIQUE COMMENT 'Unique token for reservation',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_restaurant_id (restaurant_id),
    INDEX idx_date_time (date_time),
    INDEX idx_expires_at (expires_at),
    INDEX idx_status (status),
    INDEX idx_reservation_token (reservation_token),
    INDEX idx_created_at (created_at),
    INDEX idx_restaurant_datetime_status (restaurant_id, date_time, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

