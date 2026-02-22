-- Migration: Add is_spam column to User_Restaurant_Metadata table
-- Description: Allows restaurants to mark users as spam on a per-restaurant basis
-- When 5+ restaurants mark a user as spam, the user is automatically marked as global spam in Users table

ALTER TABLE User_Restaurant_Metadata
ADD COLUMN is_spam BOOLEAN DEFAULT FALSE COMMENT 'Whether this user is marked as spam for this restaurant';

-- Add indexes for efficient spam queries
ALTER TABLE User_Restaurant_Metadata
ADD INDEX idx_is_spam (is_spam),
ADD INDEX idx_user_restaurant_spam (user_id, restaurant_id, is_spam);
