#!/bin/bash
set -e

CERT_DIR="./certs/mysql"
mkdir -p "$CERT_DIR"
cd "$CERT_DIR"

# Valid for 10 years
DAYS=3650

echo "=== Generating CA ==="
openssl genrsa 4096 > ca-key.pem
openssl req -new -x509 -nodes -days $DAYS \
  -key ca-key.pem \
  -out ca.pem \
  -subj "/CN=Airly-MySQL-CA/O=Airly/C=PL"

echo "=== Generating Server Certificate ==="
openssl req -newkey rsa:4096 -nodes \
  -keyout server-key.pem \
  -out server-req.pem \
  -subj "/CN=mariadb/O=Airly/C=PL"

openssl x509 -req -days $DAYS \
  -in server-req.pem \
  -CA ca.pem -CAkey ca-key.pem -CAcreateserial \
  -out server-cert.pem

echo "=== Generating Client Certificate ==="
openssl req -newkey rsa:4096 -nodes \
  -keyout client-key.pem \
  -out client-req.pem \
  -subj "/CN=airly-client/O=Airly/C=PL"

openssl x509 -req -days $DAYS \
  -in client-req.pem \
  -CA ca.pem -CAkey ca-key.pem -CAcreateserial \
  -out client-cert.pem

# Cleanup CSR files
rm -f server-req.pem client-req.pem ca.srl

# Set permissions
chmod 600 *-key.pem
chmod 644 *.pem

echo "=== Certificates generated in $CERT_DIR ==="
ls -la
