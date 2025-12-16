-- Migration: Add restaurant_id and deleted_at columns to Orders table
-- Description: Adds restaurant association and soft delete capability to orders

-- Add restaurant_id column
ALTER TABLE Orders
ADD COLUMN restaurant_id INT NULL AFTER user_id,
ADD CONSTRAINT fk_orders_restaurant
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(id)
    ON DELETE SET NULL ON UPDATE CASCADE;

-- Add deleted_at column for soft deletes
ALTER TABLE Orders
ADD COLUMN deleted_at TIMESTAMP NULL DEFAULT NULL AFTER updated_at;

-- Add indexes for the new columns
ALTER TABLE Orders
ADD INDEX idx_restaurant_id (restaurant_id),
ADD INDEX idx_deleted_at (deleted_at),
ADD INDEX idx_restaurant_status (restaurant_id, status);

