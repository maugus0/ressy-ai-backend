-- Migration: Create POS catalog archive table
-- Description: Stores rollback snapshots for archive-first restaurant catalog migrations.

CREATE TABLE IF NOT EXISTS POS_Catalog_Archives (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id INT NOT NULL,
    pos_integration_id INT NOT NULL,
    label VARCHAR(255) DEFAULT NULL,
    notes TEXT DEFAULT NULL,
    created_by VARCHAR(255) DEFAULT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    payload JSON NOT NULL,
    restored_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (pos_integration_id) REFERENCES POS_Integrations(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_pca_restaurant_integration (restaurant_id, pos_integration_id),
    INDEX idx_pca_status (status),
    INDEX idx_pca_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
