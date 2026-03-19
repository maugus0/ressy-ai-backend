-- Migration: Create Business_Order_Details table
-- Description: Stores individual catalogue items in a business order (generalized from Order_Details)

CREATE TABLE IF NOT EXISTS Business_Order_Details (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    catalogue_item_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES Business_Orders(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (catalogue_item_id) REFERENCES Catalogue(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_order_id (order_id),
    INDEX idx_catalogue_item_id (catalogue_item_id),
    INDEX idx_created_at (created_at),
    INDEX idx_order_catalogue (order_id, catalogue_item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
