-- Migration: Create Restaurant_Features table
-- Description: Stores per-restaurant feature flags for voice agent capabilities

CREATE TABLE IF NOT EXISTS Restaurant_Features (
    restaurant_id INT NOT NULL,
    orders_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    reservations_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    faqs_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (restaurant_id),
    CONSTRAINT fk_restaurant_features_restaurant
        FOREIGN KEY (restaurant_id) REFERENCES Restaurants(id)
        ON DELETE CASCADE,
    INDEX idx_orders_enabled (orders_enabled),
    INDEX idx_reservations_enabled (reservations_enabled),
    INDEX idx_faqs_enabled (faqs_enabled)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Seed defaults for existing restaurants
INSERT INTO Restaurant_Features (restaurant_id)
SELECT r.id
FROM Restaurants r
LEFT JOIN Restaurant_Features rf ON rf.restaurant_id = r.id
WHERE rf.restaurant_id IS NULL;
