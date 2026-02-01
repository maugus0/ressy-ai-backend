-- Align Notification_Logs column sizes with Copilot recommendations.
-- Safe to run after 033: updates existing tables (VARCHAR(20)->30, VARCHAR(50)->100);
-- no-op if 033 already created table with correct sizes.
ALTER TABLE Notification_Logs
    MODIFY COLUMN recipient_phone VARCHAR(30) NOT NULL COMMENT 'Customer phone number (E.164 + formatting)',
    MODIFY COLUMN twilio_message_sid VARCHAR(100) COMMENT 'Twilio message SID for tracking';
