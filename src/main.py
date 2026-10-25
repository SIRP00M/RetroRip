"""RetroRip 1.0: persistent five-page desktop app. Run with --demo for an offline tour."""
import argparse
import math
import tempfile
import wave
from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import Qt, Signal, QTimer, QUrl, QStandardPaths, QPointF, QRectF, QVariantAnimation, QEasingCurve, QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QPainter, QColor, QPixmap, QDesktopServices, QFont, QPalette, QLinearGradient, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QHBoxLayout, QVBoxLayout, QGridLayout,
    QStackedWidget, QScrollArea, QLabel, QPushButton, QLineEdit, QComboBox, QTextEdit,
    QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog, QDialog,
    QDialogButtonBox, QFormLayout, QMenu, QMessageBox,
)
from studio import RetroRipWindow, text_label, button, duration_text
from downloader import create_video_profile
from deck_scene import DeckScene, rounded, label, artwork, ease
from storage import Store
from themes import stylesheet
from player import PlayerDialog

COLORS = {"Forest": "#263d3b", "Midnight": "#263e59", "Terracotta": "#864d3c", "Plum": "#654763", "Graphite": "#35414b"}
PROFILES = ["MP4 Best", "MP4 1080p", "MP4 720p", "MP3 Best Audio"]


class Studio(RetroRipWindow):
    state_changed = Signal(str)
    recorded = Signal(object, bytes)
    kept = Signal()
    problem = Signal(str)

    def __init__(self, demo=False):
        self.cover_data = b""
        self.last_error = ""
        self.automatic = False
        self.current_tape_id = None
        self.default_profile = "MP4 Best"
        super().__init__(demo)
        self.setMinimumSize(0,0)
        self.scene.setMinimumHeight(255)
        self.pages.setFixedHeight(166)
        self.count_label.hide()
        self.sound_btn.hide()
        self.footer_status.hide()
        self.step_label.hide()
        root=self.centralWidget().layout()
        root.setContentsMargins(24,24,24,12)
        header=root.itemAt(0).layout()
        for i in range(header.count()):
            if header.itemAt(i).widget(): header.itemAt(i).widget().hide()
        root.itemAt(1).widget().hide()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Name your tape")
        self.color_combo = QComboBox(); self.color_combo.addItems(COLORS)
        row = QHBoxLayout(); row.addWidget(self.name_edit,1); row.addWidget(self.color_combo)
        self.ready_page.layout().insertLayout(1,row)
        self.name_edit.textChanged.connect(self.apply_label)
        self.color_combo.currentTextChanged.connect(self.apply_label)
        self.quality.currentTextChanged.connect(self.apply_label)
        self.scene.transport.connect(self.transport)

    def transport(self,action):
        if action=="rec": self.insert_tape()
        elif action=="stop": self.stop_download()
        elif action=="eject":
            if self.state=="ready": self.new_tape()
            else: self.stop_download()

    def update_state(self,state):
        super().update_state(state)
        if hasattr(self,"name_edit"):
            editable=state=="ready" and not self.automatic
            self.name_edit.setEnabled(editable); self.color_combo.setEnabled(editable)
            if self.automatic:
                self.quality.setEnabled(False)
                for page in (self.ready_page,self.archived_page,self.stopped_page):
                    for control in page.findChildren(QPushButton): control.setEnabled(False)
            else:
                for page in (self.archived_page,self.stopped_page):
                    for control in page.findChildren(QPushButton): control.setEnabled(True)
                for control in self.ready_page.findChildren(QPushButton): control.setEnabled(state=="ready" and not self.info_job)
        self.state_changed.emit(state)

    def media_ready(self,media,picture):
        if self.demo and not picture: picture=getattr(self,"demo_cover",b"")
        self.cover_data = picture
        self.current_tape_id = None
        self.last_error = ""
        super().media_ready(media,picture)
        self.name_edit.setText(media.title)
        self.select_profile(self.default_profile)
        self.apply_label()

    def select_profile(self,name):
        index = self.quality.findText(name)
        if index < 0 and name.startswith("MP4 ") and name.endswith("p"):
            height = int(name.split()[1][:-1])
            profile = create_video_profile(height)
            self.profiles.append(profile)
            self.quality.addItem(profile.name)
            index = len(self.profiles)-1
        self.quality.setCurrentIndex(max(0,index))

    def apply_label(self,*args):
        if self.media:
            self.scene.title = self.name_edit.text().strip() or self.media.title
            self.scene.tape_color = COLORS[self.color_combo.currentText()]
            self.scene.quality = self.quality.currentText()
            self.scene.update()

    def on_success(self,final_path=None):
        if self.state not in ("recording","processing","stopping"):
            return
        info = dict(title=self.scene.title, original_title=self.media.title, creator=self.media.creator,
                    platform=self.media.platform, duration=self.media.duration,
                    duration_text=duration_text(self.media.duration), quality=self.quality.currentText(),
                    color=self.scene.tape_color, path=final_path or "", url=self.loaded_url, kept=False, demo=self.demo)
        self.recorded.emit(info,self.cover_data)
        super().on_success(final_path)

    def on_archived(self):
        super().on_archived()
        self.kept.emit()

    def new_tape(self):
        if self.automatic: return
        super().new_tape()
        if self.state == "idle":
            self.last_error = ""
            self.current_tape_id = None
            self.cover_data = b""

    def retry(self):
        if self.automatic: return
        self.last_error = ""
        super().retry()

    def on_failed(self,message):
        self.last_error = message
        super().on_failed(message)

    def info_failed(self,message):
        self.last_error = message
        super().info_failed(message)

    def show_error(self,title,message):
        self.problem.emit(title + ": " + message)
        if not self.automatic:
            super().show_error(title,message)


class TapeArt(QWidget):
    clicked = Signal()
    def __init__(self,tape,cover,parent=None):
        super().__init__(parent)
        self.setMinimumHeight(158)
        self.setCursor(Qt.PointingHandCursor)
        self.renderer = DeckScene(self)
        self.renderer.hide(); self.renderer.timer.stop()
        self.renderer.load(tape["title"],tape.get("creator",""),tape.get("platform",""),tape.get("duration_text",""),cover)
        self.renderer.quality = tape.get("quality","")
        self.renderer.tape_color = tape.get("color","#263d3b")
        self.renderer.mode = "ready"
        self.hover = False

    def enterEvent(self,event):
        self.hover = True; self.update()
    def leaveEvent(self,event):
        self.hover = False; self.update()
    def mousePressEvent(self,event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHints(QPainter.Antialiasing|QPainter.SmoothPixmapTransform)
        rounded(p,4,self.height()-11,self.width()-8,8,3,"#b29976")
        rounded(p,5,self.height()-12,self.width()-10,3,1,"#d2bd98")
        s=min((self.width()-14)/380,(self.height()-20)/220)
        p.translate(self.width()/2,self.height()/2-10 if self.hover else self.height()/2-6)
        p.scale(s,s)
        self.renderer.draw_tape(p,0,0,1,-2 if self.hover else 0)
        p.end()


class ArchiveFlight(QWidget):
    def __init__(self,parent,start,end,title,cover):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setGeometry(parent.rect())
        self.start,self.end,self.title=start,end,title
        self.cover=QPixmap(); self.cover.loadFromData(cover)
        self.t=0.0
        self.animation=QVariantAnimation(self)
        self.animation.setStartValue(0.0); self.animation.setEndValue(1.0)
        self.animation.setDuration(1000); self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.valueChanged.connect(self.advance)
        self.animation.finished.connect(self.deleteLater)
        self.show(); self.raise_(); self.animation.start()
    def advance(self,value):
        self.t=value; self.update()
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        t=self.t; x=(1-t)*self.start.x()+t*self.end.x(); y=(1-t)*self.start.y()+t*self.end.y()-110*math.sin(math.pi*t)
        p.translate(x,y); p.rotate(7*(1-t)); p.scale(1-.8*t,1-.8*t)
        p.setOpacity(1-max(0,(t-.9)*10))
        rounded(p,-110,-58,220,126,7,"#ddcba6","#b69e78")
        artwork(p,QRectF(-92,-40,65,52),self.cover)
        label(p,-18,-17,self.title,12,"#30483f",True,width=109)
        label(p,-90,47,"RETRO RIP / COLLECTION",9,"#846b4d",True,True)
        p.end()


class QueueStack(QWidget):
    """A physical stack that settles when the next cassette is picked up."""
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFixedHeight(172)
        self.items=[]; self.dark=False; self.shift=0
        self.motion=QVariantAnimation(self); self.motion.setStartValue(24.0); self.motion.setEndValue(0.0)
        self.motion.setDuration(650); self.motion.setEasingCurve(QEasingCurve.OutCubic)
        self.motion.valueChanged.connect(self.move_stack)
    def move_stack(self,value):
        self.shift=value; self.update()
    def set_items(self,items):
        pending=[x for x in items if x["status"]=="pending"]
        if [x["id"] for x in pending]!=[x["id"] for x in self.items]: self.motion.start()
        self.items=pending; self.update()
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.translate(30,16+self.shift)
        for i in range(min(4,max(1,len(self.items)))-1,-1,-1):
            p.save(); p.translate(i*18,i*22); p.rotate(-3+i*2)
            rounded(p,3,7,285,66,8,"#0b1b23")
            rounded(p,0,0,285,66,8,list(COLORS.values())[i],"#6b8584")
            rounded(p,13,10,257,43,4,"#ecdfbe")
            p.fillRect(QRectF(13,10,7,43),QColor("#d17b4b"))
            text=self.items[i].get("title",self.items[i]["url"]) if i<len(self.items) else "YOUR NEXT MIXTAPE"
            label(p,29,28,text,11,"#29423e",True,width=228)
            label(p,29,45,f"{i+1:02} / WAITING TO RECORD" if self.items else "PASTE A LINK TO START",8,"#8d765a",mono=True)
            p.restore()
        p.resetTransform()
        label(p,410,70,f"{len(self.items):02} TAPES IN THE STACK",19,"#e0e7df" if self.dark else "#29434d",True)
        label(p,410,97,"One goes in. One comes out. Every one is kept.",12,"#a3b4b1" if self.dark else "#828f85")
        p.end()


class AppWindow(QMainWindow):
    def __init__(self,data_dir=None,demo=False):
        super().__init__()
        self.demo=demo
        self._temporary=tempfile.TemporaryDirectory(prefix="retrorip-demo-") if demo and not data_dir else None
        location=data_dir or (self._temporary.name if self._temporary else QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
        self.store=Store(location)
        self.queue_running=False
        self.active_queue=None
        self.queue_terminal=None
        self.queue_after=0
        self.last_state=""
        self.players=[]
        self.dark=self.store.setting("theme","light")=="dark"
        self.setWindowTitle("RetroRip • Pocket Studio 1.0"+(" • DEMO" if demo else ""))
        self.resize(1340,900); self.setMinimumSize(1100,780)
        self.build_shell()
        self.studio=Studio(demo)
        self.studio.output_folder=self.store.setting("output",str(Path.home()/"Downloads"/"RetroRip"))
        self.studio.folder_label.setText("SAVING TO / "+self.studio.output_folder)
        self.studio.default_profile=self.store.setting("quality","MP4 Best")
        self.studio.sound_enabled=self.store.setting("sound",True)
        self.studio.state_changed.connect(self.studio_changed)
        self.studio.recorded.connect(self.save_recording)
        self.studio.kept.connect(self.archive_recording)
        self.studio.problem.connect(self.notify)
        self.studio.change_btn.hide()
        self.build_home()
        self.stack.addWidget(self.studio)
        self.build_collection()
        self.build_queue()
        self.build_settings()
        self.apply_theme(self.dark,save=False)
        self.refresh_catalog()
        self.refresh_queue()
        self.navigate(0)
        self.pump=QTimer(self); self.pump.setInterval(250); self.pump.timeout.connect(self.queue_tick); self.pump.start()
        if demo:
            self.seed_demo()
            self.studio.demo_cover=self.store.cover(self.store.tapes()[-1]["id"])

    def build_shell(self):
        root=QWidget(); root.setObjectName("shell"); self.setCentralWidget(root)
        row=QHBoxLayout(root); row.setContentsMargins(0,0,0,0); row.setSpacing(0)
        sidebar=QFrame(); sidebar.setObjectName("sidebar"); sidebar.setFixedWidth(190)
        nav=QVBoxLayout(sidebar); nav.setContentsMargins(18,27,18,20); nav.setSpacing(9)
        nav.addWidget(text_label("▰ RETRORIP","brand"))
        nav.addWidget(text_label("POCKET STUDIO / 1.0","navSmall")); nav.addSpacing(33)
        self.nav=[]
        for i,name in enumerate(("⌂   Home","●   Studio","▤   Collection","≡   Queue","⚙   Settings")):
            b=button(name,lambda checked=False,index=i:self.navigate(index),"nav")
            b.setCheckable(True); nav.addWidget(b); self.nav.append(b)
        nav.addStretch()
        self.catalog_count=text_label("0 TAPES","stat"); nav.addWidget(self.catalog_count)
        nav.addWidget(text_label("Your own little archive.","hint"))
        nav.addSpacing(18)
        self.theme_toggle=button("☾ DARK THEME",lambda:self.apply_theme(not self.dark),"secondary")
        nav.addWidget(self.theme_toggle)
        row.addWidget(sidebar)
        body=QVBoxLayout(); body.setContentsMargins(14,8,14,12)
        self.stack=QStackedWidget(); body.addWidget(self.stack,1)
        bar=QFrame(); bar.setObjectName("statusbar")
        layout=QHBoxLayout(bar)
        self.global_status=text_label("Ready to make a tape.","hint",elide=True); layout.addWidget(self.global_status,1)
        self.global_progress=text_label("","readout"); layout.addWidget(self.global_progress)
        layout.addWidget(button("BACK TO STUDIO →",lambda:self.navigate(1),"quiet"))
        body.addWidget(bar); row.addLayout(body,1)

    def page(self,title,subtitle):
        page=QWidget(); page.setObjectName("page")
        layout=QVBoxLayout(page); layout.setContentsMargins(24,24,24,16); layout.setSpacing(15)
        layout.addWidget(text_label(title,"pageTitle"))
        layout.addWidget(text_label(subtitle,"hint"))
        self.stack.addWidget(page)
        return page,layout

    def build_home(self):
        self.home,layout=self.page("A little analog soul.","Welcome to your personal recording room. Link it. Spin it. Keep it.")
        feature=QFrame(); feature.setObjectName("card"); r=QHBoxLayout(feature)
        words=QVBoxLayout(); words.addWidget(text_label("The internet.\nOn your shelf.","pageTitle"))
        words.addWidget(text_label("Record a favorite, give it a name,\nand make a little collection of your own.","hint"))
        words.addWidget(button("● MAKE A NEW TAPE",self.go_studio,"primary"))
        words.addWidget(button("+ IMPORT EXISTING FILES",self.import_files,"secondary")); words.addStretch()
        r.addLayout(words,1)
        self.home_scene=DeckScene(); self.home_scene.setMinimumSize(390,230); self.home_scene.setMaximumHeight(320)
        self.home_scene.transport.connect(lambda action:self.go_studio())
        r.addWidget(self.home_scene,2); layout.addWidget(feature)
        row=QHBoxLayout(); self.home_summary=text_label("","panelTitle"); row.addWidget(self.home_summary); row.addStretch()
        row.addWidget(button("VIEW COLLECTION →",lambda:self.navigate(2),"quiet")); layout.addLayout(row)
        self.recent=QWidget(); self.recent_layout=QHBoxLayout(self.recent); self.recent_layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.recent); layout.addStretch()

    def build_collection(self):
        self.collection,layout=self.page("Your tape shelf.","A cover, a name, a memory. Click a cassette to play it.")
        row=QHBoxLayout(); self.search=QLineEdit(); self.search.setPlaceholderText("Search titles or creators…")
        self.search.textChanged.connect(self.refresh_catalog); row.addWidget(self.search,1)
        row.addWidget(button("+ IMPORT FILES",self.import_files,"primary")); layout.addLayout(row)
        self.collection_empty=text_label("Make your first tape in Studio, or import media you already have.","hint")
        layout.addWidget(self.collection_empty)
        scroll=QScrollArea(); scroll.setWidgetResizable(True)
        content=QWidget(); self.shelf=QGridLayout(content); self.shelf.setAlignment(Qt.AlignTop); self.shelf.setSpacing(16)
        scroll.setWidget(content); layout.addWidget(scroll,1)

    def build_queue(self):
        self.queue_page,layout=self.page("Next on the deck.","Stack up a few links. We'll record and shelve them one at a time.")
        self.queue_art=QueueStack(); layout.addWidget(self.queue_art)
        self.queue_input=QTextEdit(); self.queue_input.setPlaceholderText("Paste one URL per line…")
        self.queue_input.setMaximumHeight(110); layout.addWidget(self.queue_input)
        row=QHBoxLayout(); self.queue_profile=QComboBox(); self.queue_profile.addItems(PROFILES)
        row.addWidget(self.queue_profile); row.addWidget(button("+ ADD TO STACK",self.add_queue,"primary")); row.addStretch()
        self.queue_start=button("▶ START QUEUE",self.start_queue,"primary"); row.addWidget(self.queue_start)
        row.addWidget(button("Ⅱ PAUSE AFTER CURRENT",self.pause_queue,"secondary")); layout.addLayout(row)
        self.queue_summary=text_label("","hint"); layout.addWidget(self.queue_summary)
        self.queue_table=QTableWidget(0,4); self.queue_table.setHorizontalHeaderLabels(["TAPE / LINK","FORMAT","STATUS","ACTION"])
        self.queue_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch)
        for col in (1,2,3): self.queue_table.horizontalHeader().setSectionResizeMode(col,QHeaderView.ResizeToContents)
        self.queue_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.queue_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.queue_table.verticalHeader().hide(); layout.addWidget(self.queue_table,1)

    def build_settings(self):
        self.settings_page,layout=self.page("Make yourself at home.","Your preferences are saved automatically on this computer.")
        panel=QFrame(); panel.setObjectName("card"); form=QFormLayout(panel); form.setContentsMargins(24,24,24,24); form.setSpacing(22)
        self.theme_combo=QComboBox(); self.theme_combo.addItems(["Light — Cream studio","Dark — Midnight studio"])
        self.theme_combo.setCurrentIndex(1 if self.dark else 0)
        self.theme_combo.currentIndexChanged.connect(lambda i:self.apply_theme(i==1)); form.addRow("Appearance",self.theme_combo)
        self.default_quality=QComboBox(); self.default_quality.addItems(PROFILES)
        self.default_quality.setCurrentText(self.studio.default_profile)
        self.default_quality.currentTextChanged.connect(self.save_quality); form.addRow("Default recording format",self.default_quality)
        self.sound_check=QCheckBox("Mechanical button and cassette sounds")
        self.sound_check.setChecked(self.studio.sound_enabled); self.sound_check.toggled.connect(self.save_sound)
        form.addRow("Sound effects",self.sound_check)
        row=QHBoxLayout(); self.output_value=text_label(self.studio.output_folder,"hint",elide=True)
        row.addWidget(self.output_value,1); row.addWidget(button("CHOOSE…",self.choose_output,"secondary")); form.addRow("Download folder",row)
        form.addRow("Collection data",button("OPEN DATA FOLDER ↗",lambda:self.open_path(self.store.directory),"secondary"))
        layout.addWidget(panel)
        layout.addWidget(text_label("RetroRip Pocket Studio 1.0\nPython · Qt · yt-dlp\nFFmpeg is required for video/audio merging and MP3 conversion.","hint"))
        layout.addStretch()

    def navigate(self,index):
        if index>=self.stack.count(): return
        self.stack.setCurrentIndex(index)
        for i,b in enumerate(self.nav): b.setChecked(i==index)

    def go_studio(self):
        if self.studio.state in ("archived","stopped") and not self.active_queue:
            self.studio.new_tape()
        self.navigate(1)

    def apply_theme(self,dark,save=True):
        self.dark=bool(dark)
        style=stylesheet(self.dark)
        self.setStyleSheet(style); self.studio.setStyleSheet(style)
        self.studio.scene.dark=self.dark; self.home_scene.dark=self.dark
        self.queue_art.dark=self.dark; self.queue_art.update()
        palette=QApplication.instance().palette()
        for role,shade in ((QPalette.Window,"#131c24" if dark else "#f3f0e7"),(QPalette.WindowText,"#dce5de" if dark else "#273f48"),
                           (QPalette.Base,"#1c2933" if dark else "#fffcf5"),(QPalette.Text,"#dce5de" if dark else "#273f48")):
            palette.setColor(role,QColor(shade))
        QApplication.instance().setPalette(palette)
        self.theme_toggle.setText("☀ LIGHT THEME" if dark else "☾ DARK THEME")
        if hasattr(self,"theme_combo"):
            self.theme_combo.blockSignals(True); self.theme_combo.setCurrentIndex(int(dark)); self.theme_combo.blockSignals(False)
        if save: self.store.set_setting("theme","dark" if dark else "light")
        for player in self.players:
            player.setStyleSheet(style); player.scene.dark=dark

    def save_quality(self,value):
        self.studio.default_profile=value; self.store.set_setting("quality",value)
    def save_sound(self,value):
        self.studio.sound_enabled=value; self.store.set_setting("sound",value)
    def choose_output(self):
        if self.studio.state not in ("idle","ready","archived","stopped","complete"):
            self.notify("Change the output folder after the current recording finishes."); return
        folder=QFileDialog.getExistingDirectory(self,"Choose output folder",self.studio.output_folder)
        if folder:
            self.studio.output_folder=folder; self.store.set_setting("output",folder)
            self.output_value.setText(folder); self.studio.folder_label.setText("SAVING TO / "+folder)

    def notify(self,text):
        self.global_status.setText(str(text))
    def studio_changed(self,state):
        changed=state!=self.last_state
        self.last_state=state
        title=self.studio.scene.title if self.studio.media else "Ready to make a tape"
        self.global_status.setText(f"{state.upper()}  /  {title}")
        if self.active_queue:
            if changed:
                self.store.update_queue(self.active_queue,status=state,title=title)
            if state=="idle" and self.studio.last_error:
                self.queue_terminal="failed"
            elif state=="stopped":
                self.queue_terminal="failed" if self.studio.last_error else "cancelled"
            if changed: self.refresh_queue()

    def save_recording(self,info,cover):
        try:
            if self.demo and not info["path"]:
                info["path"]=str(self.demo_audio())
            tape=self.store.add_tape(info,cover)
            self.studio.current_tape_id=tape["id"]
            self.refresh_catalog()
        except Exception as exc:
            self.queue_running=False
            self.studio.current_tape_id=None
            self.studio.last_error="Could not save the collection: "+str(exc)
            QMessageBox.warning(self,"Collection could not be saved",f"The media file remains in the output folder.\n{exc}")

    def archive_recording(self):
        key=self.studio.current_tape_id
        if key:
            self.store.update_tape(key,kept=True)
            tape=self.store.tape(key)
            start=self.studio.scene.mapTo(self,QPointF(self.studio.scene.width()*.8,self.studio.scene.height()*.8).toPoint()) if self.stack.currentIndex()==1 else self.global_status.mapTo(self,self.global_status.rect().center())
            end=self.nav[2].mapTo(self,self.nav[2].rect().center())
            ArchiveFlight(self,QPointF(start),QPointF(end),tape["title"],self.store.cover(key))
        if self.active_queue:
            self.queue_terminal="complete" if key else "failed"
        self.refresh_catalog()

    @staticmethod
    def clear_layout(layout):
        while layout.count():
            item=layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def tape_card(self,tape,compact=False):
        frame=QFrame(); frame.setObjectName("card"); frame.setMinimumWidth(235)
        layout=QVBoxLayout(frame); layout.setContentsMargins(12,12,12,12)
        art=TapeArt(tape,self.store.cover(tape["id"])); art.clicked.connect(lambda:self.play_tape(tape["id"]))
        layout.addWidget(art)
        layout.addWidget(text_label(tape["title"],"panelTitle",elide=True))
        layout.addWidget(text_label(tape.get("quality","Local")+"  ·  "+tape.get("duration_text","—"),"hint"))
        row=QHBoxLayout(); row.addWidget(button("▶ PLAY",lambda:self.play_tape(tape["id"]),"primary"),1)
        more=button("•••",lambda:self.tape_menu(tape["id"],frame),"secondary"); row.addWidget(more)
        layout.addLayout(row)
        return frame

    def refresh_catalog(self,*args):
        if not hasattr(self,"shelf"): return
        all_tapes=self.store.tapes()
        self.catalog_count.setText(f"{len(all_tapes):03} TAPES")
        self.home_summary.setText(f"RECENT RECORDINGS  /  {len(all_tapes)} in your collection")
        self.clear_layout(self.shelf); self.clear_layout(self.recent_layout)
        items=self.store.tapes(self.search.text())
        self.collection_empty.setVisible(not items)
        cols=3 if self.width()>=1250 else 2
        for i,tape in enumerate(items): self.shelf.addWidget(self.tape_card(tape),i//cols,i%cols)
        for tape in all_tapes[:2]: self.recent_layout.addWidget(self.tape_card(tape,True))
        if not all_tapes:
            self.recent_layout.addWidget(text_label("Your first cassette is waiting to be made.","hint"))

    def tape_menu(self,key,widget):
        menu=QMenu(self)
        menu.addAction("Open file externally",lambda:self.open_tape(key))
        menu.addAction("Open containing folder",lambda:self.open_tape(key,folder=True))
        menu.addAction("Edit name / tape color",lambda:self.edit_tape(key))
        menu.addAction("Locate moved file…",lambda:self.locate_tape(key))
        menu.exec(widget.mapToGlobal(widget.rect().bottomRight()))

    def resolve_tape(self,key):
        tape=self.store.tape(key)
        if tape and Path(tape["path"]).is_file(): return tape
        self.notify("File is missing or moved. Use ••• → Locate moved file.")
        return None
    def play_tape(self,key):
        tape=self.resolve_tape(key)
        if not tape: return
        player=PlayerDialog(tape,self.store.cover(key),self.dark,self)
        player.setStyleSheet(stylesheet(self.dark)); self.players.append(player)
        player.finished.connect(lambda result:self.players.remove(player) if player in self.players else None)
        player.show(); player.toggle()
    def open_path(self,path):
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))): self.notify("Could not open: "+str(path))
    def open_tape(self,key,folder=False):
        tape=self.resolve_tape(key)
        if tape: self.open_path(Path(tape["path"]).parent if folder else tape["path"])
    def locate_tape(self,key):
        path,_=QFileDialog.getOpenFileName(self,"Locate the media file")
        if path: self.store.update_tape(key,path=path); self.refresh_catalog()

    def edit_tape(self,key):
        tape=self.store.tape(key)
        dialog=QDialog(self); dialog.setWindowTitle("Edit tape label"); dialog.setMinimumWidth(410)
        form=QFormLayout(dialog); name=QLineEdit(tape["title"]); colors=QComboBox(); colors.addItems(COLORS)
        colors.setCurrentText(next((k for k,v in COLORS.items() if v==tape.get("color")),"Forest"))
        form.addRow("Tape name",name); form.addRow("Shell color",colors)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); form.addRow(buttons)
        if dialog.exec()==QDialog.Accepted and name.text().strip():
            self.store.update_tape(key,title=name.text().strip(),color=COLORS[colors.currentText()]); self.refresh_catalog()

    def import_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,"Import existing recordings",self.studio.output_folder,"Media (*.mp4 *.mkv *.webm *.mp3 *.wav *.m4a *.flac *.ogg);;All files (*)")
        for path in paths:
            self.store.add_tape(dict(title=Path(path).stem,creator="Local file",platform="Local",duration_text="—",quality=Path(path).suffix[1:].upper(),path=path,url="",color=list(COLORS.values())[len(self.store.tapes())%len(COLORS)],kept=True))
        self.refresh_catalog()

    def add_queue(self):
        urls=[line.strip() for line in self.queue_input.toPlainText().splitlines() if line.strip()]
        try: valid=bool(urls) and all(urlsplit(u).scheme in ("http","https") and urlsplit(u).netloc for u in urls)
        except ValueError: valid=False
        if not valid:
            self.notify("Paste complete http:// or https:// links, one per line."); return
        self.store.add_queue(list(dict.fromkeys(urls)),self.queue_profile.currentText())
        self.queue_input.clear(); self.refresh_queue(); self.notify(f"Added {len(set(urls))} tapes to the queue.")

    def start_queue(self):
        if not self.active_queue and self.studio.state not in ("idle","archived","stopped"):
            self.notify("Finish or reset the current Studio tape before starting the queue."); return
        self.queue_running=True; self.refresh_queue()
    def pause_queue(self):
        self.queue_running=False; self.refresh_queue(); self.notify("Queue paused. The current tape will finish and be kept.")
    def cancel_queue_item(self,key):
        if key==self.active_queue:
            if self.studio.state in ("analyzing","ready"):
                self.queue_terminal="cancelled"; self.notify("Cancelling this item when analysis returns.")
            elif self.studio.state in ("ejecting","complete","archiving","archived"):
                self.notify("This recording has finished and is being saved.")
            else: self.studio.stop_download()
        else: self.store.update_queue(key,status="cancelled")
        self.refresh_queue()
    def retry_queue_item(self,key):
        self.store.update_queue(key,status="pending",error=""); self.refresh_queue()

    def refresh_queue(self):
        if not hasattr(self,"queue_table"): return
        items=self.store.queue(); self.queue_table.setRowCount(len(items))
        self.queue_art.set_items(items)
        for row,item in enumerate(items):
            for col,text in enumerate((item.get("title",item["url"]),item["profile"],item["status"].upper())):
                cell=QTableWidgetItem(text); cell.setToolTip(item.get("error") or item["url"]); self.queue_table.setItem(row,col,cell)
            key=item["id"]
            if item["status"] in ("failed","cancelled"):
                action=button("RETRY",lambda checked=False,k=key:self.retry_queue_item(k),"quiet")
            elif item["status"]=="complete": action=text_label("✓ KEPT","hint")
            else: action=button("CANCEL",lambda checked=False,k=key:self.cancel_queue_item(k),"quiet")
            self.queue_table.setCellWidget(row,3,action); self.queue_table.setRowHeight(row,51)
        pending=sum(x["status"]=="pending" for x in items)
        self.nav[3].setText(f"≡   Queue  {pending}")
        self.queue_summary.setText(f"{'RUNNING' if self.queue_running else 'PAUSED'}  /  {pending} waiting  /  one recording at a time")

    def queue_tick(self):
        s=self.studio
        self.global_progress.setText(s.percent_label.text() if s.state in ("recording","processing","stopping") else "")
        if self.active_queue:
            if self.queue_terminal and not s.info_job and not s.download_job and s.state in ("idle","archived","stopped","ready"):
                self.store.update_queue(self.active_queue,status=self.queue_terminal,error=s.last_error)
                self.active_queue=None; self.queue_terminal=None; s.automatic=False
                s.default_profile=self.store.setting("quality","MP4 Best")
                if s.state in ("archived","stopped","ready"): s.new_tape()
                self.refresh_queue(); return
            if self.queue_terminal=="cancelled": return
            if s.state=="ready" and not s.info_job:
                s.insert_tape()
            elif s.state=="complete" and not s.download_job:
                s.keep_tape()
            return
        if not self.queue_running or s.info_job or s.download_job: return
        if s.state not in ("idle","archived","stopped"): return
        pending=next((x for x in self.store.queue() if x["status"]=="pending"),None)
        if not pending:
            self.queue_running=False; self.refresh_queue(); return
        if s.state!="idle": s.new_tape()
        self.active_queue=pending["id"]; self.queue_terminal=None
        s.automatic=True; s.last_error=""; s.default_profile=pending["profile"]
        s.url_input.setText(pending["url"]); s.analyze()

    def demo_audio(self):
        path=self.store.directory/"demo-tone.wav"
        if not path.exists():
            import struct
            with wave.open(str(path),"wb") as f:
                f.setnchannels(1); f.setsampwidth(2); f.setframerate(22050)
                f.writeframes(b"".join(struct.pack("<h",int(1800*math.sin(i*2*math.pi*220/22050))) for i in range(22050*3)))
        return path

    def seed_demo(self):
        if self.store.tapes(): return
        path=str(self.demo_audio())
        for i,title in enumerate(("Night drive / city lights","Sunday, on repeat","Little things worth keeping")):
            cover=QPixmap(480,270); p=QPainter(cover); p.setRenderHint(QPainter.Antialiasing)
            g=QLinearGradient(0,0,480,270)
            g.setColorAt(0,QColor(("#183b57","#6a8071","#be785f")[i])); g.setColorAt(1,QColor(("#815670","#d9bc87","#dbc791")[i]))
            p.fillRect(cover.rect(),g); p.setPen(Qt.NoPen); p.setBrush(QColor("#ebc57f")); p.drawEllipse(QRectF(305,38,92,92))
            p.setBrush(QColor(("#102a43","#344e4b","#775c55")[i]))
            for j in range(12): p.drawRoundedRect(QRectF(j*44-10,160+(j%3)*14,35,120),4,4)
            p.end(); data=QByteArray(); buffer=QBuffer(data); buffer.open(QIODevice.WriteOnly); cover.save(buffer,"PNG")
            self.store.add_tape(dict(title=title,creator="RetroRip Demo",platform="Demo",duration_text="00:03",duration=3,quality="WAV Demo",path=path,color=list(COLORS.values())[i],kept=True,demo=True),bytes(data))
        self.refresh_catalog()

    def closeEvent(self,event):
        if self.studio.info_job or self.studio.download_job:
            self.notify("Use STOP and wait for the active job before closing."); event.ignore(); return
        self.pump.stop(); self.studio.demo_timer.stop(); self.studio.scene.timer.stop(); self.home_scene.timer.stop()
        for player in list(self.players): player.close()
        self.store.close(); event.accept()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--demo",action="store_true")
    parser.add_argument("--data-dir",help="Optional custom catalog directory")
    args=parser.parse_args()
    app=QApplication([]); app.setApplicationName("RetroRip"); app.setOrganizationName("RetroRip")
    app.setWindowIcon(QIcon(str(Path(__file__).resolve().parent/"assets"/"retrorip.svg")))
    app.setStyle("Fusion"); app.setFont(QFont("Segoe UI",10))
    window=AppWindow(args.data_dir,args.demo); window.show()
    return app.exec()


if __name__=="__main__":
    raise SystemExit(main())
