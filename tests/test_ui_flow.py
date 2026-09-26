"""Offline state-flow checks using real Qt widgets (no media is downloaded)."""
import os
import sys
import unittest
import time
from unittest.mock import patch
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from main import RetroRipWindow
from downloader import MediaInfo

APP = QApplication.instance() or QApplication([])
APP.setStyle("Fusion")


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.window = RetroRipWindow(demo=True)
        self.window.sound_enabled = False
        self.window.show()
        APP.processEvents()
        self.errors = []
        self.window.show_error = lambda title, message: self.errors.append((title, message))

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()

    def load(self, title="Night drive / city lights"):
        picture = QPixmap(160,90)
        picture.fill(QColor("#c36d46"))
        data=QByteArray()
        buffer=QBuffer(data)
        buffer.open(QIODevice.WriteOnly)
        picture.save(buffer,"PNG")
        media = MediaInfo(title,"Studio","Test",123,"https://example.invalid/demo",[1080,720])
        self.window.media_ready(media,bytes(data))
        self.transition()
        return media

    def transition(self):
        scene=self.window.scene
        scene.start_time -= 3
        scene.tick()
        APP.processEvents()

    def start(self):
        self.window.insert_tape()
        self.assertEqual(self.window.state,"inserting")
        self.transition()
        self.window.demo_timer.stop()
        self.assertEqual(self.window.state,"recording")

    def test_success_full_lifecycle_and_second_tape(self):
        w=self.window
        self.assertEqual(w.state,"idle")
        self.load()
        self.assertFalse(w.scene.cover.isNull())
        self.assertEqual(w.quality.count(),4)
        self.start()
        w.on_progress({"status":"downloading","percent":100,"filename":"video","downloaded_bytes":100})
        w.on_progress({"status":"finished"})
        self.assertEqual(w.state,"recording")  # End of video stream must NOT eject.
        w.on_progress({"status":"downloading","percent":20,"filename":"audio","downloaded_bytes":20})
        self.assertEqual(w.stream_number,2)
        self.assertEqual(w.progress_bar.value(),200)
        w.on_status("Processing media with FFmpeg...")
        self.assertEqual(w.state,"processing")
        self.assertEqual(w.scene.mode,"processing")
        w.on_success()
        self.assertEqual(w.state,"ejecting")
        self.transition()
        self.assertEqual(w.state,"complete")
        w.keep_tape()
        self.assertEqual(w.state,"archiving")
        self.transition()
        self.assertEqual(w.state,"archived")
        self.assertEqual(w.scene.saved_count,1)
        self.assertEqual(w.scene.saved_title,"Night drive / city lights")
        w.new_tape()
        self.assertEqual(w.state,"idle")
        self.assertIsNone(w.media)
        self.assertEqual(w.scene.saved_count,1)

    def test_another_tape_restores_clean_scene_after_repeated_recordings(self):
        w = self.window
        w.scene.timer.stop()

        def snapshot():
            w.scene.phase = 0
            w.scene.angle = 0
            w.scene.update()
            APP.processEvents()
            return w.scene.grab().toImage()

        fresh_scene = snapshot()
        for count in (1, 2):
            self.load(f"Tape {count}")
            self.start()
            w.on_success()
            self.transition()
            w.keep_tape()
            self.transition()
            self.assertEqual(w.state, "archived")
            w.new_tape()
            self.assertEqual(w.state, "idle")
            self.assertEqual(w.scene.saved_count, count)
            self.assertEqual(snapshot(), fresh_scene,
                             "Previous sleeve overlaps the next tape's landing scene")

    def test_cancel_during_insertion_never_starts_download(self):
        self.load()
        w=self.window
        w.insert_tape()
        w.stop_download()
        self.assertEqual(w.state,"stopped")
        self.assertFalse(w.demo_timer.isActive())
        self.assertIsNone(w.download_job)
        self.assertEqual(w.scene.saved_count,0)
        self.transition()
        self.assertEqual(w.state,"stopped")
        w.retry()
        self.assertEqual(w.state,"ready")

    def test_error_returns_tape_without_archiving(self):
        self.load()
        self.start()
        w=self.window
        w.on_failed("Network unavailable")
        self.transition()
        self.assertEqual(w.state,"stopped")
        self.assertEqual(w.scene.saved_count,0)
        self.assertEqual(len(self.errors),1)
        w.keep_tape()
        self.assertEqual(w.state,"stopped")

    def test_cancelled_recording_ignores_late_progress(self):
        self.load()
        self.start()
        w=self.window
        w.stop_download()
        self.assertEqual(w.state,"stopping")
        w.on_progress({"status":"downloading","percent":99})
        self.assertEqual(w.state,"stopping")
        w.on_cancelled()
        self.transition()
        self.assertEqual(w.state,"stopped")
        self.assertEqual(w.scene.saved_count,0)

    def test_real_qthreads_deliver_results_and_release_workers(self):
        class FakeEngine:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
            def get_info(self, url):
                return MediaInfo("Worker tape", "Test", "Offline", 60, url, [720])
            def download(self, url, profile):
                self.kwargs["progress_callback"]({"status":"downloading", "percent":60, "filename":"test"})
                self.kwargs["status_callback"]("Processing media with FFmpeg...")

        def wait_for(predicate):
            deadline=time.monotonic()+3
            while not predicate() and time.monotonic()<deadline:
                QTest.qWait(10)
            self.assertTrue(predicate())

        w=self.window
        w.demo=False
        with patch("main.RetroRipDownloader", FakeEngine):
            w.url_input.setText("https://example.invalid/worker")
            w.analyze()
            wait_for(lambda: w.info_job is None)
            self.assertEqual(w.state,"ready")
            w.insert_tape()
            self.transition()
            wait_for(lambda: w.download_job is None)
            self.assertEqual(w.state,"ejecting")
            self.transition()
            self.assertEqual(w.state,"complete")

    def test_long_title_and_minimum_window_render(self):
        self.load("ยามค่ำคืนกับเพลงโปรด • " * 30)
        w=self.window
        w.resize(920,740)
        APP.processEvents()
        self.assertEqual(w.width(),920)
        self.assertLessEqual(w.pages.geometry().right(),w.width())
        self.assertFalse(w.grab().isNull())


if __name__ == "__main__":
    unittest.main()
