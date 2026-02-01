-- Migration: Add is_24_hours flag for per-day operating hours
-- Description: Adds a boolean flag for each day to indicate 24-hour operation
-- When is_24_hours=true, the restaurant is open all day (open/close times ignored)
--
-- Depends on: 031_add_daily_operating_hours.sql (per-day open/close/closed columns).
-- Run migrations in numerical order; 032 must run after 031.

ALTER TABLE Restaurants
    ADD COLUMN monday_24_hours BOOLEAN DEFAULT FALSE,
    ADD COLUMN tuesday_24_hours BOOLEAN DEFAULT FALSE,
    ADD COLUMN wednesday_24_hours BOOLEAN DEFAULT FALSE,
    ADD COLUMN thursday_24_hours BOOLEAN DEFAULT FALSE,
    ADD COLUMN friday_24_hours BOOLEAN DEFAULT FALSE,
    ADD COLUMN saturday_24_hours BOOLEAN DEFAULT FALSE,
    ADD COLUMN sunday_24_hours BOOLEAN DEFAULT FALSE;
