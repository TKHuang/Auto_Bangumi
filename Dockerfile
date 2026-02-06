# syntax=docker/dockerfile:1

ARG VERSION=0.0.0

# Build stage: Build the webui
FROM node:20-alpine AS webui-builder

WORKDIR /webui

RUN npm install -g pnpm@9

COPY webui/package.json webui/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY webui/ ./
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

RUN set -ex && \
    apk add --no-cache \
        bash \
        busybox-suid \
        python3 \
        py3-bcrypt \
        py3-pip \
        su-exec \
        shadow \
        tini \
        openssl \
        tzdata

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY backend/pyproject.toml /tmp/pyproject.toml
RUN set -ex && \
    uv pip install --system --no-cache -r /tmp/pyproject.toml && \
    mkdir -p /home/ab && \
    addgroup -S ab -g 911 && \
    adduser -S ab -G ab -h /home/ab -s /sbin/nologin -u 911

COPY --chmod=755 backend/src/. .

RUN echo "VERSION='${VERSION}'" > module/__version__.py

COPY --from=webui-builder --chmod=755 /webui/dist ./dist

COPY --chmod=755 entrypoint.sh /entrypoint.sh

RUN mkdir -p /app/config /app/data

RUN rm -rf \
        /root/.cache \
        /tmp/*

ENTRYPOINT ["tini", "-g", "--", "/entrypoint.sh"]

EXPOSE 7892
VOLUME [ "/app/config" , "/app/data" ]
