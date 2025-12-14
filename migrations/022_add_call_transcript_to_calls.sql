-- Migration: Add call_transcript column to Calls table
-- Description: Stores full call transcript JSON directly on the Calls table and adds indexes to optimize filtering/search.

ALTER TABLE Calls
    ADD COLUMN call_transcript LONGTEXT NULL COMMENT 'Full call transcript JSON';

-- Indexing for filtering and search
CREATE INDEX idx_calls_created_at ON Calls (created_at);
CREATE INDEX idx_calls_restaurant_created ON Calls (restaurant_id, created_at);

-- Full-text search on transcript content
CREATE FULLTEXT INDEX idx_calls_transcript_ft ON Calls (call_transcript);
