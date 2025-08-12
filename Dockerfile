FROM python:3.11-slim

# Install system dependencies including LibreOffice
RUN apt-get update && apt-get install -y \
    libreoffice-writer \
    libreoffice-core \
    libreoffice-common \
    fonts-dejavu \
    fonts-liberation \
    ghostscript \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-por \
    tesseract-ocr-eng \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p uploads sessions shared/templates shared/assets && \
    chown -R appuser:appuser /app

# Change to non-root user
USER appuser

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV LIBREOFFICE_PATH=/usr/bin/libreoffice

# Expose port
EXPOSE 8080

# Command that honors Render's PORT variable
CMD ["bash", "-c", "gunicorn app:app --bind 0.0.0.0:${PORT:-8080} --workers 4 --timeout 120"]