# JellyPatrol

Monitors Jellyfin/Emby media servers and automatically terminates transcode sessions based on configurable policies.

## Features

- **Resolution Policies**: Terminate 4K, 1080P, or ALL video transcodes
- **Multi-Server Support**: Monitor multiple servers simultaneously
- **Live TV Support**: Allow container changes for live TV in web browsers
- **Dry-Run Mode**: Test configuration without terminating sessions
- **User Notifications**: Send messages before terminating sessions
- **Docker Compose**: Simple deployment with pre-built images

## Quick Start with Docker Compose

1. **Create docker-compose.yml**:
   ```yaml
   version: '3.8'
   
   services:
     jellypatrol:
       image: ghcr.io/d3v1l1989/jellypatrol:latest
       container_name: jellypatrol
       restart: unless-stopped
       env_file:
         - .env
       # Adjust networking as needed for your setup
       networks:
         - mediaserver
   
   networks:
     mediaserver:
       external: true
   ```

2. **Create .env file**:
   ```bash
   # JellyPatrol Configuration
   # Copy this file to .env and configure your settings
   
   # ===== GENERAL SETTINGS =====
   # Check interval in seconds
   CHECK_INTERVAL_SECONDS=30
   
   # Resolution policy: 4K, 1080P, or ALL
   # 4K: Only terminate 4K+ content (3840x2160 and above)
   # 1080P: Terminate 1080P+ content (1920x1080 and above) 
   # ALL: Terminate any video transcode regardless of resolution
   RESOLUTION_POLICY=4K
   
   # Whether to actually terminate streams (true) or run in dry-run mode (false)
   KILL_STREAMS=true
   
   # Whether to check and terminate audio transcodes
   CHECK_AUDIO_TRANSCODES=false
   
   # Allow container format changes during playback (useful for live TV in web browsers)
   # When enabled, ContainerNotSupported and ContainerBitrateExceedsLimit will be ignored
   ALLOW_CONTAINER_CHANGES=false
   
   # ===== USER MESSAGES =====
   MESSAGE_HEADER=Playback Terminated by Server Policy
   MESSAGE_BODY=Your video transcode session is being terminated due to server resource policy. Please adjust your quality settings.
   MESSAGE_DISPLAY_TIMEOUT_MS=7000
   
   # ===== SERVER CONFIGURATION =====
   # Server 1 (Jellyfin)
   SERVER1_ENABLED=true
   SERVER1_NAME=My Jellyfin Server
   SERVER1_TYPE=jellyfin
   SERVER1_URL=http://jellyfin:8096
   SERVER1_API_KEY=your_api_key_here
   
   # Server 2 (Emby)
   SERVER2_ENABLED=false
   SERVER2_NAME=My Emby Server
   SERVER2_TYPE=emby
   SERVER2_URL=http://emby:8096
   SERVER2_API_KEY=your_emby_api_key_here
   
   # Additional servers can be configured by adding SERVER3_, SERVER4_, etc.
   # SERVER3_ENABLED=false
   # SERVER3_NAME=Another Server
   # SERVER3_TYPE=jellyfin
   # SERVER3_URL=http://another-server:8096
   # SERVER3_API_KEY=
   
   # ===== ADVANCED SETTINGS =====
   # Video transcode indicators (comma-separated list)
   # These are the transcode reasons that will trigger termination for video content
   VIDEO_TRANSCODE_INDICATORS=VideoCodecNotSupported,VideoResolutionNotSupported,VideoBitrateNotSupported,VideoFramerateNotSupported,VideoLevelNotSupported,VideoProfileNotSupported,AnamorphicVideoNotSupported,VideoRangeNotSupported,VideoRangeTypeNotSupported,ContainerNotSupported,ContainerBitrateExceedsLimit
   
   # Audio transcode indicators (comma-separated list)
   # These are the transcode reasons that will trigger termination for audio content
   AUDIO_TRANSCODE_INDICATORS=AudioCodecNotSupported,AudioBitrateNotSupported,AudioChannelsNotSupported,AudioSampleRateNotSupported,AudioBitDepthNotSupported
   
   # User agent for API requests
   SCRIPT_USER_AGENT=MediaServerPatrol/2.0
   ```

3. **Deploy with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

4. **Monitor logs**:
   ```bash
   docker-compose logs -f jellypatrol
   ```

## Key Configuration Options

- **`RESOLUTION_POLICY`**: `4K` (3840x2160+), `1080P` (1920x1080+), or `ALL` 
- **`KILL_STREAMS`**: `true` for live mode, `false` for dry-run testing
- **`ALLOW_CONTAINER_CHANGES`**: `true` to allow container changes for live TV
- **`CHECK_AUDIO_TRANSCODES`**: `true` to also monitor audio transcoding

## Getting API Keys

**Jellyfin**: Dashboard → API Keys → "+"
**Emby**: Settings → Advanced → API Keys → "New API Key"

## Docker Compose Commands

```bash
# Start JellyPatrol
docker-compose up -d

# View logs
docker-compose logs -f jellypatrol

# Stop JellyPatrol
docker-compose down

# Update to latest image
docker-compose pull && docker-compose up -d
```
