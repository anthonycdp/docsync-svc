#!/bin/bash
# Render build script for doc-sync-service

echo "Starting build process for doc-sync-service..."

# Update package list
echo "Updating package list..."
apt-get update

# Install LibreOffice for PDF conversion
echo "Installing LibreOffice..."
apt-get install -y libreoffice-writer libreoffice-calc libreoffice-common

# Install additional system dependencies
echo "Installing additional dependencies..."
apt-get install -y fonts-liberation fonts-dejavu-core

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Build process completed successfully!"
echo "PDF conversion method:"
echo "- LibreOffice: $(which libreoffice || echo 'NOT FOUND')"