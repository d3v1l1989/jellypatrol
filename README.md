JellyPatrol is a Python script that monitors active playback sessions on a Jellyfin or Emby media server and automatically terminates any 4K video streams that are being transcoded. This helps to prevent excessive server load and enforces a policy against 4K video transcoding.
Features

    Monitors all active Jellyfin/Emby sessions
    Detects when 4K video content (3840x2160 or higher) is being transcoded
    Optionally sends a message to the user before terminating their session
    Can be run in dry-run mode to only report offending streams without terminating them
