-- Migration: Create Business_Orders table
-- Description: Stores order information for businesses (generalized from Orders)

CREATE TABLE IF NOT EXISTS Business_Orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    business_id INT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending' COMMENT 'Order status (pending, confirmed, preparing, ready, completed, cancelled)',
    total_amount DECIMAL(10, 2) NOT NULL,
    order_details JSON COMMENT 'Order details as JSON',
    customization JSON COMMENT 'Customization options',
    deleted_at TIMESTAMP NULL DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_business_id (business_id),
    INDEX idx_status (status),
    INDEX idx_deleted_at (deleted_at),
    INDEX idx_created_at (created_at),
    INDEX idx_user_status (user_id, status),
    INDEX idx_business_status (business_id, status),
    INDEX idx_created_at_desc (created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
