import sys

from downloader import (
    RetroRipDownloader,
    DOWNLOAD_PROFILES,
)


APP_NAME = "RetroRip"
VERSION = "0.3"


# ============================================================
# UTILITIES
# ============================================================

def format_duration(seconds):

    if seconds is None:
        return "Unknown"

    seconds = int(seconds)

    hours = seconds // 3600

    minutes = (
        seconds % 3600
    ) // 60

    secs = seconds % 60

    if hours:

        return (
            f"{hours:02}:"
            f"{minutes:02}:"
            f"{secs:02}"
        )

    return (
        f"{minutes:02}:"
        f"{secs:02}"
    )


def format_bytes(value):

    if value is None:
        return "?"

    units = [
        "B",
        "KB",
        "MB",
        "GB",
    ]

    size = float(value)

    for unit in units:

        if size < 1024:
            return f"{size:.2f} {unit}"

        size /= 1024

    return f"{size:.2f} TB"


# ============================================================
# CALLBACKS
# ============================================================

def status_callback(message):

    print(
        f"\n[STATUS] {message}"
    )


def progress_callback(data):

    if (
        data["status"]
        == "downloading"
    ):

        percent = data.get(
            "percent"
        )

        speed = data.get(
            "speed"
        )

        eta = data.get(
            "eta"
        )

        downloaded = data.get(
            "downloaded_bytes"
        )

        total = data.get(
            "total_bytes"
        )

        if percent is None:

            percent_text = "??.?%"

        else:

            percent_text = (
                f"{percent:5.1f}%"
            )

        message = (
            f"\r[DOWNLOAD] "
            f"{percent_text}"
        )

        if downloaded:

            message += (
                " | "
                + format_bytes(
                    downloaded
                )
            )

        if total:

            message += (
                " / "
                + format_bytes(total)
            )

        if speed:

            message += (
                " | "
                + format_bytes(speed)
                + "/s"
            )

        if eta is not None:

            message += (
                f" | ETA {eta}s"
            )

        print(
            message,
            end="",
            flush=True,
        )

    elif (
        data["status"]
        == "finished"
    ):

        print()

        print(
            "[DOWNLOAD] 100.0%"
        )


# ============================================================
# CLI
# ============================================================

def print_header():

    print()

    print(
        "=" * 58
    )

    print(
        f"                  "
        f"{APP_NAME} v{VERSION}"
    )

    print(
        "          Rewind the web. Keep the media."
    )

    print(
        "=" * 58
    )

    print()


def show_profiles():

    print()
    print("Available formats")
    print("-" * 40)

    for key, profile in (
        DOWNLOAD_PROFILES.items()
    ):

        print(
            f"[{key}] "
            f"{profile.name}"
        )

    print()


# ============================================================
# MAIN
# ============================================================

def main():

    print_header()

    downloader = RetroRipDownloader(
        output_dir="downloads",

        progress_callback=
            progress_callback,

        status_callback=
            status_callback,
    )

    url = input(
        "Paste media URL: "
    ).strip()

    if not url:

        print(
            "[ERROR] URL is empty."
        )

        return

    # ========================================================
    # FETCH INFO
    # ========================================================

    try:

        media = downloader.get_info(
            url
        )

    except Exception as error:

        print()
        print(
            "[ERROR] Could not read URL."
        )

        print(error)

        return

    print()

    print(
        "=" * 58
    )

    print(
        "MEDIA FOUND"
    )

    print(
        "=" * 58
    )

    print(
        f"Title    : "
        f"{media.title}"
    )

    print(
        f"Creator  : "
        f"{media.creator}"
    )

    print(
        f"Platform : "
        f"{media.platform}"
    )

    print(
        f"Duration : "
        f"{format_duration(media.duration)}"
    )

    print(
        "=" * 58
    )

    # ========================================================
    # PROFILE SELECT
    # ========================================================

    show_profiles()

    choice = input(
        "Select [1-5]: "
    ).strip()

    profile = (
        DOWNLOAD_PROFILES.get(
            choice
        )
    )

    if profile is None:

        print(
            "[ERROR] Invalid selection."
        )

        return

    print()

    print(
        f"Selected: "
        f"{profile.name}"
    )

    confirm = input(
        "Download? [Y/n]: "
    ).strip().lower()

    if confirm not in (
        "",
        "y",
        "yes",
    ):

        print(
            "Cancelled."
        )

        return

    # ========================================================
    # DOWNLOAD
    # ========================================================

    try:

        downloader.download(
            url,
            profile,
        )

    except Exception as error:

        print()
        print()

        print(
            "=" * 58
        )

        print(
            "DOWNLOAD FAILED"
        )

        print(
            "=" * 58
        )

        print(error)

        return

    print()
    print()

    print(
        "=" * 58
    )

    print(
        "DOWNLOAD COMPLETE"
    )

    print(
        "=" * 58
    )


if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print()
        print()

        print(
            "[STOP] "
            "RetroRip interrupted."
        )

        sys.exit(0)