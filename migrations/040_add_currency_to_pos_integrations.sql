-- Migration: Add currency column to POS_Integrations table
-- Description: Adds currency field to support different currencies per POS integration

ALTER TABLE POS_Integrations
ADD COLUMN currency VARCHAR(3) DEFAULT 'USD' COMMENT 'Currency code (3-letter ISO 4217, e.g., ''USD'', ''CAD'', ''EUR''; format validated at the application layer)';

-- Note: No index is created on `currency` because current POS integration queries
-- do not filter by currency alone. If future features require such queries,
-- add an appropriate index in a separate migration.
