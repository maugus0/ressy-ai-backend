-- Migration: Add business_type column to Businesses table
-- Description: Adds business_type column to differentiate business types and map to different prompts

ALTER TABLE Businesses
ADD COLUMN business_type VARCHAR(50) NULL DEFAULT 'restaurant'
COMMENT 'Business type (e.g., restaurant, salon, spa, clinic, etc.) - used for prompt selection'
AFTER name;

-- Add index for business_type lookups
CREATE INDEX idx_business_type ON Businesses(business_type);

-- Update existing businesses to have default type
UPDATE Businesses SET business_type = 'restaurant' WHERE business_type IS NULL;
