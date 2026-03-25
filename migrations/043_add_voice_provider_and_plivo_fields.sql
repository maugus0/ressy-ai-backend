-- Migration: Add voice provider toggle and Plivo fields to Restaurants table
-- Description: Adds support for choosing between Twilio and Plivo as voice service providers

ALTER TABLE Restaurants
ADD COLUMN voice_provider ENUM('twilio', 'plivo') DEFAULT 'twilio' COMMENT 'Voice service provider: twilio or plivo',
ADD COLUMN plivo_phone_number VARCHAR(20) COMMENT 'Plivo phone number for routing calls (E.164 format)',
ADD COLUMN plivo_details JSON COMMENT 'Plivo configuration and settings (auth_id, auth_token, etc.)',
ADD INDEX idx_voice_provider (voice_provider),
ADD INDEX idx_plivo_phone_number (plivo_phone_number);
