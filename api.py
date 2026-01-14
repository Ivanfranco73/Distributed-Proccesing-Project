#!/usr/bin/env python3
"""
Airly Data API
REST API for adding and retrieving air quality measurements.
"""

from fastapi import FastAPI, HTTPException, Depends, Header, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
import mysql.connector
from mysql.connector import Error as MySQLError
import os

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Rate limiter setup
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Airly Data API",
    description="API for air quality data storage and retrieval",
    version="1.0.0"
)

# Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Database configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "mariadb"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "database": os.getenv("DB_NAME", "airly"),
    "user": os.getenv("DB_USER", "airly"),
    "password": os.getenv("DB_PASSWORD", "airly_pass"),
}

# Add SSL configuration if certificates are available
ssl_ca = os.getenv("DB_SSL_CA")
ssl_cert = os.getenv("DB_SSL_CERT")
ssl_key = os.getenv("DB_SSL_KEY")

if ssl_ca and ssl_cert and ssl_key:
    DB_CONFIG["ssl_ca"] = ssl_ca
    DB_CONFIG["ssl_cert"] = ssl_cert
    DB_CONFIG["ssl_key"] = ssl_key
    DB_CONFIG["ssl_verify_cert"] = True

API_KEY = os.getenv("API_KEY", "")


# Data models
class MeasurementInput(BaseModel):
    datetime_utc: Optional[datetime] = None
    city: str = "Gdansk"
    lat: float = 54.3520
    lon: float = 18.6466
    pm25: Optional[float] = None
    pm10: Optional[float] = None
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    aqi: Optional[float] = None
    station_id: Optional[int] = None


class MeasurementOutput(BaseModel):
    id: int
    datetime_utc: datetime
    city: str
    lat: float
    lon: float
    hour_utc: int
    minute_utc: int
    pm25: Optional[float]
    pm10: Optional[float]
    temperature: Optional[float]
    humidity: Optional[float]
    pressure: Optional[float]
    aqi: Optional[float]
    station_id: Optional[int]
    created_at: datetime


# Dependencies
def get_db():
    """Create database connection."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        yield conn
    except MySQLError as e:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()


def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """Verify API key for write operations."""
    if not API_KEY:
        raise HTTPException(status_code=500, detail="API key not configured on server")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


# Endpoints
@app.get("/health")
def health_check():
    """Health check endpoint (no auth required)."""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/measurements", response_model=List[dict])
@limiter.limit("100/minute")
def get_measurements(
    request: Request,
    limit: int = Query(default=10, le=1000),
    city: Optional[str] = None,
    station_id: Optional[int] = None,
    conn=Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Get recent measurements."""
    cursor = conn.cursor(dictionary=True)
    
    query = "SELECT * FROM measurements WHERE 1=1"
    params = []
    
    if city:
        query += " AND city = %s"
        params.append(city)
    
    if station_id:
        query += " AND station_id = %s"
        params.append(station_id)
    
    query += " ORDER BY datetime_utc DESC LIMIT %s"
    params.append(limit)
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    cursor.close()
    
    # Convert datetime objects to strings for JSON serialization
    for row in results:
        if row.get('datetime_utc'):
            row['datetime_utc'] = row['datetime_utc'].isoformat()
        if row.get('created_at'):
            row['created_at'] = row['created_at'].isoformat()
    
    return results


@app.get("/measurements/latest")
@limiter.limit("100/minute")
def get_latest_measurement(
    request: Request,
    city: Optional[str] = None,
    station_id: Optional[int] = None,
    conn=Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Get the most recent measurement."""
    cursor = conn.cursor(dictionary=True)
    
    query = "SELECT * FROM measurements WHERE 1=1"
    params = []
    
    if city:
        query += " AND city = %s"
        params.append(city)
    
    if station_id:
        query += " AND station_id = %s"
        params.append(station_id)
    
    query += " ORDER BY datetime_utc DESC LIMIT 1"
    
    cursor.execute(query, params)
    result = cursor.fetchone()
    cursor.close()
    
    if not result:
        raise HTTPException(status_code=404, detail="No measurements found")
    
    if result.get('datetime_utc'):
        result['datetime_utc'] = result['datetime_utc'].isoformat()
    if result.get('created_at'):
        result['created_at'] = result['created_at'].isoformat()
    
    return result


@app.get("/measurements/stats")
@limiter.limit("100/minute")
def get_stats(
    request: Request,
    conn=Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Get database statistics."""
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT city) as cities,
            COUNT(DISTINCT station_id) as stations,
            MIN(datetime_utc) as first_record,
            MAX(datetime_utc) as last_record,
            AVG(pm25) as avg_pm25,
            AVG(pm10) as avg_pm10,
            AVG(aqi) as avg_aqi
        FROM measurements
    """)
    result = cursor.fetchone()
    cursor.close()
    
    if result.get('first_record'):
        result['first_record'] = result['first_record'].isoformat()
    if result.get('last_record'):
        result['last_record'] = result['last_record'].isoformat()
    
    return result


@app.post("/measurements")
@limiter.limit("100/minute")
def add_measurement(
    request: Request,
    data: MeasurementInput,
    conn=Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Add a new measurement (requires API key)."""
    cursor = conn.cursor()
    
    # Use provided datetime or current UTC time
    dt = data.datetime_utc or datetime.utcnow()
    
    try:
        cursor.execute("""
            INSERT INTO measurements 
            (datetime_utc, city, lat, lon, hour_utc, minute_utc, 
             pm25, pm10, temperature, humidity, pressure, aqi, station_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            dt,
            data.city,
            data.lat,
            data.lon,
            dt.hour,
            dt.minute,
            data.pm25,
            data.pm10,
            data.temperature,
            data.humidity,
            data.pressure,
            data.aqi,
            data.station_id
        ))
        
        conn.commit()
        row_id = cursor.lastrowid
        cursor.close()
        
        return {
            "status": "ok",
            "id": row_id,
            "datetime_utc": dt.isoformat()
        }
        
    except MySQLError as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to insert: {e}")


@app.delete("/measurements/{measurement_id}")
@limiter.limit("100/minute")
def delete_measurement(
    request: Request,
    measurement_id: int,
    conn=Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """Delete a measurement by ID (requires API key)."""
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM measurements WHERE id = %s", (measurement_id,))
    conn.commit()
    
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Measurement not found")
    
    cursor.close()
    return {"status": "ok", "deleted_id": measurement_id}
