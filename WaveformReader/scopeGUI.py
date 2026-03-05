from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QApplication
from PyQt5.QtCore import QTimer, Qt, QEvent
from struct import pack

from plotter import WaveformPlot
from controls import ControlPanel
from measurement import MeasurementManager, MeasurementPanel
from tcpWaveformReader import TCPWaveformReader

import numpy as np
from scipy.ndimage import median_filter

class scopeGUI(QMainWindow):
    def __init__(self, frame_size):        
        super().__init__()

        self.FRAME_SIZE = frame_size       # 2000 (receive size from hardware)
        self.DISPLAY_SIZE = 1000           # Always display 1000 points after trigger
        self.NUM_FRAMES = 1
        self.AVERAGING = True  # Toggle state for averaging
        
        # Signal processing constants
        self.BASE_GAIN = 50/3
        self.BASE_OFFSET = 0.575
        
        # Timebase calibration: corrects x-axis to match true sample rate
        # Hardware samples for a nominal 10-division window; cal = true_period / displayed_period
        self.NOMINAL_HORZ_DIVS = 10  # Original design: 10 divisions worth of samples
        self.TIMEBASE_CAL = 5.0 / 5.849  # Measured with 200kHz reference at 5μs/div

        self.setWindowTitle("PocketProbe")
        self.setGeometry(100, 100, 2000, 1400)  # Enlarged window

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_layout = QHBoxLayout(self.central_widget)

        plot_area = QWidget()
        plot_layout = QVBoxLayout(plot_area)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.setSpacing(8)

        self.control = ControlPanel()
        
        self.plot = WaveformPlot(control=self.control)  # Pass control panel
        plot_layout.addWidget(self.plot, stretch=1)

        # Division size labels below the plot
        self.div_labels_widget = QWidget()
        div_labels_layout = QHBoxLayout(self.div_labels_widget)
        div_labels_layout.setContentsMargins(0, 0, 0, 0)
        div_labels_layout.setSpacing(32)

        self.vert_div_label = QLabel()
        self.horz_div_label = QLabel()
        self.vert_div_label.setStyleSheet("color: #aaa; font-weight: bold; font-size: 12pt;")
        self.horz_div_label.setStyleSheet("color: #aaa; font-weight: bold; font-size: 12pt;")
        self.vert_div_label.setTextFormat(Qt.RichText)
        self.horz_div_label.setTextFormat(Qt.RichText)
        div_labels_layout.addWidget(self.vert_div_label)
        div_labels_layout.addWidget(self.horz_div_label)
        plot_layout.addWidget(self.div_labels_widget, stretch=0)

        # Add averaging toggle below the plot
        self.averaging_widget = QWidget()
        averaging_layout = QHBoxLayout(self.averaging_widget)
        averaging_layout.setContentsMargins(0, 0, 0, 0)
        averaging_layout.setSpacing(12)

        self.averaging_checkbox = QCheckBox("Averaging")
        self.averaging_checkbox.setChecked(True)
        self.averaging_checkbox.stateChanged.connect(self._on_averaging_changed)
        averaging_layout.addWidget(self.averaging_checkbox)
        averaging_layout.addStretch()  # Push checkbox to the left
        plot_layout.addWidget(self.averaging_widget, stretch=0)

        self.main_layout.addWidget(plot_area, stretch=6)
        
        self.measurements = MeasurementManager(self.plot)
        self.measurement_panel = MeasurementPanel(self.measurements)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Battery indicator at the top of the control panel
        self.battery_label = QLabel("Battery: --")
        self.battery_label.setStyleSheet(
            "color: #aaa; font-weight: bold; font-size: 11pt; padding: 4px;"
            "background-color: #3c3f41; border-radius: 4px;"
        )
        self.battery_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.battery_label)
        self._prev_battery_text = None

        # Top: control sliders
        right_layout.addLayout(self.control.layout)

        # Bottom: cursor and measurement panels side by side
        bottom_split = QHBoxLayout()
        bottom_split.addWidget(self.measurement_panel)

        right_layout.addLayout(bottom_split)
        self.main_layout.addWidget(right_panel, stretch=2)

        # Timer for periodic updates
        self.timer = QTimer()
        self.timer.setInterval(10)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()

        # Use generic waveform reader (could be serial or TCP)
        self.waveform_reader = TCPWaveformReader(frame_size=self.FRAME_SIZE)
        self._prev_y_display = np.zeros(self.DISPLAY_SIZE)  # Display size after trigger
        self.control.on_knob_change(self.send_knob_packet)
        self.control.autoscale_btn.clicked.connect(self._on_autoscale)
        
        # Track connection state and resend settings on connect/reconnect
        self._prev_connected = False
        self._sync_timer = QTimer()
        self._sync_timer.setInterval(500)  # Check every 500ms
        self._sync_timer.timeout.connect(self._check_and_sync_settings)
        self._sync_timer.start()

        # --- Low-power / inactivity timer ---
        self.INACTIVITY_TIMEOUT_MS = 300000
        self._is_sleeping = False

        self._inactivity_timer = QTimer()
        self._inactivity_timer.setSingleShot(True)
        self._inactivity_timer.setInterval(self.INACTIVITY_TIMEOUT_MS)
        self._inactivity_timer.timeout.connect(self._enter_sleep)
        self._inactivity_timer.start()

        # Sleep overlay label (hidden initially)
        self._sleep_overlay = QLabel("Low Power Mode\nMove mouse or press any key to wake", self.central_widget)
        self._sleep_overlay.setAlignment(Qt.AlignCenter)
        self._sleep_overlay.setStyleSheet(
            "color: #ffffff; font-size: 18pt; font-weight: bold;"
            "background-color: rgba(0, 0, 0, 180); border-radius: 12px; padding: 40px;"
        )
        self._sleep_overlay.setVisible(False)

        # Install application-wide event filter for activity tracking
        QApplication.instance().installEventFilter(self)

    def _check_and_sync_settings(self):
        """Send current settings when TCP connection is established or re-established"""
        current_connected = self.waveform_reader._connected
        
        # Detect connection or reconnection (transition from False to True)
        if current_connected and not self._prev_connected:
            print("Connection established. Sending current settings to synchronize with hardware...")
            self.control.send_all_settings()
            # If we were sleeping, wake up the hardware too
            if self._is_sleeping:
                self._wake_up()
        
        self._prev_connected = current_connected

    # --- Low-power mode ---
    def eventFilter(self, obj, event):
        """Application-wide event filter to detect user activity"""
        etype = event.type()
        if etype in (QEvent.MouseMove, QEvent.MouseButtonPress,
                     QEvent.KeyPress, QEvent.Wheel):
            # User activity detected — reset inactivity timer
            self._inactivity_timer.start()  # restart the single-shot timer
            if self._is_sleeping:
                self._wake_up()
        return super().eventFilter(obj, event)

    def _enter_sleep(self):
        """Enter low-power mode after inactivity timeout"""
        if self._is_sleeping:
            return
        self._is_sleeping = True
        print("Entering low power mode — ADC clock disabled")
        self.send_knob_packet(self.control.OP_MAP['S'], 0)

        # Show overlay
        self._sleep_overlay.setVisible(True)
        self._sleep_overlay.raise_()
        self._resize_sleep_overlay()

    def _wake_up(self):
        """Wake from low-power mode on user activity"""
        if not self._is_sleeping:
            return
        self._is_sleeping = False
        print("Waking up — ADC clock enabled")
        self.send_knob_packet(self.control.OP_MAP['S'], 1)

        # Hide overlay
        self._sleep_overlay.setVisible(False)

        # Resend all settings to ensure hardware is synchronized
        self.control.send_all_settings()

    def _resize_sleep_overlay(self):
        """Center the sleep overlay over the plot area"""
        self._sleep_overlay.setGeometry(self.central_widget.rect())

    def resizeEvent(self, event):
        """Keep sleep overlay sized correctly on window resize"""
        super().resizeEvent(event)
        if self._sleep_overlay.isVisible():
            self._resize_sleep_overlay()

    def _format_packet_info(self, op_code, value):
        """Format packet information for human-readable logging"""
        op_names = {
            1: "Vertical Division",
            2: "Timebase",
            3: "Vertical Offset",
            4: "Sleep/Wake",
        }
        
        op_name = op_names.get(op_code, f"Unknown (op_code={op_code})")
        
        if op_code == 1:  # Vertical division
            if value >= 1000:
                formatted_value = f"{value / 1000:.1f}V"
            else:
                formatted_value = f"{value}mV"
            return f"[{op_name}] Setting voltage scale to {formatted_value}"
            
        elif op_code == 2:  # Timebase
            if value < 1000:
                formatted_value = f"{value}μs"
            elif value < 1000000:
                formatted_value = f"{value / 1000:.1f}ms"
            else:
                formatted_value = f"{value / 1000000:.3f}s"
            return f"[{op_name}] Setting timebase to {formatted_value}"
            
        elif op_code == 3:  # Vertical offset
            dac_steps = value - 85
            offset_volts = dac_steps * 0.012
            if offset_volts >= 0:
                formatted_value = f"+{dac_steps} DAC steps (+{offset_volts*1000:.1f}mV)"
            else:
                formatted_value = f"{dac_steps} DAC steps ({offset_volts*1000:.1f}mV)"
            return f"[{op_name}] Setting offset to {formatted_value}"
            
        elif op_code == 4:  # Sleep/Wake
            state = "Wake (ADC clock ON)" if value else "Sleep (ADC clock OFF)"
            return f"[{op_name}] {state}"
            
        else:
            return f"[{op_name}] Raw value: {value}"

    def send_knob_packet(self, op_code, value):
        # op_code: int, value: int
        try:
            pkt = pack('<H', op_code) + pack('<I', value)
            # Format packet as hex bytes without \x prefix
            hex_bytes = ' '.join(f'{b:02X}' for b in pkt)
            print(f"Packet: {hex_bytes} | {self._format_packet_info(op_code, value)}")
            self.waveform_reader.send_packet(pkt)
        except Exception as e:
            print(f"Failed to send packet: {e}")

    def update_plot(self):
        #First update the division labels
        vLabel, hLabel, vOffset, hOffset = self.control.getDivisionLabels()

        vText = f"""
        <div align="left">Vertical: {vLabel}</div>
        <div align="right">{vOffset}</div>
        """

        hText = f"""
        <div align="left">Horizontal: {hLabel}</div>
        <div align="right">{hOffset}</div>
        """

        self.vert_div_label.setText(vText)
        self.horz_div_label.setText(hText)

        if self.control.getMode() != "Stop":
            # x_display: calibrated time span of 1000 samples (fills ~8 grid divisions)
            hDiv = self.control.getHorizontalDiv()
            x_cal_max = self.NOMINAL_HORZ_DIVS * hDiv * self.TIMEBASE_CAL
            x_display = np.linspace(0, x_cal_max, self.DISPLAY_SIZE)

            # Get y values from waveform reader (2000 points), keep previous if no new values
            new_y = self.waveform_reader.get_latest_samples()
            
            if new_y is not None and len(new_y) == self.FRAME_SIZE:
                y_display = np.array(new_y)

                voltage_gain = self.control.getVoltageMultiplier()
                voltage_offset_steps = self.control.getCommittedVertOffsetDacSteps()
                
                # Step 1: Diff Amp Inverse Function (all 2000 points)
                y_display = y_display * 1.01204 + 0.0416623
                
                # Step 2: Subtract Offset Function (all 2000 points)
                if voltage_offset_steps > 0:
                    offset = voltage_offset_steps * 0.0119877 + 0.00247083
                else:
                    offset = -voltage_offset_steps * -0.0121568 + 0.0014475  
                    
                y_display = y_display - offset
                
                # Step 3: Voltage Division and Base Gain (all 2000 points)
                y_display = y_display * (1 / voltage_gain)
                y_display = y_display * self.BASE_GAIN
                
                y_display = (y_display - 0.316584) / 0.986886
                
                # Step 4: Remove outliers using median filtering (all 2000 points)
                filter_size = 4 if self.AVERAGING else 2
                y_display = median_filter(y_display, size=filter_size)
                
                # Step 5: Software trigger — extract 1000 points from 2000
                y_display = self._apply_trigger(y_display)
                
                self._prev_y_display = y_display
            else:
                y_display = self._prev_y_display

            waveform = (x_display, y_display)

            self.plot.update_waveform(waveform)
            self.measurements.update_data(x_display, y_display)
            
        self.measurement_panel.update_display()

        # Update battery indicator
        batt = self.waveform_reader.battery_info
        if batt is not None:
            if batt['charging']:
                display_text = "Battery: Charging"
                batt_color = "#44FF44"
            else:
                pct = batt['percentage']
                display_text = f"Battery: {pct}%"
                if pct > 50:
                    batt_color = "#44FF44"   # Green
                elif pct > 20:
                    batt_color = "#FFAA00"   # Orange
                else:
                    batt_color = "#FF4444"   # Red

            if display_text != self._prev_battery_text:
                self._prev_battery_text = display_text
                self.battery_label.setText(display_text)
                self.battery_label.setStyleSheet(
                    f"color: {batt_color}; font-weight: bold; font-size: 11pt; padding: 4px;"
                    "background-color: #3c3f41; border-radius: 4px;"
                )

    def _apply_trigger(self, y_data):
        """Apply software trigger to 2000-point frame.
        Horizontal offset shifts the pre/post split around the trigger point.
        Returns 1000 points, or middle 1000 if trigger is off or not found."""
        trigger_mode = self.control.getTriggerMode()
        trigger_level = self.control.getTriggerLevelVolts()
        h_offset = self.control.getHorzOffset()  # -500 to +500 sample points
        
        # Adjust pre/post split based on horizontal offset
        # Positive offset = more pre-trigger (trigger moves right on screen)
        # Negative offset = more post-trigger (trigger moves left on screen)
        base = self.DISPLAY_SIZE // 2  # 500
        pre = max(0, min(self.DISPLAY_SIZE, base + h_offset))
        post = self.DISPLAY_SIZE - pre
        
        if trigger_mode == 'off':
            # No trigger — return 1000 points shifted by horizontal offset
            mid = len(y_data) // 2
            start = max(0, min(len(y_data) - self.DISPLAY_SIZE, mid - base + h_offset))
            return y_data[start : start + self.DISPLAY_SIZE]
        
        # Search region: must have 'pre' points before and 'post' points after
        search_start = pre
        search_end = len(y_data) - post
        
        if search_start >= search_end:
            mid = len(y_data) // 2
            return y_data[mid - base : mid + base]
        
        region = y_data[search_start:search_end]
        
        # Shift data by trigger level so we detect crossings at the trigger level
        shifted = region - trigger_level
        
        # Find zero crossings in the shifted region
        if trigger_mode == 'rising':
            crossings = np.where((shifted[:-1] < 0) & (shifted[1:] >= 0))[0]
        elif trigger_mode == 'falling':
            crossings = np.where((shifted[:-1] >= 0) & (shifted[1:] < 0))[0]
        else:
            mid = len(y_data) // 2
            return y_data[mid - base : mid + base]
        
        if len(crossings) == 0:
            # No trigger found — return middle 1000 points
            mid = len(y_data) // 2
            return y_data[mid - base : mid + base]
        
        # Use the first valid crossing
        trigger_idx = crossings[0] + search_start
        
        # Extract 1000-point window: pre points before trigger, post points after
        return y_data[trigger_idx - pre : trigger_idx + post]

    def _on_autoscale(self):
        """Autoscale: analyze current waveform and set optimal V/div, timebase, trigger, and offset"""
        y = self._prev_y_display
        if y is None or len(y) == 0:
            print("Autoscale: no waveform data")
            return

        vmax = np.max(y)
        vmin = np.min(y)
        vpp = vmax - vmin
        vmean = (vmax + vmin) / 2.0

        print(f"Autoscale: Vpp={vpp:.4f}V, Vmax={vmax:.4f}V, Vmin={vmin:.4f}V, Vmean={vmean:.4f}V")

        # --- 1. Vertical scale: fit Vpp in ~5 divisions (2.5 above/below center) ---
        target_divs = 5.0
        best_vert_idx = len(self.control.voltbase_labels) - 1  # default to largest
        for idx in range(len(self.control.voltbase_labels)):
            vDiv = self.control.getVerticalDivFromIndex(idx)
            if vpp <= target_divs * vDiv:
                best_vert_idx = idx
                break

        self.control.vert_knob.setValue(best_vert_idx)
        print(f"Autoscale: V/div → {self.control.voltbase_labels[best_vert_idx]}")

        # --- 2. Vertical offset: center signal on screen ---
        # View center = -vOffset, signal mean = vmean
        # To center: need view center at vmean → vOffset = -vmean
        # dac_steps = vOffset / 0.012 = -vmean / 0.012
        center_steps = int(round(-vmean / 0.012))
        center_steps = max(-85, min(85, center_steps))
        self.control.vert_off_slider.setValue(center_steps)
        self.control._on_vert_off_released()
        print(f"Autoscale: Vertical offset → {center_steps} DAC steps ({center_steps * 12}mV)")

        # --- 3. Horizontal scale: show ~2 cycles ---
        hDiv_current = self.control.getHorizontalDiv()
        x_current = np.linspace(0, self.NOMINAL_HORZ_DIVS * hDiv_current * self.TIMEBASE_CAL, len(y))
        freq = self.measurements._estimate_frequency(x_current, y)

        if freq > 0:
            period = 1.0 / freq
            # Want ~2 cycles across 8 divisions
            target_hDiv = (2.0 * period) / 8.0

            best_horz_idx = len(self.control.timebase_labels) - 1
            for idx in range(len(self.control.timebase_labels)):
                hDiv = self.control.getHorizontalDivFromIndex(idx)
                if hDiv >= target_hDiv:
                    best_horz_idx = idx
                    break

            self.control.horz_knob.setValue(best_horz_idx)
            print(f"Autoscale: Freq={freq:.1f}Hz, T/div → {self.control.timebase_labels[best_horz_idx]}")
        else:
            # No frequency detected — try next higher timebase until we find one or max out
            current_idx = self.control.horz_knob.value()
            max_idx = len(self.control.timebase_labels) - 1
            if current_idx < max_idx:
                self.control.horz_knob.setValue(current_idx + 1)
                print(f"Autoscale: No frequency detected, trying next timebase → {self.control.timebase_labels[current_idx + 1]}")
            else:
                print("Autoscale: No frequency detected, already at max timebase")

        # --- 4. Trigger: rising edge at 50% of signal amplitude ---
        if self.control.trigger_select.currentIndex() == 0:  # "Off"
            self.control.trigger_select.setCurrentIndex(1)    # "Rising Edge"

        trigger_mv = int(round(vmean * 1000.0 / 50.0)) * 50  # Round to nearest 50mV
        self.control._trigger_level_mv = trigger_mv
        self.control._update_trigger_level_label()
        print(f"Autoscale: Trigger level → {trigger_mv}mV")

        # --- 5. Zero horizontal offset ---
        self.control.horz_off_slider.setValue(0)

        print("Autoscale complete")

    def _on_averaging_changed(self, state):
        """Handle averaging checkbox state change"""
        self.AVERAGING = (state == Qt.Checked)