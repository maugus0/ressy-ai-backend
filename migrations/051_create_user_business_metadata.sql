-- Migration: Create User_Business_Metadata table
-- Description: Maps users to businesses they are associated with (generalized from User_Restaurant_Metadata)

CREATE TABLE IF NOT EXISTS User_Business_Metadata (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    business_id INT NOT NULL,
    source VARCHAR(50) NOT NULL DEFAULT 'dashboard' COMMENT 'How the association was created: dashboard, booking, call',
    notes TEXT COMMENT 'Optional notes about the user-business relationship',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE ON UPDATE CASCADE,
    UNIQUE KEY unique_user_business (user_id, business_id),
    INDEX idx_user_id (user_id),
    INDEX idx_business_id (business_id),
    INDEX idx_source (source),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
