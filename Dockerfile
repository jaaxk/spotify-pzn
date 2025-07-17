# Base image
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    # Required for psycopg2
    libpq-dev \
    python3-dev \
    gcc \
    # Required for Qdrant client
    libssl-dev \
    libffi-dev \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user and switch to it
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN mkdir -p /app && chown -R appuser:appuser /app

# Set the working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY --chown=appuser:appuser requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the rest of the application
COPY --chown=appuser:appuser . .

# Ensure .env is available in the container
COPY --chown=appuser:appuser .env .

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=run.py
ENV FLASK_DEBUG=1

# Set Hugging Face cache directory
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=${HF_HOME}/transformers
ENV HUGGINGFACE_HUB_CACHE=${HF_HOME}/hub

# Create cache directories
RUN mkdir -p ${HF_HOME} ${TRANSFORMERS_CACHE} ${HUGGINGFACE_HUB_CACHE} && \
    chown -R appuser:appuser ${HF_HOME}
ENV PORT=5000
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create necessary directories with proper permissions
RUN mkdir -p /app/.cache && \
    mkdir -p /app/embed_lib_pipe/spotify/data && \
    chown -R appuser:appuser /app/.cache /app/embed_lib_pipe 

# Switch to non-root user
USER appuser

# Expose the port the app runs on
EXPOSE 5000

# Command to run the application
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
#CMD ["python", "run.py"]