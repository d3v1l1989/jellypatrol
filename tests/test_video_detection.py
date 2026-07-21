import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "jellypatrol.py"
SPEC = importlib.util.spec_from_file_location("jellypatrol", MODULE_PATH)
jellypatrol = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(jellypatrol)


class VideoTranscodeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.original_allow_container_changes = jellypatrol.ALLOW_CONTAINER_CHANGES
        jellypatrol.ALLOW_CONTAINER_CHANGES = True

    def tearDown(self):
        jellypatrol.ALLOW_CONTAINER_CHANGES = self.original_allow_container_changes

    def test_detects_4k_hdr_conversion_hidden_by_container_reason(self):
        source = {"Codec": "hevc", "Width": 3840, "Height": 2160, "VideoRange": "HDR"}
        output = {
            "VideoCodec": "h264",
            "Width": 1920,
            "Height": 1080,
            "IsVideoDirect": False,
            "TranscodeReasons": ["ContainerBitrateExceedsLimit"],
        }

        evidence = jellypatrol.get_video_transcode_evidence(source, output)

        self.assertIn("server reports IsVideoDirect=false", evidence)
        self.assertIn("video codec changes from hevc to h264", evidence)
        self.assertTrue(any("3840x2160 to 1920x1080" in item for item in evidence))

    def test_allows_a_real_container_only_change(self):
        source = {"Codec": "hevc", "Width": 3840, "Height": 2160}
        output = {
            "VideoCodec": "hevc",
            "Width": 3840,
            "Height": 2160,
            "IsVideoDirect": True,
            "TranscodeReasons": ["ContainerNotSupported"],
        }

        self.assertEqual([], jellypatrol.get_video_transcode_evidence(source, output))

    def test_codec_change_is_a_fallback_for_servers_without_direct_flag(self):
        source = {"Codec": "hevc", "Width": 3840, "Height": 2160}
        output = {"VideoCodec": "h264", "Width": 3840, "Height": 2160}

        self.assertIn(
            "video codec changes from hevc to h264",
            jellypatrol.get_video_transcode_evidence(source, output),
        )

    @patch.object(jellypatrol, "get_item_details", return_value=None)
    def test_container_reason_does_not_hide_real_video_conversion(self, _get_item_details):
        session = {
            "NowPlayingItem": {
                "Id": "item-id",
                "MediaStreams": [
                    {
                        "Type": "Video",
                        "Codec": "hevc",
                        "Width": 3840,
                        "Height": 2160,
                        "VideoRange": "HDR",
                        "VideoRangeType": "HDR10Plus",
                    }
                ],
            },
            "TranscodingInfo": {
                "VideoCodec": "h264",
                "Width": 1920,
                "Height": 1080,
                "IsVideoDirect": False,
                "TranscodeReasons": ["ContainerBitrateExceedsLimit"],
            },
        }

        should_terminate, reason = jellypatrol.check_video_transcode(
            session, "Test Server", "Test User", "Test Client", "session-id", "http://server", "api-key"
        )

        self.assertTrue(should_terminate)
        self.assertIn("ContainerBitrateExceedsLimit", reason)

    @patch.object(jellypatrol, "get_item_details", return_value=None)
    def test_real_container_only_change_remains_allowed(self, _get_item_details):
        session = {
            "NowPlayingItem": {
                "Id": "item-id",
                "MediaStreams": [
                    {"Type": "Video", "Codec": "hevc", "Width": 3840, "Height": 2160, "VideoRange": "SDR"}
                ],
            },
            "TranscodingInfo": {
                "VideoCodec": "hevc",
                "Width": 3840,
                "Height": 2160,
                "IsVideoDirect": True,
                "TranscodeReasons": ["ContainerNotSupported"],
            },
        }

        should_terminate, reason = jellypatrol.check_video_transcode(
            session, "Test Server", "Test User", "Test Client", "session-id", "http://server", "api-key"
        )

        self.assertFalse(should_terminate)
        self.assertEqual("", reason)


class ActiveEncodingFallbackTests(unittest.TestCase):
    def test_finds_newest_matching_play_session_id(self):
        lines = [
            'GET /videos/item/hls/main/1?DeviceId=tv-1&MediaSourceId=media-1&PlaySessionId=old HTTP/2.0',
            'GET /videos/item/hls/main/1?DeviceId=other&MediaSourceId=media-1&PlaySessionId=wrong HTTP/2.0',
            'GET /videos/item/hls/main/2?DeviceId=tv-1&MediaSourceId=media-1&PlaySessionId=new HTTP/2.0',
        ]
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as access_log:
            access_log.write("\n".join(lines))
            access_log.flush()

            play_session_id = jellypatrol.find_play_session_id(access_log.name, "tv-1", "media-1")

        self.assertEqual("new", play_session_id)

    @patch.object(jellypatrol.requests, "delete")
    @patch.object(jellypatrol, "find_play_session_id", return_value="play-session")
    def test_stops_only_the_matching_active_encoding(self, _find_play_session_id, delete):
        response = delete.return_value
        response.status_code = 204
        session = {
            "Id": "session-id",
            "DeviceId": "device-id",
            "PlayState": {"MediaSourceId": "media-source-id"},
        }

        stopped = jellypatrol.stop_active_encoding("http://server", "api-key", session)

        self.assertTrue(stopped)
        delete.assert_called_once_with(
            "http://server/Videos/ActiveEncodings",
            headers=jellypatrol.get_headers("api-key"),
            params={"deviceId": "device-id", "playSessionId": "play-session"},
            timeout=10,
        )

    @patch.object(jellypatrol, "stop_active_encoding")
    @patch.object(jellypatrol, "session_is_still_transcoding", return_value=False)
    @patch.object(jellypatrol.time, "sleep")
    @patch.object(jellypatrol.requests, "post")
    @patch.object(jellypatrol, "send_message_to_session")
    def test_does_not_fallback_when_normal_stop_works(
        self, _send_message, post, _sleep, _session_is_still_transcoding, stop_active_encoding
    ):
        post.return_value.status_code = 204
        session = {"Id": "session-id"}
        with patch.object(jellypatrol, "ACTIVE_ENCODING_FALLBACK", True):
            jellypatrol.terminate_session("http://server", "api-key", session, "jellyfin")

        stop_active_encoding.assert_not_called()

    @patch.object(jellypatrol, "stop_active_encoding")
    @patch.object(jellypatrol, "session_is_still_transcoding", return_value=True)
    @patch.object(jellypatrol.time, "sleep")
    @patch.object(jellypatrol.requests, "post")
    @patch.object(jellypatrol, "send_message_to_session")
    def test_falls_back_when_session_is_still_transcoding(
        self, _send_message, post, _sleep, _session_is_still_transcoding, stop_active_encoding
    ):
        post.return_value.status_code = 204
        session = {"Id": "session-id"}
        with patch.object(jellypatrol, "ACTIVE_ENCODING_FALLBACK", True):
            jellypatrol.terminate_session("http://server", "api-key", session, "jellyfin")

        stop_active_encoding.assert_called_once_with("http://server", "api-key", session)


if __name__ == "__main__":
    unittest.main()
