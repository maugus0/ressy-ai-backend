ALTER TABLE Restaurants
ADD COLUMN reservation_seating_capacity INT DEFAULT 50,
ADD COLUMN reservation_advance_days INT DEFAULT 30;

CREATE INDEX idx_reservation_capacity_config ON Restaurants(reservation_seating_capacity, reservation_advance_days);
