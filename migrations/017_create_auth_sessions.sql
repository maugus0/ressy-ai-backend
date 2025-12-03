-- Migration: Create Auth_Sessions table
-- Description: Introduces the Auth_Sessions table for refresh token sessions

-- Create Auth_Sessions table for refresh token session management
CREATE TABLE IF NOT EXISTS Auth_Sessions (
    id CHAR(36) NOT NULL,
    user_id CHAR(36) NOT NULL,
    user_type VARCHAR(16) NOT NULL,
    refresh_token_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    revoked TINYINT(1) NOT NULL DEFAULT 0,
    user_agent VARCHAR(512) NULL,
    ip_address VARCHAR(64) NULL,
    PRIMARY KEY (id),
    INDEX idx_auth_sessions_user (user_id, user_type),
    INDEX idx_auth_sessions_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
