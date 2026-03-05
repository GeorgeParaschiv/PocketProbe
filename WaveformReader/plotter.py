import pyqtgraph as pg
import numpy as np
import math

class WaveformPlot(pg.PlotWidget):
    def __init__(self, control=None):
        super().__init__(title="Waveform Display")
        
         # --- Division counts ---
        self.NUM_HORZ_DIVS = 8   # Horizontal divisions
        self.NUM_VERT_DIVS = 8   # Vertical divisions
        
        self.setBackground('#1e1e1e')
        self.plotItem.showGrid(x=True, y=True, alpha=0.3)

        # Fix grid spacing
        self.HMAX = 1
        self.HMIN = 0
        self.plotItem.setLimits(xMin=self.HMIN, xMax=self.HMAX, yMin=-40, yMax=40)

        # Disable zooming and panning
        self.plotItem.setMouseEnabled(x=False, y=False)
        self.plotItem.vb.setMouseEnabled(False, False)

        # Customize axes
        for axis in ['bottom', 'left']:
            ax = self.plotItem.getAxis(axis)
            ax.setPen(pg.mkPen(color='#aaa'))
            ax.setTextPen(pg.mkPen(color='#aaa'))

        # Plot line
        self.plot = self.plotItem.plot(pen=pg.mkPen('yellow', width=1.5))

        # Trigger level indicator — horizontal line across the plot
        self.trigger_line = pg.InfiniteLine(
            pos=0, angle=0,
            pen=pg.mkPen(color='#FF4444', width=1, style=pg.QtCore.Qt.DashLine),
            movable=False
        )
        self.trigger_line.setVisible(False)  # Hidden when trigger is off
        self.plotItem.addItem(self.trigger_line)

        # Trigger level arrow/tick on the left edge
        self.trigger_arrow = pg.ArrowItem(
            angle=0,  # Points right
            tipAngle=30, headLen=10, tailLen=0, tailWidth=0,
            pen=pg.mkPen('#FF4444', width=1),
            brush=pg.mkBrush('#FF4444')
        )
        self.trigger_arrow.setVisible(False)
        self.plotItem.addItem(self.trigger_arrow)

        # Horizontal offset marker — vertical line showing trigger position
        self.horz_offset_line = pg.InfiniteLine(
            pos=0, angle=90,
            pen=pg.mkPen(color='#44AAFF', width=1, style=pg.QtCore.Qt.DashLine),
            movable=False
        )
        self.horz_offset_line.setVisible(False)
        self.plotItem.addItem(self.horz_offset_line)

        # Horizontal offset arrow/tick on the top edge
        self.horz_offset_arrow = pg.ArrowItem(
            angle=-90,  # Points down
            tipAngle=30, headLen=10, tailLen=0, tailWidth=0,
            pen=pg.mkPen('#44AAFF', width=1),
            brush=pg.mkBrush('#44AAFF')
        )
        self.horz_offset_arrow.setVisible(False)
        self.plotItem.addItem(self.horz_offset_arrow)

        # Reference to control panel for knob adjustment
        self.control = control

        # Enable mouse wheel events for axes
        self.plotItem.getAxis('bottom').wheelEvent = self.x_axis_wheel_event
        self.plotItem.getAxis('left').wheelEvent = self.y_axis_wheel_event

    def set_control(self, control):
        self.control = control
        # Re-attach wheel events if needed
        self.plotItem.getAxis('bottom').wheelEvent = self.x_axis_wheel_event
        self.plotItem.getAxis('left').wheelEvent = self.y_axis_wheel_event

    def x_axis_wheel_event(self, event):
        if self.control is None:
            return
        knob = self.control.horz_knob
        delta = event.delta()
        # Less sensitive: only change knob if delta >= 120 or <= -120
        if delta >= 120:
            knob.setValue(min(knob.value() + 1, knob.maximum()))
        elif delta <= -120:
            knob.setValue(max(knob.value() - 1, knob.minimum()))
        event.accept()

    def y_axis_wheel_event(self, event):
        if self.control is None:
            return
        knob = self.control.vert_knob
        delta = event.delta()
        # Less sensitive: only change knob if delta >= 120 or <= -120
        if delta >= 120:
            knob.setValue(min(knob.value() + 1, knob.maximum()))
        elif delta <= -120:
            knob.setValue(max(knob.value() - 1, knob.minimum()))
        event.accept()

    def setTicks(self, x_step, y_step, vOffset=0):
        x_ticks = [(i * x_step, f"{i * x_step:.3g}") for i in range(self.NUM_HORZ_DIVS + 1)]

        # Viewport is shifted by vOffset, so calculate visible y range
        yMin = -y_step * (self.NUM_VERT_DIVS / 2) - vOffset
        yMax = y_step * (self.NUM_VERT_DIVS / 2) - vOffset

        # Generate ticks at fixed multiples of y_step covering the visible range
        # Tick positions stay in data space — they don't shift
        first_idx = math.floor(yMin / y_step) if y_step != 0 else 0
        last_idx = math.ceil(yMax / y_step) if y_step != 0 else 0

        y_ticks = []
        for i in range(first_idx, last_idx + 1):
            val = round(i * y_step, 10)
            y_ticks.append((val, f"{val:.3g}"))

        self.plotItem.getAxis('bottom').setTicks([x_ticks])
        self.plotItem.getAxis('left').setTicks([y_ticks])

    def setPlotRange(self, vDiv, hDiv, vOffset=0):
        # Shift the viewport by vOffset — grid physically moves
        yMin = round(-vDiv * (self.NUM_VERT_DIVS/2) - vOffset, 6)
        yMax = round(vDiv * (self.NUM_VERT_DIVS/2) - vOffset, 6)
        self.plotItem.setRange(
            xRange=(0, self.NUM_HORZ_DIVS * hDiv),
            yRange=(yMin, yMax)
        )

    def update_waveform(self, waveform):
        # Get division sizes from ControlPanel properties
        hDiv = self.control.getHorizontalDiv()
        vDiv = self.control.getVerticalDiv()
        vOffset = self.control.getVertOffsetValue()  # Get numeric value in volts
        
        # Set axis ticks and range (y-axis shifted by offset)
        self.setPlotRange(vDiv, hDiv, vOffset)
        self.setTicks(hDiv, vDiv, vOffset)
        
        # Update trigger level indicator
        trigger_mode = self.control.getTriggerMode()
        if trigger_mode != 'off':
            trigger_level = self.control.getTriggerLevelVolts()
            self.trigger_line.setValue(trigger_level)
            self.trigger_line.setVisible(True)
            # Position arrow at left edge of plot at trigger level
            self.trigger_arrow.setPos(0, trigger_level)
            self.trigger_arrow.setVisible(True)
        else:
            self.trigger_line.setVisible(False)
            self.trigger_arrow.setVisible(False)
        
        # Update horizontal offset marker (shows where trigger point is on screen)
        h_offset = self.control.getHorzOffset()
        if h_offset != 0 and trigger_mode != 'off':
            # Use actual waveform x-range for accurate marker placement
            x_data_max = waveform[0][-1] if len(waveform[0]) > 0 else self.NUM_HORZ_DIVS * hDiv
            trigger_x = x_data_max * (500 + h_offset) / 1000.0
            self.horz_offset_line.setValue(trigger_x)
            self.horz_offset_line.setVisible(True)
            # Position arrow at top of visible y range
            yMax = vDiv * (self.NUM_VERT_DIVS / 2) - vOffset
            self.horz_offset_arrow.setPos(trigger_x, yMax)
            self.horz_offset_arrow.setVisible(True)
        else:
            self.horz_offset_line.setVisible(False)
            self.horz_offset_arrow.setVisible(False)
        
        self.plot.setData(waveform[0], waveform[1])

