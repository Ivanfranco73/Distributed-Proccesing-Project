-- MariaDB initialization script for Airly data
-- This script runs automatically when the container is first created

USE airly;

CREATE TABLE IF NOT EXISTS measurements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    datetime_utc DATETIME NOT NULL,
    city VARCHAR(100) NOT NULL,
    lat DECIMAL(10, 6) NOT NULL,
    lon DECIMAL(10, 6) NOT NULL,
    hour_utc TINYINT NOT NULL,
    minute_utc TINYINT NOT NULL,
    pm25 DECIMAL(10, 2),
    pm10 DECIMAL(10, 2),
    temperature DECIMAL(6, 2),
    humidity DECIMAL(6, 2),
    pressure DECIMAL(8, 2),
    aqi DECIMAL(6, 2),
    station_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_datetime (datetime_utc),
    INDEX idx_city (city),
    INDEX idx_aqi (aqi),
    INDEX idx_station (station_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
