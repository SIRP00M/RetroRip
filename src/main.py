"""RetroRip 0.7 — a portable recorder for the web.
Run with --demo to preview the entire UI sequence without a network download.
"""
import math
import os
import sys
import time
from pathlib import Path
from threading import Event
from urllib.request import Request, urlopen

from PySide6.QtCore import QThread, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QSizePolicy, QStackedWidget, QVBoxLayout, QWidget,
)
try:
    from PySide6.QtMultimedia import QSoundEffect
except ImportError:
    QSoundEffect = None

from deck_scene import DeckScene
from downloader import DownloadCancelled, MediaInfo, RetroRipDownloader, create_audio_profile, create_video_profile

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent / "assets"
VERSION = "0.7.1"


def duration_text(seconds):
    if seconds is None:
        return "LIVE / UNKNOWN"
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}" if hours else f"{minutes:02}:{seconds:02}"


def size_text(value):
    if value is None:
        return "—"
    number = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if number < 1024 or unit == "GB":
            return f"{number:.1f} {unit}"
        number /= 1024


class ElidedLabel(QLabel):
    """Long media titles and paths never stretch the window."""
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.full_text = text
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setText(text)

    def setText(self, text):
        self.full_text = str(text)
        self.setToolTip(self.full_text)
        super().setText(self.fontMetrics().elidedText(self.full_text, Qt.ElideRight, max(20, self.width())))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QLabel.setText(self, self.fontMetrics().elidedText(self.full_text, Qt.ElideRight, max(20, self.width())))


def text_label(text, name="", parent=None, elide=False):
    widget = ElidedLabel(text, parent) if elide else QLabel(text, parent)
    widget.setTextFormat(Qt.PlainText)
    if name:
        widget.setObjectName(name)
    return widget


def button(text, callback, name=""):
    b = QPushButton(text)
    b.setObjectName(name)
    b.setCursor(Qt.PointingHandCursor)
    b.clicked.connect(callback)
    return b


class InfoJob(QThread):
    result = Signal(object, bytes)
    failed = Signal(str)

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self.url = url

    def run(self):
        try:
            media = RetroRipDownloader().get_info(self.url)
            picture = b""
            if media.thumbnail_url and media.thumbnail_url.startswith(("https://", "http://")):
                try:
                    request = Request(media.thumbnail_url, headers={"User-Agent": "Mozilla/5.0"})
                    with urlopen(request, timeout=6) as response:
                        if response.headers.get_content_type().startswith("image/"):
                            picture = response.read(2_000_001)
                            if len(picture) > 2_000_000:
                                picture = b""
                except Exception:
                    pass
            self.result.emit(media, picture)
        except Exception as exc:
            self.failed.emit(str(exc))


class DownloadJob(QThread):
    progress = Signal(object)
    status = Signal(str)
    success = Signal()
    cancelled = Signal()
    failed = Signal(str)

    def __init__(self, url, profile, folder, parent=None):
        super().__init__(parent)
        self.url, self.profile, self.folder = url, profile, folder
        self.cancel_event = Event()
        self.last_progress_emit = 0.0

    def forward_progress(self, data):
        now = time.monotonic()
        if data.get("status") != "downloading" or now - self.last_progress_emit >= .05:
            self.last_progress_emit = now
            self.progress.emit(data)

    def run(self):
        try:
            engine = RetroRipDownloader(
                output_dir=self.folder, progress_callback=self.forward_progress,
                status_callback=self.status.emit, cancel_event=self.cancel_event,
            )
            engine.download(self.url, self.profile)
            if self.cancel_event.is_set():
                self.cancelled.emit()
            else:
                self.success.emit()
        except Exception as exc:
            if isinstance(exc, DownloadCancelled) or self.cancel_event.is_set():
                self.cancelled.emit()
            else:
                self.failed.emit(str(exc))


class RetroRipWindow(QMainWindow):
    def __init__(self, demo=False):
        super().__init__()
        self.demo = demo
        self.state = "idle"
        self.media = None
        self.loaded_url = ""
        self.profiles = []
        self.info_job = self.download_job = None
        self.output_folder = str(ROOT / "downloads")
        self.pending_outcome = "success"
        self.failure_message = ""
        self.stream_number = 0
        self.stream_filename = None
        self.transfer_percent = None
        self.sound_enabled = True
        self.sound = None
        self.demo_progress = 0.0
        self.demo_timer = QTimer(self)
        self.demo_timer.setInterval(100)
        self.demo_timer.timeout.connect(self.demo_tick)
        self.setWindowTitle(f"RetroRip • Pocket Studio {VERSION}" + (" • DEMO" if demo else ""))
        self.resize(1120, 830)
        self.setMinimumSize(920, 740)
        self.make_ui()
        self.setStyleSheet(STYLE)
        if QSoundEffect:
            self.sound = QSoundEffect(self)
            self.sound.setSource(QUrl.fromLocalFile(str(ASSETS / "clack.wav")))
            self.sound.setVolume(.3)
        else:
            self.sound_btn.setEnabled(False)
            self.sound_btn.setText("SOUND UNAVAILABLE")
        self.update_state("idle")

    def make_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(34, 22, 34, 15)
        root.setSpacing(10)
        nav = QHBoxLayout()
        nav.addWidget(text_label("▰  RETRORIP", "brand"))
        nav.addWidget(text_label("POCKET STUDIO  /  01", "navSmall"))
        nav.addStretch()
        self.sound_btn = button("SOUND ON", self.toggle_sound, "quiet")
        nav.addWidget(self.sound_btn)
        self.count_label = text_label("000 TAPES KEPT", "navSmall")
        nav.addWidget(self.count_label)
        root.addLayout(nav)
        rule = QFrame()
        rule.setObjectName("rule")
        rule.setFixedHeight(1)
        root.addWidget(rule)

        headline_row = QHBoxLayout()
        headings = QVBoxLayout()
        headings.setSpacing(0)
        self.headline = text_label("Make it a mixtape.", "headline")
        self.subheading = text_label("Your favorites, with a little analog soul.", "subheading")
        headings.addWidget(self.headline)
        headings.addWidget(self.subheading)
        headline_row.addLayout(headings)
        headline_row.addStretch()
        self.step_label = text_label("01  LINK     /     02  RECORD     /     03  KEEP", "steps")
        headline_row.addWidget(self.step_label, 0, Qt.AlignBottom)
        root.addLayout(headline_row)
        self.scene = DeckScene()
        self.scene.inserted.connect(self.begin_download)
        self.scene.ejected.connect(self.on_ejected)
        self.scene.archived.connect(self.on_archived)
        self.scene.mechanical.connect(self.clack)
        root.addWidget(self.scene, 1)

        self.panel = QFrame()
        self.panel.setObjectName("panel")
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(25, 17, 25, 17)
        self.pages = QStackedWidget()
        self.pages.setFixedHeight(119)
        panel_layout.addWidget(self.pages)
        root.addWidget(self.panel)
        self.build_input_page()
        self.build_ready_page()
        self.build_record_page()
        self.build_complete_page()
        self.build_archived_page()
        self.build_stopped_page()

        footer = QHBoxLayout()
        self.folder_label = text_label("SAVING TO  /  " + self.output_folder, "footer", elide=True)
        self.folder_label.setMinimumWidth(0)
        footer.addWidget(self.folder_label, 1)
        self.change_btn = button("CHANGE", self.choose_folder, "quiet")
        footer.addWidget(self.change_btn)
        footer.addWidget(button("OPEN FOLDER ↗", self.open_folder, "quiet"))
        root.addLayout(footer)
        self.footer_status = text_label("YOUTUBE  ·  TIKTOK  ·  FACEBOOK       /       REWIND THE WEB. KEEP THE MEDIA.", "footerTiny")
        root.addWidget(self.footer_status)

    def new_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(9)
        self.pages.addWidget(page)
        return page, layout

    def build_input_page(self):
        self.input_page, layout = self.new_page()
        layout.addWidget(text_label("01  /  START WITH A LINK", "eyebrow"))
        row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste a video or audio link here…")
        self.url_input.setClearButtonEnabled(True)
        self.url_input.returnPressed.connect(self.analyze)
        row.addWidget(self.url_input,1)
        self.load_btn = button("MAKE A TAPE   →",self.analyze,"primary")
        self.load_btn.setMinimumWidth(190)
        row.addWidget(self.load_btn)
        layout.addLayout(row)
        self.input_hint = text_label("We'll make the label. You choose the quality.", "hint")
        layout.addWidget(self.input_hint)

    def build_ready_page(self):
        self.ready_page, layout = self.new_page()
        self.media_title = text_label("YOUR TAPE", "panelTitle", elide=True)
        layout.addWidget(self.media_title)
        row = QHBoxLayout()
        self.quality = QComboBox()
        self.quality.setMinimumWidth(240)
        row.addWidget(self.quality,1)
        row.addWidget(button("CHANGE LINK",self.new_tape,"secondary"))
        self.rec_btn = button("●  RECORD THIS TAPE",self.insert_tape,"primary")
        row.addWidget(self.rec_btn)
        layout.addLayout(row)
        self.media_meta = text_label("", "hint", elide=True)
        layout.addWidget(self.media_meta)

    def build_record_page(self):
        self.record_page, layout = self.new_page()
        upper = QHBoxLayout()
        self.record_label = text_label("02  /  RECORDING", "eyebrow")
        self.percent_label = text_label("—", "readout")
        upper.addWidget(self.record_label)
        upper.addStretch()
        upper.addWidget(self.percent_label)
        layout.addLayout(upper)
        row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0,1000)
        self.progress_bar.setTextVisible(False)
        row.addWidget(self.progress_bar,1)
        self.stop_btn = button("■  STOP",self.stop_download,"secondary")
        self.stop_btn.setMinimumWidth(130)
        row.addWidget(self.stop_btn)
        layout.addLayout(row)
        self.transfer_label = text_label("Sliding the tape into place…", "hint")
        layout.addWidget(self.transfer_label)

    def build_complete_page(self):
        self.complete_page, layout = self.new_page()
        layout.addWidget(text_label("03  /  A LITTLE SOMETHING TO KEEP", "eyebrow"))
        row = QHBoxLayout()
        self.complete_title = text_label("Your recording is ready.", "panelTitle", elide=True)
        row.addWidget(self.complete_title,1)
        row.addWidget(button("OK  ·  KEEP MY TAPE   ↘",self.keep_tape,"primary"))
        layout.addLayout(row)
        layout.addWidget(text_label("Your file is saved. Tuck the tape into its sleeve.", "hint"))

    def build_archived_page(self):
        self.archived_page, layout = self.new_page()
        layout.addWidget(text_label("FILE SAVED  /  TAPE KEPT", "eyebrow"))
        row = QHBoxLayout()
        row.addWidget(text_label("One for the collection.", "panelTitle"),1)
        row.addWidget(button("OPEN DOWNLOADS ↗",self.open_folder,"secondary"))
        row.addWidget(button("MAKE ANOTHER TAPE   +",self.new_tape,"primary"))
        layout.addLayout(row)
        layout.addWidget(text_label("The sleeve is your keepsake. The media is in your output folder.", "hint"))

    def build_stopped_page(self):
        self.stopped_page, layout = self.new_page()
        self.stopped_title = text_label("RECORDING STOPPED", "eyebrow")
        layout.addWidget(self.stopped_title)
        row = QHBoxLayout()
        self.stopped_hint = text_label("You can try again or load another link.", "hint")
        self.stopped_hint.setWordWrap(True)
        row.addWidget(self.stopped_hint,1)
        row.addWidget(button("NEW LINK",self.new_tape,"secondary"))
        self.retry_btn = button("TRY AGAIN   ↻",self.retry,"primary")
        row.addWidget(self.retry_btn)
        layout.addLayout(row)

    def update_state(self, state):
        self.state = state
        pages = {
            "idle": self.input_page, "analyzing": self.input_page, "ready": self.ready_page,
            "inserting": self.record_page, "recording": self.record_page, "processing": self.record_page,
            "stopping": self.record_page, "ejecting": self.record_page, "complete": self.complete_page,
            "archiving": self.complete_page, "archived": self.archived_page, "stopped": self.stopped_page,
        }
        self.pages.setCurrentWidget(pages[state])
        text = {
            "idle": ("Make it a mixtape.", "Your favorites, with a little analog soul."),
            "analyzing": ("Let's make a label.", "Finding the title, artwork and available qualities."),
            "ready": ("This one's yours.", "Choose a format, then let the reels do their thing."),
            "inserting": ("A little analog magic.", "Loading your cassette into the recorder."),
            "recording": ("Good things take a spin.", "Recording your favorite corner of the internet."),
            "processing": ("The finishing touches.", "Preparing the final media file. Almost there."),
            "stopping": ("Bringing the reels to rest.", "Waiting for the current transfer or processing step to stop."),
            "ejecting": ("Fresh off the tape.", "Opening the door and handing your cassette back."),
            "complete": ("Made to keep.", "A cover. A name. A little piece of the internet."),
            "archiving": ("Right where it belongs.", "Tucking your tape into its own sleeve."),
            "archived": ("A keeper, indeed.", "Your recording is saved. There's always room for another."),
            "stopped": ("Take it from the top.", "Your tape is out. Ready whenever you are."),
        }
        title, subtitle = text[state]
        self.headline.setText(title)
        self.subheading.setText(subtitle)
        active = state not in ("idle","ready","complete","archived","stopped")
        self.change_btn.setEnabled(not active)
        self.load_btn.setEnabled(state == "idle" and self.info_job is None)
        self.url_input.setEnabled(state == "idle")
        self.rec_btn.setEnabled(state == "ready" and self.info_job is None and self.download_job is None)
        self.retry_btn.setEnabled(state == "stopped" and self.download_job is None)
        self.stop_btn.setEnabled(state in ("inserting","recording","processing"))
        self.complete_page.setEnabled(state == "complete")
        self.quality.setEnabled(state == "ready")
        if self.demo:
            self.footer_status.setText("DEMO MODE  /  ANIMATION PREVIEW ONLY — NO MEDIA IS DOWNLOADED")

    @Slot()
    def toggle_sound(self):
        self.sound_enabled = not self.sound_enabled
        self.sound_btn.setText("SOUND ON" if self.sound_enabled else "SOUND OFF")
        self.clack()

    @Slot()
    def clack(self):
        if self.sound and self.sound_enabled and self.sound.isLoaded():
            self.sound.stop()
            self.sound.play()

    @Slot()
    def analyze(self):
        if self.state != "idle" or self.info_job or self.download_job:
            return
        url = self.url_input.text().strip()
        if not url and not self.demo:
            self.input_hint.setText("Paste a link to make your first tape.")
            self.url_input.setFocus()
            return
        if not self.demo and not url.lower().startswith(("http://","https://")):
            self.input_hint.setText("Use a complete link beginning with https:// or http://.")
            return
        self.clack()
        self.loaded_url = url
        self.update_state("analyzing")
        self.scene.set_mode("analyzing")
        self.input_hint.setText("Reading the label and looking for cover art…")
        if self.demo:
            QTimer.singleShot(650,self.load_demo_media)
            return
        self.info_job = InfoJob(url,self)
        self.info_job.result.connect(self.media_ready)
        self.info_job.failed.connect(self.info_failed)
        self.info_job.finished.connect(self.info_finished)
        self.info_job.start()

    @Slot(object,bytes)
    def media_ready(self,media,picture):
        self.media = media
        self.profiles = [create_video_profile()]
        self.profiles.extend(create_video_profile(h) for h in media.resolutions)
        self.profiles.append(create_audio_profile())
        self.quality.clear()
        self.quality.addItems([p.name for p in self.profiles])
        self.media_title.setText(media.title)
        self.media_title.setToolTip(media.title)
        self.media_meta.setText(f"{media.creator}   /   {media.platform}   /   {duration_text(media.duration)}")
        self.scene.load(media.title,media.creator,media.platform,duration_text(media.duration),picture)
        self.update_state("ready")

    @Slot(str)
    def info_failed(self,message):
        self.update_state("idle")
        self.scene.reset()
        self.input_hint.setText("Could not read this link. Check it and try again.")
        self.input_hint.setToolTip(message)
        self.show_error("Could not load media",message)

    @Slot()
    def info_finished(self):
        job = self.info_job
        self.info_job = None
        if job:
            job.deleteLater()
        self.update_state(self.state)

    @Slot()
    def insert_tape(self):
        if self.state != "ready" or not self.media or self.info_job or self.download_job:
            return
        self.stream_number = 0
        self.stream_filename = None
        self.transfer_percent = None
        self.progress_bar.setRange(0,0)
        self.percent_label.setText("LOADING")
        self.record_label.setText("02  /  LOADING YOUR TAPE")
        self.transfer_label.setText("Sliding the tape into place…")
        self.pending_outcome = "success"
        self.update_state("inserting")
        self.scene.insert()

    @Slot()
    def begin_download(self):
        if self.state != "inserting":
            return
        self.update_state("recording")
        self.record_label.setText("02  /  RECORDING")
        self.percent_label.setText("CONNECTING")
        self.transfer_label.setText("Connecting to the media stream…")
        self.scene.set_mode("recording")
        if self.demo:
            self.demo_progress = 0
            self.demo_timer.start()
            return
        profile = self.profiles[self.quality.currentIndex()]
        self.download_job = DownloadJob(self.loaded_url,profile,self.output_folder,self)
        self.download_job.progress.connect(self.on_progress)
        self.download_job.status.connect(self.on_status)
        self.download_job.success.connect(self.on_success)
        self.download_job.cancelled.connect(self.on_cancelled)
        self.download_job.failed.connect(self.on_failed)
        self.download_job.finished.connect(self.download_finished)
        self.download_job.start()

    @Slot(object)
    def on_progress(self,data):
        if self.state not in ("recording","processing"):
            return
        if data.get("status") == "downloading":
            filename = data.get("filename") or "stream"
            if filename != self.stream_filename:
                self.stream_number += 1
                self.stream_filename = filename
            self.update_state("recording")
            if self.scene.mode != "recording":
                self.scene.set_mode("recording")
            percent = data.get("percent")
            self.transfer_percent = percent
            self.record_label.setText(f"02  /  RECORDING STREAM {self.stream_number:02}")
            if percent is None:
                self.progress_bar.setRange(0,0)
                self.percent_label.setText("RECORDING")
            else:
                percent = max(0,min(100,float(percent)))
                self.progress_bar.setRange(0,1000)
                self.progress_bar.setValue(round(percent*10))
                self.percent_label.setText(f"{percent:.1f}%  OF STREAM")
                self.scene.progress = percent
            speed = size_text(data.get("speed")) + "/s" if data.get("speed") else "—"
            eta = duration_text(data.get("eta")) if data.get("eta") is not None else "—"
            self.transfer_label.setText(f"{size_text(data.get('downloaded_bytes'))}   /   {speed}   /   ETA {eta}    ·    Video and audio may transfer separately.")
        elif data.get("status") == "finished":
            # A stream finishing is not equivalent to a completed recording.
            self.progress_bar.setRange(0,0)
            self.percent_label.setText("PREPARING")
            self.transfer_label.setText("Stream received. Preparing the next step…")

    @Slot(str)
    def on_status(self,message):
        if self.state not in ("recording","processing"):
            return
        if "ffmpeg" in message.lower():
            self.update_state("processing")
            self.scene.set_mode("processing")
            self.progress_bar.setRange(0,0)
            self.percent_label.setText("FINALIZING")
            self.record_label.setText("02  /  FINISHING THE RECORDING")
            self.transfer_label.setText("Merging or converting the media file…")

    @Slot()
    def stop_download(self):
        if self.state not in ("inserting","recording","processing"):
            return
        self.clack()
        if self.state == "inserting":
            self.pending_outcome = "cancelled"
            self.scene.set_mode("stopped")
            self.update_state("stopped")
            self.stopped_title.setText("RECORDING CANCELLED")
            self.stopped_hint.setText("The recording had not started. No download was made.")
            return
        self.update_state("stopping")
        self.scene.set_mode("stopping")
        self.percent_label.setText("STOPPING")
        self.transfer_label.setText("Stop requested. Waiting for the active transfer or FFmpeg step…")
        if self.demo:
            self.demo_timer.stop()
            QTimer.singleShot(250,self.on_cancelled)
        elif self.download_job:
            self.download_job.cancel_event.set()

    @Slot()
    def on_success(self):
        if self.state not in ("recording","processing","stopping"):
            return
        self.pending_outcome = "success"
        self.update_state("ejecting")
        self.progress_bar.setRange(0,1000)
        self.progress_bar.setValue(1000)
        self.percent_label.setText("SAVED")
        self.record_label.setText("03  /  EJECTING YOUR TAPE")
        self.transfer_label.setText("Recording complete. Your cassette is on its way out…")
        self.scene.progress = 100
        self.scene.finish(True)

    @Slot()
    def on_cancelled(self):
        self.pending_outcome = "cancelled"
        self.update_state("ejecting")
        self.percent_label.setText("STOPPED")
        self.record_label.setText("EJECTING")
        self.transfer_label.setText("Recording stopped. Returning the cassette…")
        self.scene.finish(False)

    @Slot(str)
    def on_failed(self,message):
        self.pending_outcome = "failed"
        self.failure_message = message
        self.update_state("ejecting")
        self.percent_label.setText("FAILED")
        self.record_label.setText("EJECTING")
        self.transfer_label.setText("The recording could not finish. Returning the cassette…")
        self.scene.finish(False)

    @Slot()
    def download_finished(self):
        job = self.download_job
        self.download_job = None
        if job:
            job.deleteLater()
        self.update_state(self.state)

    @Slot()
    def on_ejected(self):
        if self.pending_outcome == "success":
            self.update_state("complete")
            self.complete_title.setText(self.media.title if self.media else "Your recording is ready.")
        else:
            self.update_state("stopped")
            self.stopped_title.setText("RECORDING FAILED" if self.pending_outcome == "failed" else "RECORDING STOPPED")
            self.stopped_hint.setText("A partial file may remain. Press Try again to record this tape again.")
            if self.pending_outcome == "failed":
                self.show_error("Recording failed",self.failure_message)

    @Slot()
    def keep_tape(self):
        if self.state != "complete" or self.download_job:
            return
        self.update_state("archiving")
        self.scene.archive()

    @Slot()
    def on_archived(self):
        self.count_label.setText(f"{self.scene.saved_count:03} TAPES KEPT")
        self.update_state("archived")

    @Slot()
    def retry(self):
        if self.state == "stopped" and self.media and self.download_job is None:
            self.scene.set_mode("ready")
            self.update_state("ready")

    @Slot()
    def new_tape(self):
        if self.info_job or self.download_job or self.state not in ("ready","stopped","archived"):
            return
        self.clack()
        self.media = None
        self.profiles = []
        self.loaded_url = ""
        self.url_input.clear()
        self.input_hint.setText("We'll make the label. You choose the quality.")
        self.scene.reset()
        self.update_state("idle")
        self.url_input.setFocus()

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self,"Choose download folder",self.output_folder)
        if folder:
            self.output_folder = folder
            self.folder_label.setText("SAVING TO  /  " + folder)
            self.folder_label.setToolTip(folder)

    def open_folder(self):
        try:
            os.makedirs(self.output_folder,exist_ok=True)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_folder)):
                self.show_error("Open folder",f"Open this folder manually:\n{self.output_folder}")
        except OSError as exc:
            self.show_error("Open folder",str(exc))

    def show_error(self,title,message):
        box = QMessageBox(self)
        box.setWindowTitle("RetroRip • " + title)
        box.setIcon(QMessageBox.Warning)
        box.setText(title)
        box.setInformativeText("Check the link, connection, or FFmpeg installation. Details are below.")
        box.setDetailedText(message)
        box.setAttribute(Qt.WA_DeleteOnClose)
        box.open()

    def closeEvent(self,event):
        if self.info_job or self.download_job:
            event.ignore()
            self.show_error("A job is still running", "Wait for analysis to finish, or use STOP to cancel the recording before closing.")
            return
        self.demo_timer.stop()
        self.scene.timer.stop()
        event.accept()

    def load_demo_media(self):
        if self.state != "analyzing":
            return
        info = MediaInfo("Night drive / city lights", "RetroRip Studio", "Demo", 223,
                         "https://example.invalid/demo", [1080,720,480])
        self.media_ready(info,b"")

    def demo_tick(self):
        if self.state not in ("recording","processing"):
            self.demo_timer.stop()
            return
        self.demo_progress += 2
        if self.demo_progress <= 100:
            self.on_progress({"status":"downloading", "percent":self.demo_progress,
                              "filename":"demo.mp4", "downloaded_bytes":int(self.demo_progress*850000),
                              "speed":8_500_000, "eta":(100-self.demo_progress)/20})
        elif self.demo_progress <= 120:
            self.on_status("Processing media with FFmpeg...")
        else:
            self.demo_timer.stop()
            self.on_success()


STYLE = """
QMainWindow { background: #f3f0e7; }
QWidget { color: #273f48; font-family: 'Segoe UI'; font-size: 13px; }
QLabel#brand { font-size: 19px; font-weight: 800; letter-spacing: 2px; color: #1a3742; }
QLabel#navSmall { font-family: 'Consolas'; font-size: 10px; color: #8c9186; padding-left: 13px; }
QFrame#rule { background: #dadbd0; border: none; }
QLabel#headline { font-size: 35px; font-weight: 800; color: #263f49; letter-spacing: -1px; }
QLabel#subheading { color: #888d81; font-size: 13px; padding-top: 4px; }
QLabel#steps { font-family: 'Consolas'; font-size: 10px; color: #8e9285; padding-bottom: 6px; }
QFrame#panel { background: #fffcf5; border: 1px solid #dfdfd3; border-radius: 16px; }
QLabel#eyebrow { font-family: 'Consolas'; font-size: 10px; font-weight: bold; color: #a96646; letter-spacing: 2px; }
QLabel#hint { font-size: 12px; color: #899083; }
QLabel#panelTitle { font-size: 19px; font-weight: 650; color: #2b4349; }
QLabel#readout { font-family: 'Consolas'; font-size: 13px; font-weight: bold; color: #ac6441; }
QLabel#footer { color: #8e9185; font-family: 'Consolas'; font-size: 10px; }
QLabel#footerTiny { color: #9c9f92; font-family: 'Consolas'; font-size: 9px; }
QLineEdit, QComboBox { background: #f4f2e9; border: 1px solid #d8dbce; border-radius: 9px;
                       padding: 11px 14px; color: #314a50; font-size: 14px; min-height: 21px; }
QLineEdit:focus, QComboBox:focus { border-color: #bd7754; background: #fffdf7; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: #fffcf5; color: #29444b; selection-background-color: #e5d1b6; }
QPushButton { padding: 11px 20px; border-radius: 9px; font-size: 12px; font-weight: 700; min-height: 23px; }
QPushButton#primary { background: #c96d45; color: #fff8e9; border: 1px solid #b8633e; border-bottom: 3px solid #9e5130; }
QPushButton#primary:hover { background: #d87c50; border-color: #bd643e; }
QPushButton#primary:pressed { background: #b95b39; border-bottom-width: 1px; padding-top: 13px; }
QPushButton#secondary { background: #eaece2; color: #46605f; border: 1px solid #d4d9cc; }
QPushButton#secondary:hover { background: #dce3d5; }
QPushButton#quiet { background: transparent; color: #7b8679; border: none; font-size: 10px; padding: 3px 8px; min-height: 15px; }
QPushButton#quiet:hover { color: #ae6644; background: #e9e8dc; }
QPushButton:disabled { background: #deded1; color: #a2a495; border-color: #d3d6c9; }
QPushButton#primary:disabled { background: #d9ba9d; border-color: #d5b79d; color: #faf3e8; }
QProgressBar { background: #e6e7da; border: none; border-radius: 5px; min-height: 10px; max-height: 10px; }
QProgressBar::chunk { background: #c9764e; border-radius: 5px; }
QToolTip { background: #263f46; color: #fff4df; border: none; padding: 6px; }
"""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RetroRip")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI",10))
    window = RetroRipWindow(demo="--demo" in sys.argv)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
