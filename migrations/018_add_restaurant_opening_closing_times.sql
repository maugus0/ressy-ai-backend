-- Migration: Add opening and closing times to Restaurants table
-- Description: Adds opening_time and closing_time fields for slot generation

ALTER TABLE Restaurants
ADD COLUMN opening_time TIME DEFAULT '09:00:00' COMMENT 'Restaurant opening time (HH:MM:SS format)',
ADD COLUMN closing_time TIME DEFAULT '22:00:00' COMMENT 'Restaurant closing time (HH:MM:SS format)';

-- Add indexes for better query performance
CREATE INDEX idx_opening_closing_time ON Restaurants(opening_time, closing_time);

