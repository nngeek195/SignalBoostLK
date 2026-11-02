"""SignalBoostLK 2.0 desktop UI — connection keeper dashboard.

No speed values are shown: the keeper only sends lightweight heartbeats.
"""
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QComboBox, QFormLayout, QFrame,
    QGridLayout, QHBoxLayout, QHeaderView, QLabel, QMainWindow, QMessageBox,
    QPushButton, QSpinBox, QStackedWidget, QStyleFactory,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.core.config import load_isps
from app.core.isp_detector import UNKNOWN, detect_current_isp
from app.core.keeper import (HANDSHAKE_BYTES, SERVER_IDLE_TIMEOUT_S,
                             SERVER_MAX_CONNECTION_AGE_S, State)
from app.core.monitor_worker import AUTO, KeeperController
from app.database import db

APP_VERSION = "2.0.0"
SERVERS = load_isps()
SUPPORTED_ISPS = tuple(SERVERS)
DEFAULT_INTERVAL_S = 10
# Measured per-heartbeat cost (docs/reports/stage2_endpoint_compatibility.md)
COST_REUSED_B = 800
COST_RECONNECT_B = 6100
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
    app.setStyleSheet(QSS + EXTRA_QSS)


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



EXTRA_QSS = """
QLabel#stateBig { font-size: 34px; font-weight: 800; }
"""


def fmt_bytes(n):
    if n is None:
        return "—"
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def fmt_duration(seconds):
    if seconds is None:
        return "—"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m {s:02d}s" if h else (f"{m}m {s:02d}s" if m else f"{s}s")


def fmt_ts(ts, short=False):
    if not ts:
        return "—"
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S" if short else "%Y-%m-%d  %H:%M:%S")


def estimate_per_hour(interval_s):
    """Measured model: below the idle timeout one connection lasts ~60 s, so
    a handshake is paid once per minute; above it, on every heartbeat."""
    beats = 3600 / interval_s
    if interval_s < SERVER_IDLE_TIMEOUT_S:
        return beats * COST_REUSED_B + (3600 / SERVER_MAX_CONNECTION_AGE_S) * sum(HANDSHAKE_BYTES)
    return beats * COST_RECONNECT_B


class DetectWorker(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, parent=None, force=False):
        super().__init__(parent)
        self.force = force

    def run(self):
        try:
            self.done.emit(detect_current_isp(force=self.force))
        except Exception as exc:
            self.failed.emit(f"ISP detection failed: {exc}")


def make_table(headers):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    hh = t.horizontalHeader()
    hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    hh.setStretchLastSection(True)
    hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    hh.setHighlightSections(False)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(36)
    t.setShowGrid(False)
    t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    return t


def fill_table(table, rows):
    table.setRowCount(len(rows))
    for r, values in enumerate(rows):
        for c, v in enumerate(values):
            table.setItem(r, c, QTableWidgetItem(str(v)))


# ── Main window ──────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SignalBoostLK")
        self.resize(1200, 800)
        self.setMinimumSize(1000, 700)
        self.controller = None
        self.detect_worker = None
        self._closing = False
        self._pending_start = False
        self._detected_isp = None
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._refresh_live)
        self._build_ui()
        self._load_prefs()
        self._refresh_live()
        try:
            db.prune()
        except Exception:
            pass

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
        for build in (self._dashboard_page, self._history_page, self._events_page,
                      self._settings_page):
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
        side.addWidget(label("ISP CONNECTION KEEPER", "tagline"))
        side.addSpacing(28)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for idx, text in enumerate(("Dashboard", "Session history", "Connection events",
                                    "Settings")):
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
        side.addWidget(label(f"v{APP_VERSION}", "muted"))
        return sidebar

    def _page(self):
        page = QWidget()
        page.setObjectName("page")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(16)
        return page, lay

    def _dashboard_page(self):
        page, layout = self._page()
        self.badge = Pill()
        self.badge.set_state("STOPPED", MUTED)
        layout.addLayout(page_header(
            "Connection keeper",
            "Keeps one lightweight HTTPS connection to your ISP's speed-test server. "
            "No speed tests, no large downloads.",
            self.badge))

        # Status card
        status = card()
        s = QHBoxLayout(status)
        s.setContentsMargins(24, 20, 24, 20)
        left = QVBoxLayout()
        left.setSpacing(4)
        left.addWidget(label("CONNECTION STATUS", "eyebrow"))
        self.state_label = label("Stopped", "stateBig")
        left.addWidget(self.state_label)
        self.server_label = label("Server: —", "muted")
        self.server_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        left.addWidget(self.server_label)
        s.addLayout(left, 1)
        right = QVBoxLayout()
        right.setSpacing(4)
        right.addWidget(label("CURRENT CONNECTION OPEN FOR", "eyebrow"))
        self.conn_age_label = label("—", "metric")
        right.addWidget(self.conn_age_label)
        self.session_label = label("Monitoring time: —", "muted")
        right.addWidget(self.session_label)
        s.addLayout(right)
        layout.addWidget(status)

        # Metric tiles
        grid = QGridLayout()
        grid.setSpacing(12)
        self.t_isp = InfoTile("Selected ISP", "—", "Auto-detect or choose below")
        self.t_last = InfoTile("Last heartbeat", "—", "No heartbeat yet")
        self.t_rtt = InfoTile("Avg response time", "—", "—")
        self.t_beats = InfoTile("Heartbeats", "0", "0 failed")
        self.t_reconn = InfoTile("Reconnections", "0", "0 reused requests")
        self.t_data = InfoTile("Data used (est.)", "0 B", "This session")
        self.t_rate = InfoTile("Data per hour (est.)", "—", "Measured after 1 minute")
        self.t_today = InfoTile("Data last 24 h (est.)", "—", "All sessions")
        for i, tile in enumerate((self.t_isp, self.t_last, self.t_rtt, self.t_beats,
                                  self.t_reconn, self.t_data, self.t_rate, self.t_today)):
            grid.addWidget(tile, i // 4, i % 4)
        for c in range(4):
            grid.setColumnStretch(c, 1)
        layout.addLayout(grid)

        # Controls
        ctl = card()
        c = QVBoxLayout(ctl)
        c.setContentsMargins(24, 18, 24, 18)
        c.setSpacing(12)
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(label("ISP", "muted"))
        self.isp_combo = QComboBox()
        self.isp_combo.addItems([AUTO, *SUPPORTED_ISPS])
        row.addWidget(self.isp_combo)
        self.detect_button = QPushButton("Detect ISP")
        self.detect_button.clicked.connect(lambda: self.detect_isp(force=True))
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
        self.status_label = label("Ready.", "muted", wrap=True)
        c.addWidget(self.status_label)
        layout.addWidget(ctl)

        # Live log
        logcard = card()
        lc = QVBoxLayout(logcard)
        lc.setContentsMargins(6, 10, 6, 6)
        lc.addWidget(label("   LIVE EVENTS", "eyebrow"))
        self.live_table = make_table(["TIME", "EVENT", "DETAIL"])
        lc.addWidget(self.live_table)
        layout.addWidget(logcard, 1)
        return page

    def _history_page(self):
        page, layout = self._page()
        clear_btn = QPushButton("Clear history")
        clear_btn.clicked.connect(self._clear_history)
        layout.addLayout(page_header("Session history",
                                     "Monitoring sessions and their data usage, stored locally.",
                                     clear_btn))
        panel = card()
        p = QVBoxLayout(panel)
        p.setContentsMargins(6, 6, 6, 6)
        self.history_table = make_table(["STARTED", "DURATION", "ISP", "HEARTBEATS OK",
                                         "FAILED", "RECONNECTS", "DATA (EST.)", "AVG RESPONSE"])
        p.addWidget(self.history_table)
        layout.addWidget(panel, 1)
        return page

    def _events_page(self):
        page, layout = self._page()
        layout.addLayout(page_header("Connection events",
                                     "Connections, reconnections, failures and state changes."))
        panel = card()
        p = QVBoxLayout(panel)
        p.setContentsMargins(6, 6, 6, 6)
        self.events_table = make_table(["TIME", "EVENT", "DETAIL"])
        p.addWidget(self.events_table)
        layout.addWidget(panel, 1)
        return page

    def _settings_page(self):
        page, layout = self._page()
        layout.addLayout(page_header("Settings", "Heartbeat interval and data usage."))
        panel = card()
        p = QVBoxLayout(panel)
        p.setContentsMargins(24, 22, 24, 22)
        p.setSpacing(14)
        p.addWidget(label("Heartbeat", "h2"))
        form = QFormLayout()
        form.setHorizontalSpacing(24)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 600)
        self.interval_spin.setValue(DEFAULT_INTERVAL_S)
        self.interval_spin.setSuffix(" s")
        self.interval_spin.setFixedWidth(180)
        form.addRow(label("Heartbeat interval", "muted"), self.interval_spin)
        p.addLayout(form)
        self.usage_label = label("", "muted", wrap=True)
        p.addWidget(self.usage_label)
        p.addWidget(label(
            "Each heartbeat is a single GET request to the server root, which returns a "
            "109-byte page. The 25 MB /download speed-test endpoint is never used for "
            "monitoring. Measured on all four ISP servers: a connection is closed after about "
            f"{SERVER_IDLE_TIMEOUT_S:.0f} s without traffic, and after about "
            f"{SERVER_MAX_CONNECTION_AGE_S:.0f} s in total even when heartbeats keep it busy. "
            f"Below {SERVER_IDLE_TIMEOUT_S:.0f} s, one connection carries about a minute of "
            "heartbeats and is then replaced automatically. Longer intervals send fewer requests, "
            "but every heartbeat needs a new connection (about 6 KB with the TLS handshake).",
            "muted", wrap=True))
        p.addWidget(label("Keeping a connection open does not make your internet faster.",
                          "muted", wrap=True))
        self.interval_spin.valueChanged.connect(self._update_usage)
        self._update_usage()
        p.addWidget(label("Changes apply the next time you start monitoring.", "muted"))
        layout.addWidget(panel)
        layout.addStretch()
        return page

    # ── Prefs ────────────────────────────────────────────────────────────────
    def _load_prefs(self):
        try:
            isp = db.get_pref("isp_selection", AUTO)
            iv = int(db.get_pref("interval_s", str(DEFAULT_INTERVAL_S)))
        except Exception:
            isp, iv = AUTO, DEFAULT_INTERVAL_S
        if isp in (AUTO, *SUPPORTED_ISPS):
            self.isp_combo.setCurrentText(isp)
        self.interval_spin.setValue(iv)
        self.isp_combo.currentTextChanged.connect(lambda v: self._save_pref("isp_selection", v))
        self.interval_spin.valueChanged.connect(lambda v: self._save_pref("interval_s", str(v)))

    def _save_pref(self, key, value):
        try:
            db.set_pref(key, value)
        except Exception as exc:
            self.status_label.setText(f"Could not save setting: {exc}")

    # ── Navigation ───────────────────────────────────────────────────────────
    def _go_to(self, idx):
        if idx == 1:
            self.refresh_history()
        elif idx == 2:
            self.refresh_events()
        self.pages.setCurrentIndex(idx)

    def _update_usage(self):
        iv = self.interval_spin.value()
        per_hour = estimate_per_hour(iv)
        mode = ("keeps each connection open until the server's ~60 s limit"
                if iv < SERVER_IDLE_TIMEOUT_S else "reconnects on every heartbeat")
        self.usage_label.setText(
            f"Estimated data use at {iv} s: about {fmt_bytes(per_hour)} per hour "
            f"({fmt_bytes(per_hour * 24)} per day). This interval {mode}.")

    # ── ISP detection ────────────────────────────────────────────────────────
    def detect_isp(self, force=False):
        if self.detect_worker and self.detect_worker.isRunning():
            return
        self.detect_button.setEnabled(False)
        self.status_label.setText("Detecting ISP…")
        self.detect_worker = DetectWorker(self, force=force)
        self.detect_worker.done.connect(self._apply_isp_info)
        self.detect_worker.failed.connect(self._detect_failed)
        self.detect_worker.finished.connect(
            lambda: self.detect_button.setEnabled(not self._running()))
        self.detect_worker.start()

    def _apply_isp_info(self, info):
        detected = info.get("isp", UNKNOWN)
        org = info.get("organization", "")
        src = "cached" if info.get("cached") else "detected"
        self._detected_isp = detected if detected in SERVERS else None
        if self._detected_isp:
            self.t_isp.value.setText(detected)
            self.t_isp.detail.setText(f"Auto {src} · {org}")
            self.status_label.setText(f"ISP {src}: {detected} ({org}).")
        else:
            self.t_isp.value.setText("Unknown")
            self.t_isp.detail.setText(org or "Not recognised")
            self.status_label.setText(
                f"Could not match \"{org}\" to a supported ISP. Select your ISP manually.")
        if self._pending_start:
            self._pending_start = False
            if self._detected_isp:
                self._start_keeper(self._detected_isp)
            else:
                self._set_controls(running=False)
                QMessageBox.information(self, "Select ISP",
                                        f"Your network (\"{org}\") is not one of the supported "
                                        "ISPs. Please choose your ISP manually.")

    def _detect_failed(self, message):
        self.status_label.setText(message + " Select your ISP manually.")
        if self._pending_start:
            self._pending_start = False
            self._set_controls(running=False)
            QMessageBox.warning(self, "ISP detection failed",
                                message + "\n\nSelect your ISP manually and start again.")

    # ── Monitoring ───────────────────────────────────────────────────────────
    def _running(self):
        return bool(self.controller and self.controller.is_running())

    def _set_controls(self, running):
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.isp_combo.setEnabled(not running)
        self.detect_button.setEnabled(not running)
        self.interval_spin.setEnabled(not running)

    def start_monitoring(self):
        if self._running() or self._pending_start:
            return
        self._set_controls(running=True)
        self.stop_button.setEnabled(False)
        choice = self.isp_combo.currentText()
        if choice == AUTO:
            self._pending_start = True
            self.detect_isp(force=False)
        else:
            self.t_isp.value.setText(choice)
            self.t_isp.detail.setText("Selected manually")
            self._start_keeper(choice)

    def _start_keeper(self, isp):
        server = SERVERS[isp]
        self.live_table.setRowCount(0)
        self.controller = KeeperController(server, self.interval_spin.value(), self)
        self.controller.event.connect(self._on_event)
        self.controller.state_changed.connect(self._on_state)
        self.controller.finished.connect(self._monitor_finished)
        self.server_label.setText(f"Server: {server.host}:{server.port}")
        self._set_controls(running=True)
        self.controller.start()
        self._tick.start()
        self.status_label.setText(
            f"Monitoring {isp}: heartbeat every {self.interval_spin.value()} s "
            f"({SERVERS[isp].heartbeat_method} /).")

    def stop_monitoring(self):
        if self.controller and self._running():
            self.stop_button.setEnabled(False)
            self.badge.set_state("STOPPING", WARN)
            self.controller.stop()

    def _monitor_finished(self):
        self._tick.stop()
        self._set_controls(running=False)
        self._refresh_live()
        self.status_label.setText("Monitoring stopped.")
        if self._closing:
            QTimer.singleShot(0, self.close)

    def _on_state(self, state):
        colors = {State.CONNECTED.value: GOOD, State.CONNECTING.value: WARN,
                  State.RECONNECTING.value: BAD, State.STOPPED.value: MUTED}
        self.badge.set_state(state.upper(), colors.get(state, MUTED))
        self.state_label.setText(state)
        self.state_label.setStyleSheet(f"color:{colors.get(state, TEXT)};")

    def _on_event(self, e):
        if e.kind == "heartbeat" and self.live_table.rowCount() and \
                self.live_table.item(0, 1).text() == "heartbeat":
            # collapse consecutive heartbeats into one updating row
            self.live_table.item(0, 0).setText(fmt_ts(e.at, short=True))
            self.live_table.item(0, 2).setText(e.message)
        else:
            self.live_table.insertRow(0)
            for col, v in enumerate((fmt_ts(e.at, short=True), e.kind, e.message)):
                self.live_table.setItem(0, col, QTableWidgetItem(v))
            if self.live_table.rowCount() > 200:
                self.live_table.removeRow(200)
        self._refresh_live()

    def _refresh_live(self):
        now = time.time()
        if not self.controller:
            self.t_today.value.setText(self._usage_24h())
            return
        s = self.controller.keeper.snapshot()
        running = self._running()
        self.conn_age_label.setText(fmt_duration(now - s.connection_since)
                                    if s.connection_since and running else "—")
        self.session_label.setText(f"Monitoring time: {fmt_duration(now - s.started_at)}"
                                   if running else "Monitoring time: stopped")
        if s.last_ok_at:
            self.t_last.value.setText(fmt_ts(s.last_ok_at, short=True))
            self.t_last.detail.setText(f"{fmt_duration(now - s.last_ok_at)} ago · "
                                       f"{s.last_rtt_ms:.0f} ms")
        avg = s.avg_rtt_ms
        self.t_rtt.value.setText(f"{avg:.0f} ms" if avg is not None else "—")
        self.t_rtt.detail.setText(f"Last {s.last_rtt_ms:.0f} ms" if s.last_rtt_ms else "—")
        self.t_beats.value.setText(str(s.heartbeats_ok))
        self.t_beats.detail.setText(f"{s.heartbeats_failed} failed")
        self.t_reconn.value.setText(str(s.reconnects))
        self.t_reconn.detail.setText(f"{s.reused} requests on a reused connection")
        self.t_data.value.setText(fmt_bytes(s.bytes_total))
        self.t_data.detail.setText(f"↑ {fmt_bytes(s.bytes_tx)}  ↓ {fmt_bytes(s.bytes_rx)}")
        rate = s.bytes_per_hour(now)
        self.t_rate.value.setText(fmt_bytes(rate) if rate is not None else "—")
        if int(now) % 15 == 0 or not running:
            self.t_today.value.setText(self._usage_24h())

    def _usage_24h(self):
        try:
            return fmt_bytes(db.usage_totals(time.time() - 86400))
        except Exception:
            return "—"

    # ── History / events ─────────────────────────────────────────────────────
    def refresh_history(self):
        try:
            rows = db.recent_sessions(200)
        except Exception as exc:
            self.status_label.setText(f"Could not read history: {exc}")
            return
        fill_table(self.history_table, [
            (fmt_ts(start), fmt_duration((end or time.time()) - start), isp, ok, failed,
             max(0, conns - 1), fmt_bytes(nbytes), f"{rtt:.0f} ms" if rtt else "—")
            for start, end, isp, ok, failed, conns, nbytes, rtt in rows])

    def refresh_events(self):
        try:
            rows = db.recent_events(500)
        except Exception as exc:
            self.status_label.setText(f"Could not read events: {exc}")
            return
        fill_table(self.events_table, [(fmt_ts(at), kind, msg) for at, kind, msg in rows])

    def _clear_history(self):
        if QMessageBox.question(self, "Clear history",
                                "Delete all sessions and events? This cannot be undone.") \
                != QMessageBox.StandardButton.Yes:
            return
        db.clear_history()
        self.refresh_history()
        self._refresh_live()

    # ── Shutdown ─────────────────────────────────────────────────────────────
    def closeEvent(self, event):
        if self._running():
            self._closing = True
            self.stop_monitoring()
            event.ignore()
            return
        if self.detect_worker and self.detect_worker.isRunning():
            self.detect_worker.wait(11000)
        event.accept()
