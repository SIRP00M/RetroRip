# RetroRip — Pocket Studio 1.0

**A retro cassette-inspired desktop media downloader, player, and personal collection manager.**

[English](README.md) | [ภาษาไทย](README_TH.md)

RetroRip turns the process of downloading and organizing media into a virtual tape-recording experience. Its five-page desktop interface combines animated cassette mechanics with a persistent media library, download queue, playback, and customizable tape labels.

> **Version 1.0 source distribution.** This repository includes Windows helper scripts and a PyInstaller build script; no prebuilt `.exe` or installer is bundled. FFmpeg must be installed separately. Platform and third-party website compatibility are not guaranteed.

## Features

- **Home:** Start recording, access your recent tapes, or import an existing media file.
- **Studio:** Paste a URL, inspect media metadata, choose a tape name/color and quality, record, then keep the tape.
- **Collection:** Search by title or creator, play saved media, open files/folders, rename tape labels, and relink moved files.
- **Queue:** Add URLs on separate lines and process them sequentially, automatically recording and keeping completed tapes.
- **Settings:** Switch between light/dark themes; set download quality, mechanical sound, and output directory.
- **Persistent storage:** Keep collection metadata, cover images, queues, labels, and preferences in a local SQLite database.
- **Built-in playback:** Play supported media through Qt Multimedia, or open a file in an external application.
- **Offline demo:** Explore the UI, cassette animation, and short sample playback without downloading online media.

## Requirements

- Python **3.10 or newer**
- Dependencies from [`requirements.txt`](requirements.txt): PySide6 and yt-dlp
- **FFmpeg on your PATH** for merging separate video/audio streams and converting to MP3
- A supported operating system and multimedia codecs for in-app playback

Some websites may require an additional JavaScript runtime or access verification depending on yt-dlp and the website. Version 1.0 does **not** provide a UI for supplying accounts or browser cookies. Only download content you are entitled to access and follow the source service's terms.

## Get started on Windows

1. Install Python 3.10+ and FFmpeg; confirm `ffmpeg` works in your terminal.
2. Download/extract the project (or clone this repository).
3. Double-click **`INSTALL_WINDOWS.bat`** to install the dependencies.
4. Double-click **`RUN_WINDOWS.bat`** to launch RetroRip.

You can also run the demo from a terminal in the project directory:

```bat
RUN_WINDOWS.bat --demo
```

## Run from a terminal (Windows / macOS / Linux)

```bash
python -m venv .venv
```

Activate the virtual environment:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1
```

Then install and launch:

```bash
python -m pip install -r requirements.txt
python src/main.py
```

If in-app playback is unsupported by your system's media codecs, use **••• → Open file externally** instead.

## How to use

1. Open **Studio** and paste a media URL.
2. Wait for the metadata and available formats to load.
3. Choose a tape label, cassette color, and MP4/MP3 quality, then press **RECORD**.
4. Wait for the download and any required post-processing to finish.
5. Press **KEEP** to place the tape in your Collection. Completed downloads are also persisted before KEEP so they are not lost if the app closes.
6. Open **Collection** to search, play, relabel, locate, or relink your media.

For multiple URLs, use **Queue**: paste one URL per line, select **ADD TO STACK**, then **START QUEUE**. Items run sequentially.

### Behavior and limitations

- You can navigate between pages while recording; the bottom status bar provides a shortcut back to Studio.
- **PAUSE AFTER CURRENT** finishes the current queue item before pausing. **CANCEL** cancels that item only.
- Cassette deck controls include **REC**, **STOP**, and **EJECT**. EJECT returns an idle tape or requests a stop during recording.
- Relabeling changes the Collection display name, **not** the filename on disk.
- Collection actions do not move or delete the original media file.
- Queue items left unfinished when the app closes return to a waiting state on the next launch. Press **START QUEUE** to resume; the queue does not automatically restart.
- Canceling during FFmpeg processing may take until the current operation finishes. Temporary or completed output files may remain.
- Final video/audio merging can continue after an individual download stream reports 100%.

## Application data

RetroRip stores its collection, cover art, tape labels, queue, and preferences in **SQLite** under the operating system's application-data directory. Open the location from **Settings → OPEN DATA FOLDER**.

The default media output folder is **`Downloads/RetroRip`**, configurable in Settings.

```bash
python src/main.py --data-dir /path/to/custom/catalog
python src/main.py --demo
```

`--demo` simulates recording and plays a short sample (approximately three seconds). It does not download online media and uses isolated temporary catalog data unless you explicitly supply `--data-dir`.

## Build a Windows executable

After installing the dependencies, run:

```bat
BUILD_WINDOWS_EXE.bat
```

The expected output is **`dist/RetroRip/RetroRip.exe`**. Distribute the **entire `dist/RetroRip` folder**, not just the executable. FFmpeg must still be available on the destination PC's PATH.

The supplied ZIP contains source code and a build script, **not** a built executable. A real Windows build and runtime acceptance test have not been confirmed for this package.

## Tests

```bash
python -m unittest discover -s tests -v
```

The version 1.0 package documents Qt offscreen tests covering recording/KEEP/another tape, queue workers and page navigation, cancellation/retry, persisted themes and labels, page layouts in both themes, WAV playback controls, and local HTTP download plus MP3 conversion with yt-dlp/FFmpeg. These are package-reported test scenarios, **not a claim of new tests performed for this README update**.

Actual downloads from third-party services, account-restricted content, real Windows audio hardware, and installation on other machines have not been fully verified here.

## Project structure

| Path | Purpose |
| --- | --- |
| `src/main.py` | Application shell, navigation, Queue, Collection, Settings |
| `src/studio.py` | Studio flow and worker lifecycle |
| `src/deck_scene.py` | Cassette/deck visuals and animations |
| `src/downloader.py` | yt-dlp download backend and final media-path reporting |
| `src/storage.py` | SQLite persistence |
| `src/player.py` | Qt Multimedia player |
| `src/themes.py` | Light/dark theme styling |
| `src/assets/` | Icon and cassette click sound |
| `tests/` | Automated checks |
| `tools/render_preview.py` | Preview rendering utility |

## Licensing and third-party software

PySide6, yt-dlp, and FFmpeg have their own licenses and distribution obligations. FFmpeg binaries are not included in this source package. **The repository's current `LICENSE` file is empty**, so no project-wide open-source license grant should be assumed until the maintainer publishes one.
