# syntax=docker/dockerfile:1

# Build args
ARG VERSION=0.0.0

# Build stage: Build the webui
FROM node:20-alpine AS webui-builder

WORKDIR /webui

# Install pnpm
RUN npm install -g pnpm@9

# Copy package files first for better caching
COPY webui/package.json webui/pnpm-lock.yaml ./

# Install dependencies (will use correct platform binaries)
RUN pnpm install --frozen-lockfile

# Copy source files
COPY webui/ ./

# Build the application
RUN pnpm build

# Production stage
FROM alpine:3.18

ARG VERSION=0.0.0

ENV LANG="C.UTF-8" \
    TZ=Asia/Shanghai \
    PUID=1000 \
    PGID=1000 \
    UMASK=022

WORKDIR /app

# Install system dependencies
RUN set -ex && \
    apk add --no-cache \
        bash \
        busybox-suid \
        python3 \
        py3-aiohttp \
        py3-bcrypt \
        py3-pip \
        su-exec \
        shadow \
        tini \
        openssl \
        tzdata && \
    python3 -m pip install --no-cache-dir --upgrade pip

# Copy and install Python requirements
COPY backend/requirements.txt .
RUN set -ex && \
    sed -i '/bcrypt/d' requirements.txt && \
    pip install --no-cache-dir -r requirements.txt && \
    # Add user
    mkdir -p /home/ab && \
    addgroup -S ab -g 911 && \
    adduser -S ab -G ab -h /home/ab -s /sbin/nologin -u 911

# Copy backend source code
COPY --chmod=755 backend/src/. .

# Create version file for production mode (enables webui serving)
RUN echo "VERSION='${VERSION}'" > module/__version__.py

# Copy built webui from builder stage
COPY --from=webui-builder --chmod=755 /webui/dist ./dist

# Copy entrypoint script
COPY --chmod=755 entrypoint.sh /entrypoint.sh

# Create config and data directories
RUN mkdir -p /app/config /app/data

# Clean up
RUN rm -rf \
        /root/.cache \
        /tmp/*

ENTRYPOINT ["tini", "-g", "--", "/entrypoint.sh"]

EXPOSE 7892
VOLUME [ "/app/config" , "/app/data" ]
