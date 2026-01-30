# Air Quality Data Service

A distributed air quality data collection platform. This project provides a **centralized server** with a REST API and database where multiple data collectors can submit air quality measurements.

## Project Overview

This was developed as a university assignment for distributed systems. The architecture separates concerns:

- **Server (this repository)**: Provides the REST API and MariaDB database - the fixed, shared infrastructure
- **Collectors (various)**: Students implement their own data collection programs (Python, Node-RED, etc.) that send measurements to the central server

┌─────────────────┐      
│  Collector A    │──────┐
│  (Python)       │      │
└─────────────────┘      │
                         │       ┌─────────────────┐       ┌─────────────────┐
┌─────────────────┐      ├─────▶│   REST API      │─────▶│   MariaDB       │
│  Collector B    │──────┤       │   (FastAPI)     │       │   Database      │
│  (Node-RED)     │      │       └─────────────────┘       └─────────────────┘
└─────────────────┘      │               │
                         │               ▼
┌─────────────────┐      │       ┌─────────────────┐
│  Collector C    │──────┘       │   Swagger UI    │
│  (Custom)       │              │   /docs         │
└─────────────────┘              └─────────────────┘
```

## Server Components

| Component | Description |
|-----------|-------------|
| `api.py` | REST API for data ingestion and retrieval (FastAPI) |
| `db_setup.py` | Database initialization and management |
| MariaDB | Persistent storage with SSL/TLS encryption |
| HAProxy | TLS termination and load balancing (production) |

## Requirements

- Docker & Docker Compose

## Quick Start (Server Deployment)

```bash
# Start the server (API + Database)
docker compose up -d mariadb airly-api

# Check status
docker compose ps

# View API logs
docker logs -f airly-api
```

## REST API

### Production Endpoint

```
https://airly1.veerai.tech
```

### API Documentation

Interactive Swagger UI: https://airly1.veerai.tech/docs

### Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | No | Health check |
| `/measurements` | GET | API Key | Get recent measurements |
| `/measurements/latest` | GET | API Key | Get most recent measurement |
| `/measurements/stats` | GET | API Key | Get database statistics |
| `/measurements` | POST | API Key | **Submit new measurement** |
| `/measurements/{id}` | DELETE | API Key | Delete measurement |

### Authentication

All endpoints (except `/health`) require an API key passed in the header:

```
X-API-Key: your_api_key_here
```

### Rate Limiting

- 100 requests per minute per IP address

---

## Submitting Data (For Collectors)

### Required Headers

```http
Content-Type: application/json
X-API-Key: your_api_key
```

### Request Body Schema

```json
{
  "city": "Gdansk",
  "lat": 54.3520,
  "lon": 18.6466,
  "pm25": 15.5,
  "pm10": 22.3,
  "temperature": 18.5,
  "humidity": 65.0,
  "pressure": 1013.25,
  "aqi": 45.0,
  "station_id": 3387
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `city` | string | No | City name (default: "Gdansk") |
| `lat` | float | No | Latitude |
| `lon` | float | No | Longitude |
| `pm25` | float | No | PM2.5 concentration (μg/m³) |
| `pm10` | float | No | PM10 concentration (μg/m³) |
| `temperature` | float | No | Temperature (°C) |
| `humidity` | float | No | Relative humidity (%) |
| `pressure` | float | No | Atmospheric pressure (hPa) |
| `aqi` | float | No | Air Quality Index |
| `station_id` | int | No | Unique identifier for your station |

### Example: Submit a Measurement

```bash
curl -X POST https://airly1.veerai.tech/measurements \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "city": "Gdansk",
    "lat": 54.3520,
    "lon": 18.6466,
    "pm25": 15.5,
    "pm10": 22.3,
    "temperature": 5.2,
    "humidity": 78.0,
    "pressure": 1015.0,
    "aqi": 38.0,
    "station_id": 3387
  }'
```

### Response

```json
{
  "status": "ok",
  "id": 231,
  "datetime_utc": "2026-01-30T15:30:00.000000"
}
```

---

## Reading Data

### Get Statistics

```bash
curl -H "X-API-Key: your_api_key" \
  https://airly1.veerai.tech/measurements/stats
```

Response:
```json
{
  "total_records": 500,
  "cities": 2,
  "stations": 5,
  "first_record": "2026-01-08T20:27:49",
  "last_record": "2026-01-30T15:30:00",
  "avg_pm25": 23.97,
  "avg_pm10": 33.16,
  "avg_aqi": 36.48
}
```

### Get Recent Measurements

```bash
# Get last 10 measurements
curl -H "X-API-Key: your_api_key" \
  "https://airly1.veerai.tech/measurements?limit=10"

# Filter by station
curl -H "X-API-Key: your_api_key" \
  "https://airly1.veerai.tech/measurements?station_id=3387&limit=5"

# Filter by city
curl -H "X-API-Key: your_api_key" \
  "https://airly1.veerai.tech/measurements?city=Gdansk&limit=5"
```

---

## Database Schema

The `measurements` table stores all collected data:

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT | Auto-increment primary key |
| `datetime_utc` | DATETIME | Measurement timestamp (UTC) |
| `city` | VARCHAR(100) | City name |
| `lat` | DECIMAL(10,6) | Latitude |
| `lon` | DECIMAL(10,6) | Longitude |
| `hour_utc` | TINYINT | Hour (0-23) |
| `minute_utc` | TINYINT | Minute (0-59) |
| `pm25` | DECIMAL(10,2) | PM2.5 μg/m³ |
| `pm10` | DECIMAL(10,2) | PM10 μg/m³ |
| `temperature` | DECIMAL(6,2) | Temperature °C |
| `humidity` | DECIMAL(6,2) | Humidity % |
| `pressure` | DECIMAL(8,2) | Pressure hPa |
| `aqi` | DECIMAL(6,2) | Air Quality Index |
| `station_id` | INT | Station identifier |
| `created_at` | TIMESTAMP | Record creation time |

---

## Server Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `mariadb` | Database host |
| `DB_PORT` | `3306` | Database port |
| `DB_NAME` | `airly` | Database name |
| `DB_USER` | `airly` | Database user |
| `DB_PASSWORD` | - | Database password |
| `API_KEY` | - | API key for authentication |

### SSL/TLS

- Database connections use SSL certificates
- Production API uses HTTPS via HAProxy

---

## Infrastructure (Production)

```
┌──────────────────┐       ┌──────────────────┐      ┌──────────────────┐
│   Internet       │─────▶│   HAProxy        │─────▶│   FastAPI        │
│   Clients        │ TLS   │   (TLS term.)    │      │   (port 8000)    │
└──────────────────┘       └──────────────────┘      └──────────────────┘
                                                            │
                                                            ▼ SSL
                                                    ┌──────────────────┐
                                                    │   MariaDB        │
                                                    │   (port 3306)    │
                                                    └──────────────────┘
```

---

## Reference Collector: Python (`airly_collector.py`)

This repository includes a reference Python collector that fetches data from the Airly API.

### Features

- Fetches air quality data from Airly API hourly
- Stores measurements in MariaDB database
- Optional CSV backup
- Optional forwarding to HSBI Smart Data API
- SSL/TLS encrypted database connections

### Collector Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AIRLY_API_KEY` | - | Airly API key (required) |
| `INSTALLATION_ID` | `3387` | Airly station ID to monitor |
| `LATITUDE` | `54.3520` | Station latitude |
| `LONGITUDE` | `18.6466` | Station longitude |
| `CITY_NAME` | `Gdansk` | City name |
| `INTERVAL_SECONDS` | `3600` | Collection interval (seconds) |
| `ENABLE_DATABASE` | `true` | Enable MariaDB storage |
| `ENABLE_CSV` | `false` | Enable CSV backup |
| `ENABLE_HSBI_API` | `false` | Enable HSBI API forwarding |

### Running the Collector

```bash
# Via Docker - continuous (every hour)
docker compose up -d airly-collector

# Via Docker - single collection (testing)
docker compose run --rm airly-collector python airly_collector.py --once

# Via Python directly
source .venv/bin/activate
pip install -r requirements.txt
python airly_collector.py --once  # Single run
python airly_collector.py         # Continuous
```

### View Collector Logs

```bash
docker logs -f airly-collector
```

---

## Reference Collector: Node-RED

A Node-RED flow is also provided as an alternative visual programming approach.

1. Import `flows.json` into Node-RED
2. Configure the API key and station settings
3. Deploy the flow

The flow runs on a 60-minute interval and sends data to the REST API.

---

## Custom Collectors

Students can use any technology to build collectors, as long as they:

1. Fetch air quality data from a source (Airly API, sensors, etc.)
2. Format the data according to the API schema
3. POST to the REST API with proper authentication

---

## Database Access (Admin)

```bash
# Via Docker
docker exec -it airly-mariadb mariadb -u airly -p airly

# Backup
docker exec airly-mariadb mariadb-dump -u airly -p airly > backup.sql

# Restore
docker exec -i airly-mariadb mariadb -u airly -p airly < backup.sql
```

---

## License

See [LICENSE](LICENSE) file.
