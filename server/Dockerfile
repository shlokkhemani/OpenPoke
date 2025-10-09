# OpenPoke Backend Dockerfile
# Python 3.10 FastAPI server with multi-agent orchestration

FROM python:3.10-slim

LABEL maintainer="OpenPoke Team"
LABEL description="OpenPoke FastAPI Backend Server"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 openpoke && \
    mkdir -p /app/server/data && \
    chown -R openpoke:openpoke /app

# Copy requirements and install Python dependencies
COPY server/requirements.txt ./server/
RUN pip install --no-cache-dir -r server/requirements.txt

# Copy server code
COPY server/ ./server/

# Set ownership
RUN chown -R openpoke:openpoke /app

USER openpoke

# Set Python path
ENV PYTHONPATH=/app

# Expose backend port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/api/v1/health').read()" || exit 1

# Run the FastAPI server
CMD ["python", "-m", "server.server"]

