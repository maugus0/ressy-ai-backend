-- Migration: Update User_Activity_History to support admin UUIDs
-- Description: Modifies the table to allow tracking activity from admin users who have UUIDs
-- instead of integer user IDs. Adds actor_uuid column and makes user_id nullable.

-- Step 1: Drop the foreign key constraint on user_id
-- This is necessary because admin users are in Restaurant_Administrators and Ressy_Administrators tables
ALTER TABLE User_Activity_History
DROP FOREIGN KEY user_activity_history_ibfk_1;

-- Step 2: Make user_id nullable (for cases where actor is an admin with UUID)
ALTER TABLE User_Activity_History
MODIFY COLUMN user_id INT NULL COMMENT 'User ID for customer users (from Users table), NULL for admin actions';

-- Step 3: Add actor_uuid column to store admin user UUIDs
ALTER TABLE User_Activity_History
ADD COLUMN actor_uuid VARCHAR(36) NULL COMMENT 'UUID of admin/staff user who performed the action' AFTER user_id;

-- Step 4: Add actor_type column to distinguish between different actor types
ALTER TABLE User_Activity_History
ADD COLUMN actor_type ENUM('user', 'admin', 'restaurant_admin', 'system') DEFAULT 'user' COMMENT 'Type of actor who performed the action' AFTER actor_uuid;

-- Step 5: Add index on actor_uuid for efficient lookups
ALTER TABLE User_Activity_History
ADD INDEX idx_actor_uuid (actor_uuid);

-- Step 6: Add index on actor_type for filtering
ALTER TABLE User_Activity_History
ADD INDEX idx_actor_type (actor_type);

