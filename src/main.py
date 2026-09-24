from pathlib import Path
import sys
import yt_dlp


# ============================================================
# CONFIG
# ============================================================

APP_NAME = "RetroRip"
VERSION = "0.2"

DOWNLOAD_DIR = Path("downloads")


# ============================================================
# UTILITIES
# ============================================================

def format_duration(seconds):
    if not seconds:
        return "Unknown"

    seconds = int(seconds)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours:
        return f"{hours:02}:{minutes:02}:{secs:02}"

    return f"{minutes:02}:{secs:02}"


def print_header():
    print()
    print("=" * 55)
    print(f"              {APP_NAME} v{VERSION}")
    print("       Rewind the web. Keep the media.")
    print("=" * 55)
    print()


# ============================================================
# MEDIA INFO
# ============================================================

def get_media_info(url):
    options = {
        "quiet": True,
        "no_warnings": True,

        # อย่าเพิ่งดาวน์โหลด
        "skip_download": True,

        # Playlist เอาแค่ตัวเดียวก่อน
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(
                url,
                download=False
            )

        return info

    except Exception as error:
        print()
        print("[ERROR] Cannot read media information.")
        print(error)

        return None


# ============================================================
# FORMAT
# ============================================================

def select_format():
    print()
    print("Select output format")
    print("-" * 35)
    print("[1] MP4 - Best")
    print("[2] MP4 - 1080p")
    print("[3] MP4 - 720p")
    print("[4] MP4 - 480p")
    print("[5] MP3 - Best Audio")
    print()

    choice = input("Select [1-5]: ").strip()

    formats = {

        "1": {
            "name": "MP4 Best",

            "format": (
                "bv*[ext=mp4]+ba[ext=m4a]"
                "/b[ext=mp4]"
                "/bv*+ba/b"
            ),

            "type": "video",
        },

        "2": {
            "name": "MP4 1080p",

            "format": (
                "bv*[height<=1080][ext=mp4]+ba[ext=m4a]"
                "/b[height<=1080][ext=mp4]"
                "/bv*[height<=1080]+ba/b[height<=1080]"
            ),

            "type": "video",
        },

        "3": {
            "name": "MP4 720p",

            "format": (
                "bv*[height<=720][ext=mp4]+ba[ext=m4a]"
                "/b[height<=720][ext=mp4]"
                "/bv*[height<=720]+ba/b[height<=720]"
            ),

            "type": "video",
        },

        "4": {
            "name": "MP4 480p",

            "format": (
                "bv*[height<=480][ext=mp4]+ba[ext=m4a]"
                "/b[height<=480][ext=mp4]"
                "/bv*[height<=480]+ba/b[height<=480]"
            ),

            "type": "video",
        },

        "5": {
            "name": "MP3",

            "format": "bestaudio/best",

            "type": "audio",
        },
    }

    return formats.get(choice)


# ============================================================
# PROGRESS
# ============================================================

def progress_hook(data):
    status = data.get("status")

    if status == "downloading":

        percent = data.get("_percent_str", "").strip()
        speed = data.get("_speed_str", "").strip()
        eta = data.get("_eta_str", "").strip()

        message = f"\r[DOWNLOAD] {percent}"

        if speed:
            message += f" | {speed}"

        if eta:
            message += f" | ETA {eta}"

        print(
            message,
            end="",
            flush=True
        )

    elif status == "finished":

        print()
        print("[PROCESS] Download finished.")
        print("[PROCESS] Processing media...")


# ============================================================
# DOWNLOAD
# ============================================================

def download_media(url, selected):
    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output_template = str(
        DOWNLOAD_DIR
        / "%(title).180B [%(id)s].%(ext)s"
    )

    options = {
        "format": selected["format"],

        "outtmpl": output_template,

        "noplaylist": True,

        "windowsfilenames": True,

        "progress_hooks": [
            progress_hook
        ],
    }

    # --------------------------------------------------------
    # MP4
    # --------------------------------------------------------

    if selected["type"] == "video":

        options["merge_output_format"] = "mp4"

    # --------------------------------------------------------
    # MP3
    # --------------------------------------------------------

    elif selected["type"] == "audio":

        options["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "0",
            }
        ]

    try:

        print()
        print(
            f"[OUTPUT] {selected['name']}"
        )

        print(
            f"[SAVE]   {DOWNLOAD_DIR.resolve()}"
        )

        print()

        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])

        print()
        print("=" * 55)
        print("DOWNLOAD COMPLETE")
        print("=" * 55)

        return True

    except Exception as error:

        print()
        print("=" * 55)
        print("DOWNLOAD FAILED")
        print("=" * 55)

        print(error)

        return False


# ============================================================
# MAIN
# ============================================================

def main():

    print_header()

    url = input(
        "Paste media URL: "
    ).strip()

    if not url:

        print(
            "[ERROR] No URL provided."
        )

        return

    print()
    print(
        "[INFO] Reading media information..."
    )

    info = get_media_info(url)

    if not info:
        return

    title = info.get(
        "title",
        "Unknown"
    )

    uploader = (
        info.get("uploader")
        or info.get("channel")
        or info.get("creator")
        or "Unknown"
    )

    extractor = info.get(
        "extractor_key",
        "Unknown"
    )

    duration = format_duration(
        info.get("duration")
    )

    print()
    print("=" * 55)
    print("MEDIA FOUND")
    print("=" * 55)

    print(
        f"Title    : {title}"
    )

    print(
        f"Creator  : {uploader}"
    )

    print(
        f"Platform : {extractor}"
    )

    print(
        f"Duration : {duration}"
    )

    print("=" * 55)

    selected = select_format()

    if selected is None:

        print()
        print(
            "[ERROR] Invalid option."
        )

        return

    print()
    print(
        f"Selected: {selected['name']}"
    )

    confirm = input(
        "Download? [Y/n]: "
    ).strip().lower()

    if confirm not in (
        "",
        "y",
        "yes"
    ):

        print(
            "Cancelled."
        )

        return

    download_media(
        url,
        selected
    )


if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:

        print()
        print()
        print(
            "[STOP] RetroRip interrupted."
        )

        sys.exit(0)