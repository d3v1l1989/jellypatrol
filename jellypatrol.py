import requests
import time
import json

# --- Configuration ---
JELLYFIN_URL = "http://jellyfin:8096"
API_KEY = ""
CHECK_INTERVAL_SECONDS = 30
TARGET_WIDTH = 3840
TARGET_HEIGHT = 2160
# Set to True to actually kill streams, False to just report (for testing)
KILL_STREAMS = True

# Message Configuration
MESSAGE_HEADER = "Playback Terminated"
MESSAGE_BODY = "Your 4K video transcode session is being terminated due to server policy. Please adjust your quality settings for future playback. Audio-only transcodes of 4K content may be permitted."
MESSAGE_DISPLAY_TIMEOUT_MS = 7000

# Reasons that indicate video is being transcoded (or processed in a way we want to stop)
VIDEO_TRANSCODE_INDICATORS = [
    "VideoCodecNotSupported", "VideoResolutionNotSupported",
    "VideoBitrateNotSupported", "VideoFramerateNotSupported",
    "VideoLevelNotSupported", "VideoProfileNotSupported",
    "AnamorphicVideoNotSupported", "VideoRangeNotSupported",
    "VideoRangeTypeNotSupported",
    "ContainerNotSupported", # Including this as it often forces video processing
    "ContainerBitrateExceedsLimit"
]
# --- End Configuration ---

HEADERS = {
    "X-Emby-Token": API_KEY,
    "Content-Type": "application/json",
    "User-Agent": "Jellyfin4KTranscodeKillerScript/1.7"
}

def get_active_sessions():
    """Fetches active sessions from Jellyfin."""
    try:
        response = requests.get(f"{JELLYFIN_URL}/Sessions", headers=HEADERS, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching sessions: {e}")
        return []

def send_message_to_session(session_id, header, body_text, display_timeout_ms):
    """Sends a message to a specific Jellyfin session."""
    message_url = f"{JELLYFIN_URL}/Sessions/{session_id}/Message"
    payload = {
        "Header": header,
        "Text": body_text,
        "TimeoutMs": display_timeout_ms
    }
    try:
        print(f"  Sending message to session {session_id}: '{body_text}'")
        response = requests.post(message_url, headers=HEADERS, json=payload, timeout=5)
        response.raise_for_status()
        print(f"  Message sent to session {session_id}. Status: {response.status_code}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"  Error sending message to session {session_id}: {e}")
        return False

def terminate_session(session_id, reason="Terminating 4K video transcode."):
    """Sends a message and then immediately terminates a specific Jellyfin session."""
    try:
        print(f"Terminating session {session_id} for reason: {reason}")
        if KILL_STREAMS:
            send_message_to_session(session_id, MESSAGE_HEADER, MESSAGE_BODY, MESSAGE_DISPLAY_TIMEOUT_MS)

            stop_url = f"{JELLYFIN_URL}/Sessions/{session_id}/Playing/Stop"
            print(f"  Attempting to send 'Stop Playback' command to session: {stop_url}")
            response = requests.post(stop_url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            print(f"  Session {session_id} 'Stop Playback' command sent. Status: {response.status_code}. Playback should stop.")
        else:
            print(f"[DRY RUN] Would send message and then 'Stop Playback' command to session {session_id} for: {reason}")
    except requests.exceptions.RequestException as e:
        print(f"Error in termination process for session {session_id}: {e}")

def check_and_kill_4k_transcodes():
    """Checks active sessions and terminates 4K transcodes if video is being processed."""
    print(f"\n--- Checking for 4K transcodes at {time.ctime()} ---")
    sessions = get_active_sessions()
    if not sessions:
        print("No active sessions found or error fetching sessions.")
        return

    for session in sessions:
        session_id = session.get("Id")
        user_name = session.get("UserName", "Unknown User")
        client_name = session.get("Client", "Unknown Client")
        play_state = session.get("PlayState", {})
        now_playing_item = session.get("NowPlayingItem")

        if not now_playing_item or not session_id:
            continue

        is_transcoding = play_state.get("PlayMethod") == "Transcode"
        media_type = now_playing_item.get("MediaType")

        if media_type == "Video" and is_transcoding:
            print(f"Found transcoding video session: ID={session_id}, User='{user_name}', Client='{client_name}'")

            original_video_stream = None
            for stream in now_playing_item.get("MediaStreams", []):
                if stream.get("Type") == "Video":
                    original_video_stream = stream
                    break

            if original_video_stream:
                original_width = original_video_stream.get("Width", 0)
                original_height = original_video_stream.get("Height", 0)
                codec = original_video_stream.get("Codec", "N/A")
                print(f"  Original Resolution: {original_width}x{original_height}, Codec: {codec}")

                transcoding_info = session.get("TranscodingInfo")
                transcode_reasons = []
                if transcoding_info:
                    target_width_transcoding = transcoding_info.get("Width")
                    target_height_transcoding = transcoding_info.get("Height")
                    transcode_reasons = transcoding_info.get("TranscodeReasons", []) # Ensure it's a list
                    print(f"  Transcoding To: {target_width_transcoding}x{target_height_transcoding}, Reasons: {transcode_reasons}")
                else:
                    print("  WARNING: TranscodingInfo not available for this session.")


                if original_width >= TARGET_WIDTH or original_height >= TARGET_HEIGHT:
                    # Now check if video is actually being transcoded or container bitrate exceeded
                    is_video_component_transcoding = False
                    if not transcode_reasons:
                        print("    WARNING: No transcode reasons available, but 4K file is transcoding. Assuming video transcode for safety.")
                        is_video_component_transcoding = True # Err on the side of caution
                    else:
                        for reason in transcode_reasons:
                            if reason in VIDEO_TRANSCODE_INDICATORS:
                                is_video_component_transcoding = True
                                break

                    if is_video_component_transcoding:
                        reason_message = f"Transcoding 4K content ({original_width}x{original_height}) including video components or due to container bitrate limit by User: {user_name} on Client: {client_name}. Reasons: {transcode_reasons}"
                        print(f"  ALERT: {reason_message}")
                        terminate_session(session_id, reason_message)
                    else:
                        print(f"  INFO: Transcoding 4K content ({original_width}x{original_height}) but not due to reasons targeted for termination. Skipping termination. Reasons: {transcode_reasons}")
                else:
                    print(f"  INFO: Transcoding non-4K content ({original_width}x{original_height}). Skipping.")
            else:
                print(f"  WARNING: Could not determine original video stream resolution for session {session_id}.")
        elif media_type == "Video" and not is_transcoding:
             print(f"Direct Play/Stream session: ID={session_id}, User='{user_name}', Client='{client_name}'. Skipping.")


if __name__ == "__main__":
    if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
        print("ERROR: Please configure your JELLYFIN_URL and API_KEY in the script.")
    elif JELLYFIN_URL == "http://jellyfin:8096" and API_KEY == "801efce86ecd4a5c8758b527ffa17fc7":
        print("Using your configured JELLYFIN_URL and API_KEY.")
        print(f"Starting Jellyfin 4K Transcode Killer. KILL_STREAMS is set to: {KILL_STREAMS}")
        print(f"Checking every {CHECK_INTERVAL_SECONDS} seconds.")
        print(f"Will target original media width >= {TARGET_WIDTH} or height >= {TARGET_HEIGHT} that is transcoding due to reasons: {VIDEO_TRANSCODE_INDICATORS}")
        if KILL_STREAMS:
            print(f"A message will be sent to the user before termination.")
        try:
            while True:
                check_and_kill_4k_transcodes()
                time.sleep(CHECK_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nScript stopped by user.")
    else: # General case if API key is set and doesn't match the specific elif above
        print(f"Starting Jellyfin 4K Transcode Killer with API_KEY: ...{API_KEY[-4:]}. KILL_STREAMS is set to: {KILL_STREAMS}")
        print(f"Checking every {CHECK_INTERVAL_SECONDS} seconds.")
        print(f"Will target original media width >= {TARGET_WIDTH} or height >= {TARGET_HEIGHT} that is transcoding due to reasons: {VIDEO_TRANSCODE_INDICATORS}")
        if KILL_STREAMS:
            print(f"A message will be sent to the user before termination.")
        try:
            while True:
                check_and_kill_4k_transcodes()
                time.sleep(CHECK_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nScript stopped by user.")
