# Airly Data Collector

Collects air quality data from the Airly API and stores it in MariaDB. Includes a REST API for data ingestion and retrieval.

## Architecture

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  Airly API      │────▶│  Collector      │────▶│  MariaDB        │
└─────────────────┘      └─────────────────┘      └─────────────────┘
                                                           ▲
                                                           │
                                                  ┌────────┴────────┐
                                                  │    REST API     │
                                                  │  (read/write)   │
                                                  └─────────────────┘
```

## Components

| Component | Description |
|-----------|-------------|
| `airly_collector.py` | Fetches data from Airly API hourly |
| `api.py` | REST API for data ingestion and retrieval (FastAPI) |
| `db_setup.py` | Database management utility |

## Requirements

- Docker & Docker Compose

## Quick Start

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# View collector logs
docker logs -f airly-collector
```

## Services

### Production (API + Database only)
```bash
docker compose up -d mariadb airly-api
```

### With Collector (for testing/data collection)
```bash
docker compose up -d
```

### Database Tools
```bash
# Check database status
docker compose run --rm db-setup status

# Run initial setup
docker compose run --rm db-setup setup

# Migrate CSV data
docker compose run --rm db-setup migrate
```

## REST API

The API runs on `http://localhost:8000`

### Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | No | Health check |
| `/measurements` | GET | No | Get recent measurements |
| `/measurements/latest` | GET | No | Get most recent measurement |
| `/measurements/stats` | GET | No | Get database statistics |
| `/measurements` | POST | API Key | Add new measurement |
| `/measurements/{id}` | DELETE | API Key | Delete measurement |
| `/docs` | GET | No | OpenAPI documentation |

### Reading Data

```bash
# Health check
curl http://localhost:8000/health

# Get latest measurement
curl http://localhost:8000/measurements/latest

# Get statistics
curl http://localhost:8000/measurements/stats

# Get last 10 measurements
curl "http://localhost:8000/measurements?limit=10"

# Filter by city
curl "http://localhost:8000/measurements?city=Gdansk&limit=5"
```

### Writing Data

```bash
# Add a new measurement (requires API key)
curl -X POST http://localhost:8000/measurements \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{
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
  }'

# Delete a measurement
curl -X DELETE http://localhost:8000/measurements/123 \
  -H "X-API-Key: your_api_key"
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AIRLY_API_KEY` | - | Airly API key (required for collector) |
| `INSTALLATION_ID` | `3387` | Airly station ID |
| `LATITUDE` | `54.3520` | Station latitude |
| `LONGITUDE` | `18.6466` | Station longitude |
| `CITY_NAME` | `Gdansk` | City name |
| `INTERVAL_SECONDS` | `3600` | Collection interval |
| `ENABLE_DATABASE` | `true` | Enable MariaDB storage |
| `ENABLE_CSV` | `false` | Enable CSV backup |
| `MARIADB_PASSWORD` | `airly_pass` | Database password |
| `API_KEY` | - | API key for write operations |

## Database Schema

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT | Auto-increment primary key |
| `datetime_utc` | DATETIME | Measurement timestamp |
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
| `station_id` | INT | Airly station ID |
| `created_at` | TIMESTAMP | Record creation time |

## Database Access

```bash
# From host
mariadb -h 127.0.0.1 -P 3306 -u airly -p airly

# Via Docker
docker exec -it airly-mariadb mariadb -u airly -p airly
```

## Backup & Restore

```bash
# Backup
docker exec airly-mariadb mariadb-dump -u airly -p airly > backup.sql

# Restore
docker exec -i airly-mariadb mariadb -u airly -p airly < backup.sql
```

## Development

### Run collector once (testing)
```bash
docker compose run --rm airly-collector python airly_collector.py --once
```

### View API docs
Open http://localhost:8000/docs in your browser.

## License

See [LICENSE](LICENSE) file.
