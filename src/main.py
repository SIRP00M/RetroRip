import sys

from downloader import (
    RetroRipDownloader,
    create_video_profile,
    create_audio_profile,
)


APP_NAME = "RetroRip"
VERSION = "0.4"


# ============================================================
# FORMAT HELPERS
# ============================================================

def format_duration(
    seconds,
):

    if seconds is None:
        return "Unknown"

    seconds = int(
        seconds
    )

    hours = (
        seconds // 3600
    )

    minutes = (
        seconds % 3600
    ) // 60

    secs = (
        seconds % 60
    )

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


def format_bytes(
    value,
):

    if value is None:
        return "?"

    units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
    ]

    size = float(
        value
    )

    for unit in units:

        if size < 1024:

            return (
                f"{size:.2f} "
                f"{unit}"
            )

        size /= 1024

    return (
        f"{size:.2f} PB"
    )


# ============================================================
# CALLBACKS
# ============================================================

def status_callback(
    message,
):

    print(
        f"\n[STATUS] {message}"
    )


def progress_callback(
    data,
):

    status = data.get(
        "status"
    )

    # ========================================================
    # DOWNLOADING
    # ========================================================

    if status == "downloading":

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

        # ----------------------------------------------------

        if percent is None:

            percent_text = (
                "??.?%"
            )

        else:

            percent_text = (
                f"{percent:5.1f}%"
            )

        # ----------------------------------------------------

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
                + format_bytes(
                    total
                )
            )

        if speed:

            message += (
                " | "
                + format_bytes(
                    speed
                )
                + "/s"
            )

        if eta is not None:

            message += (
                f" | ETA "
                f"{eta}s"
            )

        print(
            message,
            end="",
            flush=True,
        )

    # ========================================================
    # FINISHED
    # ========================================================

    elif status == "finished":

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
        "=" * 60
    )

    print(
        f"                  "
        f"{APP_NAME} v{VERSION}"
    )

    print(
        "          Rewind the web. Keep the media."
    )

    print(
        "=" * 60
    )

    print()


# ============================================================
# PROFILE MENU
# ============================================================

def build_profile_menu(
    resolutions,
):

    profiles = {}

    option = 1

    # ========================================================
    # BEST
    # ========================================================

    profiles[
        str(option)
    ] = create_video_profile()

    option += 1

    # ========================================================
    # RESOLUTIONS FROM MEDIA
    # ========================================================

    for height in resolutions:

        profiles[
            str(option)
        ] = create_video_profile(
            height
        )

        option += 1

    # ========================================================
    # MP3
    # ========================================================

    profiles[
        str(option)
    ] = create_audio_profile()

    return profiles


def show_profile_menu(
    profiles,
):

    print()
    print(
        "Available formats"
    )

    print(
        "-" * 42
    )

    for key, profile in (
        profiles.items()
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

    downloader = (
        RetroRipDownloader(

            output_dir=
                "downloads",

            progress_callback=
                progress_callback,

            status_callback=
                status_callback,
        )
    )

    # ========================================================
    # URL
    # ========================================================

    url = input(
        "Paste media URL: "
    ).strip()

    if not url:

        print(
            "[ERROR] URL is empty."
        )

        return

    # ========================================================
    # FETCH MEDIA INFO
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

    # ========================================================
    # MEDIA INFO
    # ========================================================

    print()

    print(
        "=" * 60
    )

    print(
        "MEDIA FOUND"
    )

    print(
        "=" * 60
    )

    print(
        f"Title       : "
        f"{media.title}"
    )

    print(
        f"Creator     : "
        f"{media.creator}"
    )

    print(
        f"Platform    : "
        f"{media.platform}"
    )

    print(
        f"Duration    : "
        f"{format_duration(media.duration)}"
    )

    # ========================================================
    # SHOW DETECTED RESOLUTIONS
    # ========================================================

    if media.resolutions:

        resolution_text = (
            ", ".join(
                f"{height}p"
                for height
                in media.resolutions
            )
        )

        print(
            f"Resolutions : "
            f"{resolution_text}"
        )

    else:

        print(
            "Resolutions : "
            "Unknown"
        )

    print(
        "=" * 60
    )

    # ========================================================
    # BUILD DYNAMIC MENU
    # ========================================================

    profiles = (
        build_profile_menu(
            media.resolutions
        )
    )

    show_profile_menu(
        profiles
    )

    # ========================================================
    # SELECT FORMAT
    # ========================================================

    choice = input(
        "Select format: "
    ).strip()

    profile = profiles.get(
        choice
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

    # ========================================================
    # CONFIRM
    # ========================================================

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
            "=" * 60
        )

        print(
            "DOWNLOAD FAILED"
        )

        print(
            "=" * 60
        )

        print(error)

        return

    # ========================================================
    # COMPLETE
    # ========================================================

    print()
    print()

    print(
        "=" * 60
    )

    print(
        "DOWNLOAD COMPLETE"
    )

    print(
        "=" * 60
    )


# ============================================================
# ENTRY POINT
# ============================================================

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