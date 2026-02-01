FROM researchdeezer/spleeter:3.8

# Set working directory
WORKDIR /app

# Install Flask
RUN pip install --no-cache-dir \
    flask==2.2.5 \
    flask-cors==4.0.0 \
    requests==2.31.0

# Copy application code
COPY spleeter_api.py .

# Create directories
RUN mkdir -p /app/uploads /app/outputs

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "spleeter_api.py"]
