-- Migration: Create Availability_Requests table
-- Description: Stores availability requests for businesses (generalized from Table_Availability_Requests)

CREATE TABLE IF NOT EXISTS Availability_Requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    start_date_time DATETIME NOT NULL,
    party_size INT NOT NULL,
    reservation_type VARCHAR(20) NOT NULL DEFAULT 'in-house' COMMENT 'Reservation type: in-house',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_business_id (business_id),
    INDEX idx_start_date_time (start_date_time),
    INDEX idx_created_at (created_at),
    INDEX idx_business_datetime (business_id, start_date_time),
    INDEX idx_business_reservation_type (business_id, reservation_type, start_date_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
