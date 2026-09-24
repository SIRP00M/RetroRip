from pathlib import Path
import yt_dlp


def download_video(url: str):
    output_dir = Path("downloads")
    output_dir.mkdir(exist_ok=True)

    options = {
        # เลือกวิดีโอคุณภาพดีที่สุด + เสียงดีที่สุด
        # แล้วพยายามให้รวมออกมาเป็น MP4
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best",

        # ที่เก็บไฟล์
        "outtmpl": str(
            output_dir / "%(title)s [%(id)s].%(ext)s"
        ),

        # ถ้า video/audio แยก stream ให้รวมเป็น mp4
        "merge_output_format": "mp4",

        # ไม่โหลด playlist ทั้งก้อน
        "noplaylist": True,

        # ทำชื่อไฟล์ให้เหมาะกับ Windows
        "windowsfilenames": True,
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])

        print("\n==============================")
        print("Download complete!")
        print("==============================")

    except Exception as e:
        print("\nDownload failed:")
        print(e)


def main():
    print("==============================")
    print("         RetroRip v0.1")
    print("==============================")
    print()

    url = input("Paste URL: ").strip()

    if not url:
        print("No URL provided.")
        return

    download_video(url)


if __name__ == "__main__":
    main()