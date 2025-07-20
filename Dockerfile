FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY jellypatrol.py .
COPY .env.example .

# Create non-root user for security
RUN groupadd -r jellypatrol && useradd --no-log-init -r -g jellypatrol jellypatrol
RUN chown -R jellypatrol:jellypatrol /app
USER jellypatrol

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python3 -c "import requests; print('Healthy')" || exit 1

# Run the application
CMD ["python3", "jellypatrol.py"]