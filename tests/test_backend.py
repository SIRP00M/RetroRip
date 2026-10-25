"""Real yt-dlp + FFmpeg conversion against a local HTTP fixture; no public website."""
import os
import sys
import tempfile
import threading
import unittest
import wave
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from downloader import RetroRipDownloader, create_audio_profile, DownloadCancelled


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args): pass


class BackendTests(unittest.TestCase):
    def test_conversion_returns_existing_final_mp3_path(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/"fixture.wav"
            with wave.open(str(source),"wb") as f:
                f.setnchannels(1); f.setsampwidth(2); f.setframerate(22050); f.writeframes(b"\0\0"*22050)
            server=ThreadingHTTPServer(("127.0.0.1",0),partial(QuietHandler,directory=d))
            thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            try:
                engine=RetroRipDownloader(Path(d)/"output")
                result=Path(engine.download(f"http://127.0.0.1:{server.server_port}/fixture.wav",create_audio_profile()))
                self.assertEqual(result.suffix,".mp3"); self.assertTrue(result.is_file()); self.assertGreater(result.stat().st_size,100)
            finally: server.shutdown(); server.server_close(); thread.join()

    def test_pre_cancelled_job_does_not_download(self):
        event=threading.Event(); event.set()
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(DownloadCancelled):
                RetroRipDownloader(d,cancel_event=event).download("https://example.invalid",create_audio_profile())


if __name__=="__main__": unittest.main()
