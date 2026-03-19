-- Migration: Create Business_Order_Item_Options_Snapshots table
-- Description: Stores snapshots of order item options for business orders (generalized from Order_Item_Options_Snapshots)

CREATE TABLE IF NOT EXISTS Business_Order_Item_Options_Snapshots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_item_id INT NOT NULL,
    option_value_id INT NULL,
    option_group_name_snapshot VARCHAR(150) NOT NULL,
    option_value_name_snapshot VARCHAR(150) NOT NULL,
    price_delta_snapshot DECIMAL(10, 2) NOT NULL DEFAULT 0,
    quantity INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (order_item_id) REFERENCES Business_Order_Item_Snapshots(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (option_value_id) REFERENCES Catalogue_Option_Values(id) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX idx_boios_order_item (order_item_id),
    INDEX idx_boios_option_value (option_value_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
