from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import QTimer, Qt
from struct import pack

from plotter import WaveformPlot
from controls import ControlPanel
from measurement import MeasurementManager, MeasurementPanel
from tcpWaveformReader import TCPWaveformReader

import numpy as np
from scipy.ndimage import gaussian_filter1d

class scopeGUI(QMainWindow):
    def __init__(self, frame_size):        
        super().__init__()

        self.FRAME_SIZE = frame_size
        self.NUM_FRAMES = 1
        self.VOLTAGE_DIVIDE = 2
        self.ATTENUATION = 1

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
            # x_display is always FRAME_SIZE points from 0 to 1
            x_display = np.linspace(0, 0.00005 * self.NUM_FRAMES, self.FRAME_SIZE)
            # Get y values from waveform reader, keep previous if no new values
            new_y = self.waveform_reader.get_latest_samples()
            
            if new_y is not None and len(new_y) == self.FRAME_SIZE:
                #print("Latest 10 y values:", new_y[:10] if new_y is not None else "No data")
                y_display = np.array(new_y)
                self._prev_y_display = y_display
            else:
                y_display = self._prev_y_display

            y_display = (y_display / self.VOLTAGE_DIVIDE) / self.ATTENUATION
            
            # Remove outliers using median filtering, then smooth with Gaussian filter
            y_display = np.clip(y_display, np.percentile(y_display, 1), np.percentile(y_display, 99))
            #y_display = gaussian_filter1d(y_display, sigma=2)
            
            waveform = (x_display, y_display)

            self.plot.update_waveform(waveform)
            self.measurements.update_data(x_display, y_display)
            
        self.measurement_panel.update_display()

    def set_1x_mode(self):
        self.ATTENUATION = 1

    def set_10x_mode(self):
        self.ATTENUATION = 10
            # Remove outliers using median filtering, then smooth with Gaussian filter
            y_display = np.clip(y_display, np.percentile(y_display, 1), np.percentile(y_display, 99))
            #y_display = gaussian_filter1d(y_display, sigma=2)
            
            waveform = (x_display, y_display)

            self.plot.update_waveform(waveform)
            self.measurements.update_data(x_display, y_display)
            
        self.measurement_panel.update_display()

    def set_1x_mode(self):
        self.ATTENUATION = 1

    def set_10x_mode(self):
        self.ATTENUATION = 10

