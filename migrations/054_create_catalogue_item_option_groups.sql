-- Migration: Create Catalogue_Item_Option_Groups table
-- Description: Maps catalogue items to option groups (generalized from Menu_Item_Option_Groups)

CREATE TABLE IF NOT EXISTS Catalogue_Item_Option_Groups (
    catalogue_item_id INT NOT NULL,
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
    PRIMARY KEY (catalogue_item_id, group_id),
    FOREIGN KEY (catalogue_item_id) REFERENCES Catalogue(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (group_id) REFERENCES Catalogue_Option_Groups(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_ciog_group (group_id),
    INDEX idx_ciog_sort (sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
