-- Migration: Add is_24_hours flag for per-day operating hours
-- Description: Adds a boolean flag for each day to indicate 24-hour operation
-- When is_24_hours=true, the restaurant is open all day (open/close times ignored)

ALTER TABLE Restaurants
    ADD COLUMN monday_24_hours BOOLEAN DEFAULT FALSE,
    ADD COLUMN tuesday_24_hours BOOLEAN DEFAULT FALSE,
    ADD COLUMN wednesday_24_hours BOOLEAN DEFAULT FALSE,
    ADD COLUMN thursday_24_hours BOOLEAN DEFAULT FALSE,
    ADD COLUMN friday_24_hours BOOLEAN DEFAULT FALSE,
    ADD COLUMN saturday_24_hours BOOLEAN DEFAULT FALSE,
    ADD COLUMN sunday_24_hours BOOLEAN DEFAULT FALSE;

-- Add index for querying 24-hour restaurants (optional, for analytics)
CREATE INDEX idx_restaurants_24_hours ON Restaurants (
    monday_24_hours, tuesday_24_hours, wednesday_24_hours,
    thursday_24_hours, friday_24_hours, saturday_24_hours, sunday_24_hours
);
