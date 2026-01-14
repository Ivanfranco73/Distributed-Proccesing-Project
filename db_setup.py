#!/usr/bin/env python3
"""
Airly Database Setup
Handles database initialization, schema creation, and data migration.
Can be run independently from the collector.
"""

import csv
import os
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv
import mysql.connector
from mysql.connector import Error as MySQLError

# Load environment variables
load_dotenv()

# Database Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "airly")
DB_USER = os.getenv("DB_USER", "airly")
DB_PASSWORD = os.getenv("DB_PASSWORD", "airly_pass")

# CSV file for migration
CSV_FILE = os.getenv("CSV_FILE", "./data/airly_gdansk.csv")
DEFAULT_STATION_ID = int(os.getenv("INSTALLATION_ID", "3387"))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database schema
SCHEMA_SQL = """
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
"""


def get_db_connection(database=None):
    """Create and return a database connection."""
    try:
        config = {
            "host": DB_HOST,
            "port": DB_PORT,
            "user": DB_USER,
            "password": DB_PASSWORD,
            "connect_timeout": 10
        }
        if database:
            config["database"] = database
        
        connection = mysql.connector.connect(**config)
        return connection
    except MySQLError as e:
        logger.error(f"Failed to connect to database: {e}")
        return None


def check_connection():
    """Check if database is accessible."""
    logger.info(f"Checking connection to {DB_HOST}:{DB_PORT}...")
    connection = get_db_connection(DB_NAME)
    if connection:
        logger.info("✓ Database connection successful")
        connection.close()
        return True
    else:
        logger.error("✗ Database connection failed")
        return False


def create_database():
    """Create the database if it doesn't exist."""
    logger.info(f"Creating database '{DB_NAME}' if not exists...")
    connection = get_db_connection()  # Connect without database
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
        cursor.execute(f"USE {DB_NAME}")
        connection.commit()
        logger.info(f"✓ Database '{DB_NAME}' ready")
        cursor.close()
        connection.close()
        return True
    except MySQLError as e:
        logger.error(f"Failed to create database: {e}")
        return False


def create_schema():
    """Create the measurements table schema."""
    logger.info("Creating schema...")
    connection = get_db_connection(DB_NAME)
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        cursor.execute(SCHEMA_SQL)
        connection.commit()
        logger.info("✓ Schema created successfully")
        cursor.close()
        connection.close()
        return True
    except MySQLError as e:
        logger.error(f"Failed to create schema: {e}")
        return False


def get_table_info():
    """Get information about the measurements table."""
    connection = get_db_connection(DB_NAME)
    if not connection:
        return None
    
    try:
        cursor = connection.cursor(dictionary=True)
        
        # Get row count
        cursor.execute("SELECT COUNT(*) as count FROM measurements")
        count = cursor.fetchone()['count']
        
        # Get date range
        cursor.execute("""
            SELECT 
                MIN(datetime_utc) as first_record,
                MAX(datetime_utc) as last_record
            FROM measurements
        """)
        dates = cursor.fetchone()
        
        cursor.close()
        connection.close()
        
        return {
            "row_count": count,
            "first_record": dates['first_record'],
            "last_record": dates['last_record']
        }
    except MySQLError as e:
        logger.error(f"Failed to get table info: {e}")
        return None


def migrate_csv(csv_file=None, skip_duplicates=True):
    """
    Migrate CSV data to MariaDB.
    
    Args:
        csv_file: Path to CSV file (defaults to CSV_FILE)
        skip_duplicates: If True, skip rows that might be duplicates based on datetime
    """
    csv_file = csv_file or CSV_FILE
    
    if not os.path.exists(csv_file):
        logger.error(f"CSV file not found: {csv_file}")
        return False
    
    logger.info(f"Migrating data from {csv_file}...")
    
    connection = get_db_connection(DB_NAME)
    if not connection:
        return False
    
    cursor = connection.cursor()
    
    insert_query = """
        INSERT INTO measurements 
        (datetime_utc, city, lat, lon, hour_utc, minute_utc, pm25, pm10, temperature, humidity, pressure, aqi, station_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    check_query = "SELECT id FROM measurements WHERE datetime_utc = %s AND city = %s LIMIT 1"
    
    rows_imported = 0
    rows_skipped = 0
    rows_duplicate = 0
    
    try:
        with open(csv_file, 'r', newline='') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    # Parse datetime
                    dt = datetime.strptime(row['datetime_utc'], '%Y-%m-%d %H:%M:%S')
                    city = row['city']
                    
                    # Check for duplicates if enabled
                    if skip_duplicates:
                        cursor.execute(check_query, (dt, city))
                        if cursor.fetchone():
                            rows_duplicate += 1
                            continue
                    
                    # Prepare values, handling empty strings
                    values = (
                        dt,
                        city,
                        float(row['lat']) if row['lat'] else None,
                        float(row['lon']) if row['lon'] else None,
                        int(row['hour_utc']) if row['hour_utc'] else None,
                        int(row['minute_utc']) if row['minute_utc'] else None,
                        float(row['PM25']) if row['PM25'] else None,
                        float(row['PM10']) if row['PM10'] else None,
                        float(row['TEMPERATURE']) if row['TEMPERATURE'] else None,
                        float(row['HUMIDITY']) if row['HUMIDITY'] else None,
                        float(row['PRESSURE']) if row['PRESSURE'] else None,
                        float(row['AQI']) if row['AQI'] else None,
                        int(row.get('station_id', DEFAULT_STATION_ID)) if row.get('station_id') else DEFAULT_STATION_ID
                    )
                    
                    cursor.execute(insert_query, values)
                    rows_imported += 1
                    
                except Exception as e:
                    logger.warning(f"Skipping row: {e}")
                    rows_skipped += 1
        
        connection.commit()
        logger.info("Migration complete!")
        logger.info(f"  ✓ Rows imported: {rows_imported}")
        if rows_duplicate > 0:
            logger.info(f"  - Duplicates skipped: {rows_duplicate}")
        if rows_skipped > 0:
            logger.info(f"  - Errors skipped: {rows_skipped}")
        
        cursor.close()
        connection.close()
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        connection.rollback()
        return False


def clear_table(confirm=False):
    """Clear all data from the measurements table."""
    if not confirm:
        logger.warning("Clear operation requires confirm=True")
        return False
    
    connection = get_db_connection(DB_NAME)
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        cursor.execute("TRUNCATE TABLE measurements")
        connection.commit()
        logger.info("✓ Table cleared")
        cursor.close()
        connection.close()
        return True
    except MySQLError as e:
        logger.error(f"Failed to clear table: {e}")
        return False


def show_status():
    """Display current database status."""
    logger.info("=" * 50)
    logger.info("DATABASE STATUS")
    logger.info("=" * 50)
    logger.info(f"Host: {DB_HOST}:{DB_PORT}")
    logger.info(f"Database: {DB_NAME}")
    logger.info(f"User: {DB_USER}")
    
    if not check_connection():
        return
    
    info = get_table_info()
    if info:
        logger.info(f"Total records: {info['row_count']}")
        if info['first_record']:
            logger.info(f"First record: {info['first_record']}")
            logger.info(f"Last record: {info['last_record']}")
    logger.info("=" * 50)


def setup_all():
    """Run full database setup: create database, schema, and show status."""
    logger.info("Running full database setup...")
    
    if not create_database():
        return False
    
    if not create_schema():
        return False
    
    show_status()
    return True


def main():
    """Main entry point with command-line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Airly Database Setup")
    parser.add_argument('command', nargs='?', default='status',
                        choices=['setup', 'status', 'migrate', 'clear', 'check'],
                        help='Command to run (default: status)')
    parser.add_argument('--csv', type=str, help='CSV file path for migration')
    parser.add_argument('--force', action='store_true', help='Force operation (e.g., clear without prompt)')
    
    args = parser.parse_args()
    
    if args.command == 'setup':
        setup_all()
    elif args.command == 'status':
        show_status()
    elif args.command == 'migrate':
        csv_file = args.csv or CSV_FILE
        migrate_csv(csv_file)
    elif args.command == 'clear':
        if args.force:
            clear_table(confirm=True)
        else:
            response = input("Are you sure you want to clear all data? (yes/no): ")
            if response.lower() == 'yes':
                clear_table(confirm=True)
            else:
                logger.info("Clear operation cancelled")
    elif args.command == 'check':
        check_connection()


if __name__ == "__main__":
    main()
