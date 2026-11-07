ARG PYTHON_BASE=python:3.11.18-bookworm@sha256:726d304906fa5eb468e5531e366548d1903286352f5adb54ef508ac01fbd80c6
FROM ${PYTHON_BASE}
ARG DEBIAN_SNAPSHOT=20261106T000000Z
ARG NODE_VERSION=22.23.4
COPY build/node-SHASUMS256.txt /tmp/node-SHASUMS256.txt
RUN sed -i \
    -e "s|http://deb.debian.org/debian-security|https://snapshot.debian.org/archive/debian-security/${DEBIAN_SNAPSHOT}/|g" \
    -e "s|http://deb.debian.org/debian|https://snapshot.debian.org/archive/debian/${DEBIAN_SNAPSHOT}/|g" \
    /etc/apt/sources.list.d/debian.sources \
 && printf 'Acquire::Check-Valid-Until "false";\n' > /etc/apt/apt.conf.d/99snapshot \
 && apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core curl ca-certificates libnss3 libdbus-1-3 libatk1.0-0 libgbm-dev libasound2 libxrandr2 libxkbcommon-dev libxfixes3 libxcomposite1 libxdamage1 libatk-bridge2.0-0 libpango-1.0-0 libcairo2 libcups2 \
 && rm -rf /var/lib/apt/lists/*
RUN case "$(dpkg --print-architecture)" in amd64) node_arch=x64;; arm64) node_arch=arm64;; *) exit 1;; esac \
 && archive="node-v${NODE_VERSION}-linux-${node_arch}.tar.xz" \
 && cd /tmp && curl --fail --show-error --location --retry 3 --output "$archive" "https://nodejs.org/dist/v${NODE_VERSION}/$archive" \
 && grep " $archive$" node-SHASUMS256.txt | sha256sum --check - \
 && tar -xJf "$archive" -C /usr/local --strip-components=1 \
 && rm "$archive" /tmp/node-SHASUMS256.txt
COPY --from=denoland/deno:bin-2.9.6@sha256:4cf0029b9aeeeed5efcbb71828737f0d7c8c8a20072df960e51a5679ef0d21ba /deno /usr/local/bin/deno
WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && pip check
COPY renderer/package.json renderer/package-lock.json renderer/
RUN cd renderer && npm ci --omit=dev && npx remotion browser ensure
COPY renderer/src renderer/src
COPY renderer/public renderer/public
COPY renderer/tsconfig.json renderer/tsconfig.json
COPY app ./app
ARG CONTENT_FACTORY_GIT_HEAD=UNKNOWN
ARG CONTENT_FACTORY_SOURCE_SHA256=UNKNOWN
ENV CONTENT_FACTORY_GIT_HEAD=${CONTENT_FACTORY_GIT_HEAD} CONTENT_FACTORY_SOURCE_SHA256=${CONTENT_FACTORY_SOURCE_SHA256}
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 DATA_DIR=/data REMOTION_DIR=/app/renderer RENDER_PUBLIC_DIR=/app/renderer/public/jobs
