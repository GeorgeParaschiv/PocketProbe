from PyQt5.QtWidgets import QApplication
import sys
from scopeGUI import scopeGUI

def apply_stylesheet(app):
    style = '''
    QWidget {
        background-color: #2b2b2b;
        color: #dddddd;
        font-family: 'Segoe UI', sans-serif;
        font-size: 11pt;
    }

    QComboBox, QLineEdit, QListWidget, QCheckBox, QLabel {
        background-color: #3c3f41;
        padding: 5px;
        border-radius: 4px;
    }

    QPushButton {
        background-color: #4e5052;
        border: 1px solid #666;
        border-radius: 4px;
        padding: 4px 8px;
    }
    QPushButton:hover {
        background-color: #5c5f61;
    }

    QSlider::groove:horizontal {
    height: 6px;
    background: #444;
    }
    QSlider::handle:horizontal {
        background: #888;
        border: 1px solid #555;
        width: 12px;
        margin: -5px 0;
        border-radius: 6px;
    }
    QSlider::tick-mark:horizontal {
        background: #bbb;
        height: 10px;
        width: 2px;
    }

    QListWidget::item {
        background-color: #3c3f41;
        border: 1px solid #444;
        margin: 2px;
        padding: 4px;
        border-radius: 3px;
    }

    QListWidget::item:selected {
        background-color: #5c5f61;
    }
    '''
    app.setStyleSheet(style)


def main():
    app = QApplication(sys.argv)
    apply_stylesheet(app)
    window = scopeGUI(1000)  # Pass frame_size as before
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
