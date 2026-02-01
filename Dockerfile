FROM python:3.8-slim

# Set environment variables for pip timeout handling
ENV PYTHONUNBUFFERED=1
ENV PIP_DEFAULT_TIMEOUT=100
ENV PIP_RETRIES=5
ENV TF_CPP_MIN_LOG_LEVEL=2

# Install system dependencies including build tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libsndfile1-dev \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install numpy first (specific version for compatibility)
RUN pip install --no-cache-dir numpy==1.23.5

# Install TensorFlow (compatible version for Spleeter 2.4.0)
RUN pip install --no-cache-dir tensorflow==2.10.1

# Install Spleeter with its dependencies
RUN pip install --no-cache-dir spleeter==2.4.0

# Install Flask separately to avoid conflicts
RUN pip install --no-cache-dir \
    flask==2.2.5 \
    flask-cors==4.0.0 \
    requests==2.31.0

# Copy application code
COPY spleeter_api.py .

# Create directories for uploads and outputs
RUN mkdir -p /app/uploads /app/outputs

# Pre-download the default model (optional - speeds up first request)
# RUN python -c "from spleeter.separator import Separator; Separator('spleeter:2stems').separate([0]*22050)"

# Expose port
EXPOSE 5000

# Health check (simplified - no requests dependency issue)
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run the application
CMD ["python", "spleeter_api.py"]
