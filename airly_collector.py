#!/usr/bin/env python3
"""
Airly Air Quality Data Collector

Fetches air quality data from Airly API and stores it in MariaDB.
Optionally forwards data to HSBI Smart Data API.
Database setup is handled separately by db_setup.py.
"""

import csv
import os
import sys
import time
import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional

import requests
import mysql.connector
from mysql.connector import Error as MySQLError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Application configuration from environment variables."""
    
    # Airly API
    airly_api_key: str
    installation_id: int
    latitude: float
    longitude: float
    city_name: str
    
    # Collection settings
    interval_seconds: int
    
    # Database
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    enable_database: bool
    
    # CSV backup
    csv_file: str
    enable_csv: bool
    
    # HSBI API
    hsbi_api_url: str
    hsbi_sensor_id: int
    hsbi_altitude: float
    hsbi_verify_ssl: bool
    enable_hsbi: bool
    
    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            airly_api_key=os.getenv("AIRLY_API_KEY", ""),
            installation_id=int(os.getenv("INSTALLATION_ID", "3387")),
            latitude=float(os.getenv("LATITUDE", "54.3520")),
            longitude=float(os.getenv("LONGITUDE", "18.6466")),
            city_name=os.getenv("CITY_NAME", "Gdansk"),
            interval_seconds=int(os.getenv("INTERVAL_SECONDS", "3600")),
            db_host=os.getenv("DB_HOST", "localhost"),
            db_port=int(os.getenv("DB_PORT", "3306")),
            db_name=os.getenv("DB_NAME", "airly"),
            db_user=os.getenv("DB_USER", "airly"),
            db_password=os.getenv("DB_PASSWORD", "airly_pass"),
            enable_database=os.getenv("ENABLE_DATABASE", "true").lower() == "true",
            csv_file=os.getenv("CSV_FILE", "/data/airly_gdansk.csv"),
            enable_csv=os.getenv("ENABLE_CSV", "false").lower() == "true",
            hsbi_api_url=os.getenv("HSBI_API_URL", ""),
            hsbi_sensor_id=int(os.getenv("HSBI_SENSOR_ID", "1")),
            hsbi_altitude=float(os.getenv("HSBI_ALTITUDE", "10.0")),
            hsbi_verify_ssl=os.getenv("HSBI_VERIFY_SSL", "true").lower() == "true",
            enable_hsbi=os.getenv("ENABLE_HSBI_API", "false").lower() == "true",
        )
    
    @property
    def airly_api_url(self) -> str:
        return f"https://airapi.airly.eu/v2/measurements/installation?installationId={self.installation_id}"


@dataclass
class Measurement:
    """Air quality measurement data."""
    
    timestamp: datetime
    city: str
    latitude: float
    longitude: float
    pm25: Optional[float] = None
    pm10: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    aqi: Optional[float] = None
    station_id: Optional[int] = None
    
    @property
    def hour_utc(self) -> int:
        return self.timestamp.hour
    
    @property
    def minute_utc(self) -> int:
        return self.timestamp.minute
    
    def to_csv_row(self) -> list:
        """Convert to CSV row format."""
        return [
            self.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            self.city,
            self.latitude,
            self.longitude,
            self.hour_utc,
            self.minute_utc,
            self.pm25 if self.pm25 is not None else "",
            self.pm10 if self.pm10 is not None else "",
            self.temperature if self.temperature is not None else "",
            self.humidity if self.humidity is not None else "",
            self.pressure if self.pressure is not None else "",
            self.aqi if self.aqi is not None else "",
        ]


class AirlyCollector:
    """Collects air quality data from Airly API."""
    
    CSV_HEADERS = [
        "datetime_utc", "city", "lat", "lon", "hour_utc", "minute_utc",
        "PM25", "PM10", "TEMPERATURE", "HUMIDITY", "PRESSURE", "AQI"
    ]
    
    def __init__(self, config: Config):
        self.config = config
    
    def fetch_from_airly(self) -> Optional[dict]:
        """Fetch raw data from Airly API."""
        if not self.config.airly_api_key:
            logger.error("Airly API key not configured")
            return None
        
        try:
            response = requests.get(
                self.config.airly_api_url,
                headers={"apikey": self.config.airly_api_key},
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch from Airly API: {e}")
            return None
    
    def parse_measurement(self, data: dict) -> Optional[Measurement]:
        """Parse API response into Measurement object."""
        if not data:
            return None
        
        values: dict = {}
        aqi: Optional[float] = None
        
        # Try current data first, fall back to history
        source = None
        if data.get("current") and data["current"].get("values"):
            source = data["current"]
        elif data.get("history") and len(data["history"]) > 0:
            source = data["history"][0]
        
        if not source:
            logger.warning("No measurement data in API response")
            return None
        
        for v in source.get("values", []):
            values[v["name"]] = v["value"]
        
        indexes = source.get("indexes", [])
        if indexes:
            aqi = indexes[0].get("value")
        
        return Measurement(
            timestamp=datetime.now(timezone.utc).replace(tzinfo=None),
            city=self.config.city_name,
            latitude=self.config.latitude,
            longitude=self.config.longitude,
            pm25=values.get("PM25"),
            pm10=values.get("PM10"),
            temperature=values.get("TEMPERATURE"),
            humidity=values.get("HUMIDITY"),
            pressure=values.get("PRESSURE"),
            aqi=aqi,
            station_id=self.config.installation_id
        )
    
    def save_to_database(self, measurement: Measurement) -> bool:
        """Save measurement to MariaDB."""
        try:
            conn = mysql.connector.connect(
                host=self.config.db_host,
                port=self.config.db_port,
                database=self.config.db_name,
                user=self.config.db_user,
                password=self.config.db_password,
                connect_timeout=10
            )
        except MySQLError as e:
            logger.error(f"Database connection failed: {e}")
            return False
        
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO measurements 
                (datetime_utc, city, lat, lon, hour_utc, minute_utc, 
                 pm25, pm10, temperature, humidity, pressure, aqi, station_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                measurement.timestamp,
                measurement.city,
                measurement.latitude,
                measurement.longitude,
                measurement.hour_utc,
                measurement.minute_utc,
                measurement.pm25,
                measurement.pm10,
                measurement.temperature,
                measurement.humidity,
                measurement.pressure,
                measurement.aqi,
                measurement.station_id
            ))
            conn.commit()
            logger.info(
                f"Saved to DB: {measurement.timestamp} - "
                f"PM2.5: {measurement.pm25}, PM10: {measurement.pm10}, AQI: {measurement.aqi}"
            )
            return True
        except MySQLError as e:
            logger.error(f"Failed to save to database: {e}")
            conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
            conn.close()
    
    def save_to_csv(self, measurement: Measurement) -> bool:
        """Append measurement to CSV file."""
        csv_dir = os.path.dirname(self.config.csv_file)
        if csv_dir:
            os.makedirs(csv_dir, exist_ok=True)
        
        file_exists = os.path.exists(self.config.csv_file)
        
        try:
            with open(self.config.csv_file, "a", newline="") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(self.CSV_HEADERS)
                writer.writerow(measurement.to_csv_row())
            logger.info(f"Saved to CSV: {self.config.csv_file}")
            return True
        except IOError as e:
            logger.error(f"Failed to save to CSV: {e}")
            return False
    
    def send_to_hsbi(self, measurement: Measurement) -> bool:
        """Forward measurement to HSBI Smart Data API."""
        if not self.config.hsbi_api_url:
            logger.warning("HSBI API URL not configured")
            return False
        
        payload = {
            "id": self.config.hsbi_sensor_id,
            "ts": measurement.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "pos": f"POINTZ({self.config.latitude} {self.config.longitude} {self.config.hsbi_altitude})",
            "temp": measurement.temperature or 0,
            "hum": measurement.humidity or 0,
            "pres": measurement.pressure or 0,
            "mass_pm2_5": measurement.pm25 or 0,
            "mass_pm10": measurement.pm10 or 0,
            "mass_pm1_0": (measurement.pm25 or 0) * 0.7,  # Approximation
            "mass_pm4": measurement.pm10 or 0,
            "number_pm0_5": 0,
            "number_pm1_0": 0,
            "number_pm2_5": 0,
            "number_pm4": 0,
            "number_pm10": 0
        }
        
        try:
            response = requests.post(
                self.config.hsbi_api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
                verify=self.config.hsbi_verify_ssl
            )
            response.raise_for_status()
            logger.info(f"Sent to HSBI API: {response.status_code}")
            return True
        except requests.RequestException as e:
            logger.error(f"Failed to send to HSBI API: {e}")
            return False
    
    def collect_once(self) -> bool:
        """Perform a single data collection cycle."""
        logger.info("Fetching data from Airly API...")
        
        data = self.fetch_from_airly()
        if not data:
            return False
        
        measurement = self.parse_measurement(data)
        if not measurement:
            return False
        
        success = True
        
        if self.config.enable_database:
            if not self.save_to_database(measurement):
                success = False
        
        if self.config.enable_csv:
            if not self.save_to_csv(measurement):
                success = False
        
        if self.config.enable_hsbi:
            self.send_to_hsbi(measurement)
        
        return success
    
    def run(self) -> None:
        """Run continuous collection loop."""
        self._log_config()
        
        while True:
            try:
                if self.collect_once():
                    logger.info("Data collection successful")
                else:
                    logger.warning("Data collection failed, will retry next interval")
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
            
            logger.info(f"Sleeping for {self.config.interval_seconds} seconds...")
            time.sleep(self.config.interval_seconds)
    
    def _log_config(self) -> None:
        """Log current configuration."""
        logger.info("=" * 50)
        logger.info("Airly Data Collector")
        logger.info("=" * 50)
        logger.info(f"Location: {self.config.city_name} ({self.config.latitude}, {self.config.longitude})")
        logger.info(f"Station ID: {self.config.installation_id}")
        logger.info(f"Interval: {self.config.interval_seconds}s")
        logger.info(f"Database: {'enabled' if self.config.enable_database else 'disabled'}")
        if self.config.enable_database:
            logger.info(f"  -> {self.config.db_host}:{self.config.db_port}/{self.config.db_name}")
        logger.info(f"CSV backup: {'enabled' if self.config.enable_csv else 'disabled'}")
        if self.config.enable_csv:
            logger.info(f"  -> {self.config.csv_file}")
        logger.info(f"HSBI API: {'enabled' if self.config.enable_hsbi else 'disabled'}")
        if self.config.enable_hsbi:
            logger.info(f"  -> {self.config.hsbi_api_url}")
        logger.info("=" * 50)


def main() -> None:
    """Entry point."""
    config = Config.from_env()
    collector = AirlyCollector(config)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        success = collector.collect_once()
        if success:
            logger.info("✓ Single collection completed")
        else:
            logger.error("✗ Collection failed")
            sys.exit(1)
    else:
        collector.run()


if __name__ == "__main__":
    main()
