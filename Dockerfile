FROM python:3.12-slim

# Install LibreOffice
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libreoffice \
        libreoffice-writer \
        libreoffice-impress \
        fonts-liberation \
        fonts-dejavu \
        fonts-noto \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

# Create directories for uploads and PDFs
RUN mkdir -p uploads pdfs /tmp/libreoffice_profile

# Set HOME to writable location for LibreOffice
ENV HOME=/tmp

# Expose port
EXPOSE 10000

# Start the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
