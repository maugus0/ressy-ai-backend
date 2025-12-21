-- Migration: Add party_size and special_request columns
-- Description: Adds party_size to Slot_Bookings and Reservations, and special_request to Reservations

-- Add party_size to Slot_Bookings
ALTER TABLE Slot_Bookings
ADD COLUMN party_size INT COMMENT 'Number of guests for the reservation'
AFTER reservation_token;

-- Add party_size to Reservations
ALTER TABLE Reservations
ADD COLUMN party_size INT COMMENT 'Number of guests for the reservation'
AFTER user_id;

-- Add special_request to Reservations
ALTER TABLE Reservations
ADD COLUMN special_request TEXT COMMENT 'Special requests or notes from the customer'
AFTER party_size;

-- Add indexes for better query performance
CREATE INDEX idx_slot_bookings_party_size ON Slot_Bookings(party_size);
CREATE INDEX idx_reservations_party_size ON Reservations(party_size);

