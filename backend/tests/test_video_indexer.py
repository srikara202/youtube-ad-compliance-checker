import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

import requests

from backend.src.services.video_indexer import (
    VideoIndexerService,
    extract_youtube_metadata,
    extract_youtube_transcript,
)


class VideoIndexerMetadataTests(unittest.TestCase):
    def test_extract_youtube_metadata_prefers_oembed(self):
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "title": "Public promo",
            "thumbnail_url": "https://img.youtube.com/vi/abc123xyz45/hqdefault.jpg",
        }

        with patch(
            "backend.src.services.video_indexer.requests.get",
            return_value=response,
        ) as request_mock, patch(
            "backend.src.services.video_indexer.yt_dlp.YoutubeDL"
        ) as ydl_mock:
            metadata = extract_youtube_metadata("https://youtu.be/abc123xyz45")

        self.assertEqual(metadata["youtube_video_id"], "abc123xyz45")
        self.assertEqual(metadata["title"], "Public promo")
        self.assertEqual(
            metadata["thumbnail_url"],
            "https://img.youtube.com/vi/abc123xyz45/hqdefault.jpg",
        )
        request_mock.assert_called_once()
        ydl_mock.assert_not_called()

    def test_extract_youtube_metadata_falls_back_to_ytdlp(self):
        ydl = MagicMock()
        ydl.extract_info.return_value = {
            "title": "Fallback promo",
            "thumbnail": "https://example.com/thumb.jpg",
        }
        ydl_context = MagicMock()
        ydl_context.__enter__.return_value = ydl
        ydl_context.__exit__.return_value = False

        with patch(
            "backend.src.services.video_indexer.requests.get",
            side_effect=requests.RequestException("oEmbed unavailable"),
        ), patch(
            "backend.src.services.video_indexer.yt_dlp.YoutubeDL",
            return_value=ydl_context,
        ):
            metadata = extract_youtube_metadata("https://youtu.be/abc123xyz45")

        self.assertEqual(metadata["youtube_video_id"], "abc123xyz45")
        self.assertEqual(metadata["title"], "Fallback promo")
        self.assertEqual(metadata["thumbnail_url"], "https://example.com/thumb.jpg")
        ydl.extract_info.assert_called_once()

    def test_extract_youtube_transcript_builds_indexer_payload(self):
        snippet_one = type("Snippet", (), {"text": "This just in"})()
        snippet_two = type("Snippet", (), {"text": "Mint Mobile is back"})()
        transcript_api = MagicMock()
        transcript_api.fetch.return_value = [snippet_one, snippet_two]

        with patch(
            "backend.src.services.video_indexer.YouTubeTranscriptApi",
            return_value=transcript_api,
        ):
            transcript_payload = extract_youtube_transcript("https://youtu.be/abc123xyz45")

        self.assertEqual(
            transcript_payload["transcript"],
            "This just in Mint Mobile is back",
        )
        self.assertEqual(transcript_payload["ocr_text"], [])
        self.assertEqual(transcript_payload["video_metadata"]["source"], "youtube_transcript_api")
        self.assertEqual(
            transcript_payload["video_metadata"]["youtube_video_id"],
            "abc123xyz45",
        )


class VideoIndexerDownloadTests(unittest.TestCase):
    def test_resolve_youtube_stream_url_selects_progressive_http_format(self):
        ydl = MagicMock()
        ydl.extract_info.return_value = {
            "formats": [
                {
                    "format_id": "137",
                    "ext": "mp4",
                    "protocol": "https",
                    "acodec": "none",
                    "vcodec": "avc1.640028",
                    "url": "https://example.com/video-only.mp4",
                    "height": 1080,
                },
                {
                    "format_id": "18",
                    "ext": "mp4",
                    "protocol": "https",
                    "acodec": "mp4a.40.2",
                    "vcodec": "avc1.42001E",
                    "url": "https://example.com/progressive.mp4",
                    "height": 360,
                },
            ]
        }
        ydl_context = MagicMock()
        ydl_context.__enter__.return_value = ydl
        ydl_context.__exit__.return_value = False

        service = VideoIndexerService()

        with patch(
            "backend.src.services.video_indexer.yt_dlp.YoutubeDL",
            return_value=ydl_context,
        ):
            stream_url, extension = service.resolve_youtube_stream_url(
                "https://youtu.be/abc123xyz45"
            )

        self.assertEqual(stream_url, "https://example.com/progressive.mp4")
        self.assertEqual(extension, "mp4")
        ydl.extract_info.assert_called_once()

    def test_download_youtube_video_prefers_direct_stream_download(self):
        service = VideoIndexerService()
        response = MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        response.raise_for_status.return_value = None
        response.iter_content.return_value = [b"abc", b"123"]

        with TemporaryDirectory() as temp_dir, patch.object(
            service,
            "resolve_youtube_stream_url",
            return_value=("https://example.com/progressive.mp4", "mp4"),
        ) as resolve_mock, patch(
            "backend.src.services.video_indexer.requests.get",
            return_value=response,
        ) as request_mock, patch(
            "backend.src.services.video_indexer.yt_dlp.YoutubeDL"
        ) as ydl_mock:
            output_path = Path(temp_dir) / "video.mp4"
            saved_path = service.download_youtube_video(
                "https://youtu.be/abc123xyz45",
                output_path=str(output_path),
            )

            self.assertEqual(saved_path, str(output_path))
            self.assertEqual(output_path.read_bytes(), b"abc123")

        resolve_mock.assert_called_once()
        request_mock.assert_called_once()
        ydl_mock.assert_not_called()

    def test_download_youtube_video_returns_clear_error_for_bot_challenge(self):
        ydl = MagicMock()
        ydl.download.side_effect = Exception(
            "ERROR: [youtube] abc123xyz45: Sign in to confirm you're not a bot."
        )
        ydl_context = MagicMock()
        ydl_context.__enter__.return_value = ydl
        ydl_context.__exit__.return_value = False

        service = VideoIndexerService()

        with patch(
            "backend.src.services.video_indexer.yt_dlp.YoutubeDL",
            return_value=ydl_context,
        ), self.assertRaisesRegex(
            Exception,
            "YouTube blocked the Azure server while downloading this video.",
        ):
            service.download_youtube_video("https://youtu.be/abc123xyz45")
