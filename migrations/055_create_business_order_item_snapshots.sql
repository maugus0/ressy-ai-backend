-- Migration: Create Business_Order_Item_Snapshots table
-- Description: Stores snapshots of order items for business orders (generalized from Order_Item_Snapshots)

CREATE TABLE IF NOT EXISTS Business_Order_Item_Snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    catalogue_item_id INT NULL,
    item_name_snapshot VARCHAR(255) NOT NULL,
    base_price_snapshot DECIMAL(10, 2) NOT NULL DEFAULT 0,
    quantity INT NOT NULL DEFAULT 1,
    instructions TEXT,
    final_unit_price_snapshot DECIMAL(10, 2) NOT NULL DEFAULT 0,
    option_total_snapshot DECIMAL(10, 2) NOT NULL DEFAULT 0,
    total_price_snapshot DECIMAL(10, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES Business_Orders(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (catalogue_item_id) REFERENCES Catalogue(id) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX idx_bois_order (order_id),
    INDEX idx_bois_catalogue_item (catalogue_item_id),
    INDEX idx_bois_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
