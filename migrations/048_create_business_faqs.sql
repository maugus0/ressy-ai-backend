-- Migration: Create Business_FAQs table
-- Description: Stores frequently asked questions for businesses (generalized from FAQs)

CREATE TABLE IF NOT EXISTS Business_FAQs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    business_id INT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX idx_business_id (business_id),
    INDEX idx_created_at (created_at),
    FULLTEXT idx_question_answer (question, answer)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
