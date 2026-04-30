# Transcription & Segmentation App

A production-scale full-stack application for audio transcription and segmentation, featuring real-time job monitoring, MinIO integration, and a beautiful React dashboard.

## Features

- **Direct Upload**: Drag-and-drop audio files for immediate transcription
- **MinIO Integration**: Process files stored in MinIO object storage
- **Real-time Dashboard**: Monitor all jobs live via WebSocket
- **CPU-Optimized**: Runs efficiently on 4CPU/16GB hardware (no GPU required)
- **Multiple Output Formats**: TXT, SRT, VTT, JSON exports
- **Segmentation**: Organize transcriptions by silence, sentences, or time
- **Scalable Architecture**: Celery workers for async processing

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React)                        │
│  ┌───────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │  Upload   │  │ Job Dashboard│  │ Result Viewers     │   │
│  │  Zone     │  │ (Real-time)  │  │ (Transcription/    │   │
│  │           │  │              │  │  Segmentation)     │   │
│  └─────┬─────┘  └──────┬───────┘  └──────────┬─────────┘   │
└────────┼───────────────┼──────────────────────┼─────────────┘
         │               │                      │
         │    WebSocket  │    REST API          │
         └───────────────┼──────────────────────┘
                         │
┌─────────────────────────────────────────────────────────────┐
│                  Backend (FastAPI)                           │
│  ┌──────────┐  ┌───────────┐  ┌────────────────────────┐   │
│  │   API    │  │ WebSocket │  │   Services             │   │
│  │  Routes  │  │  Manager  │  │   - Transcription      │   │
│  │          │  │           │  │   - Segmentation       │   │
│  │          │  │           │  │   - MinIO              │   │
│  └────┬─────┘  └─────┬─────┘  └───────────┬────────────┘   │
└───────┼──────────────┼─────────────────────┼────────────────┘
        │              │                     │
        │              │              Celery Tasks
        │              │              ┌──────┴──────┐
        │              │              │Transcription│
        │              │              │  Worker     │
        │              │              └─────────────┘
        │              │              ┌─────────────┐
        │              │              │Segmentation │
        │              │              │  Worker     │
        │              │              └─────────────┘
        │              │                     │
┌───────┴──────┐  ┌───┴────┐         ┌─────┴─────┐
│  PostgreSQL  │  │ Redis  │         │   MinIO   │
│  (Database)  │  │(Broker)│         │  (Storage)│
└──────────────┘  └────────┘         └───────────┘
```

## Quick Start

```bash
cd transcription-app

# Copy environment file
cp .env.example .env

# Start all services
docker-compose up -d

# Run database migrations
docker-compose exec backend alembic upgrade head
```

Access the application:
- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **MinIO Console**: http://localhost:9001

## Prerequisites

- Docker & Docker Compose
- 4+ CPU cores
- 16GB+ RAM
- 10GB+ disk space

## Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | React Dashboard |
| API | http://localhost:8000 | FastAPI Backend |
| API Docs | http://localhost:8000/api/docs | Swagger UI |
| ReDoc | http://localhost:8000/api/redoc | ReDoc API Docs |
| MinIO Console | http://localhost:9001 | Object Storage UI |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/upload/direct | Upload file for processing |
| POST | /api/v1/upload/minio | Submit MinIO file |
| POST | /api/v1/upload/batch | Batch submit MinIO files |
| GET | /api/v1/jobs | List all jobs |
| GET | /api/v1/jobs/:id | Get job details |
| DELETE | /api/v1/jobs/:id | Cancel/delete job |
| POST | /api/v1/jobs/:id/retry | Retry failed job |
| GET | /api/v1/jobs/stats | Job statistics |
| GET | /api/v1/transcription/:id | Get transcription |
| GET | /api/v1/transcription/:id/download | Download transcription |
| GET | /api/v1/segmentation/:id | Get segmentation |
| GET | /api/v1/segmentation/:id/export | Export segments |
| WS | /ws | WebSocket for real-time updates |

## Development

```bash
# Start backend services only
docker-compose up -d postgres redis minio backend

# Frontend dev server
cd frontend && npm install && npm run dev

# View Celery logs
docker-compose logs -f celery-transcription
docker-compose logs -f celery-segmentation

# Restart a service
docker-compose restart backend
```

## Production Deployment

```bash
# Build and start
docker-compose up -d --build

# Scale workers if needed
docker-compose up -d --scale celery-transcription=2
```

## Resource Allocation (4CPU/16GB)

| Service | CPU | Memory |
|---------|-----|--------|
| PostgreSQL | - | 512MB |
| Redis | - | 512MB |
| MinIO | - | 1GB |
| Backend API | 2.0 | 4GB |
| Celery Transcription | 2.0 | 4GB |
| Celery Segmentation | 1.0 | 1GB |
| Frontend | - | 256MB |
| **Buffer** | - | **~4.75GB** |

## Troubleshooting

- Check service health: `docker-compose ps`
- View logs: `docker-compose logs -f <service>`
- Restart a service: `docker-compose restart <service>`
- Reset database: `docker-compose down -v && docker-compose up -d`
- Rebuild backend: `docker-compose build backend && docker-compose up -d backend`

## Technology Stack

- **Backend**: Python 3.11, FastAPI, SQLAlchemy (async), Celery
- **Frontend**: React 18, Vite, TailwindCSS, React Query, Zustand
- **Database**: PostgreSQL 16
- **Cache/Broker**: Redis 7
- **Storage**: MinIO
- **ML**: faster-whisper (CTranslate2, int8 quantized)
- **Audio**: FFmpeg

## License

MIT
