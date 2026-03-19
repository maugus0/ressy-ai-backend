-- Migration: Create Booking_Slots table
-- Description: Stores available booking slots for businesses (generalized from Slot_Bookings)

CREATE TABLE IF NOT EXISTS Booking_Slots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    reservation_type VARCHAR(20) NOT NULL DEFAULT 'in-house' COMMENT 'Reservation type: in-house',
    date_time DATETIME NOT NULL,
    expires_at DATETIME NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'available' COMMENT 'Status: available, reserved, expired, cancelled',
    reservation_token VARCHAR(255) UNIQUE COMMENT 'Unique token for booking',
    party_size INT COMMENT 'Number of guests for the booking',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_business_id (business_id),
    INDEX idx_date_time (date_time),
    INDEX idx_expires_at (expires_at),
    INDEX idx_status (status),
    INDEX idx_reservation_token (reservation_token),
    INDEX idx_party_size (party_size),
    INDEX idx_created_at (created_at),
    INDEX idx_business_datetime_status (business_id, date_time, status),
    INDEX idx_business_reservation_type (business_id, reservation_type, date_time, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
