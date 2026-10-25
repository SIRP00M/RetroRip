"""Render actual Qt screens and an offline animation preview. Requires Pillow."""
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from PySide6.QtWidgets import QApplication
from PIL import Image, ImageDraw
from main import AppWindow

out=Path(sys.argv[1]) if len(sys.argv)>1 else Path("preview")
out.mkdir(parents=True,exist_ok=True)
app=QApplication([]); app.setStyle("Fusion")
with patch("studio.QSoundEffect",None): w=AppWindow(demo=True)
w.show(); w.pump.stop(); w.home_scene.timer.stop(); w.studio.scene.timer.stop(); app.processEvents()
s=w.studio; names=["Home","Studio","Collection","Queue","Settings"]
w.store.add_queue(["https://example.invalid/night-drive","https://example.invalid/sunday-mix","https://example.invalid/rainy-afternoon"],"MP3 Best Audio"); w.refresh_queue()
shots=[]
for dark in (False,True):
    w.apply_theme(dark)
    for i,name in enumerate(names):
        w.navigate(i); app.processEvents()
        path=out/f"{'Dark' if dark else 'Light'}-{name}.png"
        w.grab().save(str(path)); shots.append(path)

sheet=Image.new("RGB",(1340,5*474),(17,28,35)); draw=ImageDraw.Draw(sheet)
for theme in range(2):
    for page in range(5):
        pic=Image.open(shots[theme*5+page]).resize((670,450),Image.Resampling.LANCZOS)
        sheet.paste(pic,(theme*670,page*474+24)); draw.text((theme*670+14,page*474+6),f"{names[page]} / {'DARK' if theme else 'LIGHT'}",fill="#dccba6")
sheet.save(out/"RetroRip-All-Pages.png")

frames=[]
def capture():
    app.processEvents()
    im=w.grab().toImage().convertToFormat(__import__('PySide6.QtGui',fromlist=['QImage']).QImage.Format_RGBA8888)
    pic=Image.frombytes("RGBA",(im.width(),im.height()),bytes(im.bits())).convert("RGB")
    frames.append(pic.resize((1005,675),Image.Resampling.LANCZOS))
def hold(count=8):
    for _ in range(count): capture()
def transition(count):
    mode=s.scene.mode
    for i in range(count):
        s.scene.transition=i/(count-1); s.scene.phase+=.1
        capture()
    s.scene.start_time-=5; s.scene.tick(); s.demo_timer.stop()

w.apply_theme(False); w.navigate(0); hold(8)
w.navigate(1); hold(7)
s.update_state("analyzing"); s.load_demo_media(); s.scene.mode="ready"; hold(8)
s.insert_tape(); transition(18)
for i in range(23):
    s.on_progress({"status":"downloading","percent":i*100/22,"filename":"preview.mp4","downloaded_bytes":i*300000,"speed":5500000,"eta":(22-i)//3})
    s.scene.visual_progress=s.scene.progress; s.scene.angle+=19; s.scene.phase+=.1; capture()
s.on_status("Processing media with FFmpeg..."); hold(5)
s.on_success(); transition(15); hold(6)
s.keep_tape(); transition(13)
for _ in range(7):
    # Advance the actual Qt archive-to-sidebar animation without sleeping.
    from main import ArchiveFlight
    for flight in w.findChildren(ArchiveFlight): flight.animation.setCurrentTime(min(1000,flight.animation.currentTime()+160))
    capture()
w.navigate(2); hold(8); w.apply_theme(True); hold(8)
w.navigate(3); hold(8); w.navigate(4); hold(8)
s.new_tape(); w.navigate(1); s.update_state("analyzing"); s.load_demo_media(); s.scene.mode="ready"; s.insert_tape(); s.scene.start_time-=5; s.scene.tick(); s.demo_timer.stop()
s.on_progress({"status":"downloading","percent":68,"filename":"preview.mp4","downloaded_bytes":45000000,"speed":5500000,"eta":8})
s.scene.visual_progress=68; s.scene.angle=25; s.scene.phase=1; app.processEvents()
w.grab().save(str(out/"RetroRip-Dark-Studio.png")); hold(8)
frames[0].save(out/"RetroRip-Pocket-Studio.gif",save_all=True,append_images=frames[1:],duration=95,loop=0,optimize=True)
w.close(); print(f"Saved {len(shots)} screens and {len(frames)} animation frames to {out}")
