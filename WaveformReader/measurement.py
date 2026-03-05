import pyqtgraph as pg
import numpy as np
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QCheckBox, QListWidget, QListWidgetItem, QComboBox, QPushButton, QHBoxLayout
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from cursors import CursorManager

class MeasurementManager:
    def __init__(self, plot_widget):
        self.plot_widget = plot_widget
        
        self.latest_x = None
        self.latest_y = None

    def update_data(self, x, y):
        self.latest_x = np.array(x)
        self.latest_y = np.array(y)

    def get_measurements(self):
        if self.latest_y is None or self.latest_x is None:
            return {}

        vpp = np.max(self.latest_y) - np.min(self.latest_y)
        vmax = np.max(self.latest_y)
        vmin = np.min(self.latest_y)
        vmean = np.mean(self.latest_y)

        freq = self._estimate_frequency(self.latest_x, self.latest_y)

        return {
            "Vpp": vpp,
            "Max": vmax,
            "Min": vmin,
            "Mean": vmean,
            "Frequency": freq,
        }

    def _estimate_frequency(self, x, y):
        # Use zero crossings to estimate frequency robustly
        y = np.asarray(y)
        x = np.asarray(x)
        if len(y) < 2 or len(x) < 2:
            return 0.0
        # Remove DC offset
        y_centered = y - np.mean(y)
        # Find indices where signal crosses zero (from negative to positive)
        crossings = np.where((y_centered[:-1] < 0) & (y_centered[1:] >= 0))[0]
        if len(crossings) < 2:
            return 0.0
        # Calculate periods using x values at crossings
        periods = np.diff(x[crossings])
        avg_period = np.mean(periods)
        if avg_period > 0:
            return 1.0 / avg_period
        else:
            return 0.0


class MeasurementPanel(QWidget):
    def __init__(self, measurement_manager):
        super().__init__()
        self.mm = measurement_manager
        self.cursor_mgr = CursorManager(self.mm.plot_widget)

        self.main_layout = QHBoxLayout(self)
        self.cursor_section = QVBoxLayout()

        self.cursor_toggle_1 = QCheckBox("Show Cursor 1")
        self.cursor_toggle_1.setChecked(False)
        self.cursor_toggle_1.stateChanged.connect(lambda state: self.cursor_mgr.set_cursor_visibility('1', state == Qt.Checked))
        self.cursor_section.addWidget(self.cursor_toggle_1)

        self.center_btn_1 = QPushButton("Bring Cursor 1 to Center")
        self.center_btn_1.clicked.connect(lambda: self.cursor_mgr.bring_cursor_to_center('1'))
        self.cursor_section.addWidget(self.center_btn_1)

        self.cursor_toggle_2 = QCheckBox("Show Cursor 2")
        self.cursor_toggle_2.setChecked(False)
        self.cursor_toggle_2.stateChanged.connect(lambda state: self.cursor_mgr.set_cursor_visibility('2', state == Qt.Checked))
        self.cursor_section.addWidget(self.cursor_toggle_2)

        self.center_btn_2 = QPushButton("Bring Cursor 2 to Center")
        self.center_btn_2.clicked.connect(lambda: self.cursor_mgr.bring_cursor_to_center('2'))
        self.cursor_section.addWidget(self.center_btn_2)

        self.cursor_values_widget = QWidget()
        cursor_values_layout = QVBoxLayout(self.cursor_values_widget)
        cursor_values_layout.setContentsMargins(8, 8, 8, 8)
        cursor_values_layout.setSpacing(6)

        self.cursor_values_label = QLabel("Cursor Values:")
        font = QFont()
        font.setBold(True)
        self.cursor_values_label.setFont(font)
        self.cursor_values_label.setStyleSheet("color: #e0e0e0;")
        cursor_values_layout.addWidget(self.cursor_values_label)

        # Add a subtle border and background
        self.cursor_values_widget.setStyleSheet("""
            background-color: #35383a;
            border: 1px solid #444;
            border-radius: 6px;
        """)

        self.cursor_section.addWidget(self.cursor_values_widget)
        self.cursor_section.addStretch()
        self.main_layout.addLayout(self.cursor_section, stretch=1)

        # --- Right side: Measurement dropdown and list ---
        self.measurement_section = QVBoxLayout()

        self.measurement_dropdown = QComboBox()
        self.measurement_dropdown.addItems(["Vpp", "Max", "Min", "Mean", "Frequency"])
        self.measurement_section.addWidget(self.measurement_dropdown)

        self.add_button = QPushButton("Add Measurement")
        self.measurement_section.addWidget(self.add_button)

        self.measurement_list = QListWidget()
        self.measurement_section.addWidget(self.measurement_list)

        self.add_button.clicked.connect(self.add_measurement)

        self.main_layout.addLayout(self.measurement_section, stretch=2)

        self.active_measurements = []

    def add_measurement(self):
        key = self.measurement_dropdown.currentText()
        if key in self.active_measurements:
            return
        self.active_measurements.append(key)

        item = QListWidgetItem()
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # Two-row label: name (left) on top, value (right) on bottom
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
        layout.addWidget(label_widget)
        layout.addWidget(remove_btn)
        layout.setContentsMargins(4, 4, 4, 4)
        widget.setLayout(layout)
        from PyQt5.QtCore import QSize
        item.setSizeHint(QSize(widget.sizeHint().width(), 120))
        self.measurement_list.addItem(item)
        self.measurement_list.setItemWidget(item, widget)

        def remove():
            row = self.measurement_list.row(item)
            self.measurement_list.takeItem(row)
            self.active_measurements.remove(key)

        remove_btn.clicked.connect(remove)

    def _format_cursor_value(self, key, value):
        """Format cursor value with appropriate units based on axis"""
        if key in ('X1', 'X2', 'Δx'):
            # Time values — pick appropriate unit
            abs_v = abs(value)
            if abs_v == 0:
                return f"{key}: 0"
            elif abs_v >= 1e-3:
                return f"{key}: {value*1e3:.3f} ms"
            elif abs_v >= 1e-6:
                return f"{key}: {value*1e6:.3f} μs"
            else:
                return f"{key}: {value:.3e} s"
        else:
            # Voltage values
            abs_v = abs(value)
            if abs_v == 0:
                return f"{key}: 0"
            elif abs_v >= 1:
                return f"{key}: {value:.3f} V"
            else:
                return f"{key}: {value*1e3:.3f} mV"

    def update_display(self):
        cursor_values = self.cursor_mgr.get_cursor_values()
        lines = [self._format_cursor_value(k, v) for k, v in cursor_values.items()]
        self.cursor_values_label.setText("Cursor Values:\n" + "\n".join(lines))

        stats = self.mm.get_measurements()
        for i in range(self.measurement_list.count()):
            item = self.measurement_list.item(i)
            widget = self.measurement_list.itemWidget(item)
            label_widget = widget.layout().itemAt(0).widget()
            name_label = label_widget.layout().itemAt(0).widget()
            value_label = label_widget.layout().itemAt(1).widget()
            key = name_label.text()
            if key in stats:
                value_label.setText(self._format_measurement(key, stats[key]))

    def _format_measurement(self, key, value):
        """Format measurement value with appropriate units"""
        if key == "Frequency":
            if value == 0:
                return "N/A"
            elif value >= 1e6:
                return f"{value/1e6:.3f} MHz"
            elif value >= 1e3:
                return f"{value/1e3:.3f} kHz"
            else:
                return f"{value:.3f} Hz"
        else:
            # Voltage measurements (Vpp, Max, Min, Mean)
            abs_v = abs(value)
            if abs_v == 0:
                return "0 V"
            elif abs_v >= 1:
                return f"{value:.3f} V"
            else:
                return f"{value*1e3:.3f} mV"