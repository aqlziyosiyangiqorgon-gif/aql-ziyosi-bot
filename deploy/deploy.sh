#!/usr/bin/env bash
set -e

echo "=== AQL ZIYOSI Bot Deployment ==="

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker 
fi

# Create directories
mkdir -p data logs

# Build and start container
echo "Building and starting container..."
docker compose down || true
docker compose up -d --build

echo "=== Deployment successful! ==="
docker compose logs -f
