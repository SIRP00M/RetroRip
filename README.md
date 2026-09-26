# RetroRip • Cassette Deck

A desktop media downloader powered by yt-dlp. Use it for media you have permission to save, subject to the platform's terms.

## Windows quick start

In the extracted `retrorip` folder:

```powershell
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python src\main.py
```

Install [FFmpeg](https://ffmpeg.org/download.html) and make `ffmpeg` available on your PATH for merging video/audio and converting MP3. If your existing repository uses `src/main.py`, copy `src/main.py`, `src/downloader.py`, and the entire `src/assets` directory into its `src` directory.

Paste a URL and choose **LOAD TAPE**. Select a quality from the resolutions that yt-dlp found, then press **REC**. **STOP** requests cancellation during an active transfer; it may leave a partial file in the output directory and can take time during FFmpeg processing. **EJECT** clears the loaded media after the active job has ended. The cover art is optional; a built-in label appears if the thumbnail is unavailable. Sound needs an available audio output device.
