ALTER TABLE Restaurants
    ADD COLUMN timezone VARCHAR(64) AFTER closing_time;

UPDATE Restaurants
SET timezone = 'America/Vancouver'
WHERE timezone IS NULL;
