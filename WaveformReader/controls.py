from PyQt5.QtWidgets import QComboBox, QLabel, QSlider, QVBoxLayout, QHBoxLayout, QDial, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal, QObject

class ControlPanelSignals(QObject):
    value_changed = pyqtSignal(int, int)  # op_code, value

class ControlPanel:
    OP_MAP = {
        'V': 1,  # Vertical division
        'T': 2,  # Timebase division
        'O': 3,  # Vertical offset
        'S': 4,  # Sleep/Wake (ADC clock enable)
    }

    TIMEBASE_CAL = 5.0 / 5.849

    voltbase_labels = [
        "10mV", "20mV", "50mV", "100mV", "200mV",
        "500mV", "1V", "2V", "5V", "10V",
    ]
    timebase_labels = ["5μs", "10μs", "20μs", "50μs", "100μs"]

    def __init__(self):
        self.layout = QVBoxLayout()
        self.signals = ControlPanelSignals()

        # --- Mode selector ---
        mode_row = QHBoxLayout()
        self.mode_label = QLabel("Mode:")
        self.mode_select = QComboBox()
        self.mode_select.addItems(["Run", "Stop"])
        mode_row.addWidget(self.mode_label)
        mode_row.addWidget(self.mode_select)
        self.autoscale_btn = QPushButton("Autoscale")
        mode_row.addWidget(self.autoscale_btn)
        self.layout.addLayout(mode_row)

        # --- Division knobs ---
        div_row = QHBoxLayout()
        self.vert_label = QLabel("Volts/div")
        self.vert_knob = QDial()
        self.vert_knob.setMinimum(0)
        self.vert_knob.setMaximum(len(self.voltbase_labels) - 1)
        self.vert_knob.setValue(5)
        self.vert_knob.setNotchesVisible(True)

        self.horz_label = QLabel("Timebase (s/div)")
        self.horz_knob = QDial()
        self.horz_knob.setMinimum(0)
        self.horz_knob.setMaximum(len(self.timebase_labels) - 1)
        self.horz_knob.setValue(0)
        self.horz_knob.setNotchesVisible(True)

        div_row.addWidget(self.vert_label)
        div_row.addWidget(self.vert_knob)
        div_row.addSpacing(24)
        div_row.addWidget(self.horz_label)
        div_row.addWidget(self.horz_knob)
        self.layout.addLayout(div_row)

        # --- Vertical offset slider (-85 to +85 DAC steps, ~12mV/step) ---
        voffset_row = QHBoxLayout()
        self.vert_off_label = QLabel("Vertical Offset")
        voffset_row.addWidget(self.vert_off_label)

        self.vert_off_slider = QSlider(Qt.Horizontal)
        self.vert_off_slider.setMinimum(-85)
        self.vert_off_slider.setMaximum(85)
        self.vert_off_slider.setValue(0)
        self.vert_off_slider.setTickInterval(1)
        voffset_row.addWidget(self.vert_off_slider)

        self.vert_off_left_btn = QPushButton("◀")
        self.vert_off_left_btn.setFixedWidth(30)
        self.vert_off_left_btn.clicked.connect(self._nudge_vert_offset(-1))
        voffset_row.addWidget(self.vert_off_left_btn)

        self.vert_off_right_btn = QPushButton("▶")
        self.vert_off_right_btn.setFixedWidth(30)
        self.vert_off_right_btn.clicked.connect(self._nudge_vert_offset(1))
        voffset_row.addWidget(self.vert_off_right_btn)

        self.vert_zero_btn = QPushButton("Zero")
        self.vert_zero_btn.clicked.connect(self._on_vert_zero_clicked)
        voffset_row.addWidget(self.vert_zero_btn)

        self.layout.addLayout(voffset_row)

        # --- Horizontal offset slider (-500 to +500 samples, software only) ---
        hoffset_row = QHBoxLayout()
        self.horz_off_label = QLabel("Horizontal Offset")
        self.horz_off_slider = QSlider(Qt.Horizontal)
        self.horz_off_slider.setMinimum(-500)
        self.horz_off_slider.setMaximum(500)
        self.horz_off_slider.setValue(0)
        self.horz_off_slider.setTickInterval(50)
        hoffset_row.addWidget(self.horz_off_label)
        hoffset_row.addWidget(self.horz_off_slider)

        self.horz_left_btn = QPushButton("◀")
        self.horz_left_btn.setFixedWidth(30)
        self.horz_left_btn.clicked.connect(lambda: self.horz_off_slider.setValue(self.horz_off_slider.value() - 1))
        hoffset_row.addWidget(self.horz_left_btn)

        self.horz_right_btn = QPushButton("▶")
        self.horz_right_btn.setFixedWidth(30)
        self.horz_right_btn.clicked.connect(lambda: self.horz_off_slider.setValue(self.horz_off_slider.value() + 1))
        hoffset_row.addWidget(self.horz_right_btn)

        self.horz_zero_btn = QPushButton("Zero")
        self.horz_zero_btn.clicked.connect(lambda: self.horz_off_slider.setValue(0))
        hoffset_row.addWidget(self.horz_zero_btn)

        self.layout.addLayout(hoffset_row)

        # --- Trigger mode ---
        trigger_row = QHBoxLayout()
        self.trigger_label = QLabel("Trigger:")
        self.trigger_select = QComboBox()
        self.trigger_select.addItems(["Off", "Rising Edge", "Falling Edge"])
        self.trigger_select.setCurrentIndex(1)
        trigger_row.addWidget(self.trigger_label)
        trigger_row.addWidget(self.trigger_select)
        self.layout.addLayout(trigger_row)

        # --- Trigger level ---
        trigger_level_row = QHBoxLayout()
        self.trigger_level_label = QLabel("Trigger Level:")
        trigger_level_row.addWidget(self.trigger_level_label)

        self.trigger_level_down_btn = QPushButton("▼")
        self.trigger_level_down_btn.setMaximumWidth(30)
        self.trigger_level_down_btn.clicked.connect(self._on_trigger_level_down)
        trigger_level_row.addWidget(self.trigger_level_down_btn)

        self.trigger_level_value_label = QLabel("0mV")
        self.trigger_level_value_label.setMinimumWidth(60)
        self.trigger_level_value_label.setAlignment(Qt.AlignCenter)
        trigger_level_row.addWidget(self.trigger_level_value_label)

        self.trigger_level_up_btn = QPushButton("▲")
        self.trigger_level_up_btn.setMaximumWidth(30)
        self.trigger_level_up_btn.clicked.connect(self._on_trigger_level_up)
        trigger_level_row.addWidget(self.trigger_level_up_btn)

        self.trigger_level_zero_btn = QPushButton("Zero")
        self.trigger_level_zero_btn.clicked.connect(self._on_trigger_level_zero)
        trigger_level_row.addWidget(self.trigger_level_zero_btn)

        self.layout.addLayout(trigger_level_row)

        self._trigger_level_mv = 0
        self._trigger_level_step_mv = 50

        # Previous-value tracking for change detection
        self._prev_vert_knob = self.vert_knob.value()
        self._prev_horz_knob = self.horz_knob.value()
        self._prev_vert_off = self.vert_off_slider.value()
        self._committed_vert_offset = self.vert_off_slider.value()
        self.voltage_multiplier = self._calc_multiplier(self.vert_knob.value())

        self.vert_knob.valueChanged.connect(self._on_vert_knob_changed)
        self.horz_knob.valueChanged.connect(self._on_horz_knob_changed)
        self.vert_off_slider.sliderReleased.connect(self._on_vert_off_released)

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _parse_voltage_label(label):
        """Parse a voltbase label like '100mV' or '2V' into volts."""
        if label.endswith("mV"):
            return float(label[:-2]) * 1e-3
        return float(label[:-1])

    @staticmethod
    def _parse_time_label(label):
        """Parse a timebase label like '50μs' or '10ms' into seconds."""
        if "μs" in label:
            return float(label.replace("μs", "")) * 1e-6
        if "ms" in label:
            return float(label.replace("ms", "")) * 1e-3
        return float(label)

    def _label_to_mv(self, val):
        label = self.voltbase_labels[val]
        return int(self._parse_voltage_label(label) * 1000)

    def _calc_multiplier(self, val):
        """Hardware gain multiplier based on knob position (mirrors STM32 thresholds)."""
        mv = self._label_to_mv(val)
        if mv <= 100:
            return 10
        if mv <= 500:
            return 5
        if mv <= 2000:
            return 2
        return 1

    def _timebase_to_us(self, idx):
        """Convert timebase knob index to the sample-rate divisor sent to STM32."""
        label = self.timebase_labels[idx]
        us = int(self._parse_time_label(label) * 1e6)
        return 1 if us <= 5 else us // 5

    def _nudge_vert_offset(self, direction):
        """Return a slot that nudges the vertical offset slider by ±1 and sends."""
        def _slot():
            s = self.vert_off_slider
            s.setValue(max(s.minimum(), min(s.maximum(), s.value() + direction)))
            self._on_vert_off_released()
        return _slot

    # ── Knob / slider callbacks ──────────────────────────────────────────

    def _on_vert_knob_changed(self, val):
        if val != self._prev_vert_knob:
            self._prev_vert_knob = val
            self.voltage_multiplier = self._calc_multiplier(val)
            self.signals.value_changed.emit(self.OP_MAP['V'], self._label_to_mv(val))

    def _on_horz_knob_changed(self, val):
        if val != self._prev_horz_knob:
            self._prev_horz_knob = val
            self.signals.value_changed.emit(self.OP_MAP['T'], self._timebase_to_us(val))

    def _send_offset_command(self, val):
        self._prev_vert_off = val
        self._committed_vert_offset = val
        encoded = val + 85
        print(f"Offset: {val} DAC steps ({val * 12.0:.1f}mV), encoded: {encoded}")
        self.signals.value_changed.emit(self.OP_MAP['O'], encoded)

    def _on_vert_zero_clicked(self):
        self.vert_off_slider.setValue(0)
        self._send_offset_command(0)

    def _on_vert_off_released(self):
        val = self.vert_off_slider.value()
        if val != self._prev_vert_off:
            self._send_offset_command(val)

    # ── Trigger callbacks ────────────────────────────────────────────────

    def _update_trigger_level_label(self):
        mv = self._trigger_level_mv
        if abs(mv) >= 1000:
            self.trigger_level_value_label.setText(f"{mv / 1000.0:.2f}V")
        else:
            sign = "+" if mv > 0 else ""
            self.trigger_level_value_label.setText(f"{sign}{mv}mV")

    def _on_trigger_level_up(self):
        self._trigger_level_mv += self._trigger_level_step_mv
        self._update_trigger_level_label()

    def _on_trigger_level_down(self):
        self._trigger_level_mv -= self._trigger_level_step_mv
        self._update_trigger_level_label()

    def _on_trigger_level_zero(self):
        self._trigger_level_mv = 0
        self._update_trigger_level_label()

    # ── Public API ───────────────────────────────────────────────────────

    def on_knob_change(self, callback):
        self.signals.value_changed.connect(callback)

    def send_all_settings(self):
        self.signals.value_changed.emit(self.OP_MAP['V'], self._label_to_mv(self.vert_knob.value()))
        self.signals.value_changed.emit(self.OP_MAP['T'], self._timebase_to_us(self.horz_knob.value()))
        self.signals.value_changed.emit(self.OP_MAP['O'], self.vert_off_slider.value() + 85)

    def getDivisionLabels(self):
        return (
            self.voltbase_labels[self.vert_knob.value()],
            self.timebase_labels[self.horz_knob.value()],
            self.getVertOffset(),
            self.getHorzOffsetDisplay(),
        )

    def getMode(self):
        return self.mode_select.currentText()

    def getHorizontalDiv(self):
        return self._parse_time_label(self.timebase_labels[self.horz_knob.value()])

    def getHorizontalDivFromIndex(self, idx):
        return self._parse_time_label(self.timebase_labels[idx])

    def getVerticalDiv(self):
        return self._parse_voltage_label(self.voltbase_labels[self.vert_knob.value()])

    def getVerticalDivFromIndex(self, idx):
        return self._parse_voltage_label(self.voltbase_labels[idx])

    def getVertOffset(self):
        voltage_mv = self.vert_off_slider.value() * 12.0
        if abs(voltage_mv) >= 1000:
            return f"{voltage_mv / 1000.0:.3f}V"
        sign = "+" if voltage_mv >= 0 else ""
        return f"{sign}{voltage_mv:.0f}mV"

    def getVertOffsetDacSteps(self):
        return self.vert_off_slider.value()

    def getCommittedVertOffsetDacSteps(self):
        return self._committed_vert_offset

    def getVertOffsetValue(self):
        return self.vert_off_slider.value() * 12.0 / 1000.0

    def getHorzOffset(self):
        return self.horz_off_slider.value()

    def getHorzOffsetDisplay(self):
        val = self.horz_off_slider.value()
        if val == 0:
            return "0μs"
        time_per_sample = (10 * self.getHorizontalDiv() * self.TIMEBASE_CAL) / 1000.0
        t = val * time_per_sample
        sign = "+" if t > 0 else "-"
        a = abs(t)
        if a >= 1e-3:
            return f"{sign}{a*1e3:.2f}ms"
        if a >= 1e-6:
            return f"{sign}{a*1e6:.2f}μs"
        return f"{sign}{a:.3e}s"

    def getVoltageMultiplier(self):
        return self.voltage_multiplier

    def getTriggerMode(self):
        text = self.trigger_select.currentText()
        if text == "Rising Edge":
            return 'rising'
        if text == "Falling Edge":
            return 'falling'
        return 'off'

    def getTriggerLevelVolts(self):
        return self._trigger_level_mv / 1000.0
