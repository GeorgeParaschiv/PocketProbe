from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QApplication, QComboBox,
)
from PyQt5.QtCore import QTimer, Qt, QEvent, QPoint
from PyQt5.QtGui import QIcon, QPixmap, QCursor
from struct import pack
import ctypes
import ctypes.wintypes
import os
import sys

from plotter import WaveformPlot
from controls import ControlPanel
from measurement import MeasurementManager, MeasurementPanel
from tcpWaveformReader import TCPWaveformReader, WIFI_OPTIONS

import numpy as np
import time
from scipy.ndimage import median_filter

RESIZE_BORDER = 6


class TitleBar(QWidget):
    BUTTON_STYLE = """
        QPushButton {
            background: transparent; color: #ccc; border: none;
            font-size: 14pt; padding: 0 12px;
        }
        QPushButton:hover { background-color: #555; }
    """
    CLOSE_STYLE = """
        QPushButton {
            background: transparent; color: #ccc; border: none;
            font-size: 14pt; padding: 0 12px;
        }
        QPushButton:hover { background-color: #e81123; color: #fff; }
    """

    def __init__(self, parent, logo_path=None):
        super().__init__(parent)
        self.window = parent
        self.setFixedHeight(36)
        self.setStyleSheet("background-color: #2b2b2b;")
        self._drag_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 0, 0)
        layout.setSpacing(0)

        # ── Centred logo + title ──
        center = QHBoxLayout()
        center.setSpacing(8)
        if logo_path and os.path.exists(logo_path):
            logo_lbl = QLabel()
            logo_lbl.setPixmap(
                QPixmap(logo_path).scaledToHeight(30, Qt.SmoothTransformation)
            )
            center.addWidget(logo_lbl)
        title_lbl = QLabel("PocketProbe")
        title_lbl.setStyleSheet(
            "color: #ddd; font-weight: bold; font-size: 12pt; background: transparent;"
        )
        center.addWidget(title_lbl)

        layout.addStretch(1)
        layout.addLayout(center)
        layout.addStretch(1)

        # ── Window buttons ──
        self._btn_min = QPushButton("—")
        self._btn_max = QPushButton("☐")
        self._btn_close = QPushButton("✕")
        for btn in (self._btn_min, self._btn_max):
            btn.setFixedSize(46, 36)
            btn.setStyleSheet(self.BUTTON_STYLE)
            layout.addWidget(btn)
        self._btn_close.setFixedSize(46, 36)
        self._btn_close.setStyleSheet(self.CLOSE_STYLE)
        layout.addWidget(self._btn_close)

        self._btn_min.clicked.connect(parent.showMinimized)
        self._btn_max.clicked.connect(self._toggleMaximized)
        self._btn_close.clicked.connect(parent.close)

    def _toggleMaximized(self):
        if self.window._is_fake_fullscreen:
            self.window.exitFullscreen()
            return
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()

    # ── Drag to move ──
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.window.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            if self.window.isMaximized():
                self.window.showNormal()
                self._drag_pos = QPoint(self.window.width() // 2, 18)
            self.window.move(event.globalPos() - self._drag_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._toggleMaximized()


class scopeGUI(QMainWindow):

    OFFSET_CAL_POS = (0.0118673, 0.000490511)
    OFFSET_CAL_NEG = (0.0120159, 0.0016188)

    VGA_CAL = {
        1:  (0.0585128, -0.0212),
        2:  (0.116985,  -0.0192182),
        5:  (0.292293,  -0.0135364),
        10: (0.583947,  -0.00406364),
    }

    NOMINAL_HORZ_DIVS = 10
    TIMEBASE_CAL = 5.0 / 5.849
    SETTLE_DURATION = 0.5
    INACTIVITY_TIMEOUT_MS = 300_000

    def __init__(self, frame_size):
        super().__init__()

        self.FRAME_SIZE = frame_size
        self.DISPLAY_SIZE = 1000
        self.AVERAGING = True

        self.setWindowTitle("PocketProbe")
        self.setGeometry(100, 100, 2000, 1400)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self._is_fake_fullscreen = False
        self._saved_geometry = None
        self._saved_maximized = False

        if sys.platform == "win32":
            self._enableSnapStyles()

        logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))

        # Outer widget: title bar on top, app content below
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        outer_layout = QVBoxLayout(self.central_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self._title_bar = TitleBar(self, logo_path)
        outer_layout.addWidget(self._title_bar)

        content = QWidget()
        self.main_layout = QHBoxLayout(content)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(content, stretch=1)

        # --- Left: plot area ---
        plot_area = QWidget()
        plot_layout = QVBoxLayout(plot_area)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.setSpacing(8)

        self.control = ControlPanel()
        self.plot = WaveformPlot(control=self.control)
        plot_layout.addWidget(self.plot, stretch=1)

        lbl_style = (
            "color: #aaa; font-weight: bold; font-size: 12pt;"
            "background: transparent; border: none; padding: 0;"
        )
        box_style = (
            "background-color: #3c3f41; border: 1px solid #555;"
            "border-radius: 4px;"
        )

        def _makeInfoBox(offset_lbl, scale_lbl):
            box = QWidget()
            box.setStyleSheet(box_style)
            lay = QHBoxLayout(box)
            lay.setContentsMargins(8, 4, 8, 4)
            offset_lbl.setStyleSheet(lbl_style)
            scale_lbl.setStyleSheet(lbl_style)
            scale_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lay.addWidget(offset_lbl)
            lay.addStretch(1)
            lay.addWidget(scale_lbl)
            return box

        self.vert_offset_label = QLabel()
        self.vert_scale_label = QLabel()
        vert_box = _makeInfoBox(self.vert_offset_label, self.vert_scale_label)

        self.horz_offset_label = QLabel()
        self.horz_scale_label = QLabel()
        horz_box = _makeInfoBox(self.horz_offset_label, self.horz_scale_label)

        div_labels = QHBoxLayout()
        div_labels.setContentsMargins(0, 0, 0, 0)
        div_labels.setSpacing(16)
        div_labels.addWidget(vert_box, stretch=1)
        div_labels.addWidget(horz_box, stretch=1)
        plot_layout.addLayout(div_labels)

        self.averaging_checkbox = QCheckBox("Averaging")
        self.averaging_checkbox.setChecked(True)
        self.averaging_checkbox.stateChanged.connect(
            lambda state: setattr(self, 'AVERAGING', state == Qt.Checked)
        )
        plot_layout.addWidget(self.averaging_checkbox)

        self.main_layout.addWidget(plot_area, stretch=6)

        # --- Right: controls + measurements ---
        self.measurements = MeasurementManager()
        self.measurement_panel = MeasurementPanel(self.measurements, self.plot)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Connection status row
        conn_row = QHBoxLayout()
        self._conn_status_label = QLabel("Disconnected")
        self._conn_status_label.setAlignment(Qt.AlignCenter)
        self._setConnLabel("Disconnected", "#FF4444")
        conn_row.addWidget(self._conn_status_label, stretch=1)
        self._ssid_combo = QComboBox()
        self._ssid_combo.addItems([opt[0] for opt in WIFI_OPTIONS])
        self._ssid_combo.setStyleSheet(
            "QComboBox { background-color: #3c3f41; color: #ccc; border: 1px solid #555;"
            "border-radius: 4px; padding: 4px 8px; font-size: 11pt; }"
        )
        conn_row.addWidget(self._ssid_combo)
        self._conn_btn = QPushButton("Connect WiFi")
        self._conn_btn.clicked.connect(self._onConnectWifi)
        conn_row.addWidget(self._conn_btn)
        self._disconn_btn = QPushButton("Disconnect")
        self._disconn_btn.clicked.connect(self._onDisconnect)
        self._disconn_btn.setVisible(False)
        conn_row.addWidget(self._disconn_btn)
        right_layout.addLayout(conn_row)

        # Battery indicator
        self.battery_label = QLabel("Battery: --")
        self.battery_label.setStyleSheet(
            "color: #aaa; font-weight: bold; font-size: 11pt; padding: 4px;"
            "background-color: #3c3f41; border-radius: 4px;"
        )
        self.battery_label.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.battery_label)
        self._prev_battery_text = None

        right_layout.addLayout(self.control.layout)
        right_layout.addWidget(self.measurement_panel)
        self.main_layout.addWidget(right_panel, stretch=2)

        # --- Timers & state ---
        self.waveform_reader = TCPWaveformReader(frame_size=self.FRAME_SIZE)
        self._prev_y_display = np.zeros(self.DISPLAY_SIZE)
        self._settle_time = 0.0
        self._prev_connected = False
        self._is_sleeping = False

        self.control.onKnobChange(self.sendKnobPacket)
        self.control.autoscale_btn.clicked.connect(self._onAutoscale)

        self.timer = QTimer()
        self.timer.setInterval(10)
        self.timer.timeout.connect(self.updatePlot)
        self.timer.start()

        self._sync_timer = QTimer()
        self._sync_timer.setInterval(500)
        self._sync_timer.timeout.connect(self._checkAndSyncSettings)
        self._sync_timer.start()

        self._inactivity_timer = QTimer()
        self._inactivity_timer.setSingleShot(True)
        self._inactivity_timer.setInterval(self.INACTIVITY_TIMEOUT_MS)
        self._inactivity_timer.timeout.connect(self._enterSleep)
        self._inactivity_timer.start()

        self._sleep_overlay = QLabel(
            "Low Power Mode\nMove mouse or press any key to wake", self.central_widget
        )
        self._sleep_overlay.setAlignment(Qt.AlignCenter)
        self._sleep_overlay.setStyleSheet(
            "color: #ffffff; font-size: 18pt; font-weight: bold;"
            "background-color: rgba(0, 0, 0, 180); border-radius: 12px; padding: 40px;"
        )
        self._sleep_overlay.setVisible(False)

        QApplication.instance().installEventFilter(self)

    # ── Connection ──────────────────────────────────────────────────────

    def _onConnectWifi(self):
        if self.waveform_reader.wifiConnecting:
            return
        ssid = self._ssid_combo.currentText()
        password = dict(WIFI_OPTIONS).get(ssid, WIFI_OPTIONS[0][1])
        self._conn_btn.setEnabled(False)
        self._ssid_combo.setEnabled(False)
        self._setConnLabel("Connecting...", "#FFAA00")
        self.waveform_reader.connectWifi(ssid=ssid, password=password)

    def _onDisconnect(self):
        self.waveform_reader.userDisconnect()
        self._setConnLabel("Disconnected", "#FF4444")
        self._disconn_btn.setVisible(False)
        self._conn_btn.setVisible(True)
        self._ssid_combo.setVisible(True)

    def _setConnLabel(self, text, color):
        self._conn_status_label.setText(text)
        self._conn_status_label.setStyleSheet(
            f"color: {color}; font-weight: bold; font-size: 11pt; padding: 4px;"
            "background-color: #3c3f41; border-radius: 4px;"
        )

    def _updateConnStatus(self):
        wifi_result = self.waveform_reader.getWifiResult()
        if wifi_result is not None:
            self._conn_btn.setEnabled(True)
            self._ssid_combo.setEnabled(True)
            success, message = wifi_result
            print(message)
            self._setConnLabel(
                "Joining TCP..." if success else message,
                "#FFAA00" if success else "#FF4444",
            )

        if self.waveform_reader.connected:
            self._setConnLabel("Connected", "#44FF44")
            self._conn_btn.setVisible(False)
            self._ssid_combo.setVisible(False)
            self._disconn_btn.setVisible(True)
        elif not self.waveform_reader.wifiConnecting:
            if self._conn_status_label.text() == "Connected":
                self._setConnLabel("Disconnected", "#FF4444")
            self._conn_btn.setVisible(True)
            self._ssid_combo.setVisible(True)
            self._disconn_btn.setVisible(False)

    def _checkAndSyncSettings(self):
        self._updateConnStatus()
        connected = self.waveform_reader.connected
        if connected and not self._prev_connected:
            print("Connected — syncing settings")
            self.control.sendAllSettings()
            if self._is_sleeping:
                self._wakeUp()
        self._prev_connected = connected

    # ── Sleep / wake ────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        etype = event.type()
        if etype in (QEvent.MouseMove, QEvent.MouseButtonPress,
                     QEvent.KeyPress, QEvent.Wheel):
            self._inactivity_timer.start()
            if self._is_sleeping:
                self._wakeUp()
        return super().eventFilter(obj, event)

    def _enterSleep(self):
        if self._is_sleeping:
            return
        self._is_sleeping = True
        print("Entering low power mode")
        self.sendKnobPacket(self.control.OP_MAP['S'], 0)
        self._sleep_overlay.setVisible(True)
        self._sleep_overlay.raise_()
        self._sleep_overlay.setGeometry(self.central_widget.rect())

    def _wakeUp(self):
        if not self._is_sleeping:
            return
        self._is_sleeping = False
        print("Waking up")
        self.sendKnobPacket(self.control.OP_MAP['S'], 1)
        self._sleep_overlay.setVisible(False)
        self.control.sendAllSettings()

    # ── Native Windows hit-testing (snap, edge-resize) ────────────────

    def _enableSnapStyles(self):
        hwnd = int(self.winId())
        GWL_STYLE = -16
        WS_THICKFRAME = 0x00040000
        WS_MAXIMIZEBOX = 0x00010000
        WS_MINIMIZEBOX = 0x00020000
        user32 = ctypes.windll.user32
        style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        style |= WS_THICKFRAME | WS_MAXIMIZEBOX | WS_MINIMIZEBOX
        user32.SetWindowLongW(hwnd, GWL_STYLE, style)

    def nativeEvent(self, event_type, message):
        if sys.platform == "win32" and event_type == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))

            WM_NCCALCSIZE = 0x0083
            if msg.message == WM_NCCALCSIZE:
                return True, 0

            WM_NCHITTEST = 0x0084
            if msg.message == WM_NCHITTEST:
                pos = QCursor.pos()
                geo = self.frameGeometry()
                x, y = pos.x() - geo.x(), pos.y() - geo.y()
                w, h = geo.width(), geo.height()
                b = RESIZE_BORDER

                HTLEFT, HTRIGHT = 10, 11
                HTTOP, HTBOTTOM = 12, 15
                HTTOPLEFT, HTTOPRIGHT = 13, 14
                HTBOTTOMLEFT, HTBOTTOMRIGHT = 16, 17
                HTCAPTION = 2

                if y < b:
                    if x < b:
                        return True, HTTOPLEFT
                    if x > w - b:
                        return True, HTTOPRIGHT
                    return True, HTTOP
                if y > h - b:
                    if x < b:
                        return True, HTBOTTOMLEFT
                    if x > w - b:
                        return True, HTBOTTOMRIGHT
                    return True, HTBOTTOM
                if x < b:
                    return True, HTLEFT
                if x > w - b:
                    return True, HTRIGHT

                # Title bar area → snap/drag, but let button clicks through
                if y < self._title_bar.height():
                    local = self._title_bar.mapFromGlobal(pos)
                    child = self._title_bar.childAt(local)
                    if child is None or isinstance(child, QLabel):
                        return True, HTCAPTION

        return super().nativeEvent(event_type, message)

    # ── Key / resize events ─────────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_F11, Qt.Key_F):
            if self._is_fake_fullscreen:
                self.exitFullscreen()
            else:
                self._enterFullscreen()
        elif event.key() == Qt.Key_Escape and self._is_fake_fullscreen:
            self.exitFullscreen()
        else:
            super().keyPressEvent(event)

    def _enterFullscreen(self):
        self._saved_maximized = self.isMaximized()
        self._saved_geometry = self.normalGeometry()
        self._is_fake_fullscreen = True
        self._title_bar.setVisible(False)
        screen = QApplication.screenAt(self.geometry().center())
        if screen is None:
            screen = QApplication.primaryScreen()
        if self._saved_maximized:
            self.showNormal()
        self.setGeometry(screen.geometry())

    def exitFullscreen(self):
        self._is_fake_fullscreen = False
        self._title_bar.setVisible(True)
        if self._saved_maximized:
            self.setUpdatesEnabled(False)
            self.setGeometry(self._saved_geometry)
            self.showMaximized()
            self.setUpdatesEnabled(True)
        else:
            self.setGeometry(self._saved_geometry)

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            if not self._is_fake_fullscreen:
                self._title_bar.setVisible(True)
        super().changeEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._sleep_overlay.isVisible():
            self._sleep_overlay.setGeometry(self.central_widget.rect())

    # ── Packet sending ──────────────────────────────────────────────────

    def sendKnobPacket(self, op_code, value):
        try:
            pkt = pack('<H', op_code) + pack('<I', value)
            hex_bytes = ' '.join(f'{b:02X}' for b in pkt)
            print(f"Packet: {hex_bytes} | op={op_code} val={value}")
            self.waveform_reader.sendPacket(pkt)
            if op_code in (self.control.OP_MAP['O'], self.control.OP_MAP['V']):
                self._settle_time = time.monotonic()
        except Exception as e:
            print(f"Failed to send packet: {e}")

    # ── Main update loop ────────────────────────────────────────────────

    def updatePlot(self):
        vLabel, hLabel, vOffset, hOffset = self.control.getDivisionLabels()
        self.vert_offset_label.setText(f"Vertical: {vOffset}")
        self.vert_scale_label.setText(vLabel)
        self.horz_offset_label.setText(f"Horizontal: {hOffset}")
        self.horz_scale_label.setText(hLabel)

        if self.control.getMode() == "Stop":
            self.measurement_panel.updateDisplay()
            self._updateBatteryIndicator()
            return

        hDiv = self.control.getHorizontalDiv()
        x_display = np.linspace(
            0, self.NOMINAL_HORZ_DIVS * hDiv * self.TIMEBASE_CAL, self.DISPLAY_SIZE
        )

        new_y = self.waveform_reader.getLatestSamples()
        settling = (time.monotonic() - self._settle_time) < self.SETTLE_DURATION

        if new_y is not None and len(new_y) == self.FRAME_SIZE and not settling:
            y_display = np.array(new_y)

            voltage_gain = self.control.getVoltageMultiplier()
            offset_steps = self.control.getCommittedVertOffsetDacSteps()

            # Step 1: Subtract offset DAC contribution
            if offset_steps > 0:
                offset = self.OFFSET_CAL_POS[0] * offset_steps + self.OFFSET_CAL_POS[1]
            elif offset_steps < 0:
                offset = self.OFFSET_CAL_NEG[0] * offset_steps + self.OFFSET_CAL_NEG[1]
            else:
                offset = 0.0
            y_display -= offset

            # Step 2: Invert per-VGA transfer function
            m, c = self.VGA_CAL[voltage_gain]
            y_display = (y_display - c) / m

            # Step 3: Median filter
            y_display = median_filter(y_display, size=4 if self.AVERAGING else 2)

            # Step 4: Software trigger (2000 → 1000 points)
            y_display = self._applyTrigger(y_display)

            self._prev_y_display = y_display
        else:
            y_display = self._prev_y_display

        self.plot.updateWaveform((x_display, y_display))
        self.measurements.updateData(x_display, y_display)
        self.measurement_panel.updateDisplay()
        self._updateBatteryIndicator()

    # ── Battery ─────────────────────────────────────────────────────────

    def _updateBatteryIndicator(self):
        batt = self.waveform_reader.battery_info
        if batt is None:
            return

        if batt['charging']:
            text, color = "Battery: Charging", "#44FF44"
        else:
            pct = batt['percentage']
            text = f"Battery: {pct}%"
            color = "#44FF44" if pct > 50 else "#FFAA00" if pct > 20 else "#FF4444"

        if text != self._prev_battery_text:
            self._prev_battery_text = text
            self.battery_label.setText(text)
            self.battery_label.setStyleSheet(
                f"color: {color}; font-weight: bold; font-size: 11pt; padding: 4px;"
                "background-color: #3c3f41; border-radius: 4px;"
            )

    # ── Software trigger ────────────────────────────────────────────────

    def _applyTrigger(self, y_data):
        """Extract DISPLAY_SIZE points from FRAME_SIZE-point buffer using trigger."""
        n = len(y_data)
        ds = self.DISPLAY_SIZE
        base = ds // 2
        h_offset = self.control.getHorzOffset()

        def _defaultWindow():
            mid = n // 2
            start = max(0, min(n - ds, mid - base + h_offset))
            return y_data[start:start + ds]

        trigger_mode = self.control.getTriggerMode()
        if trigger_mode == 'off':
            return _defaultWindow()

        pre = max(0, min(ds, base + h_offset))
        post = ds - pre
        search_start = pre
        search_end = n - post

        if search_start >= search_end:
            return _defaultWindow()

        region = y_data[search_start:search_end]
        shifted = region - self.control.getTriggerLevelVolts()

        if trigger_mode == 'rising':
            crossings = np.where((shifted[:-1] < 0) & (shifted[1:] >= 0))[0]
        elif trigger_mode == 'falling':
            crossings = np.where((shifted[:-1] >= 0) & (shifted[1:] < 0))[0]
        else:
            return _defaultWindow()

        if len(crossings) == 0:
            return _defaultWindow()

        idx = crossings[0] + search_start
        result = y_data[idx - pre:idx + post]

        if len(result) != ds:
            return _defaultWindow()
        return result

    # ── Autoscale ───────────────────────────────────────────────────────

    def _onAutoscale(self):
        y = self._prev_y_display
        if y is None or len(y) == 0:
            return

        vmax, vmin = np.max(y), np.min(y)
        vpp = vmax - vmin
        vmean = (vmax + vmin) / 2.0

        # Vertical scale: fit Vpp in ~5 divisions
        best_idx = len(self.control.voltbase_labels) - 1
        for i in range(len(self.control.voltbase_labels)):
            if vpp <= 5.0 * self.control.getVerticalDivFromIndex(i):
                best_idx = i
                break
        self.control.vert_knob.setValue(best_idx)

        # Vertical offset: center signal
        steps = max(-85, min(85, int(round(-vmean / 0.012))))
        self.control.vert_off_slider.setValue(steps)
        self.control.onVertOffReleased()

        # Horizontal scale: show ~2 cycles
        hDiv_current = self.control.getHorizontalDiv()
        x_current = np.linspace(
            0, self.NOMINAL_HORZ_DIVS * hDiv_current * self.TIMEBASE_CAL, len(y)
        )
        freq = self.measurements.estimateFrequency(x_current, y)

        if freq > 0:
            target_hDiv = (2.0 / freq) / 8.0
            best_h = len(self.control.timebase_labels) - 1
            for i in range(len(self.control.timebase_labels)):
                if self.control.getHorizontalDivFromIndex(i) >= target_hDiv:
                    best_h = i
                    break
            self.control.horz_knob.setValue(best_h)
        else:
            idx = self.control.horz_knob.value()
            if idx < len(self.control.timebase_labels) - 1:
                self.control.horz_knob.setValue(idx + 1)

        # Trigger: rising edge at signal mean
        if self.control.trigger_select.currentIndex() == 0:
            self.control.trigger_select.setCurrentIndex(1)
        self.control._trigger_level_mv = int(round(vmean * 1000.0 / 50.0)) * 50
        self.control.updateTriggerLevelLabel()
        self.control.horz_off_slider.setValue(0)

        print("Autoscale complete")
