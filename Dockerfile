FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY airly_collector.py .

# Create data directory
RUN mkdir -p /data

# Run the script
CMD ["python", "-u", "airly_collector.py"]
