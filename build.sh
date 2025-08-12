#!/bin/bash
# Render build script for doc-sync-service

echo "Starting build process for doc-sync-service..."

# Update package list
echo "Updating package list..."
apt-get update

# Install LibreOffice for PDF conversion (primary method)
echo "Installing LibreOffice..."
apt-get install -y libreoffice-writer libreoffice-calc libreoffice-common

# Install wkhtmltopdf for HTML-to-PDF conversion (secondary method)
echo "Installing wkhtmltopdf..."
apt-get install -y wkhtmltopdf

# Install pandoc for document conversion (tertiary method)
echo "Installing pandoc..."
apt-get install -y pandoc

# Install additional system dependencies
echo "Installing additional dependencies..."
apt-get install -y fonts-liberation fonts-dejavu-core

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Build process completed successfully!"
echo "Available PDF conversion methods:"
echo "- LibreOffice: $(which libreoffice || echo 'NOT FOUND')"
echo "- wkhtmltopdf: $(which wkhtmltopdf || echo 'NOT FOUND')"
echo "- pandoc: $(which pandoc || echo 'NOT FOUND')"