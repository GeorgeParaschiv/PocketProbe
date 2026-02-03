from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import QTimer, Qt
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

        self.FRAME_SIZE = frame_size
        self.NUM_FRAMES = 1
        self.ATTENUATION = 1
        
        # Signal processing constants
        self.BASE_GAIN = 50/3
        self.BASE_OFFSET = 0.575

        self.setWindowTitle("PocketProbe")
        self.setGeometry(100, 100, 1600, 1000)  # Enlarged window

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

        # Add 1x and 10x buttons below the plot
        self.x_buttons_widget = QWidget()
        x_buttons_layout = QHBoxLayout(self.x_buttons_widget)
        x_buttons_layout.setContentsMargins(0, 0, 0, 0)
        x_buttons_layout.setSpacing(12)

        self.x1_btn = QPushButton("1x")
        self.x10_btn = QPushButton("10x")
        x_buttons_layout.addWidget(self.x1_btn)
        x_buttons_layout.addWidget(self.x10_btn)
        plot_layout.addWidget(self.x_buttons_widget, stretch=0)

        self.x1_btn.clicked.connect(self.set_1x_mode)
        self.x10_btn.clicked.connect(self.set_10x_mode)

        self.main_layout.addWidget(plot_area, stretch=4)
        
        self.measurements = MeasurementManager(self.plot)
        self.measurement_panel = MeasurementPanel(self.measurements)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

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
        self._prev_y_display = np.zeros(self.FRAME_SIZE)
        self.control.on_knob_change(self.send_knob_packet)
        
        # Send default settings once connected
        self._sync_sent = False
        self._sync_timer = QTimer()
        self._sync_timer.setInterval(500)  # Check every 500ms
        self._sync_timer.timeout.connect(self._check_and_send_defaults)
        self._sync_timer.start()

    def _check_and_send_defaults(self):
        """Send default settings once TCP connection is established"""
        if not self._sync_sent and self.waveform_reader._connected:
            print("Sending default settings to synchronize with hardware...")
            self.control.send_all_settings()
            self._sync_sent = True
            self._sync_timer.stop()

    def send_knob_packet(self, op_code, value):
        # op_code: int, value: int
        try:
            pkt = pack('<H', op_code) + pack('<I', value)
            print(f"Packet: {pkt}")
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
            # x_display spans the full visible window (10 divisions)
            hDiv = self.control.getHorizontalDiv()
            x_max = self.plot.NUM_HORZ_DIVS * hDiv  # Full window width in seconds
            x_display = np.linspace(0, x_max, self.FRAME_SIZE)
            # Get y values from waveform reader, keep previous if no new values
            new_y = self.waveform_reader.get_latest_samples()
            
            if new_y is not None and len(new_y) == self.FRAME_SIZE:
                #print("Latest 10 y values:", new_y[:10] if new_y is not None else "No data")
                y_display = np.array(new_y)
                self._prev_y_display = y_display
            else:
                y_display = self._prev_y_display

            voltage_gain = self.control.getVoltageMultiplier()
            voltage_offset = self.control.getVertOffset()
            
            # Step 1: Diff Amp Inverse Function
            y_display = (y_display + 0.0305928) * 1.0142615313929
            
            # Step 2: Subtract Offset Function    
            #y_display = y_display - (-0.0000019283 * voltage_offset**3 + 0.00000195206 * voltage_offset**2 + 0.0127312 * voltage_offset - 0.00123773)
            y_display = y_display - (voltage_offset * 0.0122807 - 0.00108)
            
            # Step 3: Voltage Division and Base Gain
            y_display = y_display * (1 / voltage_gain)
            y_display = y_display * self.BASE_GAIN
            
            # Step 4: Remove outliers using median filtering
            y_display = median_filter(y_display, size=4)
            
            waveform = (x_display, y_display)

            self.plot.update_waveform(waveform)
            self.measurements.update_data(x_display, y_display)
            
        self.measurement_panel.update_display()

    def set_1x_mode(self):
        self.ATTENUATION = 1

    def set_10x_mode(self):
        self.ATTENUATION = 10