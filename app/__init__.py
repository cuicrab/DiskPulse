from PySide6.QtWidgets import QApplication
from .main_window import MainWindow
from .i18n import get_translation_manager


def run():
    import sys
    app = QApplication(sys.argv)
    
    # Initialize translation manager
    trans_mgr = get_translation_manager()
    trans_mgr.set_app(app)
    trans_mgr.initialize()
    
    with open("app/resources/styles.qss", encoding="utf-8") as f:
        app.setStyleSheet(f.read())
    window = MainWindow()
    window.show()
    sys.exit(app.exec())