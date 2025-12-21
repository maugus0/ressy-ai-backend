-- Migration: Create Reservations table
-- Description: Stores confirmed reservations

CREATE TABLE IF NOT EXISTS Reservations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_availability_request_id INT,
    slot_booking_id INT NOT NULL,
    user_id INT NOT NULL,
    confirmation_number VARCHAR(100) UNIQUE NOT NULL,
    last_cancel_time DATETIME COMMENT 'Last time reservation can be cancelled',
    manage_reservation_url VARCHAR(500) COMMENT 'URL for managing reservation',
    status VARCHAR(50) NOT NULL DEFAULT 'confirmed' COMMENT 'Status: confirmed, cancelled, completed, no_show',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (table_availability_request_id) REFERENCES Table_Availability_Requests(id) ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (slot_booking_id) REFERENCES Slot_Bookings(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_table_availability_request_id (table_availability_request_id),
    INDEX idx_slot_booking_id (slot_booking_id),
    INDEX idx_user_id (user_id),
    INDEX idx_confirmation_number (confirmation_number),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at),
    INDEX idx_user_status (user_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

