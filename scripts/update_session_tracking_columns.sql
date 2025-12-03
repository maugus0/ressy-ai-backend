-- One-off update for existing databases to add session tracking columns.
-- Run manually on environments that already have Ressy_Administrator and Restaurant_Administrators.

ALTER TABLE Ressy_Administrator
    ADD COLUMN last_login TIMESTAMP NULL DEFAULT NULL AFTER updated_at;

ALTER TABLE Ressy_Administrator
    ADD COLUMN last_active TIMESTAMP NULL DEFAULT NULL AFTER last_login;

ALTER TABLE Restaurant_Administrators
    ADD COLUMN last_login TIMESTAMP NULL DEFAULT NULL AFTER updated_at;

ALTER TABLE Restaurant_Administrators
    ADD COLUMN last_active TIMESTAMP NULL DEFAULT NULL AFTER last_login;
