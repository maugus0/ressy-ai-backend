-- Migration: Create Catalogue_Option_Values table
-- Description: Stores option values for catalogue option groups (generalized from Menu_Option_Values)

CREATE TABLE IF NOT EXISTS Catalogue_Option_Values (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_id INT NOT NULL,
    name VARCHAR(150) NOT NULL,
    price_delta DECIMAL(10, 2) NOT NULL DEFAULT 0,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES Catalogue_Option_Groups(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_cov_group (group_id),
    INDEX idx_cov_name (name),
    INDEX idx_cov_default (is_default),
    INDEX idx_cov_available (is_available)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
