"""Offline integration checks with real Qt widgets, threads and persistent SQLite."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from PySide6.QtCore import Qt, QPoint, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from PySide6.QtMultimedia import QMediaPlayer
from main import AppWindow
from downloader import MediaInfo, DownloadCancelled
from player import PlayerDialog
from storage import Store

APP=QApplication.instance() or QApplication([])
APP.setStyle("Fusion")


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.sound_patch=patch("studio.QSoundEffect",None); self.sound_patch.start()
        self.w=AppWindow(self.temp.name,demo=True); self.w.show()
        self.w.pump.stop(); self.w.studio.scene.timer.stop(); self.w.home_scene.timer.stop()
        APP.processEvents()
    def tearDown(self):
        self.w.close(); self.w.deleteLater(); APP.processEvents()
        self.sound_patch.stop(); self.temp.cleanup()
    def transition(self):
        self.w.studio.scene.start_time-=4
        self.w.studio.scene.tick(); APP.processEvents()
    def load(self,title="Tape one"):
        s=self.w.studio
        s.media_ready(MediaInfo(title,"Creator","Offline",120,"https://example.invalid/one",[720]),b"")
        self.transition()
    def start(self):
        self.w.studio.insert_tape(); self.transition(); self.w.studio.demo_timer.stop()
    def complete(self):
        s=self.w.studio; s.on_success(); self.transition(); s.keep_tape(); self.transition()
    def wait_for(self,predicate):
        end=time.monotonic()+4
        while not predicate() and time.monotonic()<end: QTest.qWait(10)
        self.assertTrue(predicate())

    def test_manual_lifecycle_custom_label_and_another_tape(self):
        w=self.w; s=w.studio; count=len(w.store.tapes())
        self.load(); s.name_edit.setText("My custom tape"); s.color_combo.setCurrentText("Plum")
        self.start(); w.navigate(2)
        s.on_progress({"status":"downloading","percent":55,"filename":"one"})
        self.assertEqual(s.state,"recording")
        self.complete(); tape=w.store.tapes()[0]
        self.assertEqual(len(w.store.tapes()),count+1)
        self.assertEqual(tape["title"],"My custom tape"); self.assertEqual(tape["color"],"#654763")
        self.assertTrue(tape["kept"]); self.assertTrue(Path(tape["path"]).is_file())
        s.new_tape(); self.assertEqual(s.state,"idle"); self.assertEqual(s.scene.quality,"")
        self.assertIsNone(s.media); self.assertIsNone(s.current_tape_id)
        self.load("Second tape"); self.start(); self.complete(); s.new_tape()
        self.assertEqual(s.scene.mode,"idle"); self.assertEqual(s.scene.saved_count,2)

    def test_themes_preferences_and_collection_survive_restart(self):
        w=self.w; w.apply_theme(True); w.save_quality("MP3 Best Audio"); w.save_sound(False)
        tape=w.store.tapes()[0]; w.store.update_tape(tape["id"],title="ชื่อเทปใหม่",color="#654763")
        self.assertEqual(len(w.store.tapes("ชื่อเทป")),1)
        w.close(); w.deleteLater(); APP.processEvents()
        self.w=AppWindow(self.temp.name,demo=False)
        self.assertTrue(self.w.dark); self.assertFalse(self.w.studio.sound_enabled)
        self.assertEqual(self.w.studio.default_profile,"MP3 Best Audio")
        self.assertEqual(self.w.store.tape(tape["id"])["title"],"ชื่อเทปใหม่")
        self.assertTrue(self.w.store.cover(tape["id"]))

    def test_queue_two_real_workers_continue_while_browsing(self):
        output=str(self.w.demo_audio()); calls=[]
        class Engine:
            def __init__(self,**kw): self.kw=kw
            def get_info(self,url): return MediaInfo(url.rsplit('/',1)[-1],"Test","Offline",3,url,[720])
            def download(self,url,profile):
                calls.append((url,profile.name))
                self.kw["progress_callback"]({"status":"downloading","percent":62,"filename":url})
                self.kw["status_callback"]("Processing media with FFmpeg...")
                return output
        w=self.w; s=w.studio; s.demo=False
        w.store.add_queue(["https://example.invalid/a","https://example.invalid/b"],"MP3 Best Audio")
        w.start_queue()
        with patch("studio.RetroRipDownloader",Engine):
            for _ in range(2):
                w.queue_tick(); self.wait_for(lambda:s.info_job is None)
                w.navigate(2); w.queue_tick(); self.transition()
                self.wait_for(lambda:s.download_job is None)
                self.assertEqual(s.state,"ejecting")
                self.transition(); w.queue_tick(); self.transition(); w.queue_tick()
        self.assertEqual([i["status"] for i in w.store.queue()],["complete","complete"])
        self.assertEqual(len(calls),2); self.assertEqual(s.state,"idle")
        self.assertEqual(s.default_profile,"MP4 Best")
        self.assertEqual(w.stack.currentIndex(),2)

    def test_cancel_analysis_does_not_start_download(self):
        w=self.w; s=w.studio
        w.store.add_queue(["https://example.invalid/a"],"MP4 Best"); w.start_queue(); w.queue_tick()
        w.cancel_queue_item(w.active_queue); s.load_demo_media(); w.queue_tick()
        self.assertEqual(w.store.queue()[0]["status"],"cancelled")
        self.assertEqual(s.state,"idle"); self.assertFalse(s.demo_timer.isActive())

    def test_queue_failure_continues_and_pause_holds_next(self):
        w=self.w; s=w.studio; s.demo=False
        class Engine:
            def __init__(self,**kw): pass
            def get_info(self,url): raise RuntimeError("offline fixture failure")
        w.store.add_queue(["https://example.invalid/a","https://example.invalid/b"],"MP4 Best")
        w.start_queue()
        with patch("studio.RetroRipDownloader",Engine):
            w.queue_tick(); self.wait_for(lambda:s.info_job is None); w.pause_queue(); w.queue_tick(); w.queue_tick()
        self.assertEqual([x["status"] for x in w.store.queue()],["failed","pending"])
        self.assertIsNone(w.active_queue)
        w.retry_queue_item(w.store.queue()[0]["id"])
        self.assertEqual(w.store.queue()[0]["status"],"pending")

    def test_stop_during_insertion_and_late_progress(self):
        s=self.w.studio; self.load(); s.insert_tape(); s.stop_download(); self.transition()
        self.assertEqual(s.state,"stopped"); self.assertFalse(s.demo_timer.isActive())
        s.retry(); self.start(); s.stop_download()
        s.on_progress({"status":"downloading","percent":99})
        self.assertEqual(s.state,"stopping"); s.on_cancelled(); self.transition()
        self.assertEqual(s.state,"stopped")

    def test_queue_owns_controls_and_rejects_malformed_links(self):
        w=self.w; w.queue_input.setText("http://["); w.add_queue()
        self.assertEqual(w.store.queue(),[])
        w.store.add_queue(["https://example.invalid/a"],"MP4 Best"); w.start_queue(); w.queue_tick()
        s=w.studio; s.load_demo_media()
        self.assertFalse(s.quality.isEnabled()); self.assertFalse(s.name_edit.isEnabled())
        s.new_tape(); self.assertEqual(s.state,"ready")
        w.cancel_queue_item(w.active_queue); w.queue_tick()
        self.assertEqual(s.state,"idle")

    def test_another_tape_restores_clean_scene_pixels(self):
        s=self.w.studio; self.w.navigate(1)
        def shot():
            s.scene.phase=s.scene.angle=s.scene.velocity=0
            APP.processEvents(); return s.scene.grab().toImage()
        before=shot(); self.load(); self.start(); self.complete(); s.new_tape()
        self.assertEqual(shot(),before)

    def test_progress_does_not_write_catalog_on_every_hook(self):
        w=self.w; self.load(); self.start(); w.active_queue="fixture"
        with patch.object(w.store,"update_queue") as update:
            for i in range(15): w.studio.on_progress({"status":"downloading","percent":i,"filename":"one"})
            self.assertEqual(update.call_count,0)
        w.active_queue=None; w.studio.stop_download()

    def test_all_pages_render_at_minimum_size_in_both_themes(self):
        w=self.w; w.resize(1100,780); self.load("Long name / "*30)
        for dark in (False,True):
            w.apply_theme(dark)
            for i in range(5):
                w.navigate(i); APP.processEvents(); self.assertFalse(w.grab().isNull())
                self.assertEqual(w.width(),1100)
        self.assertTrue(w.studio.rec_btn.isEnabled())

    def test_player_reads_local_file_pause_seek_and_stop(self):
        tape=self.w.store.tapes()[0]
        player=PlayerDialog(tape,self.w.store.cover(tape["id"]),True,self.w)
        player.show(); player.toggle(); player.scene.start_time-=4; player.scene.tick()
        self.wait_for(lambda:player.player.duration()>0)
        player.player.pause(); player.player.setPosition(1200); QTest.qWait(50)
        self.assertGreaterEqual(player.player.position(),1000)
        player.stop(); self.assertEqual(player.player.playbackState(),QMediaPlayer.StoppedState)
        self.assertEqual(player.player.position(),0); player.close()


class PersistenceTests(unittest.TestCase):
    def test_interrupted_queue_is_recovered_without_autostart(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(d); store.add_queue(["https://example.invalid/a"],"MP4 Best")
            key=store.queue()[0]["id"]; store.update_queue(key,status="recording"); store.close()
            store=Store(d); self.assertEqual(store.queue()[0]["status"],"pending"); store.close()


if __name__=="__main__": unittest.main()
