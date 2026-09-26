"""A resolution-independent Walkman, cassette and sleeve, painted with Qt.

All transitions use one elapsed-time clock; there are no sleeps on the UI thread.
"""
import math
import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QSizePolicy, QWidget


def color(value, alpha=None):
    c = QColor(value)
    if alpha is not None:
        c.setAlphaF(max(0.0, min(1.0, alpha)))
    return c


def mix(a, b, t):
    return a + (b - a) * t


def ease(t):
    return t * t * (3 - 2 * t)


def rounded(p, x, y, w, h, r, fill, stroke=None, width=1):
    p.setPen(QPen(color(stroke), width) if stroke else Qt.NoPen)
    p.setBrush(color(fill) if isinstance(fill, str) else fill)
    p.drawRoundedRect(QRectF(x, y, w, h), r, r)


def label(p, x, y, text, size=12, ink="#263a42", bold=False, mono=False, width=None):
    font = QFont("Consolas" if mono else "Segoe UI", size)
    font.setPixelSize(size)
    font.setBold(bold)
    p.setFont(font)
    p.setPen(color(ink))
    if width:
        text = p.fontMetrics().elidedText(text, Qt.ElideRight, int(width))
    p.drawText(QPointF(x, y), text)


def gradient(y1, y2, stops):
    g = QLinearGradient(0, y1, 0, y2)
    for pos, shade in stops:
        g.setColorAt(pos, color(shade))
    return g


def artwork(p, rect, pixmap):
    if pixmap.isNull():
        # Original geometric print used until a video thumbnail is available.
        p.fillRect(rect, color("#174f59"))
        p.save()
        p.setClipRect(rect)
        for i in range(6):
            p.setPen(QPen(color("#f08048" if i % 2 else "#efcf80"), 9))
            y = rect.y() + 8 + i * 16
            p.drawLine(QPointF(rect.x() - 20, y + 50), QPointF(rect.right() + 20, y - 30))
        p.restore()
    else:
        factor = max(rect.width() / pixmap.width(), rect.height() / pixmap.height())
        sw, sh = rect.width() / factor, rect.height() / factor
        source = QRectF((pixmap.width() - sw) / 2, (pixmap.height() - sh) / 2, sw, sh)
        p.drawPixmap(rect, pixmap, source)


class DeckScene(QWidget):
    inserted = Signal()
    ejected = Signal()
    archived = Signal()
    mechanical = Signal()
    WIDTH, HEIGHT = 1080, 438
    TRANSITIONS = {"inserting": 1.65, "ejecting": 1.55, "archiving": 1.65, "loading": .65}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.mode = "idle"
        self.title = "YOUR NEXT FAVORITE"
        self.creator = "A little piece of the internet."
        self.platform = "RETRO RIP"
        self.duration = "C—90"
        self.cover = QPixmap()
        self.saved_title = ""
        self.saved_cover = QPixmap()
        self.saved_count = 0
        self.outcome = "success"
        self.phase = 0.0
        self.angle = 0.0
        self.velocity = 0.0
        self.progress = 0.0
        self.visual_progress = 0.0
        self.start_time = time.perf_counter()
        self.last_time = self.start_time
        self.transition = 0.0
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)

    def set_mode(self, mode):
        self.mode = mode
        self.start_time = time.perf_counter()
        self.transition = 0.0
        self.update()

    def load(self, title, creator, platform, duration, picture=b""):
        self.title, self.creator, self.platform, self.duration = title, creator, platform, duration
        self.cover = QPixmap()
        if picture:
            self.cover.loadFromData(picture)
        self.progress = self.visual_progress = 0.0
        self.set_mode("loading")

    def insert(self):
        self.set_mode("inserting")
        self.mechanical.emit()

    def finish(self, success=True):
        self.outcome = "success" if success else "stopped"
        self.set_mode("ejecting")
        self.mechanical.emit()

    def archive(self):
        self.saved_title = self.title
        self.saved_cover = self.cover.copy()
        self.set_mode("archiving")
        self.mechanical.emit()

    def reset(self):
        self.title = "YOUR NEXT FAVORITE"
        self.creator = "A little piece of the internet."
        self.platform, self.duration = "RETRO RIP", "C—90"
        self.cover = QPixmap()
        self.progress = self.visual_progress = 0.0
        self.outcome = "success"
        self.set_mode("idle")

    def tick(self):
        now = time.perf_counter()
        dt = min(.06, now - self.last_time)
        self.last_time = now
        self.phase += dt
        recording = self.mode in ("recording", "processing", "stopping")
        speed = 165 if self.mode == "recording" else 78 if recording else 0
        self.velocity += (speed - self.velocity) * min(1, dt * 6)
        self.angle = (self.angle + self.velocity * dt) % 360
        self.visual_progress += (self.progress - self.visual_progress) * min(1, dt * 5)
        duration = self.TRANSITIONS.get(self.mode)
        if duration:
            self.transition = min(1.0, (now - self.start_time) / duration)
            if self.transition >= 1:
                old = self.mode
                if old == "inserting":
                    self.set_mode("recording")
                    self.mechanical.emit()
                    self.inserted.emit()
                elif old == "ejecting":
                    self.set_mode("complete" if self.outcome == "success" else "stopped")
                    self.ejected.emit()
                elif old == "archiving":
                    self.saved_count += 1
                    self.set_mode("archived")
                    self.mechanical.emit()
                    self.archived.emit()
                else:
                    self.set_mode("ready")
        if self.isVisible():
            self.update()

    def tape_pose(self):
        # Positions correspond to the cassette center in the scene.
        ready = (795, 180, .91, 9)
        seated = (399.56, 245.88, .96, -9)
        complete = (740, 147, 1.00, -7)
        t = ease(self.transition)
        if self.mode == "inserting":
            return (mix(ready[0], seated[0], t), mix(ready[1], seated[1], t) - 42 * math.sin(t * math.pi),
                    mix(ready[2], seated[2], t), mix(ready[3], seated[3], t))
        if self.mode in ("recording", "processing", "stopping"):
            return seated
        if self.mode == "ejecting":
            return (mix(seated[0], complete[0], t), mix(seated[1], complete[1], t) - 65 * math.sin(t * math.pi),
                    mix(seated[2], complete[2], t), mix(seated[3], complete[3], t))
        if self.mode == "archiving":
            # Cubic Bezier ending behind the sleeve's front lip.
            u = 1 - t
            x = u ** 3 * complete[0] + 3 * u * u * t * 860 + 3 * u * t * t * 936 + t ** 3 * 868
            y = u ** 3 * complete[1] + 3 * u * u * t * 25 + 3 * u * t * t * 145 + t ** 3 * 338
            return x, y, mix(1, .63, t), mix(-7, 7, t)
        if self.mode in ("complete", "stopped"):
            return complete[0], complete[1] + math.sin(self.phase * 1.7) * 3, complete[2], complete[3]
        if self.mode == "loading":
            return ready[0], ready[1] + (1-t) * 30, ready[2], ready[3] + (1-t) * 7
        return ready[0], ready[1] + math.sin(self.phase * 1.3) * 4, ready[2], ready[3]

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        s = min(self.width() / self.WIDTH, self.height() / self.HEIGHT)
        p.translate((self.width() - self.WIDTH * s) / 2, (self.height() - self.HEIGHT * s) / 2)
        p.scale(s, s)
        self.draw_environment(p)
        self.draw_device(p)
        self.draw_sleeve(p, front=False)
        sleeve_before = self.mode == "archiving" and self.transition < .72
        if sleeve_before:
            self.draw_sleeve(p, front=True)
        if self.mode != "archived":
            self.draw_tape(p, *self.tape_pose())
        self.draw_door(p)
        if not sleeve_before:
            self.draw_sleeve(p, front=True)
        self.draw_notes(p)
        p.end()

    def draw_environment(self, p):
        glow = QRadialGradient(QPointF(455, 265), 400)
        glow.setColorAt(0, color("#e8e5d9", .9))
        glow.setColorAt(1, color("#e8e5d9", 0))
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QRectF(20, -40, 870, 550))
        # The cable and 3.5 mm plug run behind the chassis.
        path = QPainterPath(QPointF(203, 125))
        path.cubicTo(75, 62, 51, 270, 135, 324)
        path.cubicTo(208, 367, 105, 400, 86, 355)
        p.setPen(QPen(color("#24383c"), 6, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.setPen(QPen(color("#798883"), 1.4))
        p.drawPath(path)
        p.save()
        p.translate(85, 351)
        p.rotate(-18)
        rounded(p, -8, -29, 16, 30, 4, "#2b454b", "#172b33")
        rounded(p, -4, -54, 8, 26, 2, "#d6bc76", "#8e856b")
        for y in (-46, -38):
            p.fillRect(QRectF(-4, y, 8, 2), color("#31413e"))
        p.restore()
        for i in range(20, 0, -1):
            rounded(p, 164-i*.55, 369-i*.3, 493+i*1.1, 19+i*.6, 18, color("#3d463c", .009))

    def device_transform(self, p):
        p.translate(398, 236)
        p.rotate(-9)
        p.translate(-224, -167)

    def draw_device(self, p):
        p.save()
        self.device_transform(p)
        # Orange mechanical keys along the upper rim.
        for i in range(5):
            rounded(p, 75+i*51, -15, 43, 29, 5, "#ca5b36" if i == 0 else "#536466", "#213b42", 2)
            p.fillRect(QRectF(79+i*51, -12, 35, 2), color("#efab7f" if i == 0 else "#80908b"))
        rounded(p, 6, 7, 448, 333, 24, "#162d35", "#1d353f", 2)
        rounded(p, 0, 0, 448, 332, 22,
                gradient(0,332,[(0,"#447483"),(.06,"#2c586c"),(.55,"#204255"),(1,"#193849")]), "#6e8c91", 1.5)
        # Brushed finish: subtle, deterministic horizontal striations.
        p.save()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(3, 3, 442, 325), 20, 20)
        p.setClipPath(clip)
        for y in range(9, 325, 4):
            p.setPen(QPen(color("#b6cac4", .035), .7))
            p.drawLine(QPointF(5,y), QPointF(440,y))
        p.restore()
        label(p, 27, 34, "RETRO RIP", 18, "#f4e8ce", True)
        label(p, 28, 53, "PORTABLE INTERNET RECORDER", 8, "#a6c0c0", mono=True)
        rounded(p, 314, 21, 106, 26, 5, "#142b32", "#628087")
        p.setPen(Qt.NoPen)
        p.setBrush(color("#f68c52" if self.mode in ("recording", "processing", "stopping") else "#698983"))
        p.drawEllipse(QRectF(324, 30, 6, 6))
        label(p, 338, 38, "REC" if self.mode == "recording" else "RR—01", 11, "#e3d5b4", mono=True)
        rounded(p, 22, 68, 404, 218, 15, "#10232a", "#69888c", 1.3)
        rounded(p, 32, 77, 384, 201, 12, "#0a171c", "#091319", 3)
        # Empty transport spindles, visible through an open door.
        for x in (137, 312):
            rounded(p, x-9, 184-9, 18, 18, 4, "#7d8b85", "#293e43", 2)
        label(p, 28, 307, "STEREO  /  AUTO REVERSE", 9, "#b0c4bb", mono=True)
        label(p, 322, 307, "90  MIN", 12, "#e9dec8", True, True)
        # Right side orange volume wheel and ridges.
        rounded(p, 442, 103, 19, 72, 5, "#d27342", "#9f4d2d", 2)
        for y in range(109, 170, 5):
            p.setPen(QPen(color("#663c2f"), 1))
            p.drawLine(QPointF(449,y), QPointF(458,y))
        for x,y in ((12,16),(434,17),(12,318),(434,318)):
            p.setPen(QPen(color("#132f37"),1))
            p.setBrush(color("#7d999a"))
            p.drawEllipse(QRectF(x-3,y-3,6,6))
            p.drawLine(QPointF(x-2,y),QPointF(x+2,y))
        p.restore()

    def draw_door(self, p):
        seated = self.mode in ("recording", "processing", "stopping")
        closure = 1 if seated else 0
        if self.mode == "inserting":
            closure = ease(max(0, (self.transition-.65)/.35))
        elif self.mode == "ejecting":
            closure = 1-ease(min(1, self.transition/.3))
        if closure <= 0:
            return
        p.save()
        self.device_transform(p)
        p.setOpacity(closure)
        rounded(p, 25, 70, 398, 213, 14, color("#72989d", .12), "#6a888f", 2)
        shine = QLinearGradient(30,80,420,270)
        shine.setColorAt(0,color("#ffffff",.12))
        shine.setColorAt(.4,color("#ffffff",.02))
        shine.setColorAt(.41,color("#ffffff",.16))
        shine.setColorAt(.49,color("#ffffff",.02))
        shine.setColorAt(1,color("#ffffff",.03))
        rounded(p, 31,76,386,201,10,shine)
        label(p, 348, 269, "DOLBY NR", 7, "#ced9ce", mono=True)
        p.restore()

    def draw_tape(self, p, x, y, scale, angle):
        p.save()
        p.translate(x,y)
        p.rotate(angle)
        p.scale(scale,scale)
        p.translate(-184,-101)
        for i in range(9, 0, -1):
            rounded(p, -i*.7, 8+i*.5, 368+i*1.4, 202+i*.5, 15, color("#172933", .012))
        rounded(p, 0, 5, 368, 202, 14, "#1b302f", "#10262d", 1.5)
        rounded(p, 0, 0, 368, 202, 13,
                gradient(0,202,[(0,"#465853"),(.1,"#263d3b"),(1,"#213834")]), "#7e9282", 1.3)
        rounded(p, 12, 13, 344, 155, 8, "#eee2bf", "#182c2d", 1.5)
        rounded(p, 17, 17, 334, 14, 2, "#d76e3e")
        label(p, 24, 27, "R E T R O R I P      /      PERSONAL MIXTAPE", 7, "#fff0c8", True, True)
        artwork(p, QRectF(23, 37, 93, 54), self.cover)
        label(p, 127, 52, self.title, 12, "#273834", True, width=211)
        label(p, 127, 70, self.creator, 9, "#666c59", width=211)
        label(p, 127, 84, f"{self.platform.upper()}  /  {self.duration}", 8, "#907756", mono=True, width=211)
        rounded(p, 24, 100, 320, 62, 27, "#12282b", "#7c8067", 1.6)
        p.setPen(QPen(color("#6b4230"), 3))
        p.drawLine(QPointF(102,140), QPointF(267,140))
        self.reel(p, 102, 131, self.angle, 29 - self.visual_progress*.06)
        self.reel(p, 267, 131, self.angle*1.13, 23 + self.visual_progress*.06)
        rounded(p, 153,108,64,42,5,"#39473b", "#657161")
        for i in range(6):
            p.setPen(QPen(color("#9c9b77"), .6))
            p.drawLine(QPointF(159+i*10, 120), QPointF(159+i*10, 139))
        label(p, 24, 188, "A", 15, "#e1d9b9", True)
        label(p, 49, 188, "TYPE I   •   NORMAL POSITION", 7, "#b2c2a8", mono=True)
        label(p, 300, 188, "C—90", 13, "#e5dcb9", True, True)
        for sx,sy in ((7,11),(361,11),(8,192),(360,192)):
            p.setPen(QPen(color("#081d22"),1))
            p.setBrush(color("#87938a"))
            p.drawEllipse(QRectF(sx-2.5,sy-2.5,5,5))
            p.drawLine(QPointF(sx-1.5,sy),QPointF(sx+1.5,sy))
        p.restore()

    def reel(self,p,x,y,angle,radius):
        p.save()
        p.translate(x,y)
        p.setPen(QPen(color("#342c20"), 4))
        p.setBrush(color("#493524"))
        p.drawEllipse(QRectF(-radius,-radius,radius*2,radius*2))
        p.rotate(angle)
        p.setPen(QPen(color("#a4aaa0"), 1))
        p.setBrush(color("#d6d5b6"))
        p.drawEllipse(QRectF(-20,-20,40,40))
        for n in range(6):
            p.save()
            p.rotate(n*60)
            rounded(p,-3,-17,6,9,2,"#243a35")
            p.restore()
        p.setPen(Qt.NoPen)
        p.setBrush(color("#193331"))
        p.drawEllipse(QRectF(-7,-7,14,14))
        p.setBrush(color("#b3bba5"))
        p.drawEllipse(QRectF(-2,-2,4,4))
        p.restore()

    def draw_sleeve(self,p,front=False):
        visible = self.mode in ("ejecting","complete","stopped","archiving","archived") or self.saved_count > 0
        if not visible:
            return
        p.save()
        p.translate(868,339)
        p.rotate(7)
        if not front:
            rounded(p,-127,-70,256,162,6,color("#4c4932", .06))
            rounded(p,-127,-88,254,172,5,"#d9c9a6","#bbaa8b")
            rounded(p,-119,-80,238,146,2,"#685d47")
        else:
            # This front is painted after the moving cassette, creating occlusion.
            path=QPainterPath(QPointF(-128,-60))
            path.lineTo(-40,-60)
            path.cubicTo(-33,-43,33,-43,40,-60)
            path.lineTo(128,-60)
            path.lineTo(128,87)
            path.lineTo(-128,87)
            path.closeSubpath()
            p.setPen(QPen(color("#b5a489"),1))
            p.setBrush(gradient(-60,87,[(0,"#e7d9b9"),(1,"#d1bc92")]))
            p.drawPath(path)
            p.setPen(QPen(color("#c6b596"), .6))
            p.drawLine(QPointF(-118,-43),QPointF(-118,76))
            p.drawLine(QPointF(118,-43),QPointF(118,76))
            if self.mode == "archived" or (self.saved_count and self.mode not in ("complete","ejecting","archiving","stopped")):
                artwork(p,QRectF(-101,-27,55,49),self.saved_cover)
                label(p,-34,-9,self.saved_title,11,"#2f4440",True,width=139)
                label(p,-34,11,f"TAPE {self.saved_count:03d}",9,"#756954",mono=True)
            else:
                label(p,-99,-9,"KEEP SOMETHING GOOD.",12,"#39473e",True)
                label(p,-99,13,"YOUR PERSONAL TAPE ARCHIVE",8,"#8b7c60",mono=True)
            p.fillRect(QRectF(-103,39,206,2),color("#ce6d42"))
            label(p,-103,64,"RETRO RIP   /   VOL. 01",8,"#766e56",True,True)
        p.restore()

    def draw_notes(self,p):
        if self.mode in ("idle","analyzing","loading","ready"):
            label(p, 692, 322, "A NEW HOME FOR YOUR FAVORITES.", 10, "#7b8075", True, True)
            label(p, 735, 343, "Made to keep. Made yours.", 12, "#a39d8e")
        elif self.mode in ("recording","processing","stopping","inserting"):
            title = "ON AIR." if self.mode == "recording" else "MAKING YOUR TAPE."
            label(p, 731, 139, title, 27, "#23404b", True)
            label(p, 733, 165, "GOOD THINGS TAKE A LITTLE SPIN.", 9, "#858879", mono=True)
            for i in range(19):
                height = (8 + 43*(.5+.5*math.sin(self.phase*4+i*.7)))*(.3 if self.mode == "inserting" else 1)
                rounded(p,735+i*8,224-height,4,height,2,"#d67745" if i>13 else "#557b74")
            label(p,733,246,"TRANSFER ACTIVITY",8,"#929385",mono=True)
        elif self.mode == "complete":
            label(p,600,47,"YOUR TAPE IS READY.",10,"#b56540",True,True)
        elif self.mode == "archived":
            label(p,720,136,"A KEEPER.",32,"#2f524e",True)
            label(p,722,163,"Your file is in the output folder.",12,"#939181")
            label(p,722,185,"Ready for another one?",12,"#939181")
