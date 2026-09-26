from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from threading import Event

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

    # Resolution ที่พบจริง
    resolutions: list[int]
    thumbnail_url: str | None = None


@dataclass
class DownloadProfile:
    name: str
    format_selector: str
    media_type: str

    height: int | None = None


# ============================================================
# PROFILE BUILDERS
# ============================================================

def create_video_profile(
    height: int | None = None,
) -> DownloadProfile:

    # --------------------------------------------------------
    # BEST QUALITY
    # --------------------------------------------------------

    if height is None:

        return DownloadProfile(
            name="MP4 Best",
            format_selector=(
                "bv*[ext=mp4]+ba[ext=m4a]"
                "/b[ext=mp4]"
                "/bv*+ba/b"
            ),
            media_type="video",
            height=None,
        )

    # --------------------------------------------------------
    # SPECIFIC RESOLUTION
    # --------------------------------------------------------

    return DownloadProfile(
        name=f"MP4 {height}p",

        format_selector=(
            f"bv*[height<={height}][ext=mp4]"
            f"+ba[ext=m4a]"
            f"/b[height<={height}][ext=mp4]"
            f"/bv*[height<={height}]"
            f"+ba"
            f"/b[height<={height}]"
        ),

        media_type="video",
        height=height,
    )


def create_audio_profile() -> DownloadProfile:

    return DownloadProfile(
        name="MP3 Best Audio",
        format_selector="bestaudio/best",
        media_type="audio",
    )


# ============================================================
# RETRORIP ENGINE
# ============================================================

class DownloadCancelled(Exception):
    """The user stopped the active download."""


class RetroRipDownloader:

    def __init__(
        self,
        output_dir: str | Path = "downloads",
        progress_callback: Optional[Callable] = None,
        status_callback: Optional[Callable] = None,
        cancel_event: Event | None = None,
    ):

        self.cancel_event = cancel_event or Event()

        self.output_dir = Path(
            output_dir
        )

        self.progress_callback = (
            progress_callback
        )

        self.status_callback = (
            status_callback
        )

    # ========================================================
    # CALLBACK HELPERS
    # ========================================================

    def _status(
        self,
        message: str,
    ):

        if self.status_callback:

            self.status_callback(
                message
            )

    def _progress(
        self,
        data: dict,
    ):

        if self.progress_callback:

            self.progress_callback(
                data
            )

    # ========================================================
    # FORMAT DETECTION
    # ========================================================

    def _extract_resolutions(
        self,
        formats: list,
    ) -> list[int]:

        resolutions = set()

        for fmt in formats:

            # -----------------------------------------------
            # Skip audio-only streams
            # -----------------------------------------------

            vcodec = fmt.get(
                "vcodec"
            )

            if (
                not vcodec
                or vcodec == "none"
            ):
                continue

            # -----------------------------------------------
            # Get height
            # -----------------------------------------------

            height = fmt.get(
                "height"
            )

            if not height:
                continue

            try:

                height = int(height)

            except (
                TypeError,
                ValueError,
            ):

                continue

            # -----------------------------------------------
            # Ignore nonsense values
            # -----------------------------------------------

            if height < 100:
                continue

            resolutions.add(
                height
            )

        # สูง -> ต่ำ

        return sorted(
            resolutions,
            reverse=True,
        )

    # ========================================================
    # GET MEDIA INFO
    # ========================================================

    def get_info(
        self,
        url: str,
    ) -> MediaInfo:

        self._status(
            "Reading media information..."
        )

        options = {

            "quiet":
                True,

            "no_warnings":
                True,

            "skip_download":
                True,

            "noplaylist":
                True,
        }

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

            info = ydl.extract_info(
                url,
                download=False,
            )

        formats = info.get(
            "formats",
            [],
        )

        resolutions = (
            self._extract_resolutions(
                formats
            )
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

            resolutions=resolutions,
            thumbnail_url=info.get("thumbnail"),
        )

    # ========================================================
    # PROGRESS HOOK
    # ========================================================

    def _progress_hook(
        self,
        data: dict,
    ):

        self._check_cancel()
        status = data.get(
            "status"
        )

        # ----------------------------------------------------
        # DOWNLOADING
        # ----------------------------------------------------

        if status == "downloading":

            downloaded = data.get(
                "downloaded_bytes",
                0,
            )

            total = (
                data.get(
                    "total_bytes"
                )
                or
                data.get(
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

                "status":
                    "downloading",

                "percent":
                    percent,

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

        # ----------------------------------------------------
        # FINISHED
        # ----------------------------------------------------

        elif status == "finished":

            self._progress(
                {
                    "status":
                        "finished",

                    "percent":
                        100,
                }
            )

            self._status(
                "Download finished. Processing media..."
            )

    def _check_cancel(self):
        if self.cancel_event.is_set():
            raise DownloadCancelled("Download stopped by user")

    def _postprocessor_hook(self, data):
        self._check_cancel()
        if data.get("status") == "started":
            self._status("Processing media with FFmpeg...")

    # ========================================================
    # DOWNLOAD
    # ========================================================

    def download(
        self,
        url: str,
        profile: DownloadProfile,
    ):

        self._check_cancel()
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

            "progress_hooks": [self._progress_hook],
            "postprocessor_hooks": [self._postprocessor_hook],
            "quiet": True,
            "no_warnings": True,
        }

        # ====================================================
        # VIDEO
        # ====================================================

        if (
            profile.media_type
            == "video"
        ):

            options[
                "merge_output_format"
            ] = "mp4"

        # ====================================================
        # AUDIO
        # ====================================================

        elif (
            profile.media_type
            == "audio"
        ):

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
            f"Downloading {profile.name}..."
        )

        with yt_dlp.YoutubeDL(
            options
        ) as ydl:

            result = ydl.download(
                [url]
            )
            if result != 0:
                raise RuntimeError("yt-dlp reported a download error")

        self._check_cancel()
        self._status(
            "Complete."
        )