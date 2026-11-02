import sys

from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow, apply_theme


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SignalBoostLK")
    app.setOrganizationName("SignalBoostLK")
    apply_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
