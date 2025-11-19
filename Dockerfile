FROM python:3.13-slim

WORKDIR /app

RUN apt-get update

# Install system dependencies
RUN apt-get install -y \
    fuse \
    libfuse-dev \
    build-essential \
    python3-dev \
    pkgconf \
    borgbackup \
    libssl-dev \
    liblz4-dev \
    libzstd-dev \
    libxxhash-dev \
    libacl1-dev \
    sqlite3

RUN apt-get clean

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY ./vend/borgapi /usr/local/lib/python3.13/site-packages/borgapi

# Copy application code
COPY ./app /app/site
VOLUME /app/site/store /app/site/log

# Run the application on port 9090
EXPOSE 9090
WORKDIR /app/site
CMD ["gunicorn", "-b", "0.0.0.0:9090", "app:app"]
