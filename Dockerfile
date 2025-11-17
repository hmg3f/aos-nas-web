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
    libacl1-dev

RUN apt-get clean

COPY ./app /app/site

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY ./vend/borgapi /usr/local/lib/python3.13/site-packages/borgapi

# Run the application on port 8000
EXPOSE 8000
WORKDIR /app/site
CMD ["gunicorn", "-b", "0.0.0.0:8000", "app:app"]
