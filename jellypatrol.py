import requests
import time
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration from Environment Variables ---
CHECK_INTERVAL_SECONDS = int(os.getenv('CHECK_INTERVAL_SECONDS', '30'))
RESOLUTION_POLICY = os.getenv('RESOLUTION_POLICY', '4K').upper()
KILL_STREAMS = os.getenv('KILL_STREAMS', 'true').lower() == 'true'
CHECK_AUDIO_TRANSCODES = os.getenv('CHECK_AUDIO_TRANSCODES', 'false').lower() == 'true'
ALLOW_CONTAINER_CHANGES = os.getenv('ALLOW_CONTAINER_CHANGES', 'false').lower() == 'true'
IGNORE_STRM_FILES = os.getenv('IGNORE_STRM_FILES', 'false').lower() == 'true'
WHITELISTED_USERS = [user.strip() for user in os.getenv('WHITELISTED_USERS', '').split(',') if user.strip()]

MESSAGE_HEADER = os.getenv('MESSAGE_HEADER', 'Playback Terminated by Server Policy')
MESSAGE_BODY = os.getenv('MESSAGE_BODY', 'Your video transcode session is being terminated due to server resource policy. Please adjust your quality settings.')
MESSAGE_DISPLAY_TIMEOUT_MS = int(os.getenv('MESSAGE_DISPLAY_TIMEOUT_MS', '7000'))

# Resolution thresholds based on policy
RESOLUTION_THRESHOLDS = {
    '4K': (3840, 2160),
    '1080P': (1920, 1080),
    'ALL': (0, 0)  # Will match any resolution
}

# Get target resolution based on policy
TARGET_WIDTH, TARGET_HEIGHT = RESOLUTION_THRESHOLDS.get(RESOLUTION_POLICY, (3840, 2160))

# Load transcode indicators from environment
VIDEO_TRANSCODE_INDICATORS = os.getenv(
    'VIDEO_TRANSCODE_INDICATORS',
    'VideoCodecNotSupported,VideoResolutionNotSupported,VideoBitrateNotSupported,VideoFramerateNotSupported,VideoLevelNotSupported,VideoProfileNotSupported,AnamorphicVideoNotSupported,VideoRangeNotSupported,VideoRangeTypeNotSupported,ContainerNotSupported,ContainerBitrateExceedsLimit'
).split(',')

AUDIO_TRANSCODE_INDICATORS = os.getenv(
    'AUDIO_TRANSCODE_INDICATORS',
    'AudioCodecNotSupported,AudioBitrateNotSupported,AudioChannelsNotSupported,AudioSampleRateNotSupported,AudioBitDepthNotSupported'
).split(',')

SCRIPT_USER_AGENT = os.getenv('SCRIPT_USER_AGENT', 'MediaServerPatrol/2.0')
# --- End Configuration ---

# --- Server Configuration from Environment Variables ---
def load_servers_from_env():
    """Load server configurations from environment variables."""
    servers = []
    server_num = 1
    
    while True:
        prefix = f"SERVER{server_num}_"
        enabled = os.getenv(f"{prefix}ENABLED", '').lower() == 'true'
        
        # If no enabled setting found, we've reached the end
        if f"{prefix}ENABLED" not in os.environ:
            break
            
        if enabled:
            server = {
                "name": os.getenv(f"{prefix}NAME", f"Server {server_num}"),
                "type": os.getenv(f"{prefix}TYPE", "jellyfin"),
                "url": os.getenv(f"{prefix}URL", ""),
                "api_key": os.getenv(f"{prefix}API_KEY", ""),
                "enabled": True
            }
            servers.append(server)
        
        server_num += 1
        
        # Safety limit to prevent infinite loop
        if server_num > 20:
            break
    
    return servers

SERVERS = load_servers_from_env()
# --- End Server Configuration ---

def get_headers(api_key):
    return {
        "X-Emby-Token": api_key,
        "Content-Type": "application/json",
        "User-Agent": SCRIPT_USER_AGENT
    }

def is_strm_file(now_playing_item):
    """Check if the current playing item is a .strm file."""
    if not now_playing_item:
        return False
    
    # Check various possible fields for file path/name
    path = now_playing_item.get("Path", "")
    container = now_playing_item.get("Container", "")
    
    # Check if it's a .strm file
    return path.lower().endswith('.strm') or container.lower() == 'strm'

def is_user_whitelisted(user_name):
    """Check if a user is in the whitelist and should be exempt from termination."""
    if not WHITELISTED_USERS or not user_name:
        return False
    
    # Case-insensitive comparison
    return user_name.lower() in [user.lower() for user in WHITELISTED_USERS]

def get_active_sessions(server_url, api_key):
    """Fetches active sessions from a given server."""
    try:
        response = requests.get(f"{server_url}/Sessions", headers=get_headers(api_key), timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  [{server_url}] Error fetching sessions: {e}")
        return []

def get_item_details(server_url, api_key, item_id):
    """Fetches full item details including MediaStreams to get true source file properties."""
    try:
        # MediaSources is returned by default, only request MediaStreams in Fields
        response = requests.get(
            f"{server_url}/Items/{item_id}",
            params={"Fields": "MediaStreams"},
            headers=get_headers(api_key),
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  [{server_url}] Error fetching item details for {item_id}: {e}")
        return None

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

def check_video_transcode(session, server_name, user_name, client_name, session_id, server_url, api_key):
    """Check if a video transcode session should be terminated based on resolution policy."""
    print(f"  Found transcoding video session: ID={session_id}, User='{user_name}', Client='{client_name}'")

    now_playing_item = session.get("NowPlayingItem", {})
    item_id = now_playing_item.get("Id")

    if not item_id:
        print(f"    WARNING: Could not determine ItemId for session {session_id} on {server_name}.")
        return False, ""

    # Fetch full item details to get TRUE source file resolution (not transcoded output)
    item_details = get_item_details(server_url, api_key, item_id)
    if not item_details:
        print(f"    WARNING: Could not fetch item details for ItemId {item_id} on {server_name}. Falling back to session data.")
        # Fallback to session data if API call fails
        media_streams = now_playing_item.get("MediaStreams", [])
    else:
        # Use MediaSources from item details for true source resolution
        media_sources = item_details.get("MediaSources", [])
        if media_sources:
            media_streams = media_sources[0].get("MediaStreams", [])
        else:
            media_streams = item_details.get("MediaStreams", [])

    # Find video stream from source file
    original_video_stream = None
    for stream in media_streams:
        if stream.get("Type") == "Video":
            original_video_stream = stream
            break

    if not original_video_stream:
        print(f"    WARNING: Could not determine original video stream resolution for session {session_id} on {server_name}.")
        return False, ""

    original_width = original_video_stream.get("Width", 0)
    original_height = original_video_stream.get("Height", 0)
    codec = original_video_stream.get("Codec", "N/A")
    video_range = original_video_stream.get("VideoRange", "SDR")
    video_range_type = original_video_stream.get("VideoRangeType", "")
    print(f"    Source File Resolution: {original_width}x{original_height}, Codec: {codec}, VideoRange: {video_range}/{video_range_type}")
    
    transcoding_info = session.get("TranscodingInfo", {})
    transcode_reasons = []
    if transcoding_info:
        target_width_transcoding = transcoding_info.get("Width")
        target_height_transcoding = transcoding_info.get("Height")
        transcode_reasons = transcoding_info.get("TranscodeReasons", [])
        print(f"    Transcoding To: {target_width_transcoding}x{target_height_transcoding}, Reasons: {transcode_reasons}")
    else:
        print("    WARNING: TranscodingInfo not available for this session.")

    # Check if resolution meets our policy threshold
    if original_width >= TARGET_WIDTH or original_height >= TARGET_HEIGHT:
        is_video_component_transcoding = False

        # Special detection for HDR tone-mapping (high CPU usage scenarios)
        is_hdr_tonemapping = False
        if video_range and video_range.upper() != "SDR":
            # Source is HDR/HDR10/HDR10+/DV
            hdr_transcode_reasons = ["VideoRangeNotSupported", "VideoRangeTypeNotSupported"]
            if any(reason in transcode_reasons for reason in hdr_transcode_reasons):
                is_hdr_tonemapping = True
                print(f"      ALERT: HDR tone-mapping detected! Source is {video_range}/{video_range_type}, transcoding for client compatibility.")

        if not transcode_reasons and transcoding_info:
            print(f"      WARNING: No transcode reasons available, but {RESOLUTION_POLICY} file is transcoding. Assuming video transcode for safety.")
            is_video_component_transcoding = True
        elif is_hdr_tonemapping:
            # HDR tone-mapping is always CPU-intensive, especially from 4K sources
            print(f"      INFO: Flagging as video transcode due to HDR tone-mapping (CPU-intensive operation).")
            is_video_component_transcoding = True
        else:
            # Filter out container-related reasons if ALLOW_CONTAINER_CHANGES is enabled
            filtered_reasons = transcode_reasons
            if ALLOW_CONTAINER_CHANGES:
                container_reasons = ['ContainerNotSupported', 'ContainerBitrateExceedsLimit']
                filtered_reasons = [reason for reason in transcode_reasons if reason not in container_reasons]
                if len(filtered_reasons) != len(transcode_reasons):
                    print(f"      INFO: Container changes allowed, filtering out container-related reasons. Original: {transcode_reasons}, Filtered: {filtered_reasons}")
            
            for reason in filtered_reasons:
                if reason in VIDEO_TRANSCODE_INDICATORS:
                    is_video_component_transcoding = True
                    break
        
        if is_video_component_transcoding:
            policy_desc = f"{RESOLUTION_POLICY}" if RESOLUTION_POLICY != "ALL" else "video"
            reason_message = (f"Transcoding {policy_desc} content ({original_width}x{original_height}) on {server_name} "
                              f"by User: {user_name} on Client: {client_name}. Reasons: {transcode_reasons}")
            print(f"    ALERT: {reason_message}")
            return True, reason_message
        else:
            policy_desc = f"{RESOLUTION_POLICY}" if RESOLUTION_POLICY != "ALL" else "video"
            print(f"    INFO: Transcoding {policy_desc} content ({original_width}x{original_height}) on {server_name} "
                  f"but video components appear to be direct playing/streaming or reason not in kill list. Skipping. Reasons: {transcode_reasons}")
            return False, ""
    else:
        policy_desc = f"below {RESOLUTION_POLICY} threshold" if RESOLUTION_POLICY != "ALL" else "video"
        print(f"    INFO: Content resolution ({original_width}x{original_height}) is {policy_desc} on {server_name}. Skipping.")
        return False, ""

def check_audio_transcode(session, server_name, user_name, client_name, session_id):
    """Check if an audio transcode session should be terminated."""
    print(f"  Found transcoding audio session: ID={session_id}, User='{user_name}', Client='{client_name}'")
    
    now_playing_item = session.get("NowPlayingItem", {})
    media_streams = now_playing_item.get("MediaStreams", [])
    
    # Find audio stream info
    original_audio_streams = [stream for stream in media_streams if stream.get("Type") == "Audio"]
    if original_audio_streams:
        audio_info = original_audio_streams[0]  # Use first audio stream for info
        codec = audio_info.get("Codec", "N/A")
        channels = audio_info.get("Channels", "N/A")
        sample_rate = audio_info.get("SampleRate", "N/A")
        print(f"    Original Audio: Codec={codec}, Channels={channels}, SampleRate={sample_rate}")
    
    transcoding_info = session.get("TranscodingInfo", {})
    transcode_reasons = []
    if transcoding_info:
        transcode_reasons = transcoding_info.get("TranscodeReasons", [])
        print(f"    Audio Transcode Reasons: {transcode_reasons}")
    else:
        print("    WARNING: TranscodingInfo not available for this session.")
    
    # Check if any audio transcode reasons match our indicators
    is_audio_component_transcoding = False
    if not transcode_reasons and transcoding_info:
        print("      WARNING: No transcode reasons available, but audio file is transcoding. Assuming audio transcode for safety.")
        is_audio_component_transcoding = True
    else:
        for reason in transcode_reasons:
            if reason in AUDIO_TRANSCODE_INDICATORS:
                is_audio_component_transcoding = True
                break
    
    if is_audio_component_transcoding:
        reason_message = (f"Transcoding audio content on {server_name} "
                          f"by User: {user_name} on Client: {client_name}. Reasons: {transcode_reasons}")
        print(f"    ALERT: {reason_message}")
        return True, reason_message
    else:
        print(f"    INFO: Audio transcoding on {server_name} but reasons not in kill list. Skipping. Reasons: {transcode_reasons}")
        return False, ""

def terminate_session(server_url, api_key, session_id, reason="Terminating transcode session."):
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

def check_and_kill_transcodes_for_server(server_config):
    """Checks active sessions on a specific server and terminates transcodes based on configured policies."""
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

        # Skip whitelisted users
        if is_user_whitelisted(user_name):
            print(f"  Skipping whitelisted user session: ID={session_id}, User='{user_name}', Client='{client_name}' (user is whitelisted)")
            continue

        # Skip .strm files if IGNORE_STRM_FILES is enabled
        if IGNORE_STRM_FILES and is_strm_file(now_playing_item):
            print(f"  Skipping .strm file session: ID={session_id}, User='{user_name}', Client='{client_name}' (IGNORE_STRM_FILES enabled)")
            continue

        is_transcoding = play_state.get("PlayMethod") == "Transcode"
        media_type = now_playing_item.get("MediaType")

        if media_type == "Video" and is_transcoding:
            should_terminate, reason_message = check_video_transcode(session, server_name, user_name, client_name, session_id, server_url, api_key)
            if should_terminate:
                terminate_session(server_url, api_key, session_id, reason_message)
        elif media_type == "Audio" and is_transcoding and CHECK_AUDIO_TRANSCODES:
            should_terminate, reason_message = check_audio_transcode(session, server_name, user_name, client_name, session_id)
            if should_terminate:
                terminate_session(server_url, api_key, session_id, reason_message)
        elif media_type == "Video" and not is_transcoding:
            print(f"  Direct Play/Stream session on {server_name}: ID={session_id}, User='{user_name}', Client='{client_name}'. Skipping.")
        elif media_type == "Audio" and not is_transcoding and CHECK_AUDIO_TRANSCODES:
            print(f"  Direct Play/Stream audio session on {server_name}: ID={session_id}, User='{user_name}', Client='{client_name}'. Skipping.")


if __name__ == "__main__":
    print(f"Starting Media Server Patrol. KILL_STREAMS is set to: {KILL_STREAMS}")
    print(f"Checking every {CHECK_INTERVAL_SECONDS} seconds.")
    print(f"Resolution policy: {RESOLUTION_POLICY} (targeting width >= {TARGET_WIDTH} or height >= {TARGET_HEIGHT})")
    print(f"Audio transcode checking: {CHECK_AUDIO_TRANSCODES}")
    print(f"Allow container changes: {ALLOW_CONTAINER_CHANGES}")
    print(f"Ignore .strm files: {IGNORE_STRM_FILES}")
    if WHITELISTED_USERS:
        print(f"Whitelisted users: {', '.join(WHITELISTED_USERS)}")
    else:
        print("No whitelisted users configured")
    print(f"Video transcode indicators for termination: {VIDEO_TRANSCODE_INDICATORS}")
    if CHECK_AUDIO_TRANSCODES:
        print(f"Audio transcode indicators for termination: {AUDIO_TRANSCODE_INDICATORS}")
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
                        check_and_kill_transcodes_for_server(server_config)
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
