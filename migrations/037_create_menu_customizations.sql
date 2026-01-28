-- Migration: Create menu customization and order item snapshot tables
-- Description: Adds option groups/values, menu item mappings, and per-order snapshots for customizations

CREATE TABLE IF NOT EXISTS Menu_Option_Groups (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id INT NOT NULL,
    name VARCHAR(150) NOT NULL,
    description TEXT,
    selection_type VARCHAR(20) NOT NULL DEFAULT 'multiple' COMMENT 'single|multiple',
    min_select INT DEFAULT 0,
    max_select INT DEFAULT NULL,
    free_allowance INT NOT NULL DEFAULT 0 COMMENT 'Number of selections included at no extra charge',
    allows_quantity BOOLEAN NOT NULL DEFAULT FALSE,
    max_quantity_per_option INT DEFAULT NULL,
    prompt_style VARCHAR(30) NOT NULL DEFAULT 'ASK_IF_MENTIONED' COMMENT 'ASK_ALWAYS|ASK_IF_MENTIONED|SUGGEST_POPULAR',
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_mog_restaurant (restaurant_id),
    INDEX idx_mog_name (name),
    INDEX idx_mog_required (is_required),
    INDEX idx_mog_available (is_available),
    INDEX idx_mog_prompt_style (prompt_style)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS Menu_Option_Values (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    name VARCHAR(150) NOT NULL,
    price_delta DECIMAL(10, 2) NOT NULL DEFAULT 0,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES Menu_Option_Groups(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_mov_group (group_id),
    INDEX idx_mov_name (name),
    INDEX idx_mov_default (is_default),
    INDEX idx_mov_available (is_available)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS Menu_Item_Option_Groups (
    menu_item_id INT NOT NULL,
    group_id INT NOT NULL,
    min_select_override INT DEFAULT NULL,
    max_select_override INT DEFAULT NULL,
    free_allowance_override INT DEFAULT NULL,
    allows_quantity_override BOOLEAN DEFAULT NULL,
    max_quantity_per_option_override INT DEFAULT NULL,
    is_required_override BOOLEAN DEFAULT NULL,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (menu_item_id, group_id),
    FOREIGN KEY (menu_item_id) REFERENCES Menus(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (group_id) REFERENCES Menu_Option_Groups(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_miog_group (group_id),
    INDEX idx_miog_sort (sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS Order_Items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    menu_item_id INT NULL,
    item_name_snapshot VARCHAR(255) NOT NULL,
    base_price_snapshot DECIMAL(10, 2) NOT NULL DEFAULT 0,
    quantity INT NOT NULL DEFAULT 1,
    instructions TEXT,
    final_unit_price_snapshot DECIMAL(10, 2) NOT NULL DEFAULT 0,
    option_total_snapshot DECIMAL(10, 2) NOT NULL DEFAULT 0,
    total_price_snapshot DECIMAL(10, 2) NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES Orders(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (menu_item_id) REFERENCES Menus(id) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX idx_oi_order (order_id),
    INDEX idx_oi_menu_item (menu_item_id),
    INDEX idx_oi_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS Order_Item_Options (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_item_id INT NOT NULL,
    option_value_id INT NULL,
    option_group_name_snapshot VARCHAR(150) NOT NULL,
    option_value_name_snapshot VARCHAR(150) NOT NULL,
    price_delta_snapshot DECIMAL(10, 2) NOT NULL DEFAULT 0,
    quantity INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (order_item_id) REFERENCES Order_Items(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (option_value_id) REFERENCES Menu_Option_Values(id) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX idx_oio_order_item (order_item_id),
    INDEX idx_oio_option_value (option_value_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
