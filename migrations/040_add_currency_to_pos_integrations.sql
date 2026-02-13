-- Migration: Add currency column to POS_Integrations table
-- Description: Adds currency field to support different currencies per POS integration

ALTER TABLE POS_Integrations
ADD COLUMN currency VARCHAR(3) DEFAULT 'USD' COMMENT 'Currency code (3-letter ISO 4217, e.g., ''USD'', ''CAD'', ''EUR''; format validated at the application layer)';

CREATE INDEX idx_currency ON POS_Integrations(currency);
