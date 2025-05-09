# Use Python 3.10 slim image as base
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and data
COPY . .

# Run ETL during build to generate the SQLite database
RUN python run_etl.py 2024

# Expose port 8080 for the Flask service
EXPOSE 8080
ENV PORT 8080

# Start Gunicorn (production WSGI server)
CMD ["gunicorn", "-b", "0.0.0.0:${PORT}", "app:app"]
