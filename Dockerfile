FROM python:3.11-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core curl ca-certificates gnupg libnss3 libdbus-1-3 libatk1.0-0 libgbm-dev libasound2 libxrandr2 libxkbcommon-dev libxfixes3 libxcomposite1 libxdamage1 libatk-bridge2.0-0 libpango-1.0-0 libcairo2 libcups2 \
 && mkdir -p /etc/apt/keyrings \
 && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
 && apt-get update && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*
COPY --from=denoland/deno:bin-2.9.6 /deno /usr/local/bin/deno
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY renderer/package.json renderer/package.json
RUN cd renderer && npm install --omit=dev && npx remotion browser ensure
COPY renderer/src renderer/src
COPY renderer/public renderer/public
COPY renderer/tsconfig.json renderer/tsconfig.json
COPY app ./app
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 DATA_DIR=/data REMOTION_DIR=/app/renderer RENDER_PUBLIC_DIR=/app/renderer/public/jobs
