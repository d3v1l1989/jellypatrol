import importlib.util
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


if __name__ == "__main__":
    unittest.main()
