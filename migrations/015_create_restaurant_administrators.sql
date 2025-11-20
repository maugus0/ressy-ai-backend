-- Migration: Create Restaurant_Administrators table
-- Description: Stores restaurant-specific administrators

CREATE TABLE IF NOT EXISTS Restaurant_Administrators (
    uuid VARCHAR(36) PRIMARY KEY COMMENT 'UUID primary key',
    rest_id INT NOT NULL COMMENT 'Restaurant ID',
    email VARCHAR(255) NOT NULL,
    password VARCHAR(255) NOT NULL COMMENT 'Hashed password',
    role_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (rest_id) REFERENCES Restaurants(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (role_id) REFERENCES Crm_roles(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_rest_id (rest_id),
    INDEX idx_email (email),
    INDEX idx_role_id (role_id),
    INDEX idx_created_at (created_at),
    INDEX idx_rest_email (rest_id, email),
    UNIQUE KEY unique_rest_email (rest_id, email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

