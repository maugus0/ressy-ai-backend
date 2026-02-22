-- Migration: Create Job_Execution_Logs table
-- Description: Tracks execution of scheduled jobs (e.g., user profile sync)
-- Stores job execution status, timing, and statistics

CREATE TABLE IF NOT EXISTS Job_Execution_Logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL COMMENT 'Name of the job (e.g., user_profile_sync)',
    status VARCHAR(50) NOT NULL COMMENT 'Status: running, completed, failed, cancelled',
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL COMMENT 'When the job finished (NULL if still running or failed)',
    records_processed INT DEFAULT 0 COMMENT 'Number of records processed',
    records_updated INT DEFAULT 0 COMMENT 'Number of records successfully updated',
    records_failed INT DEFAULT 0 COMMENT 'Number of records that failed to update',
    error_message TEXT NULL COMMENT 'Error details if job failed',
    execution_time_seconds DECIMAL(10,2) NULL COMMENT 'Total execution time in seconds',
    metadata JSON NULL COMMENT 'Additional job metadata (batch size, config, etc.)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_job_name (job_name),
    INDEX idx_status (status),
    INDEX idx_started_at (started_at),
    INDEX idx_job_name_status (job_name, status),
    INDEX idx_started_at_desc (started_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
