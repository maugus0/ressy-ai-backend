-- Migration: Add per-day operating hours columns
-- Description: Replaces single opening_time/closing_time with day-specific hours
-- This is a breaking change - legacy columns will be removed

-- Step 1: Add columns for each day (21 total: open, close, closed for 7 days)
ALTER TABLE Restaurants
    ADD COLUMN monday_open TIME NULL,
    ADD COLUMN monday_close TIME NULL,
    ADD COLUMN monday_closed BOOLEAN DEFAULT FALSE,
    ADD COLUMN tuesday_open TIME NULL,
    ADD COLUMN tuesday_close TIME NULL,
    ADD COLUMN tuesday_closed BOOLEAN DEFAULT FALSE,
    ADD COLUMN wednesday_open TIME NULL,
    ADD COLUMN wednesday_close TIME NULL,
    ADD COLUMN wednesday_closed BOOLEAN DEFAULT FALSE,
    ADD COLUMN thursday_open TIME NULL,
    ADD COLUMN thursday_close TIME NULL,
    ADD COLUMN thursday_closed BOOLEAN DEFAULT FALSE,
    ADD COLUMN friday_open TIME NULL,
    ADD COLUMN friday_close TIME NULL,
    ADD COLUMN friday_closed BOOLEAN DEFAULT FALSE,
    ADD COLUMN saturday_open TIME NULL,
    ADD COLUMN saturday_close TIME NULL,
    ADD COLUMN saturday_closed BOOLEAN DEFAULT FALSE,
    ADD COLUMN sunday_open TIME NULL,
    ADD COLUMN sunday_close TIME NULL,
    ADD COLUMN sunday_closed BOOLEAN DEFAULT FALSE;

-- Step 2: Seed existing restaurants with their current hours for all days
-- Uses existing opening_time/closing_time values to populate all days
UPDATE Restaurants SET
    monday_open = opening_time, monday_close = closing_time, monday_closed = FALSE,
    tuesday_open = opening_time, tuesday_close = closing_time, tuesday_closed = FALSE,
    wednesday_open = opening_time, wednesday_close = closing_time, wednesday_closed = FALSE,
    thursday_open = opening_time, thursday_close = closing_time, thursday_closed = FALSE,
    friday_open = opening_time, friday_close = closing_time, friday_closed = FALSE,
    saturday_open = opening_time, saturday_close = closing_time, saturday_closed = FALSE,
    sunday_open = opening_time, sunday_close = closing_time, sunday_closed = FALSE
WHERE opening_time IS NOT NULL OR closing_time IS NOT NULL;

-- Step 3: Remove legacy columns and their index
DROP INDEX idx_opening_closing_time ON Restaurants;
ALTER TABLE Restaurants DROP COLUMN opening_time, DROP COLUMN closing_time;
