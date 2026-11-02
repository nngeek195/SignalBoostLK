from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QColor, QDesktopServices, QFont, QIcon, QPainter, QPainterPath, QPalette, QPen,
)
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QComboBox, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QMainWindow, QMessageBox,
    QProgressBar, QPushButton, QSizePolicy, QSpinBox, QStackedWidget, QStyleFactory,
    QTableWidget, QTableWidgetItem, QToolTip, QVBoxLayout, QWidget,
)

from app.core.download_engine import SUPPORTED_ISPS
from app.core.isp_detector import detect_current_isp
from app.core.monitor_worker import AUTO, MonitorWorker
from app.database.db import clear_history, recent_tests

ASSETS = (Path(__file__).resolve().parent / "assets").as_posix()

# ── Developer links ──────────────────────────────────────────────────────────
SOCIAL_LINKS = (
    ("GitHub", "github.svg", "https://github.com/nngeek195"),
    ("LinkedIn", "linkedin.svg", "https://www.linkedin.com/in/niranga-nayanajith/"),
)

# ── Palette ──────────────────────────────────────────────────────────────────
BG = "#0B1020"
SURFACE = "#121A2E"
SURFACE_2 = "#18223A"
BORDER = "#222D4A"
TEXT = "#E8ECF8"
TEXT_2 = "#AEB8D3"
MUTED = "#7C88A8"
ACCENT = "#6366F1"
ACCENT_HOVER = "#7C7FF5"
CHART = "#38BDF8"
GOOD = "#10B981"
WARN = "#F59E0B"
BAD = "#F87171"

QSS = f"""
* {{ font-family: 'Inter', 'Ubuntu Sans', 'Ubuntu', 'Noto Sans', sans-serif; font-size: 13px; color: {TEXT}; }}
QMainWindow, QWidget#root, QStackedWidget, QWidget#page {{ background: {BG}; }}
QToolTip {{ background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px 8px; border-radius: 6px; }}

QFrame#sidebar {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
QLabel#brand {{ font-size: 19px; font-weight: 800; }}
QLabel#tagline {{ color: {MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; }}
QPushButton#nav {{ background: transparent; border: 0; border-radius: 8px; text-align: left;
    padding: 10px 14px; color: {TEXT_2}; font-weight: 600; }}
QPushButton#nav:hover {{ background: {SURFACE_2}; color: {TEXT}; }}
QPushButton#nav:checked {{ background: rgba(99, 102, 241, 0.18); color: #C7C9FF; }}
QLabel#footerTitle {{ color: {MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; }}
QPushButton#social {{ background: transparent; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 8px 12px; text-align: left; color: {TEXT_2}; font-weight: 600; }}
QPushButton#social:hover {{ background: {SURFACE_2}; color: {TEXT}; border-color: #33426A; }}

QFrame#card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; }}
QLabel#h1 {{ font-size: 22px; font-weight: 700; }}
QLabel#h2 {{ font-size: 15px; font-weight: 700; }}
QLabel#sub, QLabel#muted {{ color: {MUTED}; }}
QLabel#eyebrow {{ color: {MUTED}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
QLabel#metric {{ font-size: 20px; font-weight: 700; }}
QLabel#hero {{ font-size: 54px; font-weight: 800; }}
QLabel#heroUnit {{ color: {TEXT_2}; font-size: 18px; font-weight: 600; }}
QLabel#pill {{ border-radius: 11px; padding: 3px 10px; font-size: 11px; font-weight: 700; }}

QPushButton {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 8px 16px; font-weight: 600; }}
QPushButton:hover {{ background: #22304F; border-color: #33426A; }}
QPushButton:disabled {{ color: #4F5A78; background: {SURFACE}; border-color: {BORDER}; }}
QPushButton#primary {{ background: {ACCENT}; border: 0; color: white; padding: 10px 20px; }}
QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#primary:disabled {{ background: #2C2F66; color: #8E91C9; }}
QPushButton#danger {{ background: transparent; border: 1px solid #7F3445; color: {BAD}; padding: 10px 20px; }}
QPushButton#danger:hover {{ background: rgba(248, 113, 113, 0.10); }}
QPushButton#danger:disabled {{ color: #4F5A78; border-color: {BORDER}; }}

QComboBox, QSpinBox {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 7px 10px; min-height: 20px; min-width: 140px; }}
QComboBox:hover, QSpinBox:hover {{ border-color: #3A4A75; }}
QComboBox:focus, QSpinBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: 0; width: 28px; }}
QComboBox::down-arrow {{ image: url({ASSETS}/chevron-down.svg); width: 10px; height: 6px; }}
QSpinBox::up-arrow {{ image: url({ASSETS}/chevron-up.svg); width: 9px; height: 5px; }}
QSpinBox::down-arrow {{ image: url({ASSETS}/chevron-down.svg); width: 9px; height: 5px; }}
QSpinBox {{ padding-right: 28px; }}
QSpinBox::up-button, QSpinBox::down-button {{ subcontrol-origin: border; width: 24px;
    background: {SURFACE_2}; border-left: 1px solid {BORDER}; }}
QSpinBox::up-button {{ subcontrol-position: top right; border-top-right-radius: 8px; }}
QSpinBox::down-button {{ subcontrol-position: bottom right; border-bottom-right-radius: 8px; }}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {{ background: #22304F; }}
QComboBox QAbstractItemView {{ background: {SURFACE_2}; border: 1px solid {BORDER};
    selection-background-color: {ACCENT}; outline: 0; padding: 4px; }}

QProgressBar {{ background: {SURFACE_2}; border: 0; border-radius: 4px; max-height: 8px; min-height: 8px; }}
QProgressBar::chunk {{ background: {CHART}; border-radius: 4px; }}

QTableWidget {{ background: {SURFACE}; border: 0; gridline-color: transparent;
    selection-background-color: rgba(99, 102, 241, 0.25); selection-color: {TEXT}; }}
QTableWidget::item {{ padding: 8px 12px; border-bottom: 1px solid {BORDER}; }}
QHeaderView::section {{ background: {SURFACE}; color: {MUTED}; padding: 10px 12px; border: 0;
    border-bottom: 1px solid {BORDER}; font-size: 11px; font-weight: 700; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2A3658; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""


def apply_theme(app: QApplication):
    """Use Fusion so the stylesheet renders identically on every desktop theme."""
    app.setStyle(QStyleFactory.create("Fusion"))
    pal = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, BG), (QPalette.ColorRole.Base, SURFACE),
        (QPalette.ColorRole.AlternateBase, SURFACE_2), (QPalette.ColorRole.Text, TEXT),
        (QPalette.ColorRole.WindowText, TEXT), (QPalette.ColorRole.Button, SURFACE_2),
        (QPalette.ColorRole.ButtonText, TEXT), (QPalette.ColorRole.Highlight, ACCENT),
        (QPalette.ColorRole.HighlightedText, "#FFFFFF"),
        (QPalette.ColorRole.ToolTipBase, SURFACE_2), (QPalette.ColorRole.ToolTipText, TEXT),
    ):
        pal.setColor(role, QColor(color))
    app.setPalette(pal)
    app.setStyleSheet(QSS)


# ── Small building blocks ────────────────────────────────────────────────────
def label(text="", name=None, wrap=False):
    w = QLabel(text)
    if name:
        w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


def card():
    frame = QFrame()
    frame.setObjectName("card")
    return frame


def page_header(title, subtitle, right=None):
    row = QHBoxLayout()
    col = QVBoxLayout()
    col.setSpacing(2)
    col.addWidget(label(title, "h1"))
    col.addWidget(label(subtitle, "sub"))
    row.addLayout(col)
    row.addStretch()
    if right is not None:
        row.addWidget(right, alignment=Qt.AlignmentFlag.AlignVCenter)
    return row


class Pill(QLabel):
    """Status badge: coloured dot + text, never colour alone."""

    def __init__(self):
        super().__init__()
        self.setObjectName("pill")

    def set_state(self, text, color):
        c = QColor(color)
        self.setText(f"●  {text}")
        self.setStyleSheet(
            f"color:{color}; background: rgba({c.red()},{c.green()},{c.blue()},0.14);"
        )


class InfoTile(QFrame):
    def __init__(self, title, value, detail):
        super().__init__()
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(4)
        lay.addWidget(label(title.upper(), "eyebrow"))
        self.value = label(value, "metric")
        self.value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail = label(detail, "muted")
        self.detail.setWordWrap(True)
        lay.addWidget(self.value)
        lay.addWidget(self.detail)
        lay.addStretch()


class SpeedChart(QWidget):
    """Single-series line chart of recent download speeds (oldest → newest)."""

    def __init__(self):
        super().__init__()
        self.points = []  # list of (label, mbps, isp)
        self.setMinimumHeight(150)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._hover = None

    def set_points(self, points):
        self.points = points
        self._hover = None
        self.update()

    def _geometry(self):
        r = QRectF(self.rect()).adjusted(44, 10, -12, -24)
        top = max((p[1] for p in self.points), default=0)
        top = self._nice_ceiling(top)
        return r, top

    @staticmethod
    def _nice_ceiling(v):
        if v <= 0:
            return 10.0
        for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000):
            if v <= step * 4:
                return float(step * 4) if v > step * 3 else float(step * (int(v // step) + 1))
        return float(int(v) + 1)

    def _xy(self, i, v, r, top):
        n = len(self.points)
        x = r.left() + (r.width() * (i / (n - 1)) if n > 1 else r.width() / 2)
        y = r.bottom() - r.height() * (v / top)
        return QPointF(x, y)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r, top = self._geometry()
        small = QFont(self.font())
        small.setPointSizeF(max(7.5, small.pointSizeF() - 2))
        p.setFont(small)

        # Recessive grid + y labels.
        for k in range(5):
            v = top * k / 4
            y = r.bottom() - r.height() * k / 4
            p.setPen(QPen(QColor(BORDER), 1))
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))
            p.setPen(QColor(MUTED))
            p.drawText(QRectF(0, y - 8, r.left() - 8, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{v:g}")

        if not self.points:
            p.setPen(QColor(MUTED))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "No tests yet — results will appear here")
            return

        pts = [self._xy(i, v, r, top) for i, (_, v, _) in enumerate(self.points)]

        # Soft area fill under the line.
        if len(pts) > 1:
            area = QPainterPath(QPointF(pts[0].x(), r.bottom()))
            for pt in pts:
                area.lineTo(pt)
            area.lineTo(QPointF(pts[-1].x(), r.bottom()))
            fill = QColor(CHART)
            fill.setAlpha(28)
            p.fillPath(area, fill)
            line = QPainterPath(pts[0])
            for pt in pts[1:]:
                line.lineTo(pt)
            p.setPen(QPen(QColor(CHART), 2, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPath(line)

        # Markers: the latest point always, plus the hovered one.
        for i in {len(pts) - 1, self._hover} - {None}:
            p.setPen(QPen(QColor(SURFACE), 2))
            p.setBrush(QColor(CHART))
            p.drawEllipse(pts[i], 4.5, 4.5)

        # X labels: first and last only, to avoid collisions.
        p.setPen(QColor(MUTED))
        p.drawText(QRectF(r.left(), r.bottom() + 6, 120, 16), Qt.AlignmentFlag.AlignLeft,
                   self.points[0][0])
        if len(pts) > 1:
            p.drawText(QRectF(r.right() - 120, r.bottom() + 6, 120, 16),
                       Qt.AlignmentFlag.AlignRight, self.points[-1][0])

        if self._hover is not None:
            p.setPen(QPen(QColor(MUTED), 1, Qt.PenStyle.DashLine))
            x = pts[self._hover].x()
            p.drawLine(QPointF(x, r.top()), QPointF(x, r.bottom()))

    def mouseMoveEvent(self, e):
        if not self.points:
            return
        r, top = self._geometry()
        xs = [self._xy(i, v, r, top).x() for i, (_, v, _) in enumerate(self.points)]
        i = min(range(len(xs)), key=lambda k: abs(xs[k] - e.position().x()))
        if i != self._hover:
            self._hover = i
            when, mbps, isp = self.points[i]
            QToolTip.showText(e.globalPosition().toPoint(),
                              f"<b>{mbps:.2f} Mbps</b><br>{isp} · {when}", self)
            self.update()

    def leaveEvent(self, _):
        self._hover = None
        QToolTip.hideText()
        self.update()


class DetectWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            self.done.emit(detect_current_isp())
        except Exception as exc:
            self.failed.emit(f"ISP detection failed: {exc}")


def fmt_time(iso, short=False):
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    return dt.strftime("%H:%M" if short else "%Y-%m-%d  %H:%M:%S")


# ── Main window ──────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SignalBoostLK")
        self.resize(1200, 780)
        self.setMinimumSize(980, 680)
        self.worker = None
        self.detect_worker = None
        self._closing = False
        self._countdown = 0
        self._last_failed = False
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._on_tick)
        self._build_ui()
        self.refresh_history()

    # ── Layout ───────────────────────────────────────────────────────────────
    def _build_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._sidebar())

        self.pages = QStackedWidget()
        for build in (self._overview_page, self._history_page, self._settings_page):
            self.pages.addWidget(build())
        outer.addWidget(self.pages, 1)

    def _sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 24, 16, 18)
        side.setSpacing(4)

        brand = label(f"SignalBoost<span style='color:{ACCENT_HOVER}'>LK</span>", "brand")
        brand.setTextFormat(Qt.TextFormat.RichText)
        side.addWidget(brand)
        side.addWidget(label("ISP MONITOR · SPEED TEST", "tagline"))
        side.addSpacing(28)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for idx, text in enumerate(("Overview", "Test history", "Settings")):
            btn = QPushButton(text)
            btn.setObjectName("nav")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.nav_group.addButton(btn, idx)
            side.addWidget(btn)
        self.nav_group.button(0).setChecked(True)
        self.nav_group.idClicked.connect(self._go_to)

        side.addStretch()
        side.addWidget(label("DEVELOPER", "footerTitle"))
        side.addSpacing(4)
        for name, icon, url in SOCIAL_LINKS:
            btn = QPushButton(f"  {name}")
            btn.setObjectName("social")
            btn.setIcon(QIcon(f"{ASSETS}/{icon}"))
            btn.setIconSize(QSize(18, 18))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(url)
            btn.clicked.connect(lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            side.addWidget(btn)
        side.addSpacing(14)
        side.addWidget(label("Linux edition · v0.1.0", "muted"))
        return sidebar

    def _page(self):
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(18)
        return page, lay

    def _overview_page(self):
        page, layout = self._page()
        self.badge = Pill()
        self.badge.set_state("IDLE", WARN)
        layout.addLayout(page_header(
            "Network overview",
            "Monitor your ISP connection and measure download performance.",
            self.badge,
        ))

        # Hero: latest speed + trend chart.
        hero = card()
        h = QHBoxLayout(hero)
        h.setContentsMargins(24, 20, 24, 20)
        h.setSpacing(28)
        left = QVBoxLayout()
        left.setSpacing(2)
        left.addWidget(label("LAST DOWNLOAD", "eyebrow"))
        num_row = QHBoxLayout()
        num_row.setSpacing(8)
        self.speed_value = label("—", "hero")
        num_row.addWidget(self.speed_value, alignment=Qt.AlignmentFlag.AlignBottom)
        num_row.addWidget(label("Mbps", "heroUnit"), alignment=Qt.AlignmentFlag.AlignBottom)
        num_row.addStretch()
        left.addLayout(num_row)
        self.speed_detail = label("No completed test yet", "muted")
        left.addWidget(self.speed_detail)
        left.addSpacing(10)
        self.stats_label = label("", "muted")
        left.addWidget(self.stats_label)
        left.addStretch()
        lw = QWidget()
        lw.setLayout(left)
        lw.setFixedWidth(250)
        h.addWidget(lw)

        right = QVBoxLayout()
        right.setSpacing(6)
        right.addWidget(label("RECENT SPEED (Mbps)", "eyebrow"))
        self.chart = SpeedChart()
        right.addWidget(self.chart, 1)
        h.addLayout(right, 1)
        layout.addWidget(hero, 3)

        # Info tiles.
        tiles = QGridLayout()
        tiles.setSpacing(14)
        self.isp_tile = InfoTile("Current ISP", "Unknown", "Detect or select an ISP")
        self.ip_tile = InfoTile("Public IP", "—", "Not detected yet")
        self.org_tile = InfoTile("Organization", "—", "From ipinfo.io")
        self.org_tile.value.setStyleSheet("font-size:15px;")
        self.org_tile.value.setWordWrap(True)
        for i, tile in enumerate((self.isp_tile, self.ip_tile, self.org_tile)):
            tiles.addWidget(tile, 0, i)
            tiles.setColumnStretch(i, 1)
        layout.addLayout(tiles)

        # Controls + progress.
        ctl = card()
        c = QVBoxLayout(ctl)
        c.setContentsMargins(24, 20, 24, 20)
        c.setSpacing(14)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(label("ISP", "muted"))
        self.isp_combo = QComboBox()
        self.isp_combo.addItems([AUTO, *SUPPORTED_ISPS])
        row.addWidget(self.isp_combo)
        self.detect_button = QPushButton("Detect ISP")
        self.detect_button.clicked.connect(self.detect_isp)
        row.addWidget(self.detect_button)
        row.addStretch()
        self.start_button = QPushButton("Start monitoring")
        self.start_button.setObjectName("primary")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("danger")
        self.stop_button.setEnabled(False)
        for b in (self.start_button, self.stop_button, self.detect_button):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_button.clicked.connect(self.start_monitoring)
        self.stop_button.clicked.connect(self.stop_monitoring)
        row.addWidget(self.start_button)
        row.addWidget(self.stop_button)
        c.addLayout(row)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background:{BORDER};")
        c.addWidget(line)

        prog_head = QHBoxLayout()
        prog_head.addWidget(label("Download test", "h2"))
        prog_head.addStretch()
        self.test_state = label("Ready", "muted")
        prog_head.addWidget(self.test_state)
        c.addLayout(prog_head)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        c.addWidget(self.progress)
        self.status_label = label("Ready. Press Start monitoring to run the first test.", "muted", wrap=True)
        c.addWidget(self.status_label)
        layout.addWidget(ctl)
        return page

    def _history_page(self):
        page, layout = self._page()
        clear_btn = QPushButton("Clear history")
        clear_btn.clicked.connect(self._clear_history)
        layout.addLayout(page_header(
            "Test history", "Your latest completed download tests, stored locally.", clear_btn))

        panel = card()
        p = QVBoxLayout(panel)
        p.setContentsMargins(6, 6, 6, 6)
        self.history_table = QTableWidget(0, 5)
        self.history_table.setHorizontalHeaderLabels(
            ["DATE / TIME", "ISP", "DOWNLOAD", "SIZE", "DURATION"])
        hh = self.history_table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        hh.setHighlightSections(False)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.verticalHeader().setDefaultSectionSize(42)
        self.history_table.setShowGrid(False)
        self.history_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        p.addWidget(self.history_table)
        self.history_empty = label("No tests recorded yet.", "muted")
        self.history_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p.addWidget(self.history_empty)
        layout.addWidget(panel, 1)
        return page

    def _settings_page(self):
        page, layout = self._page()
        layout.addLayout(page_header("Settings", "Configure monitoring and data usage."))
        panel = card()
        p = QVBoxLayout(panel)
        p.setContentsMargins(24, 22, 24, 22)
        p.setSpacing(14)
        p.addWidget(label("Monitoring", "h2"))
        form = QFormLayout()
        form.setHorizontalSpacing(24)
        form.setVerticalSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(1, 500)
        self.size_spin.setValue(25)
        self.size_spin.setSuffix(" MB")
        self.size_spin.setFixedWidth(180)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 3600)
        self.interval_spin.setValue(5)
        self.interval_spin.setSuffix(" s")
        self.interval_spin.setFixedWidth(180)
        form.addRow(label("Download test size", "muted"), self.size_spin)
        form.addRow(label("Interval between tests", "muted"), self.interval_spin)
        p.addLayout(form)
        self.usage_label = label("", "muted", wrap=True)
        p.addWidget(self.usage_label)
        self.size_spin.valueChanged.connect(self._update_usage)
        self.interval_spin.valueChanged.connect(self._update_usage)
        self._update_usage()
        p.addWidget(label("Changes apply the next time you start monitoring.", "muted"))
        layout.addWidget(panel)
        layout.addStretch()
        return page

    # ── Navigation ───────────────────────────────────────────────────────────
    def _go_to(self, idx):
        if idx == 1:
            self.refresh_history()
        self.pages.setCurrentIndex(idx)

    def _update_usage(self):
        size = self.size_spin.value()
        per_hour = size * 3600 / self.interval_spin.value()  # upper bound, ignores test time
        self.usage_label.setText(
            f"Worst case data use: up to ~{per_hour / 1000:.1f} GB per hour "
            f"({size} MB every {self.interval_spin.value()} s).")

    # ── ISP detection ────────────────────────────────────────────────────────
    def detect_isp(self):
        if self.detect_worker and self.detect_worker.isRunning():
            return
        self.detect_button.setEnabled(False)
        self.status_label.setText("Detecting public IP and ISP…")
        self.detect_worker = DetectWorker(self)
        self.detect_worker.done.connect(self._apply_isp_info)
        self.detect_worker.failed.connect(self._show_error)
        self.detect_worker.finished.connect(self._detect_finished)
        self.detect_worker.start()

    def _detect_finished(self):
        self.detect_button.setEnabled(not (self.worker and self.worker.isRunning()))

    def _apply_isp_info(self, info):
        ip = info.get("ip", "—")
        org = info.get("organization", "Not available")
        loc = ", ".join(x for x in (info.get("city"), info.get("country")) if x)
        self.ip_tile.value.setText(ip)
        self.ip_tile.detail.setText(loc or "Location unavailable")
        self.org_tile.value.setText(org)
        detected = info.get("isp", "Unknown")
        if detected != "Unknown":
            self.isp_tile.value.setText(detected)
            self.isp_tile.detail.setText("Automatically detected")
            if not (self.worker and self.worker.isRunning()):
                self.status_label.setText(f"Detected {detected}. You can start monitoring.")
        else:
            self.isp_tile.value.setText("Unknown")
            self.isp_tile.detail.setText("Not recognised — choose manually")
            if not (self.worker and self.worker.isRunning()):
                self.status_label.setText("Could not recognise your ISP. Select it manually.")

    def _show_error(self, message):
        self.status_label.setText(message)
        QMessageBox.warning(self, "Network error", message)

    # ── Monitoring ───────────────────────────────────────────────────────────
    def start_monitoring(self):
        if self.worker and self.worker.isRunning():
            return
        self.worker = MonitorWorker(
            self.isp_combo.currentText(), self.size_spin.value(), self.interval_spin.value())
        self.worker.status.connect(self.status_label.setText)
        self.worker.isp_info.connect(self._apply_isp_info)
        self.worker.test_started.connect(self._test_started)
        self.worker.progress.connect(self._update_progress)
        self.worker.test_result.connect(self._test_completed)
        self.worker.error.connect(self._worker_error)
        self.worker.waiting.connect(self._start_countdown)
        self.worker.finished.connect(self._monitor_finished)
        for w in (self.start_button, self.isp_combo, self.detect_button):
            w.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.badge.set_state("MONITORING", GOOD)
        self.worker.start()

    def stop_monitoring(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self._tick.stop()
            self.stop_button.setEnabled(False)
            self.badge.set_state("STOPPING", WARN)
            self.status_label.setText("Stopping monitoring…")

    def _monitor_finished(self):
        self._tick.stop()
        for w in (self.start_button, self.isp_combo, self.detect_button):
            w.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.badge.set_state("IDLE", WARN)
        if self.test_state.text().endswith("%") or "next test" in self.test_state.text() \
                or "retrying" in self.test_state.text():
            self.test_state.setText("Stopped")
        if self._closing:
            QTimer.singleShot(0, self.close)

    def _test_started(self, isp):
        self._tick.stop()
        self._last_failed = False
        self.badge.set_state("MONITORING", GOOD)
        self.progress.setValue(0)
        self.test_state.setText(f"Testing {isp}…")

    def _update_progress(self, received, total):
        percent = min(100, int(received * 100 / max(total, 1)))
        self.progress.setValue(percent)
        self.test_state.setText(
            f"{received / 1_000_000:.1f} / {total / 1_000_000:.0f} MB  ·  {percent}%")

    def _test_completed(self, result):
        self.speed_value.setText(f"{result['mbps']:.2f}")
        self.speed_detail.setText(
            f"{result['isp']} · {result['bytes'] / 1_000_000:.1f} MB in {result['seconds']:.1f} s")
        self.isp_tile.value.setText(result["isp"])
        self.progress.setValue(100)
        self.test_state.setText("Completed")
        self.refresh_history()

    def _worker_error(self, message):
        self.status_label.setText(message)
        self._last_failed = True
        self.test_state.setText("Failed")
        self.badge.set_state("ERROR — RETRYING", BAD)

    def _start_countdown(self, seconds):
        self._countdown = seconds
        self._tick.start()
        self._on_tick(initial=True)

    def _on_tick(self, initial=False):
        if not initial:
            self._countdown -= 1
        if self._countdown <= 0:
            self._tick.stop()
            return
        if self._last_failed:
            self.test_state.setText(f"Failed · retrying in {self._countdown}s")
        else:
            self.test_state.setText(f"Completed · next test in {self._countdown}s")

    # ── History ──────────────────────────────────────────────────────────────
    def refresh_history(self):
        try:
            rows = recent_tests(100)
        except Exception as exc:
            self.status_label.setText(f"Could not read history: {exc}")
            return

        self.history_table.setRowCount(len(rows))
        self.history_table.setVisible(bool(rows))
        self.history_empty.setVisible(not rows)
        for r, (tested_at, isp, speed, nbytes, secs, *_) in enumerate(rows):
            values = [fmt_time(tested_at), isp, f"{speed:.2f} Mbps",
                      f"{nbytes / 1_000_000:.1f} MB", f"{secs:.1f} s"]
            for c, value in enumerate(values):
                item = QTableWidgetItem(value)
                if c == 2:
                    f = item.font()
                    f.setBold(True)
                    item.setFont(f)
                self.history_table.setItem(r, c, item)

        recent = list(reversed(rows[:30]))
        self.chart.set_points([(fmt_time(t, short=True), s, i) for t, i, s, *_ in recent])
        if rows:
            speeds = [row[2] for row in rows[:30]]
            self.stats_label.setText(
                f"Last {len(speeds)} tests\n"
                f"Avg {sum(speeds) / len(speeds):.1f}  ·  "
                f"Min {min(speeds):.1f}  ·  Max {max(speeds):.1f} Mbps")
            if self.speed_value.text() == "—":
                t, isp, speed, nbytes, secs, _ = rows[0]
                self.speed_value.setText(f"{speed:.2f}")
                self.speed_detail.setText(f"{isp} · {fmt_time(t)}")
        else:
            self.stats_label.setText("")

    def _clear_history(self):
        if QMessageBox.question(self, "Clear history",
                                "Delete all recorded tests? This cannot be undone.") \
                != QMessageBox.StandardButton.Yes:
            return
        clear_history()
        self.speed_value.setText("—")
        self.speed_detail.setText("No completed test yet")
        self.refresh_history()

    # ── Shutdown ─────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            # The worker aborts its download promptly; close once it finishes.
            self._closing = True
            self.stop_monitoring()
            event.ignore()
            return
        if self.detect_worker and self.detect_worker.isRunning():
            self.detect_worker.wait(11000)  # detection has a 10 s timeout
        event.accept()
