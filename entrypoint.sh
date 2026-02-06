#!/bin/bash
# shellcheck shell=bash

umask ${UMASK}

groupmod -o -g "${PGID}" ab
usermod -o -u "${PUID}" ab

chown ab:ab -R /app /home/ab

exec su-exec "${PUID}:${PGID}" python3 main.py