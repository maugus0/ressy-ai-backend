-- Migration: Add metadata column to Catalogue table
-- Description: Adds metadata JSON column to store additional item information (e.g., location for real estate)

ALTER TABLE Catalogue
ADD COLUMN metadata JSON NULL COMMENT 'Additional metadata for catalogue items (e.g., location for real estate properties)'
AFTER item_desc;
