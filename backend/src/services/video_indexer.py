"""
Connector : Python and Azure video indexer
"""
import logging
import os
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import requests
import yt_dlp
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

# Load the .env file
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

logger = logging.getLogger("video-indexer")
YOUTUBE_OEMBED_URL = "https://www.youtube.com/oembed"
YOUTUBE_AUTH_CHALLENGE_MARKERS = (
    "sign in to confirm you're not a bot",
    "sign in to confirm you\u2019re not a bot",
    "--cookies-from-browser",
    "--cookies",
    "authentication",
    "captcha",
    "login required",
)
YOUTUBE_DOWNLOAD_BLOCKED_MESSAGE = (
    "YouTube blocked the Azure server while downloading this video. "
    "The preview can still load, but the full audit cannot continue from this App Service for this video."
)
DEFAULT_MEDIA_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36"
    )
}


def normalize_youtube_url(url: str) -> tuple[str, str]:
    """
    Validates a supported YouTube URL and returns the video ID plus a canonical URL.
    """
    candidate = (url or "").strip()
    if not candidate:
        raise ValueError("Please provide a YouTube URL.")

    if "://" not in candidate:
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    host = parsed.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    video_id = None

    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif host in {"youtube.com", "m.youtube.com", "music.youtube.com"}:
        path = parsed.path.rstrip("/")
        if path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif path.startswith("/shorts/"):
            parts = [part for part in path.split("/") if part]
            video_id = parts[1] if len(parts) > 1 else None
        elif path.startswith("/embed/"):
            parts = [part for part in path.split("/") if part]
            video_id = parts[1] if len(parts) > 1 else None
        elif path.startswith("/live/"):
            parts = [part for part in path.split("/") if part]
            video_id = parts[1] if len(parts) > 1 else None

    if not video_id or not re.match(r"^[A-Za-z0-9_-]{6,}$", video_id):
        raise ValueError("Please provide a valid YouTube URL.")

    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    return video_id, canonical_url


def _build_youtube_ydl_options(download: bool, output_path: str | None = None) -> dict:
    options = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
        "http_headers": DEFAULT_MEDIA_REQUEST_HEADERS,
    }

    if download:
        options.update(
            {
                "format": "best",
                "outtmpl": output_path or "temp_video.mp4",
            }
        )
    else:
        options.update(
            {
                "skip_download": True,
                "extract_flat": False,
            }
        )

    return options


def _build_youtube_thumbnail_url(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def _build_display_title(source_name: str, fallback: str) -> str:
    candidate = unquote((source_name or "").strip())
    if not candidate:
        return fallback

    stem = Path(candidate).stem or candidate
    pretty_title = re.sub(r"[_-]+", " ", stem)
    pretty_title = re.sub(r"\s+", " ", pretty_title).strip()
    return pretty_title or fallback


def _is_youtube_auth_challenge_error(error: Exception | str) -> bool:
    error_text = str(error).lower()
    return any(marker in error_text for marker in YOUTUBE_AUTH_CHALLENGE_MARKERS)


def _is_direct_http_media_format(
    fmt: dict,
    *,
    require_audio: bool = True,
    require_video: bool = True,
) -> bool:
    if not fmt.get("url"):
        return False

    protocol = (fmt.get("protocol") or "").split("+")[0]
    if protocol not in {"http", "https"}:
        return False

    if require_audio and fmt.get("acodec") in {None, "none"}:
        return False

    if require_video and fmt.get("vcodec") in {None, "none"}:
        return False

    return True


def _youtube_format_sort_key(fmt: dict) -> tuple[int, int, int, int]:
    return (
        1 if (fmt.get("ext") or "").lower() == "mp4" else 0,
        fmt.get("height") or 0,
        int(fmt.get("tbr") or 0),
        int(fmt.get("filesize") or fmt.get("filesize_approx") or 0),
    )


def normalize_media_source_url(url: str) -> str:
    candidate = (url or "").strip()
    if not candidate:
        raise ValueError("Please provide a media URL.")

    if "://" not in candidate:
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Please provide a valid media URL.")

    return candidate


def _fetch_youtube_oembed_metadata(canonical_url: str, video_id: str) -> dict:
    response = requests.get(
        YOUTUBE_OEMBED_URL,
        params={"url": canonical_url, "format": "json"},
        timeout=10,
    )
    response.raise_for_status()

    data = response.json()
    title = (data.get("title") or "").strip()
    thumbnail_url = (data.get("thumbnail_url") or "").strip() or _build_youtube_thumbnail_url(
        video_id
    )
    if not title:
        raise ValueError("Missing title in oEmbed response.")

    return {
        "video_url": canonical_url,
        "source_type": "youtube",
        "source_label": video_id,
        "youtube_video_id": video_id,
        "title": title,
        "thumbnail_url": thumbnail_url,
    }


def extract_media_url_metadata(url: str) -> dict:
    canonical_url = normalize_media_source_url(url)
    parsed = urlparse(canonical_url)
    file_name = Path(unquote(parsed.path)).name
    source_label = file_name or parsed.netloc

    return {
        "video_url": canonical_url,
        "source_type": "media_url",
        "source_label": source_label,
        "youtube_video_id": None,
        "title": _build_display_title(source_label, "Remote media"),
        "thumbnail_url": None,
    }


def build_uploaded_file_preview(filename: str | None) -> dict:
    source_label = (filename or "uploaded-video.mp4").strip() or "uploaded-video.mp4"
    return {
        "video_url": f"uploaded://{source_label}",
        "source_type": "upload",
        "source_label": source_label,
        "youtube_video_id": None,
        "title": _build_display_title(source_label, "Uploaded video"),
        "thumbnail_url": None,
    }


def extract_youtube_metadata(url: str) -> dict:
    """
    Fetches YouTube metadata without downloading the video.
    """
    youtube_video_id, canonical_url = normalize_youtube_url(url)
    logger.info("Fetching YouTube metadata for %s", canonical_url)

    try:
        return _fetch_youtube_oembed_metadata(canonical_url, youtube_video_id)
    except Exception as exc:
        logger.warning("oEmbed metadata lookup failed for %s: %s", canonical_url, exc)

    try:
        with yt_dlp.YoutubeDL(_build_youtube_ydl_options(download=False)) as ydl:
            info = ydl.extract_info(canonical_url, download=False)
    except Exception as exc:
        if _is_youtube_auth_challenge_error(exc):
            raise ValueError(
                "Could not fetch YouTube metadata from the Azure server because YouTube "
                "requested additional bot verification for this video."
            ) from exc
        raise ValueError(f"Could not fetch YouTube metadata: {exc}") from exc

    thumbnails = info.get("thumbnails") or []
    thumbnail_url = info.get("thumbnail")
    if not thumbnail_url:
        for item in reversed(thumbnails):
            if item.get("url"):
                thumbnail_url = item["url"]
                break

    title = (info.get("title") or "").strip()
    if not title or not thumbnail_url:
        raise ValueError("Could not fetch YouTube metadata for this video.")

    return {
        "video_url": canonical_url,
        "source_type": "youtube",
        "source_label": youtube_video_id,
        "youtube_video_id": youtube_video_id,
        "title": title,
        "thumbnail_url": thumbnail_url,
    }


class VideoIndexerService:
    ARM_SCOPE = "https://management.azure.com/.default"
    MANAGEMENT_API_VERSION = "2024-01-01"

    def __init__(self):
        self.account_id = os.getenv("AZURE_VI_ACCOUNT_ID")
        self.location = os.getenv("AZURE_VI_LOCATION")
        self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        self.resource_group = os.getenv("AZURE_RESOURCE_GROUP")
        self.vi_name = os.getenv("AZURE_VI_NAME")
        self.credential = DefaultAzureCredential()

    def get_access_token(self):
        """
        Generates an ARM Access Token
        """
        try:
            token_object = self.credential.get_token(self.ARM_SCOPE)
            return token_object.token
        except Exception as exc:
            logger.error("Failed to get Azure token : %s", str(exc))
            raise

    def get_account_token(self, arm_access_token):
        """
        Exchanges the ARM token for Video Indexer account team
        """
        url = (
            f"https://management.azure.com/subscriptions/{self.subscription_id}"
            f"/resourceGroups/{self.resource_group}"
            f"/providers/Microsoft.VideoIndexer/accounts/{self.vi_name}"
            f"/generateAccessToken?api-version={self.MANAGEMENT_API_VERSION}"
        )
        headers = {"Authorization": f"Bearer {arm_access_token}"}
        payload = {"permissionType": "Contributor", "scope": "Account"}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            raise Exception(f"Failed to get the VI account token : {response.text}")
        vi_token = response.json().get("accessToken")
        if not vi_token:
            raise Exception("Failed to get the VI account token : missing accessToken in response")
        return vi_token

    @staticmethod
    def _extract_uploaded_video_id(response: requests.Response) -> str:
        try:
            response_data = response.json()
        except ValueError:
            response_data = {"id": response.text.strip().strip('"')}

        video_id = response_data.get("id") or response_data.get("videoId")
        if not video_id:
            raise Exception(f"Azure upload succeeded but no video id was returned : {response.text}")
        return video_id

    def resolve_youtube_stream_url(self, url: str) -> tuple[str, str]:
        _, canonical_url = normalize_youtube_url(url)
        logger.info("Resolving direct YouTube media stream for %s", canonical_url)

        try:
            with yt_dlp.YoutubeDL(_build_youtube_ydl_options(download=False)) as ydl:
                info = ydl.extract_info(canonical_url, download=False)
        except Exception as exc:
            if _is_youtube_auth_challenge_error(exc):
                raise Exception(YOUTUBE_DOWNLOAD_BLOCKED_MESSAGE) from exc
            raise Exception(f"Could not resolve a downloadable YouTube stream : {str(exc)}") from exc

        formats = info.get("formats") or []
        progressive_candidates = sorted(
            [
                fmt
                for fmt in formats
                if _is_direct_http_media_format(fmt, require_audio=True, require_video=True)
            ],
            key=_youtube_format_sort_key,
            reverse=True,
        )

        if not progressive_candidates and _is_direct_http_media_format(
            info,
            require_audio=True,
            require_video=True,
        ):
            progressive_candidates = [info]

        if not progressive_candidates:
            raise Exception(
                "Could not find a directly downloadable YouTube stream with both audio and video."
            )

        selected_format = progressive_candidates[0]
        return selected_format["url"], (selected_format.get("ext") or "mp4").lower()

    def download_video_stream(
        self,
        source_url: str,
        output_path: str,
        *,
        headers: dict[str, str] | None = None,
    ) -> str:
        logger.info("Downloading media stream to %s", output_path)

        with requests.get(
            source_url,
            headers=headers or DEFAULT_MEDIA_REQUEST_HEADERS,
            stream=True,
            timeout=(10, 120),
        ) as response:
            try:
                response.raise_for_status()
            except requests.RequestException as exc:
                raise Exception(f"Media stream download failed : {str(exc)}") from exc

            with open(output_path, "wb") as output_file:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        output_file.write(chunk)

        return output_path

    def download_youtube_video(self, url, output_path="temp_video.mp4"):
        """
        Downloads the YouTube video to a local file.
        """
        _, canonical_url = normalize_youtube_url(url)
        logger.info("Downloading Youtube Video : %s", canonical_url)

        try:
            stream_url, _ = self.resolve_youtube_stream_url(canonical_url)
            return self.download_video_stream(
                stream_url,
                output_path=output_path,
                headers={
                    **DEFAULT_MEDIA_REQUEST_HEADERS,
                    "Referer": canonical_url,
                },
            )
        except Exception as exc:
            if _is_youtube_auth_challenge_error(exc) or YOUTUBE_DOWNLOAD_BLOCKED_MESSAGE in str(exc):
                raise Exception(YOUTUBE_DOWNLOAD_BLOCKED_MESSAGE) from exc
            logger.warning(
                "Direct YouTube stream download failed for %s. Falling back to yt-dlp download. Error: %s",
                canonical_url,
                exc,
            )

        try:
            with yt_dlp.YoutubeDL(
                _build_youtube_ydl_options(download=True, output_path=output_path)
            ) as ydl:
                ydl.download([canonical_url])
            logger.info("Download Complete")
            return output_path
        except Exception as exc:
            if _is_youtube_auth_challenge_error(exc):
                raise Exception(YOUTUBE_DOWNLOAD_BLOCKED_MESSAGE) from exc
            raise Exception(f"Youtube Video Download Failed : {str(exc)}") from exc

    def upload_video(self, video_path, video_name):
        arm_token = self.get_access_token()
        vi_token = self.get_account_token(arm_token)

        api_url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos"

        params = {
            "accessToken": vi_token,
            "name": video_name,
            "privacy": "Private",
            "indexingPreset": "Default",
        }

        logger.info("Uploading file %s to Azure.......", video_path)

        # Open the file in binary mode and stream it to Azure.
        with open(video_path, "rb") as video_file:
            files = {"file": video_file}
            response = requests.post(api_url, params=params, files=files)

        if response.status_code not in (200, 202):
            raise Exception(f"Azure upload failed : {response.text}")
        return self._extract_uploaded_video_id(response)

    def upload_video_url(self, source_url: str, video_name: str):
        canonical_url = normalize_media_source_url(source_url)
        arm_token = self.get_access_token()
        vi_token = self.get_account_token(arm_token)

        api_url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos"
        params = {
            "accessToken": vi_token,
            "name": video_name,
            "privacy": "Private",
            "indexingPreset": "Default",
            "videoUrl": canonical_url,
        }

        logger.info("Submitting remote media URL %s to Azure Video Indexer.......", canonical_url)
        response = requests.post(api_url, params=params)
        if response.status_code not in (200, 202):
            raise Exception(f"Azure upload from URL failed : {response.text}")
        return self._extract_uploaded_video_id(response)

    def wait_for_processing(self, video_id):
        logger.info("Waiting for the video %s to process.....", video_id)
        while True:
            arm_token = self.get_access_token()
            vi_token = self.get_account_token(arm_token)

            url = f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos/{video_id}/Index"
            params = {"accessToken": vi_token}
            response = requests.get(url, params=params)
            if response.status_code != 200:
                raise Exception(f"Failed to fetch video insights : {response.text}")
            data = response.json()

            state = data.get("state")
            if state == "Processed":
                return data
            if state == "Failed":
                raise Exception("Video Indexing Failed in Azure")
            if state == "Quarantined":
                raise Exception("Video Quarantined (Copyright / Content Policy Violation)")
            logger.info("Status : %s.....waiting 30s", state)
            time.sleep(30)

    def extract_data(self, vi_json):
        """
        Parses the Azure response JSON into the workflow state format.
        """
        transcript_lines = []
        for video in vi_json.get("videos", []):
            for insight in video.get("insights", {}).get("transcript", []):
                transcript_lines.append(insight.get("text"))

        ocr_lines = []
        for video in vi_json.get("videos", []):
            for insight in video.get("insights", {}).get("ocr", []):
                ocr_lines.append(insight.get("text"))

        return {
            "transcript": " ".join(filter(None, transcript_lines)),
            "ocr_text": [line for line in ocr_lines if line],
            "video_metadata": {
                "duration": vi_json.get("summarizedInsights", {}).get("duration"),
                "platform": "youtube",
            },
        }
