"""RetroRip cassette deck UI. Run: python src/main.py"""
import math
import os
import sys
from pathlib import Path
from threading import Event
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, QThread, QTimer, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QColor, QDesktopServices, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)
from downloader import DownloadCancelled, RetroRipDownloader, create_audio_profile, create_video_profile

APP_NAME = "RetroRip"
VERSION = "0.6"
ASSETS = Path(__file__).resolve().parent / "assets"


def duration_text(seconds):
    if seconds is None:
        return "—"
    seconds = int(seconds)
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{secs:02}" if hours else f"{minutes:02}:{secs:02}"


class InfoWorker(QObject):
    result = Signal(object, bytes)
    error = Signal(str)
    status = Signal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    @Slot()
    def run(self):
        try:
            media = RetroRipDownloader(status_callback=self.status.emit).get_info(self.url)
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
                    pass  # Artwork is optional; metadata remains usable.
            self.result.emit(media, picture)
        except Exception as exc:
            self.error.emit(str(exc))


class DownloadWorker(QObject):
    progress = Signal(float)
    status = Signal(str)
    complete = Signal()
    cancelled = Signal()
    error = Signal(str)

    def __init__(self, url, profile, folder, cancel_event):
        super().__init__()
        self.url, self.profile, self.folder = url, profile, folder
        self.cancel_event = cancel_event

    def on_progress(self, data):
        if data.get("status") == "downloading" and data.get("percent") is not None:
            self.progress.emit(max(0, min(100, float(data["percent"]))))
        elif data.get("status") == "finished":
            self.progress.emit(100)

    @Slot()
    def run(self):
        try:
            engine = RetroRipDownloader(
                output_dir=self.folder, progress_callback=self.on_progress,
                status_callback=self.status.emit, cancel_event=self.cancel_event,
            )
            engine.download(self.url, self.profile)
            self.complete.emit()
        except Exception as exc:
            if self.cancel_event.is_set() or isinstance(exc, DownloadCancelled):
                self.cancelled.emit()
            else:
                self.error.emit(str(exc))


class Cassette(QWidget):
    """Vector drawn tape. Animation updates only the reel angle and LED."""
    def __init__(self):
        super().__init__()
        self.setMinimumHeight(355)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.angle = 0.0
        self.moving = False
        self.active = False
        self.progress = 0.0
        self.title = "NO TAPE LOADED"
        self.subtitle = "PASTE A LINK  /  PRESS ANALYZE"
        self.cover = QPixmap()
        self.phase = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def tick(self):
        self.phase += .09
        if self.moving:
            self.angle = (self.angle + (4.5 if self.active else 2.2)) % 360
        self.update()

    def set_media(self, media=None, picture=b""):
        self.cover = QPixmap()
        if media:
            self.title = media.title.upper()
            self.subtitle = f"{media.platform.upper()}   /   {duration_text(media.duration)}"
            if picture:
                self.cover.loadFromData(picture)
        else:
            self.title = "NO TAPE LOADED"
            self.subtitle = "PASTE A LINK  /  PRESS ANALYZE"
        self.progress = 0.0
        self.update()

    @staticmethod
    def rounded(painter, x, y, w, h, radius, fill, stroke=None, width=1):
        painter.setPen(QPen(QColor(stroke), width) if stroke else Qt.NoPen)
        painter.setBrush(QColor(fill) if isinstance(fill, str) else fill)
        painter.drawRoundedRect(x, y, w, h, radius, radius)

    def reel(self, painter, x, y, rotation, radius, accent):
        painter.save()
        painter.translate(x, y)
        painter.setPen(QPen(QColor("#0e1014"), 9))
        painter.setBrush(QColor("#171b22"))
        painter.drawEllipse(-radius, -radius, radius * 2, radius * 2)
        painter.setPen(QPen(QColor("#52575a"), 2))
        painter.setBrush(QColor("#a0a9a3"))
        painter.drawEllipse(-radius + 8, -radius + 8, (radius - 8) * 2, (radius - 8) * 2)
        painter.rotate(rotation)
        for n in range(6):
            painter.save()
            painter.rotate(n * 60)
            path = QPainterPath()
            path.addRoundedRect(-7, -radius + 15, 14, 24, 5, 5)
            painter.fillPath(path, QColor("#252b2c"))
            painter.restore()
        painter.setBrush(QColor(accent))
        painter.setPen(QPen(QColor("#444a46"), 2))
        painter.drawEllipse(-16, -16, 32, 32)
        painter.setBrush(QColor("#24272a"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(-6, -6, 12, 12)
        painter.restore()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        scale = min((self.width() - 8) / 780, (self.height() - 8) / 372)
        p.translate((self.width() - 780 * scale) / 2, (self.height() - 372 * scale) / 2)
        p.scale(scale, scale)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#080d12"))
        p.drawRoundedRect(5, 8, 770, 354, 22, 22)
        face = QLinearGradient(0, 13, 0, 350)
        face.setColorAt(0, QColor("#424954"))
        face.setColorAt(.22, QColor("#202832"))
        face.setColorAt(1, QColor("#131b25"))
        self.rounded(p, 12, 12, 756, 344, 18, face, "#727779", 2)
        self.rounded(p, 32, 27, 716, 255, 12, "#d1c8b0", "#121d25", 3)
        self.rounded(p, 47, 38, 686, 25, 3, "#db5537")
        p.setFont(QFont("Consolas", 10, QFont.Bold))
        p.setPen(QColor("#f6e8cc"))
        p.drawText(61, 56, "R E T R O R I P     /     MAGNETIC MEDIA SYSTEM")
        self.rounded(p, 47, 76, 686, 97, 6, "#eee5d0")
        if not self.cover.isNull():
            cropped = self.cover.scaled(148, 84, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            p.save()
            p.setClipRect(57, 83, 148, 84)
            p.drawPixmap(57, 83, cropped)
            p.restore()
        else:
            self.rounded(p, 57, 83, 148, 84, 3, "#263746")
            p.setFont(QFont("Consolas", 25, QFont.Bold))
            p.setPen(QColor("#e3744e"))
            p.drawText(90, 137, "RR / 90")
        p.setPen(QColor("#17212a"))
        p.setFont(QFont("Consolas", 13, QFont.Bold))
        title = p.fontMetrics().elidedText(self.title, Qt.ElideRight, 496)
        p.drawText(220, 112, title)
        p.setFont(QFont("Consolas", 10))
        p.setPen(QColor("#68665c"))
        p.drawText(220, 137, self.subtitle[:85])
        self.rounded(p, 48, 184, 684, 82, 15, "#141b23", "#747569", 2)
        self.rounded(p, 277, 188, 226, 73, 8, "#232b31", "#696e6c", 2)
        p.setPen(QPen(QColor("#12100e"), 7))
        p.drawLine(275, 224, 503, 224)
        self.reel(p, 189, 226, self.angle, 38, "#c3bdab")
        self.reel(p, 591, 226, self.angle * .95, 38, "#c3bdab")
        for x in (62, 718):
            for y in (89, 268):
                p.setPen(QPen(QColor("#393d3d"), 3))
                p.setBrush(QColor("#a9aca5"))
                p.drawEllipse(x-5, y-5, 10, 10)
                p.drawLine(x-3, y-3, x+3, y+3)
        p.setPen(QColor("#d7c9a7"))
        p.setFont(QFont("Consolas", 11, QFont.Bold))
        p.drawText(49, 320, "TYPE I     •     STEREO")
        p.drawText(620, 320, "SIDE  A  /  01")
        p.fillRect(305, 298, int(170 * self.progress / 100), 6, QColor("#e57146"))
        p.setPen(QColor("#56616a"))
        p.drawRect(304, 297, 171, 7)
        p.end()


class RetroRipWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.media = None
        self.loaded_url = ""
        self.profiles = []
        self.info_thread = self.info_worker = None
        self.download_thread = self.download_worker = None
        self.stop_flag = None
        self.output_folder = os.path.abspath("downloads")
        self.setWindowTitle(f"{APP_NAME}  /  CASSETTE DECK")
        self.setMinimumSize(810, 740)
        self.resize(990, 830)
        self.sound = QSoundEffect(self)
        self.sound.setSource(QUrl.fromLocalFile(str(ASSETS / "clack.wav")))
        self.sound.setVolume(.34)
        self.make_ui()
        self.setStyleSheet(STYLE)
        self.anim = QTimer(self)
        self.anim.timeout.connect(self.animate)
        self.anim.start(30)
        self.target_progress = 0.0
        self.display_progress = 0.0
        self.processing = False
        self.busy = False
        self.refresh_buttons()

    def make_ui(self):
        shell = QWidget()
        self.setCentralWidget(shell)
        root = QVBoxLayout(shell)
        root.setContentsMargins(35, 25, 35, 24)
        root.setSpacing(15)
        top = QHBoxLayout()
        brand = QLabel("◉   R E T R O R I P")
        brand.setObjectName("brand")
        top.addWidget(brand)
        top.addStretch()
        edition = QLabel("DECK 01   /   DIGITAL TO ANALOG")
        edition.setObjectName("minor")
        top.addWidget(edition)
        root.addLayout(top)

        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("PASTE A YOUTUBE  /  TIKTOK  /  FACEBOOK LINK")
        self.url_input.returnPressed.connect(self.analyze)
        self.url_input.textChanged.connect(self.url_changed)
        self.analyze_btn = QPushButton("LOAD TAPE   ↗")
        self.analyze_btn.setObjectName("secondary")
        self.analyze_btn.clicked.connect(self.analyze)
        url_row.addWidget(self.url_input, 1)
        url_row.addWidget(self.analyze_btn)
        root.addLayout(url_row)

        deck = QFrame()
        deck.setObjectName("deck")
        deck_layout = QVBoxLayout(deck)
        deck_layout.setContentsMargins(17, 15, 17, 12)
        top_line = QHBoxLayout()
        self.led = QLabel("●   STANDBY")
        self.led.setObjectName("led")
        top_line.addWidget(self.led)
        top_line.addStretch()
        top_line.addWidget(QLabel("AUTO REVERSE   /   HI-FI  STEREO"))
        deck_layout.addLayout(top_line)
        self.cassette = Cassette()
        deck_layout.addWidget(self.cassette, 1)
        root.addWidget(deck, 1)

        details = QHBoxLayout()
        self.meta_label = QLabel("NO MEDIA LOADED  •  INSERT A LINK TO BEGIN")
        self.meta_label.setObjectName("meta")
        self.meta_label.setWordWrap(True)
        details.addWidget(self.meta_label, 1)
        self.quality = QComboBox()
        self.quality.setMinimumWidth(235)
        self.quality.setEnabled(False)
        details.addWidget(self.quality)
        root.addLayout(details)

        progress_row = QHBoxLayout()
        progress_row.addWidget(QLabel("TAPE POSITION"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 1000)
        progress_row.addWidget(self.progress_bar, 1)
        self.percent_label = QLabel("00.0 %")
        self.percent_label.setObjectName("digits")
        progress_row.addWidget(self.percent_label)
        root.addLayout(progress_row)

        self.status = QLabel("AWAITING INPUT")
        self.status.setObjectName("status")
        root.addWidget(self.status)

        controls = QHBoxLayout()
        self.rec_btn = QPushButton("●   REC")
        self.rec_btn.setObjectName("rec")
        self.rec_btn.clicked.connect(self.record)
        self.stop_btn = QPushButton("■   STOP")
        self.stop_btn.clicked.connect(self.stop)
        self.eject_btn = QPushButton("⏏   EJECT")
        self.eject_btn.clicked.connect(self.eject)
        for button in (self.rec_btn, self.stop_btn, self.eject_btn):
            button.setMinimumHeight(53)
            controls.addWidget(button, 1)
        root.addLayout(controls)

        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("OUTPUT   /"))
        self.folder_label = QLabel(self.output_folder)
        self.folder_label.setObjectName("path")
        folder_row.addWidget(self.folder_label, 1)
        browse = QPushButton("CHANGE")
        browse.clicked.connect(self.choose_folder)
        self.browse_btn = browse
        folder_row.addWidget(browse)
        open_btn = QPushButton("OPEN ↗")
        open_btn.clicked.connect(self.open_folder)
        folder_row.addWidget(open_btn)
        root.addLayout(folder_row)

    def click(self):
        if self.sound.isLoaded():
            self.sound.stop()
            self.sound.play()

    def animate(self):
        if abs(self.target_progress - self.display_progress) > .03:
            self.display_progress += (self.target_progress - self.display_progress) * .16
        else:
            self.display_progress = self.target_progress
        self.progress_bar.setValue(round(self.display_progress * 10))
        self.cassette.progress = self.display_progress
        self.percent_label.setText(f"{self.display_progress:04.1f} %")
        if self.busy and self.cassette.moving:
            self.led.setStyleSheet("color: #ff704b" if math.sin(self.cassette.phase * 3) > 0 else "color: #824e42")
        else:
            self.led.setStyleSheet("color: #86b89b" if self.media else "color: #777d80")

    def refresh_buttons(self):
        analyzing = self.info_thread is not None
        downloading = self.download_thread is not None
        self.analyze_btn.setEnabled(not analyzing and not downloading)
        self.url_input.setEnabled(not downloading)
        self.quality.setEnabled(bool(self.media) and not downloading)
        self.rec_btn.setEnabled(bool(self.media) and not analyzing and not downloading)
        self.stop_btn.setEnabled(downloading and self.stop_flag is not None and not self.stop_flag.is_set())
        self.eject_btn.setEnabled(not analyzing and not downloading and bool(self.media or self.url_input.text()))
        self.browse_btn.setEnabled(not downloading)

    def url_changed(self):
        if self.media and self.url_input.text().strip() != self.loaded_url:
            self.clear_media()
            self.status.setText("NEW LINK DETECTED  /  PRESS LOAD TAPE")
        self.refresh_buttons()

    def clear_media(self):
        self.media = None
        self.loaded_url = ""
        self.profiles.clear()
        self.quality.clear()
        self.meta_label.setText("NO MEDIA LOADED  •  INSERT A LINK TO BEGIN")
        self.cassette.set_media()
        self.target_progress = self.display_progress = 0
        self.processing = False
        self.refresh_buttons()

    def analyze(self):
        url = self.url_input.text().strip()
        if not url or self.info_thread or self.download_thread:
            if not url:
                self.status.setText("PASTE A LINK FIRST")
            return
        self.click()
        self.clear_media()
        self.busy = True
        self.cassette.moving = True
        self.cassette.active = False
        self.status.setText("READING TAPE LABEL...")
        thread = QThread(self)
        worker = InfoWorker(url)
        worker.moveToThread(thread)
        self.info_thread, self.info_worker = thread, worker
        thread.started.connect(worker.run)
        worker.result.connect(lambda media, pic: self.media_ready(url, media, pic))
        worker.error.connect(self.info_error)
        worker.result.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.info_done)
        thread.start()
        self.refresh_buttons()

    def media_ready(self, requested_url, media, picture):
        self.busy = self.cassette.moving = False
        if self.url_input.text().strip() != requested_url:
            self.status.setText("LINK CHANGED  /  PRESS LOAD TAPE AGAIN")
            return
        self.media = media
        self.loaded_url = requested_url
        self.cassette.set_media(media, picture)
        self.profiles = [create_video_profile()]
        self.profiles.extend(create_video_profile(h) for h in media.resolutions)
        self.profiles.append(create_audio_profile())
        self.quality.addItems([p.name for p in self.profiles])
        self.meta_label.setText(f"{media.creator}    •    {media.platform}    •    {duration_text(media.duration)}")
        self.status.setText("TAPE READY  /  SELECT QUALITY AND PRESS REC")
        self.refresh_buttons()

    def info_error(self, error):
        self.busy = self.cassette.moving = False
        self.status.setText("COULD NOT LOAD TAPE")
        QMessageBox.warning(self, "RetroRip • Analyze failed", error)

    def info_done(self):
        self.info_thread = self.info_worker = None
        self.refresh_buttons()

    def record(self):
        if not self.media or self.download_thread:
            return
        self.click()
        profile = self.profiles[self.quality.currentIndex()]
        self.target_progress = self.display_progress = 0
        self.processing = False
        self.busy = self.cassette.moving = self.cassette.active = True
        self.led.setText("●   RECORDING")
        self.status.setText(f"RECORDING  /  {profile.name.upper()}")
        self.stop_flag = Event()
        thread = QThread(self)
        worker = DownloadWorker(self.loaded_url, profile, self.output_folder, self.stop_flag)
        worker.moveToThread(thread)
        self.download_thread, self.download_worker = thread, worker
        thread.started.connect(worker.run)
        worker.progress.connect(self.set_progress)
        worker.status.connect(self.set_status)
        worker.complete.connect(self.complete)
        worker.cancelled.connect(self.cancelled)
        worker.error.connect(self.download_error)
        for signal in (worker.complete, worker.cancelled, worker.error):
            signal.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self.download_done)
        thread.start()
        self.refresh_buttons()

    def set_progress(self, value):
        self.target_progress = max(self.target_progress, value)

    def set_status(self, value):
        self.status.setText(value.upper())
        if "Processing" in value or "processing" in value:
            self.processing = True
            self.cassette.active = False
            self.led.setText("●   FINALIZING")

    def stop(self):
        if self.stop_flag and self.download_thread and not self.stop_flag.is_set():
            self.click()
            self.stop_flag.set()  # Directly set thread-safe flag: worker event loop is busy.
            self.status.setText("STOP REQUESTED  /  WAITING FOR CURRENT TRANSFER")
            self.refresh_buttons()

    def complete(self):
        self.target_progress = 100
        self.busy = self.cassette.moving = False
        self.led.setText("●   COMPLETE")
        self.status.setText("RECORDING COMPLETE  /  FILE IN OUTPUT FOLDER")
        self.click()

    def cancelled(self):
        self.busy = self.cassette.moving = False
        self.led.setText("●   STOPPED")
        self.status.setText("STOPPED  /  PARTIAL DOWNLOAD MAY REMAIN")

    def download_error(self, error):
        self.busy = self.cassette.moving = False
        self.led.setText("●   ERROR")
        self.status.setText("RECORDING FAILED")
        QMessageBox.critical(self, "RetroRip • Download failed", error)

    def download_done(self):
        self.download_thread = self.download_worker = self.stop_flag = None
        self.refresh_buttons()

    def eject(self):
        if self.info_thread or self.download_thread:
            return
        self.click()
        self.clear_media()
        self.url_input.clear()
        self.led.setText("●   STANDBY")
        self.status.setText("TAPE EJECTED  /  AWAITING INPUT")

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", self.output_folder)
        if folder:
            self.click()
            self.output_folder = folder
            self.folder_label.setText(folder)

    def open_folder(self):
        os.makedirs(self.output_folder, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_folder))

    def closeEvent(self, event):
        if self.info_thread or self.download_thread:
            QMessageBox.information(self, "RetroRip", "Wait for analysis or recording to finish. Use STOP to cancel a recording.")
            event.ignore()
            return
        event.accept()


STYLE = """
QMainWindow { background: #111820; }
QWidget { color: #d5d1c1; font: 12px 'Consolas'; }
QFrame#deck { background: #202934; border: 2px solid #46505a; border-radius: 14px; }
QLabel#brand { color: #f29264; font: bold 23px 'Consolas'; }
QLabel#minor { color: #80919c; font-size: 10px; }
QLabel#led { color: #83a891; font-weight: bold; }
QLabel#meta { color: #e7dabe; font-size: 12px; }
QLabel#status { color: #e6a16b; font-weight: bold; letter-spacing: 1px; }
QLabel#digits { color: #f4ae75; font: bold 18px 'Consolas'; min-width: 86px; }
QLabel#path { color: #9daab2; }
QLineEdit, QComboBox { background: #1a232c; border: 1px solid #55616a; border-radius: 6px;
                       padding: 11px; color: #f3e6cd; selection-background-color: #b96546; }
QLineEdit:focus, QComboBox:focus { border-color: #e18459; }
QComboBox QAbstractItemView { background: #202a32; color: #f3e6cd; selection-background-color: #b96546; }
QPushButton { background: #34404b; border: 1px solid #62727b; border-bottom: 4px solid #101820;
              border-radius: 7px; padding: 9px 16px; color: #e5dcc8; font: bold 13px 'Consolas'; }
QPushButton:hover { background: #485967; border-color: #e2a372; }
QPushButton:pressed { border-bottom: 1px solid #101820; padding-top: 12px; }
QPushButton:disabled { background: #232c34; border-color: #303b42; color: #627078; }
QPushButton#rec { background: #b9503c; border-color: #e17f5b; color: #fff1d7; font-size: 18px; }
QPushButton#rec:hover { background: #d16347; }
QPushButton#rec:disabled { background: #513e3c; border-color: #594d4b; color: #83746f; }
QPushButton#secondary { background: #454e46; }
QProgressBar { background: #081117; border: 1px solid #485967; border-radius: 5px; height: 13px; }
QProgressBar::chunk { background: #e27b50; border-radius: 4px; }
"""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = RetroRipWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
