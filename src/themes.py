from studio import STYLE


def stylesheet(dark):
    base = STYLE
    swaps = {
        "#f3f0e7":"#131c24", "#fffcf5":"#1c2933", "#f4f2e9":"#15212a",
        "#fffdf7":"#1e303c", "#273f48":"#d9e4e3", "#263f49":"#ebeee5",
        "#1a3742":"#eef1e8", "#2b4349":"#dbe6df", "#314a50":"#d5e4df",
        "#29444b":"#e6eee3", "#46605f":"#b5cfc5", "#eaece2":"#2a3c45",
        "#dce3d5":"#36505a", "#d4d9cc":"#40535b", "#dfdfd3":"#34464e",
        "#d8dbce":"#34464e", "#dadbd0":"#34464e", "#e6e7da":"#33474f",
        "#e9e8dc":"#263c48", "#888d81":"#a7b5b5", "#899083":"#a4b5b2",
        "#8e9185":"#a1b1b0", "#8c9186":"#a5b2b0", "#7b8679":"#b4c2ba",
        "#a96646":"#d7946b", "#ac6441":"#e1a273", "#8e9285":"#a7b6b3",
    }
    if dark:
        for a,b in swaps.items():
            base = base.replace(a,b)
    bg,panel,ink,muted,line = ("#131c24","#1c2933","#e0e7df","#a3b4b1","#34464e") if dark else ("#f3f0e7","#fffcf5","#263f49","#828f85","#dfdfd3")
    return base + f"""
    QDialog, QWidget#page, QWidget#shell {{ background: {bg}; }}
    QFrame#sidebar {{ background: {'#0d161f' if dark else '#e6e8dc'}; border-right: 1px solid {line}; }}
    QPushButton#nav {{ text-align:left; border:none; border-radius:8px; padding:15px 18px; color:{muted}; background:transparent; }}
    QPushButton#nav:checked {{ background:{'#2c4049' if dark else '#d2dbcc'}; color:{ink}; }}
    QPushButton#nav:hover {{ color:#d78658; }}
    QFrame#card, QFrame#statusbar {{ background:{panel}; border:1px solid {line}; border-radius:12px; }}
    QLabel#pageTitle {{ font-size:32px; font-weight:800; color:{ink}; }}
    QLabel#stat {{ font-size:22px; font-weight:bold; color:#c9764e; }}
    QScrollArea {{ border:none; background:transparent; }}
    QScrollArea > QWidget > QWidget {{ background:transparent; }}
    QTextEdit, QTableWidget {{ background:{panel}; color:{ink}; border:1px solid {line}; border-radius:8px; padding:8px; }}
    QTableWidget {{ selection-background-color:{'#36505a' if dark else '#dfdfc8'}; gridline-color:{line}; }}
    QHeaderView::section {{ background:{bg}; color:{muted}; border:none; padding:9px; }}
    QCheckBox {{ color:{ink}; spacing:9px; }}
    QSlider::groove:horizontal {{ height:5px; background:{line}; border-radius:2px; }}
    QSlider::handle:horizontal {{ width:13px; margin:-5px 0; background:#d28252; border-radius:6px; }}
    QLabel {{ background:transparent; }}
    """
