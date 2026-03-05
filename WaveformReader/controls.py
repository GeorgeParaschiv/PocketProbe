from PyQt5.QtWidgets import QComboBox, QLabel, QSlider, QVBoxLayout, QHBoxLayout, QDial, QPushButton, QCheckBox
from PyQt5.QtCore import Qt, pyqtSignal, QObject

class ControlPanelSignals(QObject):
    value_changed = pyqtSignal(int, int)  # op_code (int), value (int)

class ControlPanel:
    OP_MAP = {
        'V': 1,  # Vertical division
        'T': 2,  # Timebase division
        'O': 3,  # Vertical offset
        'S': 4,  # Sleep/Wake (ADC clock enable)
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
        
        self.autoscale_btn = QPushButton("Autoscale")
        mode_row.addWidget(self.autoscale_btn)
        
        self.layout.addLayout(mode_row)

        # Division values for labels
        self.voltbase_labels = ["10mV", "20mV", "50mV", "100mV", "200mV", "500mV", "1V", "2V", "5V", "10V"]
        self.timebase_labels = ["5μs", "10μs", "20μs", "50μs", "100μs"]

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
        self.horz_knob.setValue(0)
        self.horz_knob.setNotchesVisible(True)

        div_row.addWidget(self.vert_label)
        div_row.addWidget(self.vert_knob)
        div_row.addSpacing(24)
        div_row.addWidget(self.horz_label)
        div_row.addWidget(self.horz_knob)
        self.layout.addLayout(div_row)

        # --- Vertical Offset slider ---
        # DAC range: -85 to +85 steps
        # DAC step size: ~12mV per step
        voffset_row = QHBoxLayout()
        self.vert_off_label = QLabel("Vertical Offset")
        voffset_row.addWidget(self.vert_off_label)
        
        self.vert_off_slider = QSlider(Qt.Horizontal)
        self.vert_off_slider.setMinimum(-85)  # Minimum DAC steps
        self.vert_off_slider.setMaximum(85)   # Maximum DAC steps
        self.vert_off_slider.setValue(0)
        self.vert_off_slider.setTickInterval(1)
        voffset_row.addWidget(self.vert_off_slider)
        
        # Arrow buttons (decrease/increase by 1 DAC step)
        self.vert_off_left_btn = QPushButton("◀")
        self.vert_off_left_btn.setFixedWidth(30)
        self.vert_off_left_btn.clicked.connect(self._on_vert_off_left_clicked)
        voffset_row.addWidget(self.vert_off_left_btn)
        
        self.vert_off_right_btn = QPushButton("▶")
        self.vert_off_right_btn.setFixedWidth(30)
        self.vert_off_right_btn.clicked.connect(self._on_vert_off_right_clicked)
        voffset_row.addWidget(self.vert_off_right_btn)
        
        # --- Zero button for Vertical Offset ---
        self.vert_zero_btn = QPushButton("Zero")
        self.vert_zero_btn.clicked.connect(self._on_vert_zero_clicked)
        voffset_row.addWidget(self.vert_zero_btn)
        
        self.layout.addLayout(voffset_row)

        # --- Horizontal Offset slider (software-only, shifts trigger window) ---
        hoffset_row = QHBoxLayout()
        self.horz_off_label = QLabel("Horizontal Offset")
        self.horz_off_slider = QSlider(Qt.Horizontal)
        self.horz_off_slider.setMinimum(-500)  # Max shift left (samples)
        self.horz_off_slider.setMaximum(500)   # Max shift right (samples)
        self.horz_off_slider.setValue(0)
        self.horz_off_slider.setTickInterval(50)
        hoffset_row.addWidget(self.horz_off_label)
        hoffset_row.addWidget(self.horz_off_slider)

        # --- Arrow buttons for Horizontal Offset ---
        self.horz_left_btn = QPushButton("◀")
        self.horz_left_btn.setFixedWidth(30)
        self.horz_left_btn.clicked.connect(lambda: self.horz_off_slider.setValue(self.horz_off_slider.value() - 1))
        hoffset_row.addWidget(self.horz_left_btn)

        self.horz_right_btn = QPushButton("▶")
        self.horz_right_btn.setFixedWidth(30)
        self.horz_right_btn.clicked.connect(lambda: self.horz_off_slider.setValue(self.horz_off_slider.value() + 1))
        hoffset_row.addWidget(self.horz_right_btn)

        # --- Zero button for Horizontal Offset ---
        self.horz_zero_btn = QPushButton("Zero")
        self.horz_zero_btn.clicked.connect(lambda: self.horz_off_slider.setValue(0))
        hoffset_row.addWidget(self.horz_zero_btn)

        self.layout.addLayout(hoffset_row)

        # --- Trigger mode selector ---
        trigger_row = QHBoxLayout()
        self.trigger_label = QLabel("Trigger:")
        self.trigger_select = QComboBox()
        self.trigger_select.addItems(["Off", "Rising Edge", "Falling Edge"])
        self.trigger_select.setCurrentIndex(1)  # Default to Rising Edge
        trigger_row.addWidget(self.trigger_label)
        trigger_row.addWidget(self.trigger_select)
        self.layout.addLayout(trigger_row)

        # --- Trigger level controls ---
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

        # Trigger level in mV (steps of 50mV)
        self._trigger_level_mv = 0
        self._trigger_level_step_mv = 50

        # Store previous values for change detection
        self._prev_vert_knob = self.vert_knob.value()
        self._prev_horz_knob = self.horz_knob.value()
        self._prev_vert_off = self.vert_off_slider.value()
        
        # Committed offset value (only updated on release, used for signal processing)
        self._committed_vert_offset = self.vert_off_slider.value()
        
        # Hardware gain multiplier - initialized based on default knob value
        self.voltage_multiplier = self._calc_multiplier(self.vert_knob.value())

        # Connect signals for change detection
        self.vert_knob.valueChanged.connect(self._on_vert_knob_changed)
        self.horz_knob.valueChanged.connect(self._on_horz_knob_changed)
        self.vert_off_slider.sliderReleased.connect(self._on_vert_off_released)

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

    def _on_vert_off_left_clicked(self):
        """Decrease vertical offset by 1 DAC step"""
        current_val = self.vert_off_slider.value()
        new_val = max(self.vert_off_slider.minimum(), current_val - 1)
        self.vert_off_slider.setValue(new_val)
        self._on_vert_off_released()

    def _on_vert_off_right_clicked(self):
        """Increase vertical offset by 1 DAC step"""
        current_val = self.vert_off_slider.value()
        new_val = min(self.vert_off_slider.maximum(), current_val + 1)
        self.vert_off_slider.setValue(new_val)
        self._on_vert_off_released()

    def _send_offset_command(self, val):
        """Send offset command to hardware (internal helper function)"""
        self._prev_vert_off = val
        self._committed_vert_offset = val  # Update committed value
        # Encode signed offset as unsigned: add 85 so range becomes 0-170
        # ESP32 will subtract 85 to get the actual signed value
        encoded_val = val + 85
        print(f"Offset: {val} DAC steps ({val * 12.0:.1f}mV), encoded: {encoded_val}")
        self.signals.value_changed.emit(self.OP_MAP['O'], encoded_val)

    def _on_vert_zero_clicked(self):
        """Handle zero button click - always sends zero offset regardless of current value"""
        self.vert_off_slider.setValue(0)
        self._send_offset_command(0)

    def _on_vert_off_released(self):
        """Handle vertical offset slider release (called when slider is released)"""
        val = self.vert_off_slider.value()  # DAC steps (-85 to +85)
        if val != self._prev_vert_off:
            self._send_offset_command(val)

    def on_knob_change(self, callback):
        self.signals.value_changed.connect(callback)

    def send_all_settings(self):
        """Send all current control values to synchronize with hardware on startup"""
        # Send vertical division (voltage gain)
        mv = self._label_to_mv(self.vert_knob.value())
        self.signals.value_changed.emit(self.OP_MAP['V'], mv)
        
        # Send horizontal division (timebase)
        label = self.timebase_labels[self.horz_knob.value()]
        if "μs" in label:
            us = int(float(label.replace("μs", "")))
        else:
            us = int(float(label) * 1000000)
        if us <= 5:
            us = 1
        else:
            us //= 5
        self.signals.value_changed.emit(self.OP_MAP['T'], us)
        
        # Send vertical offset (encoded as unsigned: value + 85)
        encoded_offset = self.vert_off_slider.value() + 85
        self.signals.value_changed.emit(self.OP_MAP['O'], encoded_offset)

    def getDivisionLabels(self):
        return self.voltbase_labels[self.vert_knob.value()], \
               self.timebase_labels[self.horz_knob.value()], \
               self.getVertOffset(), \
               self.getHorzOffsetDisplay()

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
        return self.getVerticalDivFromIndex(idx)

    def getVerticalDivFromIndex(self, idx):
        """Returns vertical div in volts for a given knob index"""
        label = self.voltbase_labels[idx]
        if "mV" in label:
            return float(label.replace("mV", "")) * 1e-3
        elif "V" in label:
            return float(label.replace("V", ""))
        return 1.0

    def getHorizontalDivFromIndex(self, idx):
        """Returns horizontal div in seconds for a given knob index"""
        label = self.timebase_labels[idx]
        if "μs" in label:
            return float(label.replace("μs", "")) * 1e-6
        elif "ms" in label:
            return float(label.replace("ms", "")) * 1e-3
        return 1.0

    def getVertOffset(self):
        """Returns formatted string for display (e.g., '+120mV' or '1.02V')"""
        dac_steps = self.getVertOffsetDacSteps()
        # Convert DAC steps to voltage (12mV per step)
        voltage_mv = dac_steps * 12.0
        if abs(voltage_mv) >= 1000:
            # Show in volts if >= 1V
            return f"{voltage_mv / 1000.0:.3f}V"
        else:
            # Show in millivolts
            sign = "+" if voltage_mv >= 0 else ""
            return f"{sign}{voltage_mv:.0f}mV"
    
    def getVertOffsetDacSteps(self):
        """Returns the raw DAC steps value (-85 to +85)"""
        return self.vert_off_slider.value()
    
    def getCommittedVertOffsetDacSteps(self):
        """Returns the committed DAC steps value (only updated on release)"""
        return self._committed_vert_offset
    
    def getVertOffsetValue(self):
        """Returns numeric voltage offset in volts for calculations"""
        dac_steps = self.getVertOffsetDacSteps()
        # Convert DAC steps to voltage in volts (12mV per step)
        return (dac_steps * 12.0) / 1000.0
    
    def getHorzOffset(self):
        """Returns horizontal offset in sample points (-500 to +500).
        Positive = trigger moves right (more pre-trigger data shown)."""
        return self.horz_off_slider.value()

    def getHorzOffsetDisplay(self):
        """Returns formatted horizontal offset string as a time value"""
        val = self.horz_off_slider.value()
        if val == 0:
            return "0"
        # Time per sample = (10 divs * hDiv * cal_factor) / 1000 samples
        TIMEBASE_CAL = 5.0 / 5.849
        hDiv = self.getHorizontalDiv()  # seconds per division
        time_per_sample = (10 * hDiv * TIMEBASE_CAL) / 1000.0
        time_offset = val * time_per_sample  # seconds
        abs_t = abs(time_offset)
        sign = "+" if time_offset > 0 else "-"
        if abs_t >= 1e-3:
            return f"{sign}{abs_t*1e3:.2f}ms"
        elif abs_t >= 1e-6:
            return f"{sign}{abs_t*1e6:.2f}μs"
        else:
            return f"{sign}{abs_t:.3e}s"

    def getVoltageMultiplier(self):
        """Returns the current hardware gain multiplier"""
        return self.voltage_multiplier

    # --- Trigger methods ---
    def _update_trigger_level_label(self):
        """Update the trigger level display label"""
        mv = self._trigger_level_mv
        if abs(mv) >= 1000:
            self.trigger_level_value_label.setText(f"{mv / 1000.0:.2f}V")
        else:
            sign = "+" if mv > 0 else ""
            self.trigger_level_value_label.setText(f"{sign}{mv}mV")

    def _on_trigger_level_up(self):
        """Increase trigger level by 50mV"""
        self._trigger_level_mv += self._trigger_level_step_mv
        self._update_trigger_level_label()

    def _on_trigger_level_down(self):
        """Decrease trigger level by 50mV"""
        self._trigger_level_mv -= self._trigger_level_step_mv
        self._update_trigger_level_label()

    def _on_trigger_level_zero(self):
        """Reset trigger level to 0mV"""
        self._trigger_level_mv = 0
        self._update_trigger_level_label()

    def getTriggerMode(self):
        """Returns trigger mode: 'off', 'rising', or 'falling'"""
        text = self.trigger_select.currentText()
        if text == "Rising Edge":
            return 'rising'
        elif text == "Falling Edge":
            return 'falling'
        return 'off'

    def getTriggerLevelVolts(self):
        """Returns the trigger level in volts"""
        return self._trigger_level_mv / 1000.0