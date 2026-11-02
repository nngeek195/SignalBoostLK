import threading

from PySide6.QtCore import QThread, Signal

from app.core.download_engine import SUPPORTED_ISPS, TestCancelled, run_download_test
from app.core.isp_detector import detect_current_isp
from app.database.db import save_test

AUTO = "Auto-detect"


class MonitorWorker(QThread):
    status = Signal(str)
    isp_info = Signal(dict)
    test_started = Signal(str)
    progress = Signal(int, int)
    test_result = Signal(dict)
    error = Signal(str)
    waiting = Signal(int)  # seconds until next cycle

    def __init__(self, selected_isp, size_mb, interval_seconds):
        super().__init__()
        # selected_isp is either AUTO or one of SUPPORTED_ISPS.
        self.selected_isp = selected_isp
        self.size_bytes = int(size_mb * 1_000_000)
        self.interval = interval_seconds
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def _resolve_isp(self, cycle):
        """Detect network info; a manual choice always wins over detection."""
        info = {}
        try:
            info = detect_current_isp()
            self.isp_info.emit(info)
        except Exception as exc:
            if self.selected_isp == AUTO:
                raise RuntimeError(f"ISP detection failed: {exc}") from exc
            self.status.emit(f"Cycle #{cycle}: IP lookup failed, using {self.selected_isp}.")

        if self.selected_isp != AUTO:
            return self.selected_isp, info
        detected = info.get("isp", "Unknown")
        if detected not in SUPPORTED_ISPS:
            raise RuntimeError(
                f"Could not identify ISP from \"{info.get('organization', 'unknown')}\". "
                "Select your ISP manually."
            )
        return detected, info

    def run(self):
        cycle = 0
        while not self._stop_event.is_set():
            cycle += 1
            try:
                self.status.emit(f"Cycle #{cycle}: detecting network…")
                isp, info = self._resolve_isp(cycle)
                if self._stop_event.is_set():
                    break

                self.status.emit(f"Cycle #{cycle}: testing {isp}…")
                self.test_started.emit(isp)
                result = run_download_test(
                    isp,
                    self.size_bytes,
                    lambda received, total: self.progress.emit(received, total),
                    should_cancel=self._stop_event.is_set,
                )
                result["public_ip"] = info.get("ip", "")
                save_test(result, result["public_ip"])
                self.test_result.emit(result)
                self.status.emit(
                    f"Cycle #{cycle}: {isp} — {result['mbps']:.2f} Mbps"
                )
            except TestCancelled:
                break
            except Exception as exc:
                self.error.emit(f"Cycle #{cycle} failed: {exc}")

            if self._stop_event.is_set():
                break
            self.waiting.emit(self.interval)
            self._stop_event.wait(self.interval)

        self.status.emit("Monitoring stopped.")
