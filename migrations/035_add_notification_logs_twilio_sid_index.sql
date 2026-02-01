-- Migration: 035_add_notification_logs_twilio_sid_index.sql
-- Description: Add idx_twilio_sid index for Notification_Logs (SMS tracking)
-- Depends on: 033_create_notification_logs.sql
--
-- Safe to run in both environments:
-- - Local/dev (old table): adds missing index
-- - Production (fresh 033): index already exists from 033; "Duplicate key" is ignored

ALTER TABLE Notification_Logs
    ADD INDEX idx_twilio_sid (twilio_message_sid);
