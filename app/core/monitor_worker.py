"""Qt adapter around ConnectionKeeper: persists events and re-emits them as
Qt signals (delivered on the GUI thread via queued connections).

Replaces the 0.1.0 worker, which downloaded 25 MB on every cycle. Nothing in
here performs a speed test.
"""
from __future__ import annotations

import logging
import time

from PySide6.QtCore import QObject, Signal

from app.core.config import IspServer
from app.core.keeper import ConnectionKeeper, Event, State
from app.database import db

log = logging.getLogger(__name__)
AUTO = "Auto-detect"
PERSIST_EVERY_S = 30


class KeeperController(QObject):
    event = Signal(object)      # keeper.Event
    state_changed = Signal(str)
    finished = Signal()

    def __init__(self, server: IspServer, interval_s: float, parent=None) -> None:
        super().__init__(parent)
        self.server = server
        self.keeper = ConnectionKeeper(server, interval_s, on_event=self._on_event)
        self.session_id: int | None = None
        self._last_persist = 0.0

    def start(self) -> None:
        try:
            self.session_id = db.start_session(self.server.name, self.server.host,
                                               self.keeper.interval_s, time.time())
        except Exception:
            log.exception("could not create session row")
        self.keeper.start()

    def stop(self) -> None:
        self.keeper.stop(wait=None)  # returns immediately; STOPPED event follows

    def is_running(self) -> bool:
        return self.keeper.is_running()

    # runs on the keeper thread
    def _on_event(self, e: Event) -> None:
        sid = self.session_id
        try:
            if e.kind == "heartbeat" and sid:
                db.add_heartbeat(sid, e.at, True, e.data.get("rtt_ms"), e.data.get("reused"),
                                 e.data.get("bytes"))
            elif e.kind in ("connected", "error", "info", "state"):
                db.add_event(sid, e.at, e.kind, e.message)
                if e.kind == "error" and sid:
                    db.add_heartbeat(sid, e.at, False, None, None, None)
            now = time.time()
            stopped = e.kind == "state" and e.data.get("state") is State.STOPPED
            if sid and (stopped or now - self._last_persist >= PERSIST_EVERY_S):
                db.update_session(sid, self.keeper.snapshot(), ended_at=now if stopped else None)
                self._last_persist = now
        except Exception:
            log.exception("persisting keeper event failed")
        self.event.emit(e)
        if e.kind == "state":
            self.state_changed.emit(e.data["state"].value)
            if e.data.get("state") is State.STOPPED:
                self.finished.emit()
