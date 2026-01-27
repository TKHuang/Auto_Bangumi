# PikPak + Rclone Setup Guide

This guide explains how to use AutoBangumi with PikPak cloud storage and rclone for local file access.

## Overview

When using PikPak as your downloader:
- **AutoBangumi** handles RSS feeds, downloads (via PikPak API), and file renaming (via PikPak API)
- **Rclone** mounts your PikPak storage locally so media servers (Jellyfin/Plex) can access the files

```
PikPak Cloud (AB/)
    ↑ API (download, rename)
    │
AutoBangumi ←──── rclone mount ────→ /mnt/pikpak (local)
                                          ↓
                                    Jellyfin/Plex
```

## Quick Start

### 1. Configure AutoBangumi for PikPak

In your `config/config.json`:

```json
{
  "downloader": {
    "type": "pikpak",
    "username": "your-pikpak-email",
    "password": "your-pikpak-password",
    "path": "AB"
  }
}
```

### 2. Adjust Docker Compose Paths

Edit `docker-compose.pikpak.yml` to set your local paths:

```yaml
volumes:
  # Change these to your preferred locations:
  - /path/to/your/media:/mnt/pikpak:shared      # Where you want to see files
  - /path/to/cache:/cache                        # Cache storage (SSD recommended)
```

### 3. Start Services

```bash
docker-compose -f docker-compose.pikpak.yml up -d
```

### 4. Point Media Server to Mount

Configure Jellyfin/Plex to use the mount path (e.g., `/path/to/your/media`).

## Configuration Options

### Cache Settings

Adjust in `docker-compose.pikpak.yml`:

| Variable | Default | Description |
|----------|---------|-------------|
| `RCLONE_CACHE_MAX_SIZE` | `10G` | Maximum cache size on disk |
| `RCLONE_CACHE_MAX_AGE` | `1h` | How long cached files are kept |

### Troubleshooting

**Mount not working?**

If you see permission errors, try using privileged mode. Replace:

```yaml
cap_add:
  - SYS_ADMIN
devices:
  - /dev/fuse
security_opt:
  - apparmor:unconfined
```

With:

```yaml
privileged: true
```

**Files not appearing?**

1. Check rclone logs: `docker logs ab-rclone`
2. Verify PikPak credentials in config.json
3. Ensure `downloader.path` matches your PikPak folder

## Development Setup

For local development:

```bash
docker-compose -f docker-compose.pikpak.dev.yml up
```

This reads from `config_dev.json` and mounts to `./dev-config/pikpak/`.

**Note:** AutoBangumi must authenticate with PikPak first to generate OAuth tokens. The rclone sidecar reuses these tokens from `pikpak_token.json`.

### macOS Limitation

On macOS, FUSE mounts inside Docker containers don't propagate to the host filesystem due to Docker Desktop's Linux VM architecture. The mount works **inside the container** but isn't visible on macOS.

**Workarounds:**

1. Access files through the container: `docker exec ab-rclone-dev ls /mnt/pikpak/`
2. Run rclone natively on macOS (outside Docker)
3. On Linux hosts, the mount propagates correctly with `:shared` volume option
