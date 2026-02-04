# ZenBangumi

Zen Bangumi - Automated anime management system

## Quick Start with Docker Compose

### Prerequisites

- Docker Engine 20.10+
- Docker Compose v2.0+

### Environment Setup

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env` and configure your downloader settings:

```env
DOWNLOADER_HOST=http://your-qbittorrent:8080
DOWNLOADER_USERNAME=admin
DOWNLOADER_PASSWORD=your-password
SECRET_KEY=your-secret-key-here
```

### Deployment

Start all services:

```bash
docker-compose up -d
```

Check service status:

```bash
docker-compose ps
```

View logs:

```bash
docker-compose logs -f
```

Stop services:

```bash
docker-compose down
```

### Access

- Frontend: http://localhost:7892
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Data Persistence

Application data is stored in:
- `./data` - Database and application data
- `./config` - Configuration files

These directories are automatically created and mounted as Docker volumes.

### Updating

Pull latest changes and rebuild:

```bash
git pull
docker-compose down
docker-compose up -d --build
```

### Troubleshooting

Check backend health:

```bash
curl http://localhost:8000/health
```

Check frontend health:

```bash
curl http://localhost:7892
```

View backend logs:

```bash
docker-compose logs -f backend
```

View frontend logs:

```bash
docker-compose logs -f frontend
```

## Development

### Backend Development

```bash
cd backend
uv sync
uv run uvicorn zen_bangumi.main:app --reload
```

### Frontend Development

```bash
cd frontend
bun install
bun run dev
```

## Architecture

- **Backend**: FastAPI + SQLAlchemy + APScheduler
- **Frontend**: React + TypeScript + Vite + TailwindCSS
- **Database**: SQLite (via aiosqlite)
- **Downloader**: qBittorrent API

## License

MIT
