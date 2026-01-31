# Slovo Tool Base Image
FROM python:3.11-slim

# Security: Create non-root user
RUN groupadd -r slovo && useradd -r -g slovo slovo

# Set working directory
WORKDIR /app

# Install dependencies first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Create data directory for persistent storage
RUN mkdir -p /data && chown slovo:slovo /data

# Security: Switch to non-root user
USER slovo

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Default entrypoint
ENTRYPOINT ["python", "main.py"]
