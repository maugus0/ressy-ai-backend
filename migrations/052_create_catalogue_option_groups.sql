-- Migration: Create Catalogue_Option_Groups table
-- Description: Stores option groups for catalogue items (generalized from Menu_Option_Groups)

CREATE TABLE IF NOT EXISTS Catalogue_Option_Groups (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    name VARCHAR(150) NOT NULL,
    description TEXT,
    selection_type VARCHAR(20) NOT NULL DEFAULT 'multiple' COMMENT 'single|multiple',
    min_select INT DEFAULT 0,
    max_select INT DEFAULT NULL,
    free_allowance INT NOT NULL DEFAULT 0 COMMENT 'Number of selections included at no extra charge',
    free_allowance_strategy VARCHAR(32) NOT NULL DEFAULT 'HIGHEST_PRICE_FIRST' COMMENT 'HIGHEST_PRICE_FIRST|LOWEST_PRICE_FIRST',
    allows_quantity BOOLEAN NOT NULL DEFAULT FALSE,
    max_quantity_per_option INT DEFAULT NULL,
    prompt_style VARCHAR(30) NOT NULL DEFAULT 'ASK_IF_MENTIONED' COMMENT 'ASK_ALWAYS|ASK_IF_MENTIONED|SUGGEST_POPULAR',
    is_required BOOLEAN NOT NULL DEFAULT FALSE,
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_cog_business (business_id),
    INDEX idx_cog_name (name),
    INDEX idx_cog_required (is_required),
    INDEX idx_cog_available (is_available),
    INDEX idx_cog_prompt_style (prompt_style)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
