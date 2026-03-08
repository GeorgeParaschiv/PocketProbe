import numpy as np
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QCheckBox, QListWidget,
    QListWidgetItem, QComboBox, QPushButton, QHBoxLayout,
)
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFont
from cursors import CursorManager


class MeasurementManager:
    def __init__(self):
        self.latest_x = None
        self.latest_y = None

    def update_data(self, x, y):
        self.latest_x = np.asarray(x)
        self.latest_y = np.asarray(y)

    def get_measurements(self):
        if self.latest_y is None or self.latest_x is None:
            return {}
        return {
            "Vpp":       np.ptp(self.latest_y),
            "Max":       np.max(self.latest_y),
            "Min":       np.min(self.latest_y),
            "Mean":      np.mean(self.latest_y),
            "Frequency": self._estimate_frequency(self.latest_x, self.latest_y),
        }

    @staticmethod
    def _estimate_frequency(x, y):
        y = np.asarray(y)
        x = np.asarray(x)
        if len(y) < 2 or len(x) < 2:
            return 0.0
        y_centered = y - np.mean(y)
        crossings = np.where((y_centered[:-1] < 0) & (y_centered[1:] >= 0))[0]
        if len(crossings) < 2:
            return 0.0
        avg_period = np.mean(np.diff(x[crossings]))
        return 1.0 / avg_period if avg_period > 0 else 0.0


class MeasurementPanel(QWidget):
    MEASUREMENT_KEYS = ["Vpp", "Max", "Min", "Mean", "Frequency"]

    def __init__(self, measurement_manager, plot_widget):
        super().__init__()
        self.mm = measurement_manager
        self.cursor_mgr = CursorManager(plot_widget)

        self.main_layout = QHBoxLayout(self)

        # --- Left: cursors ---
        cursor_col = QVBoxLayout()

        self.cursor_toggle_1 = QCheckBox("Show Cursor 1")
        self.cursor_toggle_1.setChecked(False)
        self.cursor_toggle_1.stateChanged.connect(
            lambda s: self.cursor_mgr.set_cursor_visibility('1', s == Qt.Checked)
        )
        cursor_col.addWidget(self.cursor_toggle_1)

        self.center_btn_1 = QPushButton("Bring Cursor 1 to Center")
        self.center_btn_1.clicked.connect(lambda: self.cursor_mgr.bring_cursor_to_center('1'))
        cursor_col.addWidget(self.center_btn_1)

        self.cursor_toggle_2 = QCheckBox("Show Cursor 2")
        self.cursor_toggle_2.setChecked(False)
        self.cursor_toggle_2.stateChanged.connect(
            lambda s: self.cursor_mgr.set_cursor_visibility('2', s == Qt.Checked)
        )
        cursor_col.addWidget(self.cursor_toggle_2)

        self.center_btn_2 = QPushButton("Bring Cursor 2 to Center")
        self.center_btn_2.clicked.connect(lambda: self.cursor_mgr.bring_cursor_to_center('2'))
        cursor_col.addWidget(self.center_btn_2)

        self.cursor_values_widget = QWidget()
        cv_layout = QVBoxLayout(self.cursor_values_widget)
        cv_layout.setContentsMargins(8, 8, 8, 8)
        cv_layout.setSpacing(6)

        self.cursor_values_label = QLabel("Cursor Values:")
        font = QFont()
        font.setBold(True)
        self.cursor_values_label.setFont(font)
        self.cursor_values_label.setStyleSheet("color: #e0e0e0;")
        cv_layout.addWidget(self.cursor_values_label)

        self.cursor_values_widget.setStyleSheet(
            "background-color: #35383a; border: 1px solid #444; border-radius: 6px;"
        )

        cursor_col.addWidget(self.cursor_values_widget)
        cursor_col.addStretch()
        self.main_layout.addLayout(cursor_col, stretch=1)

        # --- Right: measurements ---
        meas_col = QVBoxLayout()

        self.measurement_dropdown = QComboBox()
        self.measurement_dropdown.addItems(self.MEASUREMENT_KEYS)
        meas_col.addWidget(self.measurement_dropdown)

        self.add_button = QPushButton("Add Measurement")
        self.add_button.clicked.connect(self.add_measurement)
        meas_col.addWidget(self.add_button)

        self.measurement_list = QListWidget()
        meas_col.addWidget(self.measurement_list)

        self.main_layout.addLayout(meas_col, stretch=2)

        self.active_measurements = []

    # ── Add / remove measurements ────────────────────────────────────────

    def add_measurement(self):
        key = self.measurement_dropdown.currentText()
        if key in self.active_measurements:
            return
        self.active_measurements.append(key)

        item = QListWidgetItem()
        widget = QWidget()
        row = QHBoxLayout(widget)
        row.setContentsMargins(4, 4, 4, 4)

        label_widget = QWidget()
        label_layout = QVBoxLayout(label_widget)
        label_layout.setContentsMargins(0, 0, 0, 0)
        label_layout.setSpacing(2)

        name_label = QLabel(key)
        name_label.setAlignment(Qt.AlignLeft)
        name_label.setStyleSheet("font-size: 10pt; color: #aaa;")

        value_label = QLabel("--")
        value_label.setAlignment(Qt.AlignRight)
        value_label.setStyleSheet("font-size: 10pt; color: #e0e0e0; font-weight: bold;")

        label_layout.addWidget(name_label)
        label_layout.addWidget(value_label)
        label_widget.setMinimumWidth(120)
        label_widget.setMinimumHeight(50)

        remove_btn = QPushButton("x")
        remove_btn.setFixedWidth(24)

        row.addWidget(label_widget)
        row.addWidget(remove_btn)

        item.setSizeHint(QSize(widget.sizeHint().width(), 120))
        self.measurement_list.addItem(item)
        self.measurement_list.setItemWidget(item, widget)

        def remove():
            self.measurement_list.takeItem(self.measurement_list.row(item))
            self.active_measurements.remove(key)

        remove_btn.clicked.connect(remove)

    # ── Display update ───────────────────────────────────────────────────

    def update_display(self):
        cursor_values = self.cursor_mgr.get_cursor_values()
        lines = [self._format_cursor_value(k, v) for k, v in cursor_values.items()]
        self.cursor_values_label.setText("Cursor Values:\n" + "\n".join(lines))

        stats = self.mm.get_measurements()
        for i in range(self.measurement_list.count()):
            widget = self.measurement_list.itemWidget(self.measurement_list.item(i))
            label_widget = widget.layout().itemAt(0).widget()
            name = label_widget.layout().itemAt(0).widget().text()
            value_lbl = label_widget.layout().itemAt(1).widget()
            if name in stats:
                value_lbl.setText(self._format_measurement(name, stats[name]))

    # ── Formatting ───────────────────────────────────────────────────────

    @staticmethod
    def _format_voltage(value):
        if abs(value) >= 1:
            return f"{value:.3f} V"
        if value == 0:
            return "0 V"
        return f"{value*1e3:.3f} mV"

    @staticmethod
    def _format_time(value):
        a = abs(value)
        if a == 0:
            return "0"
        if a >= 1e-3:
            return f"{value*1e3:.3f} ms"
        if a >= 1e-6:
            return f"{value*1e6:.3f} μs"
        return f"{value:.3e} s"

    @classmethod
    def _format_cursor_value(cls, key, value):
        if key in ('X1', 'X2', 'Δx'):
            return f"{key}: {cls._format_time(value)}"
        return f"{key}: {cls._format_voltage(value)}"

    @classmethod
    def _format_measurement(cls, key, value):
        if key == "Frequency":
            if value == 0:
                return "N/A"
            if value >= 1e6:
                return f"{value/1e6:.3f} MHz"
            if value >= 1e3:
                return f"{value/1e3:.3f} kHz"
            return f"{value:.3f} Hz"
        return cls._format_voltage(value)
