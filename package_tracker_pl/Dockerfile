ARG BUILD_FROM=ghcr.io/hassio-addons/base:14.2.4
FROM ${BUILD_FROM}

LABEL   io.hass.version="0.1.0"   io.hass.name="Advanced Package Tracker (PL)"   io.hass.description="Tracks DHL (PL) and InPost packages; web UI for adding numbers; MQTT discovery sensors."   io.hass.type="addon"   io.hass.arch="aarch64|amd64|armhf|armv7|i386"   maintainer="You <you@example.com>"

RUN apk add --no-cache python3 py3-pip bash &&     python3 -m pip install --no-cache-dir --upgrade pip

COPY app /app
WORKDIR /app

RUN pip3 install --no-cache-dir -r requirements.txt

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
