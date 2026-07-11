# FourCast — Track 2 submission image (and demo UI via CMD override)
FROM python:3.12-slim

# Debian ffmpeg: full protocol support (https seek on remote clips)
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
ENV FFMPEG_BIN=ffmpeg

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent/ agent/
COPY app/ app/

# Track 2 injects no credentials — the image carries its own revocable key
# (base64; set at build: --build-arg FW_KEY_B64=...)
ARG FW_KEY_B64=""
ENV T2_FW_KEY_B64=$FW_KEY_B64

# Harness mode (default): /input/tasks.json -> /output/results.json
CMD ["python", "-m", "agent"]

# Demo UI mode:
#   docker run -p 8000:8000 <image> uvicorn app.main:app --host 0.0.0.0 --port 8000
