FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Node.js for frontend build
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers and dependencies
# Note: install-deps may fail on some systems, so we install manually
RUN playwright install chromium || true
RUN playwright install-deps chromium || \
    (apt-get update && \
     apt-get install -y --no-install-recommends \
     fonts-liberation \
     fonts-unifont \
     libasound2 \
     libatk-bridge2.0-0 \
     libatk1.0-0 \
     libatspi2.0-0 \
     libcups2 \
     libdbus-1-3 \
     libdrm2 \
     libgbm1 \
     libgtk-3-0 \
     libnspr4 \
     libnss3 \
     libwayland-client0 \
     libxcomposite1 \
     libxdamage1 \
     libxfixes3 \
     libxkbcommon0 \
     libxrandr2 \
     xdg-utils \
     && rm -rf /var/lib/apt/lists/*) || true

# Build frontend
COPY frontend/package.json frontend/package-lock.json* ./frontend/
WORKDIR /app/frontend
RUN npm ci || npm install
COPY frontend/ .
RUN npm run build
WORKDIR /app

# Copy application code (exclude static/ which is built above)
# Copy only necessary files to avoid overwriting freshly built static files
COPY app/ ./app/
COPY main.py .
COPY requirements.txt .
COPY pytest.ini .
COPY search_recipes.json .
COPY docker-compose.yml .
COPY start.sh .

# Expose port
EXPOSE 8001

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

