import requests
import time
import json

# --- Global Configuration ---
CHECK_INTERVAL_SECONDS = 30
TARGET_WIDTH = 3840
TARGET_HEIGHT = 2160
KILL_STREAMS = True # Set to True to actually kill streams, False for dry run

MESSAGE_HEADER = "Playback Terminated by Server Policy"
MESSAGE_BODY = "Your 4K video transcode session is being terminated due to server resource policy. Please adjust your quality settings. Audio-only 4K transcodes may be permitted."
MESSAGE_DISPLAY_TIMEOUT_MS = 7000

# Reasons that indicate video is being transcoded or processed in a way we want to stop
VIDEO_TRANSCODE_INDICATORS = [
    "VideoCodecNotSupported", "VideoResolutionNotSupported",
    "VideoBitrateNotSupported", "VideoFramerateNotSupported",
    "VideoLevelNotSupported", "VideoProfileNotSupported",
    "AnamorphicVideoNotSupported", "VideoRangeNotSupported",
    "VideoRangeTypeNotSupported",
    "ContainerNotSupported",
    "ContainerBitrateExceedsLimit"
]
# --- End Global Configuration ---

# --- Server Configuration ---
# Add or modify your server details here.
SERVERS = [
    {
        "name": "My Jellyfin Server",
        "type": "jellyfin",
        "url": "http://jellyfin:8096",
        "api_key": "",
        "enabled": True
    },
    {
        "name": "My Emby Server",
        "type": "emby",
        "url": "http://emby:8096",
        "api_key": "",
        "enabled": True # Set to True to enable this server
    },
]
# --- End Server Configuration ---

SCRIPT_USER_AGENT = "MediaServerPatrol/2.0"

def get_headers(api_key):
    return {
        "X-Emby-Token": api_key,
        "Content-Type": "application/json",
        "User-Agent": SCRIPT_USER_AGENT
    }

def get_active_sessions(server_url, api_key):
    """Fetches active sessions from a given server."""
    try:
        response = requests.get(f"{server_url}/Sessions", headers=get_headers(api_key), timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  [{server_url}] Error fetching sessions: {e}")
        return []

def send_message_to_session(server_url, api_key, session_id, header, body_text, display_timeout_ms):
    """Sends a message to a specific session on a given server."""
    message_url = f"{server_url}/Sessions/{session_id}/Message"
    payload = {
        "Header": header,
        "Text": body_text,
        "TimeoutMs": display_timeout_ms
    }
    try:
        print(f"    Sending message to session {session_id} on {server_url}: '{body_text}'")
        response = requests.post(message_url, headers=get_headers(api_key), json=payload, timeout=5)
        response.raise_for_status()
        print(f"    Message sent to session {session_id}. Status: {response.status_code}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"    Error sending message to session {session_id} on {server_url}: {e}")
        return False

def terminate_session(server_url, api_key, session_id, reason="Terminating 4K video transcode."):
    """Sends a message and then immediately terminates a specific session on a given server."""
    try:
        print(f"  Terminating session {session_id} on {server_url} for reason: {reason}")
        if KILL_STREAMS:
            send_message_to_session(server_url, api_key, session_id, MESSAGE_HEADER, MESSAGE_BODY, MESSAGE_DISPLAY_TIMEOUT_MS)

            stop_url = f"{server_url}/Sessions/{session_id}/Playing/Stop"
            print(f"    Attempting to send 'Stop Playback' command to session: {stop_url}")
            response = requests.post(stop_url, headers=get_headers(api_key), timeout=10)
            response.raise_for_status()
            print(f"    Session {session_id} 'Stop Playback' command sent. Status: {response.status_code}. Playback should stop.")
        else:
            print(f"  [DRY RUN] Would send message and then 'Stop Playback' command to session {session_id} on {server_url} for: {reason}")
    except requests.exceptions.RequestException as e:
        print(f"  Error in termination process for session {session_id} on {server_url}: {e}")

def check_and_kill_4k_transcodes_for_server(server_config):
    """Checks active sessions on a specific server and terminates 4K transcodes if video is being processed."""
    server_name = server_config["name"]
    server_url = server_config["url"]
    api_key = server_config["api_key"]
    # server_type = server_config["type"] # Available for future API-specific logic

    print(f"\n--- Checking server: {server_name} ({server_url}) at {time.ctime()} ---")

    if not api_key or api_key in ["YOUR_JELLYFIN_API_KEY_HERE", "YOUR_EMBY_API_KEY_HERE"]: # Basic check for unconfigured API keys
        print(f"  ERROR: API key for {server_name} is not configured. Skipping.")
        return

    sessions = get_active_sessions(server_url, api_key)
    if not sessions:
        print(f"  No active sessions found or error fetching sessions from {server_name}.")
        return

    for session in sessions:
        session_id = session.get("Id")
        user_name = session.get("UserName", "Unknown User")
        client_name = session.get("Client", "Unknown Client")
        play_state = session.get("PlayState", {})
        now_playing_item = session.get("NowPlayingItem", {})

        if not now_playing_item or not session_id:
            continue

        is_transcoding = play_state.get("PlayMethod") == "Transcode"
        media_type = now_playing_item.get("MediaType")

        if media_type == "Video" and is_transcoding:
            print(f"  Found transcoding video session: ID={session_id}, User='{user_name}', Client='{client_name}'")

            original_video_stream = None
            media_streams = now_playing_item.get("MediaStreams", [])
            for stream in media_streams:
                if stream.get("Type") == "Video":
                    original_video_stream = stream
                    break

            if original_video_stream:
                original_width = original_video_stream.get("Width", 0)
                original_height = original_video_stream.get("Height", 0)
                codec = original_video_stream.get("Codec", "N/A")
                print(f"    Original Resolution: {original_width}x{original_height}, Codec: {codec}")

                transcoding_info = session.get("TranscodingInfo", {})
                transcode_reasons = []
                if transcoding_info:
                    target_width_transcoding = transcoding_info.get("Width")
                    target_height_transcoding = transcoding_info.get("Height")
                    transcode_reasons = transcoding_info.get("TranscodeReasons", [])
                    print(f"    Transcoding To: {target_width_transcoding}x{target_height_transcoding}, Reasons: {transcode_reasons}")
                else:
                    print("    WARNING: TranscodingInfo not available for this session.")

                if original_width >= TARGET_WIDTH or original_height >= TARGET_HEIGHT:
                    is_video_component_transcoding = False
                    if not transcode_reasons and transcoding_info:
                        print("      WARNING: No transcode reasons available, but 4K file is transcoding. Assuming video transcode for safety.")
                        is_video_component_transcoding = True
                    else:
                        for reason in transcode_reasons:
                            if reason in VIDEO_TRANSCODE_INDICATORS:
                                is_video_component_transcoding = True
                                break

                    if is_video_component_transcoding:
                        reason_message = (f"Transcoding 4K content ({original_width}x{original_height}) on {server_name} "
                                          f"by User: {user_name} on Client: {client_name}. Reasons: {transcode_reasons}")
                        print(f"    ALERT: {reason_message}")
                        terminate_session(server_url, api_key, session_id, reason_message)
                    else:
                        print(f"    INFO: Transcoding 4K content ({original_width}x{original_height}) on {server_name} "
                              f"but video components appear to be direct playing/streaming or reason not in kill list. Skipping. Reasons: {transcode_reasons}")
                else:
                    print(f"    INFO: Transcoding non-4K content ({original_width}x{original_height}) on {server_name}. Skipping.")
            else:
                print(f"    WARNING: Could not determine original video stream resolution for session {session_id} on {server_name}.")
        elif media_type == "Video" and not is_transcoding:
             print(f"  Direct Play/Stream session on {server_name}: ID={session_id}, User='{user_name}', Client='{client_name}'. Skipping.")


if __name__ == "__main__":
    print(f"Starting Media Server Patrol. KILL_STREAMS is set to: {KILL_STREAMS}")
    print(f"Checking every {CHECK_INTERVAL_SECONDS} seconds.")
    print(f"Will target original media width >= {TARGET_WIDTH} or height >= {TARGET_HEIGHT}.")
    print(f"Video transcode indicators for termination: {VIDEO_TRANSCODE_INDICATORS}")
    if KILL_STREAMS:
        print("A message will be sent to the user before termination.")
    else:
        print("DRY RUN MODE: No streams will actually be terminated.")

    enabled_servers_count = sum(1 for s in SERVERS if s.get("enabled"))
    if enabled_servers_count == 0:
        print("\nWARNING: No servers are enabled in the SERVERS configuration. Exiting.")
        exit()
    else:
        print("\nEnabled servers:")
        for server in SERVERS:
            if server.get("enabled"):
                print(f"  - {server.get('name')} ({server.get('type')} at {server.get('url')})")

    try:
        while True:
            for server_config in SERVERS:
                if server_config.get("enabled"):
                    try:
                        check_and_kill_4k_transcodes_for_server(server_config)
                    except Exception as e:
                        # Basic error handling for an individual server check
                        print(f"!! UNHANDLED EXCEPTION while processing server {server_config.get('name', 'Unknown Server')}: {e}")
                # Silently skip disabled servers after initial announcement
            
            print(f"\n--- Cycle complete. Waiting {CHECK_INTERVAL_SECONDS} seconds... ---")
            time.sleep(CHECK_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nScript stopped by user.")
    except Exception as e:
        # Catch-all for unexpected errors in the main loop
        print(f"!! A CRITICAL UNHANDLED EXCEPTION occurred in the main loop: {e}")
