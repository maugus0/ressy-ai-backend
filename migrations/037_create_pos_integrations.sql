CREATE TABLE IF NOT EXISTS pos_Integrations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id INT NOT NULL,
    pos_type ENUM('SQUARE', 'TOAST') NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    credentials JSON,
    location_id VARCHAR(255),
    default_order_options JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(id) ON DELETE CASCADE ON UPDATE CASCADE,
    UNIQUE KEY unique_restaurant_pos (restaurant_id, pos_type),
    INDEX idx_restaurant_pos (restaurant_id, pos_type),
    INDEX idx_enabled (enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
