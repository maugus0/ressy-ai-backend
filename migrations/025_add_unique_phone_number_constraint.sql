-- Migration: Add unique constraint on phone_number in Users table
-- Description: Fixes BUG-004 - Duplicate caller entries preventing profile updates
-- This migration:
-- 1. Identifies and merges duplicate phone number records (keeping the earliest created)
-- 2. Updates foreign key references to point to the canonical (oldest) user record
-- 3. Adds a unique constraint on phone_number to prevent future duplicates

-- Step 1: Create a temporary table mapping duplicate user IDs to canonical user IDs
-- The canonical user is the one with the earliest created_at for each phone_number
CREATE TEMPORARY TABLE IF NOT EXISTS User_Duplicates AS
SELECT 
    u.id AS duplicate_id,
    canonical.id AS canonical_id,
    u.phone_number
FROM Users u
INNER JOIN (
    SELECT phone_number, MIN(id) AS id
    FROM Users
    WHERE phone_number IS NOT NULL AND phone_number != ''
    GROUP BY phone_number
    HAVING COUNT(*) > 1
) canonical ON u.phone_number = canonical.phone_number AND u.id != canonical.id;

-- Step 2: Update foreign key references in Reservations table
UPDATE Reservations r
INNER JOIN User_Duplicates ud ON r.user_id = ud.duplicate_id
SET r.user_id = ud.canonical_id;

-- Step 3: Update foreign key references in Orders table
UPDATE Orders o
INNER JOIN User_Duplicates ud ON o.user_id = ud.duplicate_id
SET o.user_id = ud.canonical_id;

-- Step 4: Update foreign key references in User_Restaurant_Metadata table
-- First, update mappings that don't conflict
UPDATE User_Restaurant_Metadata urm
INNER JOIN User_Duplicates ud ON urm.user_id = ud.duplicate_id
LEFT JOIN User_Restaurant_Metadata existing ON existing.user_id = ud.canonical_id AND existing.restaurant_id = urm.restaurant_id
SET urm.user_id = ud.canonical_id
WHERE existing.id IS NULL;

-- Delete duplicate mappings that would conflict with unique constraint
DELETE urm FROM User_Restaurant_Metadata urm
INNER JOIN User_Duplicates ud ON urm.user_id = ud.duplicate_id;

-- Step 5: Merge user data - update canonical user with non-null values from duplicates
-- Update name if canonical has NULL but duplicate has a value
UPDATE Users canonical
INNER JOIN (
    SELECT ud.canonical_id, MAX(u.name) as name
    FROM User_Duplicates ud
    INNER JOIN Users u ON u.id = ud.duplicate_id
    WHERE u.name IS NOT NULL
    GROUP BY ud.canonical_id
) dup_data ON canonical.id = dup_data.canonical_id
SET canonical.name = COALESCE(canonical.name, dup_data.name);

-- Update email if canonical has NULL but duplicate has a value
UPDATE Users canonical
INNER JOIN (
    SELECT ud.canonical_id, MAX(u.email) as email
    FROM User_Duplicates ud
    INNER JOIN Users u ON u.id = ud.duplicate_id
    WHERE u.email IS NOT NULL
    GROUP BY ud.canonical_id
) dup_data ON canonical.id = dup_data.canonical_id
SET canonical.email = COALESCE(canonical.email, dup_data.email);

-- Update address if canonical has NULL but duplicate has a value
UPDATE Users canonical
INNER JOIN (
    SELECT ud.canonical_id, MAX(u.address) as address
    FROM User_Duplicates ud
    INNER JOIN Users u ON u.id = ud.duplicate_id
    WHERE u.address IS NOT NULL
    GROUP BY ud.canonical_id
) dup_data ON canonical.id = dup_data.canonical_id
SET canonical.address = COALESCE(canonical.address, dup_data.address);

-- Step 6: Delete duplicate user records (now safe since FKs have been updated)
DELETE u FROM Users u
INNER JOIN User_Duplicates ud ON u.id = ud.duplicate_id;

-- Step 7: Drop the temporary table
DROP TEMPORARY TABLE IF EXISTS User_Duplicates;

-- Step 8: Add unique constraint on phone_number
-- Note: We allow NULL phone_numbers (multiple NULLs are allowed by MySQL unique constraints)
ALTER TABLE Users 
ADD CONSTRAINT unique_phone_number UNIQUE (phone_number);

