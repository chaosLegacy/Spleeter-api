FROM python:3.9-slim

# Set environment variables for pip timeout handling
ENV PYTHONUNBUFFERED=1
ENV PIP_DEFAULT_TIMEOUT=100
ENV PIP_RETRIES=5

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Upgrade pip first
RUN pip install --no-cache-dir --upgrade pip

# Install TensorFlow separately (largest package, most likely to timeout)
# This allows Docker to cache this layer independently
RUN pip install --no-cache-dir \
    --default-timeout=100 \
    --retries 5 \
    tensorflow==2.9.3

# Install remaining dependencies
RUN pip install --no-cache-dir \
    spleeter==2.4.0 \
    flask==3.0.0 \
    flask-cors==4.0.0

# Copy application code
COPY spleeter_api.py .

# Create directories for models and temporary files
RUN mkdir -p /app/models /app/temp /app/outputs

# Pre-download Spleeter models (optional but recommended)
# Uncomment the models you want to pre-download to speed up first API call
# RUN python -c "from spleeter.separator import Separator; Separator('spleeter:2stems')"
# RUN python -c "from spleeter.separator import Separator; Separator('spleeter:4stems')"
# RUN python -c "from spleeter.separator import Separator; Separator('spleeter:5stems')"

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health')" || exit 1

# Run the application
CMD ["python", "spleeter_api.py"]
