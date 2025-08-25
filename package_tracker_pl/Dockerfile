ARG BUILD_FROM=ghcr.io/home-assistant/{arch}-base:latest
FROM ${BUILD_FROM}

LABEL   io.hass.version="0.1.1"   io.hass.name="Advanced Package Tracker (PL)"   io.hass.description="Tracks DHL (PL) and InPost packages; web UI for adding numbers; MQTT discovery sensors."   io.hass.type="addon"   io.hass.arch="aarch64|amd64|armhf|armv7|i386"   maintainer="You <you@example.com>"

RUN apk add --no-cache python3 py3-pip bash

# App files
COPY app /app
WORKDIR /app

# Create venv and install deps inside it to avoid system pip (PEP 668)
RUN python3 -m venv /opt/venv && . /opt/venv/bin/activate && pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Runtime entry
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
