# Use Playwright's official image which includes browsers and necessary system libs
FROM mcr.microsoft.com/playwright/python:latest

WORKDIR /app

# Copy only requirements first to leverage layer cache
COPY requirements.txt /app/requirements.txt

# Install Python deps
RUN pip install --upgrade pip
RUN pip install -r /app/requirements.txt

# Copy repo
COPY . /app

# Environment - safe defaults
ENV PLAYWRIGHT_HEADLESS=true
ENV CHI311_DRY_RUN=true

# Expose application port
EXPOSE 8000

# Run using uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]