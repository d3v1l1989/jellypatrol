# JellyPatrol

JellyPatrol is a configurable Python application that monitors active playback sessions on Jellyfin or Emby media servers and automatically terminates transcode sessions based on your configured policies. This helps prevent excessive server load and enforces transcoding policies.

## Features

- **Flexible Resolution Policies**: Configure to terminate 4K, 1080P, or ALL video transcodes
- **Audio Transcode Monitoring**: Optional checking and termination of audio transcodes
- **Multi-Server Support**: Monitor multiple Jellyfin/Emby servers simultaneously
- **Environment-Based Configuration**: Configure via `.env` file or environment variables
- **Docker Support**: Ready-to-use Docker images published to GitHub Container Registry
- **Dry-Run Mode**: Test your configuration without actually terminating sessions
- **User Notifications**: Send messages to users before terminating their sessions
- **Health Monitoring**: Built-in health checks for containerized deployments

## Quick Start with Docker

### Using Docker Compose (Recommended)

1. **Create your environment file**:
   ```bash
   cp .env.example .env
   ```

2. **Configure your settings** in `.env`:
   ```bash
   # Basic configuration
   RESOLUTION_POLICY=4K          # Options: 4K, 1080P, ALL
   KILL_STREAMS=true             # Set to false for dry-run mode
   CHECK_AUDIO_TRANSCODES=false  # Set to true to monitor audio transcodes
   
   # Server configuration
   SERVER1_ENABLED=true
   SERVER1_NAME=My Jellyfin Server
   SERVER1_TYPE=jellyfin
   SERVER1_URL=http://jellyfin:8096
   SERVER1_API_KEY=your_api_key_here
   ```

3. **Run with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

### Using Docker CLI

```bash
docker run -d \
  --name jellypatrol \
  --restart unless-stopped \
  --env-file .env \
  ghcr.io/d3v1l1989/jellypatrol:latest
```

## Configuration Options

### Resolution Policies

- **`4K`**: Only terminate transcodes of 4K content (3840x2160 and above)
- **`1080P`**: Terminate transcodes of 1080P content and above (1920x1080+)
- **`ALL`**: Terminate any video transcode regardless of resolution

### Key Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `RESOLUTION_POLICY` | `4K` | Resolution threshold policy |
| `CHECK_AUDIO_TRANSCODES` | `false` | Whether to monitor audio transcodes |
| `KILL_STREAMS` | `true` | Set to `false` for dry-run mode |
| `CHECK_INTERVAL_SECONDS` | `30` | How often to check for transcodes |
| `MESSAGE_HEADER` | `Playback Terminated by Server Policy` | Message title sent to users |
| `MESSAGE_BODY` | `Your video transcode session...` | Message body sent to users |

### Server Configuration

Configure up to 20 servers using the pattern `SERVER{N}_*`:

```bash
# Server 1
SERVER1_ENABLED=true
SERVER1_NAME=My Jellyfin Server
SERVER1_TYPE=jellyfin  # or 'emby'
SERVER1_URL=http://jellyfin:8096
SERVER1_API_KEY=your_jellyfin_api_key

# Server 2
SERVER2_ENABLED=true
SERVER2_NAME=My Emby Server
SERVER2_TYPE=emby
SERVER2_URL=http://emby:8096
SERVER2_API_KEY=your_emby_api_key
```

## Installation Methods

### Docker (Recommended)

The easiest way to run JellyPatrol is using the pre-built Docker images:

```bash
# Pull the latest image
docker pull ghcr.io/d3v1l1989/jellypatrol:latest

# Or use docker-compose (see docker-compose.yml)
docker-compose up -d
```

### Python (Direct)

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Run the script**:
   ```bash
   python3 jellypatrol.py
   ```

## Getting API Keys

### Jellyfin
1. Log into your Jellyfin web interface
2. Go to Dashboard → API Keys
3. Click "+" to create a new API key
4. Copy the generated key to your `.env` file

### Emby
1. Log into your Emby web interface
2. Go to Settings → Advanced → API Keys
3. Click "New API Key"
4. Copy the generated key to your `.env` file

## Monitoring and Logs

JellyPatrol provides detailed logging of its activities:

```bash
# View logs with Docker Compose
docker-compose logs -f jellypatrol

# View logs with Docker
docker logs -f jellypatrol
```

Example log output:
```
Starting Media Server Patrol. KILL_STREAMS is set to: True
Resolution policy: 4K (targeting width >= 3840 or height >= 2160)
Audio transcode checking: False

--- Checking server: My Jellyfin Server (http://jellyfin:8096) ---
  Found transcoding video session: ID=abc123, User='john_doe', Client='Jellyfin Web'
    Original Resolution: 3840x2160, Codec: hevc
    Transcoding To: 1920x1080, Reasons: ['VideoCodecNotSupported']
    ALERT: Transcoding 4K content (3840x2160) on My Jellyfin Server by User: john_doe on Client: Jellyfin Web
  Terminating session abc123 for reason: Transcoding 4K content...
```

## Health Checks

The Docker image includes built-in health checks. Monitor the container health:

```bash
# Check health status
docker inspect jellypatrol --format='{{.State.Health.Status}}'

# View health check logs
docker inspect jellypatrol --format='{{range .State.Health.Log}}{{.Output}}{{end}}'
```
