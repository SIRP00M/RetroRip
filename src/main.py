import os
import sys

from PySide6.QtCore import (
    QObject,
    QThread,
    Signal,
    Slot,
    Qt,
    QUrl,
)

from PySide6.QtGui import (
    QDesktopServices,
)

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from downloader import (
    RetroRipDownloader,
    create_video_profile,
    create_audio_profile,
)


APP_NAME = "RetroRip"
VERSION = "0.5"


# ============================================================
# HELPERS
# ============================================================

def format_duration(seconds):
    if seconds is None:
        return "Unknown"

    seconds = int(seconds)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours:
        return f"{hours:02}:{minutes:02}:{secs:02}"

    return f"{minutes:02}:{secs:02}"


# ============================================================
# INFO WORKER
# ============================================================

class InfoWorker(QObject):

    finished = Signal(object)
    error = Signal(str)
    status = Signal(str)

    def __init__(self, url):
        super().__init__()

        self.url = url

    @Slot()
    def run(self):
        try:
            downloader = RetroRipDownloader(
                status_callback=self.status.emit
            )

            media = downloader.get_info(
                self.url
            )

            self.finished.emit(
                media
            )

        except Exception as error:
            self.error.emit(
                str(error)
            )


# ============================================================
# DOWNLOAD WORKER
# ============================================================

class DownloadWorker(QObject):

    progress = Signal(int)
    status = Signal(str)

    finished = Signal()
    error = Signal(str)

    def __init__(
        self,
        url,
        profile,
        output_dir,
    ):
        super().__init__()

        self.url = url
        self.profile = profile
        self.output_dir = output_dir

    def progress_callback(self, data):

        status = data.get(
            "status"
        )

        if status == "downloading":

            percent = data.get(
                "percent"
            )

            if percent is not None:
                self.progress.emit(
                    int(percent)
                )

        elif status == "finished":

            self.progress.emit(
                100
            )

    @Slot()
    def run(self):
        try:

            downloader = RetroRipDownloader(
                output_dir=self.output_dir,

                progress_callback=
                    self.progress_callback,

                status_callback=
                    self.status.emit,
            )

            downloader.download(
                self.url,
                self.profile,
            )

            self.finished.emit()

        except Exception as error:

            self.error.emit(
                str(error)
            )


# ============================================================
# MAIN WINDOW
# ============================================================

class RetroRipWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.media = None
        self.profiles = []

        self.current_url = None

        self.info_thread = None
        self.info_worker = None

        self.download_thread = None
        self.download_worker = None

        self.output_folder = os.path.abspath(
            "downloads"
        )

        self.setWindowTitle(
            f"{APP_NAME} v{VERSION}"
        )

        self.resize(
            760,
            560
        )

        self.build_ui()
        self.apply_style()

    # ========================================================
    # UI
    # ========================================================

    def build_ui(self):

        central = QWidget()

        self.setCentralWidget(
            central
        )

        layout = QVBoxLayout(
            central
        )

        layout.setContentsMargins(
            35,
            30,
            35,
            30,
        )

        layout.setSpacing(
            15
        )

        # ----------------------------------------------------
        # TITLE
        # ----------------------------------------------------

        title = QLabel(
            "RETRO RIP"
        )

        title.setObjectName(
            "title"
        )

        title.setAlignment(
            Qt.AlignCenter
        )

        subtitle = QLabel(
            "Rewind the web. Keep the media."
        )

        subtitle.setObjectName(
            "subtitle"
        )

        subtitle.setAlignment(
            Qt.AlignCenter
        )

        layout.addWidget(
            title
        )

        layout.addWidget(
            subtitle
        )

        # ----------------------------------------------------
        # URL
        # ----------------------------------------------------

        url_row = QHBoxLayout()

        self.url_input = QLineEdit()

        self.url_input.setPlaceholderText(
            "Paste YouTube / TikTok / Facebook URL..."
        )

        self.url_input.textChanged.connect(
            self.url_changed
        )

        self.analyze_button = QPushButton(
            "ANALYZE"
        )

        self.analyze_button.clicked.connect(
            self.analyze_url
        )

        url_row.addWidget(
            self.url_input
        )

        url_row.addWidget(
            self.analyze_button
        )

        layout.addLayout(
            url_row
        )

        # ----------------------------------------------------
        # MEDIA INFORMATION
        # ----------------------------------------------------

        form = QFormLayout()

        self.title_value = QLabel(
            "-"
        )

        self.creator_value = QLabel(
            "-"
        )

        self.platform_value = QLabel(
            "-"
        )

        self.duration_value = QLabel(
            "-"
        )

        self.resolution_value = QLabel(
            "-"
        )

        self.title_value.setWordWrap(
            True
        )

        form.addRow(
            "Title:",
            self.title_value,
        )

        form.addRow(
            "Creator:",
            self.creator_value,
        )

        form.addRow(
            "Platform:",
            self.platform_value,
        )

        form.addRow(
            "Duration:",
            self.duration_value,
        )

        form.addRow(
            "Available:",
            self.resolution_value,
        )

        layout.addLayout(
            form
        )

        # ----------------------------------------------------
        # QUALITY
        # ----------------------------------------------------

        quality_row = QHBoxLayout()

        quality_label = QLabel(
            "Format / Quality"
        )

        self.quality_combo = QComboBox()

        self.quality_combo.setEnabled(
            False
        )

        quality_row.addWidget(
            quality_label
        )

        quality_row.addWidget(
            self.quality_combo,
            1,
        )

        layout.addLayout(
            quality_row
        )

        # ----------------------------------------------------
        # OUTPUT FOLDER
        # ----------------------------------------------------

        folder_row = QHBoxLayout()

        self.folder_input = QLineEdit(
            self.output_folder
        )

        self.folder_input.setReadOnly(
            True
        )

        self.browse_button = QPushButton(
            "BROWSE"
        )

        self.browse_button.clicked.connect(
            self.choose_folder
        )

        self.open_button = QPushButton(
            "OPEN"
        )

        self.open_button.clicked.connect(
            self.open_folder
        )

        folder_row.addWidget(
            self.folder_input,
            1,
        )

        folder_row.addWidget(
            self.browse_button
        )

        folder_row.addWidget(
            self.open_button
        )

        layout.addLayout(
            folder_row
        )

        # ----------------------------------------------------
        # PROGRESS
        # ----------------------------------------------------

        self.progress_bar = QProgressBar()

        self.progress_bar.setRange(
            0,
            100
        )

        self.progress_bar.setValue(
            0
        )

        self.progress_bar.setFormat(
            "%p%"
        )

        layout.addWidget(
            self.progress_bar
        )

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        self.status_label = QLabel(
            "Ready"
        )

        self.status_label.setObjectName(
            "status"
        )

        self.status_label.setAlignment(
            Qt.AlignCenter
        )

        layout.addWidget(
            self.status_label
        )

        # ----------------------------------------------------
        # DOWNLOAD
        # ----------------------------------------------------

        self.download_button = QPushButton(
            "DOWNLOAD"
        )

        self.download_button.setObjectName(
            "download"
        )

        self.download_button.setEnabled(
            False
        )

        self.download_button.clicked.connect(
            self.start_download
        )

        layout.addWidget(
            self.download_button
        )

    # ========================================================
    # URL CHANGED
    # ========================================================

    def url_changed(self):

        url = self.url_input.text().strip()

        if (
            self.current_url
            and url != self.current_url
        ):

            self.media = None
            self.profiles.clear()

            self.quality_combo.clear()

            self.quality_combo.setEnabled(
                False
            )

            self.download_button.setEnabled(
                False
            )

            self.title_value.setText("-")
            self.creator_value.setText("-")
            self.platform_value.setText("-")
            self.duration_value.setText("-")
            self.resolution_value.setText("-")

            self.status_label.setText(
                "URL changed — analyze again"
            )

    # ========================================================
    # ANALYZE
    # ========================================================

    def analyze_url(self):

        url = self.url_input.text().strip()

        if not url:

            QMessageBox.warning(
                self,
                "RetroRip",
                "Paste a media URL first.",
            )

            return

        if self.info_thread is not None:
            return

        self.current_url = None
        self.media = None

        self.profiles.clear()
        self.quality_combo.clear()

        self.download_button.setEnabled(
            False
        )

        self.quality_combo.setEnabled(
            False
        )

        self.analyze_button.setEnabled(
            False
        )

        self.status_label.setText(
            "Analyzing media..."
        )

        # ----------------------------------------------------
        # THREAD
        # ----------------------------------------------------

        self.info_thread = QThread()

        self.info_worker = InfoWorker(
            url
        )

        self.info_worker.moveToThread(
            self.info_thread
        )

        self.info_thread.started.connect(
            self.info_worker.run
        )

        self.info_worker.status.connect(
            self.status_label.setText
        )

        self.info_worker.finished.connect(
            self.media_ready
        )

        self.info_worker.error.connect(
            self.media_error
        )

        self.info_worker.finished.connect(
            self.info_thread.quit
        )

        self.info_worker.error.connect(
            self.info_thread.quit
        )

        self.info_thread.finished.connect(
            self.info_worker.deleteLater
        )

        self.info_thread.finished.connect(
            self.info_thread.deleteLater
        )

        self.info_thread.finished.connect(
            self.info_thread_finished
        )

        self.info_thread.start()

    # ========================================================
    # MEDIA READY
    # ========================================================

    def media_ready(
        self,
        media,
    ):

        self.media = media

        self.current_url = (
            self.url_input
            .text()
            .strip()
        )

        self.title_value.setText(
            media.title
        )

        self.creator_value.setText(
            media.creator
        )

        self.platform_value.setText(
            media.platform
        )

        self.duration_value.setText(
            format_duration(
                media.duration
            )
        )

        # ----------------------------------------------------
        # RESOLUTIONS
        # ----------------------------------------------------

        if media.resolutions:

            text = ", ".join(
                f"{height}p"
                for height
                in media.resolutions
            )

            self.resolution_value.setText(
                text
            )

        else:

            self.resolution_value.setText(
                "Unknown"
            )

        # ----------------------------------------------------
        # PROFILES
        # ----------------------------------------------------

        self.profiles = []

        # Best
        self.profiles.append(
            create_video_profile()
        )

        # Dynamic resolutions
        for height in media.resolutions:

            self.profiles.append(
                create_video_profile(
                    height
                )
            )

        # MP3
        self.profiles.append(
            create_audio_profile()
        )

        # ----------------------------------------------------
        # COMBO BOX
        # ----------------------------------------------------

        self.quality_combo.clear()

        for profile in self.profiles:

            self.quality_combo.addItem(
                profile.name
            )

        self.quality_combo.setEnabled(
            True
        )

        self.download_button.setEnabled(
            True
        )

        self.status_label.setText(
            "Media ready"
        )

    # ========================================================
    # MEDIA ERROR
    # ========================================================

    def media_error(
        self,
        error,
    ):

        self.status_label.setText(
            "Analyze failed"
        )

        QMessageBox.critical(
            self,
            "Analyze Error",
            error,
        )

    # ========================================================
    # INFO THREAD FINISHED
    # ========================================================

    def info_thread_finished(self):

        self.info_thread = None
        self.info_worker = None

        self.analyze_button.setEnabled(
            True
        )

    # ========================================================
    # OUTPUT DIRECTORY
    # ========================================================

    def choose_folder(self):

        folder = QFileDialog.getExistingDirectory(
            self,
            "Choose download folder",
            self.output_folder,
        )

        if folder:

            self.output_folder = folder

            self.folder_input.setText(
                folder
            )

    def open_folder(self):

        os.makedirs(
            self.output_folder,
            exist_ok=True,
        )

        QDesktopServices.openUrl(
            QUrl.fromLocalFile(
                self.output_folder
            )
        )

    # ========================================================
    # START DOWNLOAD
    # ========================================================

    def start_download(self):

        if not self.media:
            return

        if not self.current_url:
            return

        if self.download_thread is not None:
            return

        index = (
            self.quality_combo
            .currentIndex()
        )

        if (
            index < 0
            or index >= len(
                self.profiles
            )
        ):

            return

        profile = (
            self.profiles[
                index
            ]
        )

        # ----------------------------------------------------
        # UI LOCK
        # ----------------------------------------------------

        self.progress_bar.setValue(
            0
        )

        self.download_button.setEnabled(
            False
        )

        self.analyze_button.setEnabled(
            False
        )

        self.quality_combo.setEnabled(
            False
        )

        self.url_input.setEnabled(
            False
        )

        self.browse_button.setEnabled(
            False
        )

        self.status_label.setText(
            f"Starting {profile.name}..."
        )

        # ----------------------------------------------------
        # THREAD
        # ----------------------------------------------------

        self.download_thread = QThread()

        self.download_worker = DownloadWorker(
            url=self.current_url,

            profile=profile,

            output_dir=
                self.output_folder,
        )

        self.download_worker.moveToThread(
            self.download_thread
        )

        self.download_thread.started.connect(
            self.download_worker.run
        )

        self.download_worker.progress.connect(
            self.progress_bar.setValue
        )

        self.download_worker.status.connect(
            self.status_label.setText
        )

        self.download_worker.finished.connect(
            self.download_complete
        )

        self.download_worker.error.connect(
            self.download_error
        )

        self.download_worker.finished.connect(
            self.download_thread.quit
        )

        self.download_worker.error.connect(
            self.download_thread.quit
        )

        self.download_thread.finished.connect(
            self.download_worker.deleteLater
        )

        self.download_thread.finished.connect(
            self.download_thread.deleteLater
        )

        self.download_thread.finished.connect(
            self.download_thread_finished
        )

        self.download_thread.start()

    # ========================================================
    # DOWNLOAD COMPLETE
    # ========================================================

    def download_complete(self):

        self.progress_bar.setValue(
            100
        )

        self.status_label.setText(
            "Download complete"
        )

        QMessageBox.information(
            self,
            "RetroRip",
            "Download complete!",
        )

    # ========================================================
    # DOWNLOAD ERROR
    # ========================================================

    def download_error(
        self,
        error,
    ):

        self.status_label.setText(
            "Download failed"
        )

        QMessageBox.critical(
            self,
            "Download Error",
            error,
        )

    # ========================================================
    # THREAD CLEANUP
    # ========================================================

    def download_thread_finished(self):

        self.download_thread = None
        self.download_worker = None

        self.download_button.setEnabled(
            self.media is not None
        )

        self.analyze_button.setEnabled(
            True
        )

        self.quality_combo.setEnabled(
            self.media is not None
        )

        self.url_input.setEnabled(
            True
        )

        self.browse_button.setEnabled(
            True
        )

    # ========================================================
    # CLOSE
    # ========================================================

    def closeEvent(
        self,
        event,
    ):

        if (
            self.download_thread
            and
            self.download_thread.isRunning()
        ):

            QMessageBox.warning(
                self,
                "RetroRip",
                "A download is still running.",
            )

            event.ignore()
            return

        if (
            self.info_thread
            and
            self.info_thread.isRunning()
        ):

            QMessageBox.warning(
                self,
                "RetroRip",
                "Media analysis is still running.",
            )

            event.ignore()
            return

        event.accept()

    # ========================================================
    # STYLE
    # ========================================================

    def apply_style(self):

        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #211C18;
            }

            QWidget {
                color: #E8D9B5;
                font-family: "Segoe UI";
                font-size: 13px;
            }

            QLabel#title {
                font-size: 32px;
                font-weight: bold;
                color: #F0C987;
            }

            QLabel#subtitle {
                color: #B89567;
                font-size: 12px;
            }

            QLabel#status {
                color: #E4A55B;
                font-weight: bold;
                padding: 7px;
            }

            QLineEdit,
            QComboBox {
                background-color: #302821;
                border: 1px solid #665443;
                padding: 9px;
                color: #F1E3C4;
                border-radius: 4px;
            }

            QLineEdit:focus,
            QComboBox:focus {
                border: 1px solid #D1793D;
            }

            QPushButton {
                background-color: #594938;
                border: 1px solid #79634B;
                padding: 9px 14px;
                color: #F1E3C4;
                border-radius: 4px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #705A43;
            }

            QPushButton:pressed {
                background-color: #3D3229;
            }

            QPushButton:disabled {
                color: #746A60;
                background-color: #342E28;
                border-color: #453C34;
            }

            QPushButton#download {
                background-color: #BD6339;
                border-color: #DB8250;
                font-size: 14px;
                padding: 12px;
            }

            QPushButton#download:hover {
                background-color: #D27342;
            }

            QProgressBar {
                border: 1px solid #655240;
                background-color: #171411;
                height: 22px;
                text-align: center;
                border-radius: 3px;
                color: #F1E3C4;
            }

            QProgressBar::chunk {
                background-color: #C96D3D;
                border-radius: 2px;
            }

            QComboBox QAbstractItemView {
                background-color: #302821;
                color: #F1E3C4;
                selection-background-color: #BD6339;
            }
            """
        )


# ============================================================
# ENTRY POINT
# ============================================================

def main():

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        APP_NAME
    )

    window = RetroRipWindow()

    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()