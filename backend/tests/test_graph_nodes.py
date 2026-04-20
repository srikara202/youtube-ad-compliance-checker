import unittest
from unittest.mock import MagicMock, patch

from backend.src.graph.nodes import index_video_node


class GraphNodeTests(unittest.TestCase):
    def test_index_video_node_falls_back_to_public_youtube_transcript(self):
        vi_service = MagicMock()
        vi_service.download_youtube_video.side_effect = Exception(
            "YouTube blocked the Azure server while downloading this video. "
            "The preview can still load, but the full audit cannot continue from this App Service for this video."
        )

        fallback_payload = {
            "transcript": "Mint Mobile and Samsung are teaming up.",
            "ocr_text": [],
            "video_metadata": {
                "duration": None,
                "platform": "youtube",
                "source": "youtube_transcript_api",
            },
        }

        with patch(
            "backend.src.graph.nodes.VideoIndexerService",
            return_value=vi_service,
        ), patch(
            "backend.src.graph.nodes.extract_youtube_transcript",
            return_value=fallback_payload,
        ) as transcript_mock:
            result = index_video_node(
                {
                    "video_url": "https://www.youtube.com/watch?v=abc123xyz45",
                    "source_type": "youtube",
                    "source_url": "https://www.youtube.com/watch?v=abc123xyz45",
                    "video_id": "vid_demo",
                }
            )

        self.assertEqual(result["transcript"], fallback_payload["transcript"])
        self.assertEqual(result["ocr_text"], [])
        self.assertEqual(result["video_metadata"]["source"], "youtube_transcript_api")
        transcript_mock.assert_called_once_with("https://www.youtube.com/watch?v=abc123xyz45")
