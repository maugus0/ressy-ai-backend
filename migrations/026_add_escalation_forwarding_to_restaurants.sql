-- Migration: Add escalation forwarding settings to Restaurants
-- Description: Adds forward_escalations and escalation_phone_number fields

ALTER TABLE Restaurants
    ADD COLUMN forward_escalations BOOLEAN DEFAULT FALSE,
    ADD COLUMN escalation_phone_number VARCHAR(20) NULL;
