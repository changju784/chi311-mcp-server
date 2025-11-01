# Use a Debian-based image with system libraries available
FROM python:3.11-slim

# Install system packages needed by Playwright + Chrome
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libxcomposite1 \
    libxrandr2 \
    libxdamage1 \
    libxfixes3 \
    libgbm1 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libx11-xcb1 \
    libdrm2 \
    fonts-liberation \
    libasound2 \
    libxss1 \
    libxshmfence1 \
    ca-certificates \
    wget \
    unzip \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy only requirements first for caching
COPY requirements.txt /app/requirements.txt

# Install Python deps
RUN pip install --upgrade pip
RUN pip install -r /app/requirements.txt

# Copy rest of the repo
COPY . /app

# Install Playwright browsers (with apt dependencies)
# Use the Playwright CLI to install browsers for Chromium/Firefox/WebKit
RUN python -m playwright install --with-deps

# Expose the port uvicorn will bind to
EXPOSE 8000

# Default environment variables
ENV PLAYWRIGHT_HEADLESS=true
ENV CHI311_DRY_RUN=true

# Start server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]