-- Migration: Create Crm_roles table
-- Description: Stores CRM roles with associated permissions

CREATE TABLE IF NOT EXISTS Crm_roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    role VARCHAR(100) NOT NULL UNIQUE COMMENT 'Role name (e.g., admin, manager, staff)',
    permission_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (permission_id) REFERENCES Permissions(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    INDEX idx_role (role),
    INDEX idx_permission_id (permission_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

