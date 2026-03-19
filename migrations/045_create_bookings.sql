-- Migration: Create Bookings table
-- Description: Stores confirmed bookings for businesses (generalized from Reservations)

CREATE TABLE IF NOT EXISTS Bookings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    reservation_type VARCHAR(20) NOT NULL DEFAULT 'in-house' COMMENT 'Reservation type: in-house',
    availability_request_id INT,
    slot_booking_id INT NOT NULL,
    user_id INT NOT NULL,
    confirmation_number VARCHAR(100) UNIQUE NOT NULL,
    party_size INT COMMENT 'Number of guests for the booking',
    special_request TEXT COMMENT 'Special requests or notes from the customer',
    notes TEXT NULL COMMENT 'Notes added by dashboard users',
    last_cancel_time DATETIME COMMENT 'Last time booking can be cancelled',
    manage_reservation_url VARCHAR(500) COMMENT 'URL for managing booking',
    status VARCHAR(50) NOT NULL DEFAULT 'confirmed' COMMENT 'Status: confirmed, cancelled, completed, no_show',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (availability_request_id) REFERENCES Availability_Requests(id) ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (slot_booking_id) REFERENCES Booking_Slots(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_availability_request_id (availability_request_id),
    INDEX idx_slot_booking_id (slot_booking_id),
    INDEX idx_user_id (user_id),
    INDEX idx_confirmation_number (confirmation_number),
    INDEX idx_status (status),
    INDEX idx_party_size (party_size),
    INDEX idx_reservation_type (reservation_type),
    INDEX idx_created_at (created_at),
    INDEX idx_user_status (user_id, status),
    INDEX idx_reservation_type_status (reservation_type, status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
