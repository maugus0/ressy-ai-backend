-- Migration: Create POS catalog sync tracking tables
-- Description: Tracks asynchronous catalog imports and surfaces admin-visible import issues.

CREATE TABLE IF NOT EXISTS POS_Catalog_Sync_Runs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id INT NOT NULL,
    pos_integration_id INT NOT NULL,
    trigger_source VARCHAR(20) NOT NULL DEFAULT 'SCHEDULED',
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    catalog_version VARCHAR(255) DEFAULT NULL,
    triggered_by VARCHAR(255) DEFAULT NULL,
    summary JSON DEFAULT NULL,
    error_message TEXT DEFAULT NULL,
    started_at TIMESTAMP NULL,
    completed_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (pos_integration_id) REFERENCES POS_Integrations(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_pcsr_restaurant_status (restaurant_id, status),
    INDEX idx_pcsr_pos_status (pos_integration_id, status),
    INDEX idx_pcsr_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS POS_Catalog_Sync_Issues (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sync_run_id INT DEFAULT NULL,
    restaurant_id INT NOT NULL,
    pos_integration_id INT NOT NULL,
    scope VARCHAR(20) NOT NULL,
    issue_type VARCHAR(64) NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'ERROR',
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN',
    external_object_id VARCHAR(255) DEFAULT NULL,
    external_parent_id VARCHAR(255) DEFAULT NULL,
    title VARCHAR(255) NOT NULL,
    details TEXT DEFAULT NULL,
    payload JSON DEFAULT NULL,
    resolved_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (sync_run_id) REFERENCES POS_Catalog_Sync_Runs(id) ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (pos_integration_id) REFERENCES POS_Integrations(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_pcsi_restaurant_status (restaurant_id, status),
    INDEX idx_pcsi_pos_status (pos_integration_id, status),
    INDEX idx_pcsi_run (sync_run_id),
    INDEX idx_pcsi_external_object (external_object_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
