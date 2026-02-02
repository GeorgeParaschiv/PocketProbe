from PyQt5.QtWidgets import QComboBox, QLabel, QSlider, QVBoxLayout, QHBoxLayout, QDial, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal, QObject

class ControlPanelSignals(QObject):
    value_changed = pyqtSignal(int, int)  # op_code (int), value (int)

class ControlPanel:
    OP_MAP = {
        'V': 1,  # Vertical division
        'T': 2,  # Timebase division
        'O': 3,  # Vertical offset
        'H': 4,  # Horizontal offset
    }

    def __init__(self):
        self.layout = QVBoxLayout()  # Use vertical layout for main panel
        self.signals = ControlPanelSignals()

        # --- Mode selector ---
        mode_row = QHBoxLayout()
        self.mode_label = QLabel("Mode:")
        self.mode_select = QComboBox()
        self.mode_select.addItems(["Run", "Stop"])
        mode_row.addWidget(self.mode_label)
        mode_row.addWidget(self.mode_select)
        self.layout.addLayout(mode_row)

        # Division values for labels
        self.voltbase_labels = ["10mV", "20mV", "50mV", "100mV", "200mV", "500mV", "1V", "2V", "5V", "10V"]
        self.timebase_labels = ["1μs", "2μs", "5μs", "10μs", "20μs", "50μs", "100μs", "200μs"]

        # --- Division knobs row ---
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
        self.horz_knob.setValue(2)
        self.horz_knob.setNotchesVisible(True)

        div_row.addWidget(self.vert_label)
        div_row.addWidget(self.vert_knob)
        div_row.addSpacing(24)
        div_row.addWidget(self.horz_label)
        div_row.addWidget(self.horz_knob)
        self.layout.addLayout(div_row)

        # --- Vertical Offset slider ---
        voffset_row = QHBoxLayout()
        self.vert_off_label = QLabel("Vertical Offset")
        self.vert_off_slider = QSlider(Qt.Horizontal)
        self.vert_off_slider.setMinimum(-40)
        self.vert_off_slider.setMaximum(40)
        self.vert_off_slider.setValue(0)
        self.vert_off_slider.setTickInterval(1)
        voffset_row.addWidget(self.vert_off_label)
        voffset_row.addWidget(self.vert_off_slider)
        self.layout.addLayout(voffset_row)
        
        # --- Zero button for Vertical Offset ---
        self.vert_zero_btn = QPushButton("Zero")
        self.vert_zero_btn.clicked.connect(lambda: (self.vert_off_slider.setValue(0), self._on_vert_off_released()))
        voffset_row.addWidget(self.vert_zero_btn)

        # --- Horizontal Offset slider ---
        hoffset_row = QHBoxLayout()
        self.horz_off_label = QLabel("Horizontal Offset")
        self.horz_off_slider = QSlider(Qt.Horizontal)
        self.horz_off_slider.setMinimum(-1)
        self.horz_off_slider.setMaximum(1)
        self.horz_off_slider.setValue(0)
        hoffset_row.addWidget(self.horz_off_label)
        hoffset_row.addWidget(self.horz_off_slider)
        self.layout.addLayout(hoffset_row)

        # --- Zero button for Horizontal Offset ---
        self.horz_zero_btn = QPushButton("Zero")
        self.horz_zero_btn.clicked.connect(lambda: (self.horz_off_slider.setValue(0), self._on_horz_off_released()))
        hoffset_row.addWidget(self.horz_zero_btn)

        # Store previous values for change detection
        self._prev_vert_knob = self.vert_knob.value()
        self._prev_horz_knob = self.horz_knob.value()
        self._prev_vert_off = self.vert_off_slider.value()
        self._prev_horz_off = self.horz_off_slider.value()
        
        # Hardware gain multiplier - initialized based on default knob value
        self.voltage_multiplier = self._calc_multiplier(self.vert_knob.value())

        # Connect signals for change detection
        self.vert_knob.valueChanged.connect(self._on_vert_knob_changed)
        self.horz_knob.valueChanged.connect(self._on_horz_knob_changed)
        self.vert_off_slider.sliderReleased.connect(self._on_vert_off_released)
        self.horz_off_slider.sliderReleased.connect(self._on_horz_off_released)

    def _label_to_mv(self, val):
        """Convert knob index to millivolts"""
        label = self.voltbase_labels[val]
        if "mV" in label:
            return int(float(label.replace("mV", "")))
        elif "V" in label:
            return int(float(label.replace("V", "")) * 1000)
        else:
            return int(float(label) * 1000)

    def _calc_multiplier(self, val):
        """Calculate hardware gain multiplier based on knob position (matches STM32 thresholds)"""
        mv = self._label_to_mv(val)
        if mv <= 100:
            return 10
        elif mv <= 500:
            return 5
        elif mv <= 2000:
            return 2
        else:
            return 1

    def _on_vert_knob_changed(self, val):
        if val != self._prev_vert_knob:
            self._prev_vert_knob = val
            
            # Update the voltage multiplier
            self.voltage_multiplier = self._calc_multiplier(val)
            
            # Send value in mV to STM32
            mv = self._label_to_mv(val)
            self.signals.value_changed.emit(self.OP_MAP['V'], mv)

    def _on_horz_knob_changed(self, val):
        if val != self._prev_horz_knob:
            self._prev_horz_knob = val
            # Send value in us
            label = self.timebase_labels[val]
            if "μs" in label:
                us = int(float(label.replace("μs", "")))
            else:
                us = int(float(label) * 1000000)

            if (us <= 5):
                us = 1
            else:
                us //= 5
             
            self.signals.value_changed.emit(self.OP_MAP['T'], us)

    def _on_vert_off_released(self):
        val = self.getVertOffset()
        if val != self._prev_vert_off:
            self._prev_vert_off = val
            print(int(val*1000 + 4000))
            self.signals.value_changed.emit(self.OP_MAP['O'], int(val * 1000 + 4000))

    def _on_horz_off_released(self):
        val = self.horz_off_slider.value()
        if val != self._prev_horz_off:
            self._prev_horz_off = val
            self.signals.value_changed.emit(self.OP_MAP['H'], val)

    def on_knob_change(self, callback):
        self.signals.value_changed.connect(callback)

    def getDivisionLabels(self):
        return self.voltbase_labels[self.vert_knob.value()], \
               self.timebase_labels[self.horz_knob.value()], \
               self.getVertOffset(), \
               self.getHorzOffset()

    def getMode(self):
        return self.mode_select.currentText()

    def getHorizontalDiv(self):
        # Returns the numeric value in seconds for the selected timebase division
        idx = self.horz_knob.value()
        label = self.timebase_labels[idx]
        # Convert label to seconds
        if "μs" in label:
            return float(label.replace("μs", "")) * 1e-6
        elif "ms" in label:
            return float(label.replace("ms", "")) * 1e-3
        else:
            return 1.0  # fallback

    def getVerticalDiv(self):
        # Returns the numeric value in volts for the selected voltbase division
        idx = self.vert_knob.value()
        label = self.voltbase_labels[idx]
        # Convert label to volts
        if "mV" in label:
            return float(label.replace("mV", "")) * 1e-3
        elif "V" in label:
            return float(label.replace("V", ""))
        else:
            return 1.0  # fallback

    def getVertOffset(self):
        
        offset = self.vert_off_slider.value() * self.getVerticalDiv() / 10
        
        if offset > 4:
            return 4
        elif offset < -4:
            return -4
        else:
            return offset
    
    def getHorzOffset(self):
        return self.horz_off_slider.value()

    def getVoltageMultiplier(self):
        """Returns the current hardware gain multiplier"""
        return self.voltage_multiplier