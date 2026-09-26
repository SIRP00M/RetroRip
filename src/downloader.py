from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import yt_dlp


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class MediaInfo:
    title: str
    creator: str
    platform: str
    duration: int | None
    webpage_url: str


@dataclass
class DownloadProfile:
    name: str
    format_selector: str
    media_type: str


# ============================================================
# DOWNLOAD PROFILES
# ============================================================

DOWNLOAD_PROFILES = {
    "1": DownloadProfile(
        name="MP4 Best",
        format_selector=(
            "bv*[ext=mp4]+ba[ext=m4a]"
            "/b[ext=mp4]"
            "/bv*+ba/b"
        ),
        media_type="video",
    ),

    "2": DownloadProfile(
        name="MP4 1080p",
        format_selector=(
            "bv*[height<=1080][ext=mp4]+ba[ext=m4a]"
            "/b[height<=1080][ext=mp4]"
            "/bv*[height<=1080]+ba/b[height<=1080]"
        ),
        media_type="video",
    ),

    "3": DownloadProfile(
        name="MP4 720p",
        format_selector=(
            "bv*[height<=720][ext=mp4]+ba[ext=m4a]"
            "/b[height<=720][ext=mp4]"
            "/bv*[height<=720]+ba/b[height<=720]"
        ),
        media_type="video",
    ),

    "4": DownloadProfile(
        name="MP4 480p",
        format_selector=(
            "bv*[height<=480][ext=mp4]+ba[ext=m4a]"
            "/b[height<=480][ext=mp4]"
            "/bv*[height<=480]+ba/b[height<=480]"
        ),
        media_type="video",
    ),

    "5": DownloadProfile(
        name="MP3 Best Audio",
        format_selector="bestaudio/best",
        media_type="audio",
    ),
}


# ============================================================
# RETRORIP ENGINE
# ============================================================

class RetroRipDownloader:

    def __init__(
        self,
        output_dir: str | Path = "downloads",
        progress_callback: Optional[Callable] = None,
        status_callback: Optional[Callable] = None,
    ):
        self.output_dir = Path(output_dir)

        self.progress_callback = progress_callback
        self.status_callback = status_callback

    # --------------------------------------------------------
    # CALLBACK HELPERS
    # --------------------------------------------------------

    def _status(self, message: str):

        if self.status_callback:
            self.status_callback(message)

    def _progress(self, data: dict):

        if self.progress_callback:
            self.progress_callback(data)

    # --------------------------------------------------------
    # FETCH MEDIA INFO
    # --------------------------------------------------------

    def get_info(self, url: str) -> MediaInfo:

        self._status(
            "Reading media information..."
        )

        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }

        with yt_dlp.YoutubeDL(options) as ydl:

            info = ydl.extract_info(
                url,
                download=False,
            )

        return MediaInfo(
            title=info.get(
                "title",
                "Unknown",
            ),

            creator=(
                info.get("uploader")
                or info.get("channel")
                or info.get("creator")
                or "Unknown"
            ),

            platform=(
                info.get("extractor_key")
                or info.get("extractor")
                or "Unknown"
            ),

            duration=info.get(
                "duration"
            ),

            webpage_url=info.get(
                "webpage_url",
                url,
            ),
        )

    # --------------------------------------------------------
    # yt-dlp DOWNLOAD PROGRESS
    # --------------------------------------------------------

    def _progress_hook(self, data: dict):

        status = data.get(
            "status"
        )

        if status == "downloading":

            downloaded = data.get(
                "downloaded_bytes",
                0,
            )

            total = (
                data.get("total_bytes")
                or data.get(
                    "total_bytes_estimate"
                )
            )

            percent = None

            if total:

                percent = (
                    downloaded
                    / total
                    * 100
                )

            progress_data = {
                "status": "downloading",

                "percent": percent,

                "downloaded_bytes":
                    downloaded,

                "total_bytes":
                    total,

                "speed":
                    data.get("speed"),

                "eta":
                    data.get("eta"),

                "filename":
                    data.get(
                        "filename"
                    ),
            }

            self._progress(
                progress_data
            )

        elif status == "finished":

            self._progress(
                {
                    "status": "finished",
                    "percent": 100,
                }
            )

            self._status(
                "Download complete. Processing..."
            )

    # --------------------------------------------------------
    # DOWNLOAD
    # --------------------------------------------------------

    def download(
        self,
        url: str,
        profile: DownloadProfile,
    ):

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_template = str(
            self.output_dir
            / "%(title).180B [%(id)s].%(ext)s"
        )

        options = {
            "format":
                profile.format_selector,

            "outtmpl":
                output_template,

            "noplaylist":
                True,

            "windowsfilenames":
                True,

            "progress_hooks": [
                self._progress_hook
            ],
        }

        # ====================================================
        # VIDEO MODE
        # ====================================================

        if profile.media_type == "video":

            options[
                "merge_output_format"
            ] = "mp4"

        # ====================================================
        # AUDIO MODE
        # ====================================================

        elif profile.media_type == "audio":

            options[
                "postprocessors"
            ] = [
                {
                    "key":
                        "FFmpegExtractAudio",

                    "preferredcodec":
                        "mp3",

                    "preferredquality":
                        "0",
                }
            ]

        self._status(
            f"Downloading: {profile.name}"
        )

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

            ydl.download(
                [url]
            )

        self._status(
            "Complete."
        )