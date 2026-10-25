"""Qt media player with cassette-loading animation and native codec errors."""
from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider, QStackedWidget
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from deck_scene import DeckScene


class PlayerDialog(QDialog):
    def __init__(self, tape, cover, dark=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("RetroRip • " + tape["title"])
        self.resize(920,700)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.path = Path(tape["path"])
        self.loaded = False
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(.65)
        self.player.setAudioOutput(self.audio)
        layout = QVBoxLayout(self)
        title = QLabel(tape["title"]); title.setTextFormat(Qt.PlainText)
        title.setObjectName("panelTitle"); title.setWordWrap(True)
        layout.addWidget(title)
        self.stage = QStackedWidget()
        self.scene = DeckScene(); self.scene.dark = dark
        self.scene.tape_color = tape.get("color", "#263d3b")
        self.scene.load(tape["title"],tape.get("creator",""),tape.get("platform",""),tape.get("duration_text",""),cover)
        self.scene.quality = tape.get("quality","")
        self.video = QVideoWidget()
        self.player.setVideoOutput(self.video)
        self.stage.addWidget(self.scene); self.stage.addWidget(self.video)
        layout.addWidget(self.stage,1)
        self.message = QLabel("Press PLAY to slide the tape into the player.")
        self.message.setWordWrap(True); layout.addWidget(self.message)
        self.seek = QSlider(Qt.Horizontal); self.seek.setRange(0,0)
        self.seek.sliderMoved.connect(self.player.setPosition)
        self.player.durationChanged.connect(lambda d:self.seek.setRange(0,d))
        self.player.positionChanged.connect(self.position_changed)
        layout.addWidget(self.seek)
        row = QHBoxLayout()
        self.play_btn = QPushButton("▶ PLAY"); self.play_btn.setObjectName("primary")
        self.play_btn.clicked.connect(self.toggle)
        row.addWidget(self.play_btn)
        stop = QPushButton("■ STOP"); stop.clicked.connect(self.stop)
        row.addWidget(stop); row.addStretch(); row.addWidget(QLabel("VOLUME"))
        volume = QSlider(Qt.Horizontal); volume.setRange(0,100); volume.setValue(65)
        volume.setMaximumWidth(180); volume.valueChanged.connect(lambda v:self.audio.setVolume(v/100))
        row.addWidget(volume); layout.addLayout(row)
        self.scene.inserted.connect(self.start_media)
        self.scene.transport.connect(lambda action:self.toggle() if action=="rec" else self.stop())
        self.player.playbackStateChanged.connect(self.state_changed)
        self.player.hasVideoChanged.connect(lambda enabled:self.stage.setCurrentWidget(self.video if enabled else self.scene))
        self.player.errorOccurred.connect(self.error)

    def toggle(self):
        if not self.loaded:
            self.play_btn.setEnabled(False)
            self.scene.insert()
        elif self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def start_media(self):
        self.loaded = True
        self.play_btn.setEnabled(True)
        self.player.setSource(QUrl.fromLocalFile(str(self.path)))
        self.player.play()

    def state_changed(self,state):
        playing = state == QMediaPlayer.PlayingState
        self.play_btn.setText("Ⅱ PAUSE" if playing else "▶ PLAY")
        self.scene.set_mode("playing" if playing else "paused")

    def stop(self):
        self.player.stop()
        self.player.setPosition(0)
        self.scene.set_mode("paused")
        self.play_btn.setEnabled(True)

    def position_changed(self,value):
        if not self.seek.isSliderDown():
            self.seek.setValue(value)
        total = self.player.duration()
        self.scene.progress = 100*value/total if total else 0
        self.message.setText(f"{value//60000:02}:{value//1000%60:02}  /  {total//60000:02}:{total//1000%60:02}")

    def error(self,*args):
        self.message.setText("Cannot play this file: " + self.player.errorString() + "  You can use Open file in Collection to play it externally.")
        self.play_btn.setEnabled(True)

    def closeEvent(self,event):
        self.player.stop()
        self.player.setSource(QUrl())
        self.scene.timer.stop()
        event.accept()
