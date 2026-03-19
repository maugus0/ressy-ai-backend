-- Migration: Create Business_Features table
-- Description: Stores per-business feature flags for voice agent capabilities (generalized from Restaurant_Features)

CREATE TABLE IF NOT EXISTS Business_Features (
    business_id INT NOT NULL,
    orders_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    reservations_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    faqs_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    orders_sms_redirect_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    orders_redirect_url VARCHAR(512) DEFAULT NULL,
    orders_redirect_message TEXT DEFAULT NULL,
    reservations_sms_redirect_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    reservations_redirect_url VARCHAR(512) DEFAULT NULL,
    reservations_redirect_message TEXT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (business_id),
    CONSTRAINT fk_business_features_business
        FOREIGN KEY (business_id) REFERENCES Businesses(id)
        ON DELETE CASCADE,
    INDEX idx_orders_enabled (orders_enabled),
    INDEX idx_reservations_enabled (reservations_enabled),
    INDEX idx_faqs_enabled (faqs_enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Seed defaults for existing businesses
INSERT INTO Business_Features (business_id)
SELECT b.id
FROM Businesses b
LEFT JOIN Business_Features bf ON bf.business_id = b.id
WHERE bf.business_id IS NULL;
