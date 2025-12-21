-- Migration: Add notes field to Reservations table
-- Description: Adds a notes field for dashboard users to add/update notes on reservations

ALTER TABLE Reservations
ADD COLUMN notes TEXT NULL COMMENT 'Notes added by dashboard users' AFTER special_request;

