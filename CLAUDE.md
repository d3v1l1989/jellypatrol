# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

JellyPatrol is a configurable Python application that monitors Jellyfin/Emby media servers for transcode sessions and automatically terminates them based on flexible policies. It supports Docker deployment with GitHub Container Registry publishing and environment-based configuration.

## Commands

### Running the Application

**With Docker (Recommended)**:
```bash
# Using Docker Compose
docker-compose up -d

# Using Docker CLI
docker run -d --env-file .env ghcr.io/d3v1l1989/jellypatrol:latest
```

**Direct Python**:
```bash
# Install dependencies
pip install -r requirements.txt

# Run with environment file
python3 jellypatrol.py
```

### Building and Testing
```bash
# Build Docker image locally
docker build -t jellypatrol:local .

# Test configuration (dry-run mode)
# Set KILL_STREAMS=false in .env file
```

## Architecture

### Environment-Based Configuration
All configuration is loaded from environment variables using python-dotenv:
- `.env.example`: Template with all available options
- `load_servers_from_env()`: Dynamically loads server configurations (SERVER1_*, SERVER2_*, etc.)
- Flexible resolution policies: 4K, 1080P, or ALL video transcodes
- Optional audio transcode monitoring

### Core Components

**Configuration Loading**:
- Environment variable loading with fallback defaults
- Dynamic server discovery (supports up to 20 servers)
- Resolution policy system with configurable thresholds
- Separate audio and video transcode indicator lists

**Session Analysis Functions**:
- `check_video_transcode()`: Analyzes video sessions against resolution policy
- `check_audio_transcode()`: Analyzes audio sessions when enabled
- `check_and_kill_transcodes_for_server()`: Main processing function (renamed from 4K-specific)

**API Communication**:
- `get_active_sessions()`: Fetches current sessions from server
- `send_message_to_session()`: Sends warning message to user
- `terminate_session()`: Stops playback after sending message

### Key Logic Flow

1. Load configuration from environment variables
2. For each enabled server, fetch active sessions
3. Filter for transcoding sessions (video and optionally audio)
4. Check video sessions against resolution policy (4K, 1080P, or ALL)
5. Check audio sessions if audio monitoring is enabled
6. Analyze transcode reasons to determine if termination criteria are met
7. Send message and terminate session if criteria match

### Configuration Notes

- Server configuration uses pattern `SERVER{N}_*` for dynamic loading
- Resolution policies determine minimum threshold for video termination
- Audio transcode checking is optional and disabled by default
- `KILL_STREAMS=false` enables dry-run mode for testing
- Both Jellyfin and Emby servers supported using same API endpoints

### Docker Deployment

- Multi-architecture images (amd64, arm64) published to GHCR
- GitHub Actions workflow for automated builds on tags/releases
- Health checks and resource limits configured
- Non-root user for security