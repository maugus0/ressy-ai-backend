-- Migration: Create OpenTable_API_Logs table
-- Description: Stores logs of all OpenTable API calls for auditing and debugging

CREATE TABLE IF NOT EXISTS OpenTable_API_Logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    restaurant_id INT NOT NULL,
    endpoint VARCHAR(500) NOT NULL COMMENT 'API endpoint called',
    method VARCHAR(10) NOT NULL COMMENT 'HTTP method (GET, POST, PUT, etc.)',
    request_payload JSON COMMENT 'Request payload sent to OpenTable API',
    response_payload JSON COMMENT 'Response payload received from OpenTable API',
    status_code INT COMMENT 'HTTP status code',
    error_message TEXT COMMENT 'Error message if API call failed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (restaurant_id) REFERENCES Restaurants(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_restaurant_id (restaurant_id),
    INDEX idx_endpoint (endpoint),
    INDEX idx_method (method),
    INDEX idx_status_code (status_code),
    INDEX idx_created_at (created_at),
    INDEX idx_restaurant_created (restaurant_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


