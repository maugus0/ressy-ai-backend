CREATE TABLE IF NOT EXISTS Menu_POS_Mapping (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id INT NOT NULL,
    menu_item_id INT NOT NULL,
    pos_integration_id INT NOT NULL,
    pos_menu_item_id VARCHAR(255) NOT NULL,
    pos_menu_item_name VARCHAR(255),
    last_synced_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (menu_item_id) REFERENCES Menus(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (pos_integration_id) REFERENCES POS_Integrations(id) ON DELETE CASCADE ON UPDATE CASCADE,
    UNIQUE KEY unique_menu_pos (menu_item_id, pos_integration_id),
    INDEX idx_restaurant_pos (restaurant_id, pos_integration_id),
    INDEX idx_menu_pos (menu_item_id, pos_integration_id),
    INDEX idx_pos_menu_item_id (pos_menu_item_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
