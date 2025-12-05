-- Migration: Add reservation_type flag to reservation tables
-- Description: Adds reservation_type column to differentiate between OpenTable and in-house reservations

-- Add reservation_type to Table_Availability_Requests
ALTER TABLE Table_Availability_Requests
ADD COLUMN reservation_type VARCHAR(20) NOT NULL DEFAULT 'in-house' 
COMMENT 'Reservation type: opentable or in-house'
AFTER party_size;

-- Add reservation_type to Slot_Bookings
ALTER TABLE Slot_Bookings
ADD COLUMN reservation_type VARCHAR(20) NOT NULL DEFAULT 'in-house' 
COMMENT 'Reservation type: opentable or in-house'
AFTER restaurant_id;

-- Add reservation_type to Reservations
ALTER TABLE Reservations
ADD COLUMN reservation_type VARCHAR(20) NOT NULL DEFAULT 'in-house' 
COMMENT 'Reservation type: opentable or in-house'
AFTER id;

-- Add indexes for better query performance
CREATE INDEX idx_table_availability_reservation_type ON Table_Availability_Requests(restaurant_id, reservation_type, start_date_time);
CREATE INDEX idx_slot_bookings_reservation_type ON Slot_Bookings(restaurant_id, reservation_type, date_time, status);
CREATE INDEX idx_reservations_reservation_type ON Reservations(reservation_type, status, created_at);

