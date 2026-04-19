import unittest
from unittest.mock import MagicMock, patch

import requests

from backend.src.services.video_indexer import (
    VideoIndexerService,
    extract_youtube_metadata,
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


class VideoIndexerDownloadTests(unittest.TestCase):
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
