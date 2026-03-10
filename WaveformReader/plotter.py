import pyqtgraph as pg
import math


class WaveformPlot(pg.PlotWidget):
    NUM_HORZ_DIVS = 8
    NUM_VERT_DIVS = 8

    def __init__(self, control):
        super().__init__(title="Waveform Display")
        self.control = control

        self.setBackground('#1e1e1e')
        self.plotItem.showGrid(x=True, y=True, alpha=0.3)
        self.plotItem.setLimits(xMin=0, xMax=1, yMin=-40, yMax=40)
        self.plotItem.setMouseEnabled(x=False, y=False)
        self.plotItem.vb.setMouseEnabled(False, False)

        for axis in ('bottom', 'left'):
            ax = self.plotItem.getAxis(axis)
            ax.setPen(pg.mkPen(color='#aaa'))
            ax.setTextPen(pg.mkPen(color='#aaa'))

        self.plot = self.plotItem.plot(pen=pg.mkPen('yellow', width=1.5))

        # Trigger level indicator
        self.trigger_line = pg.InfiniteLine(
            pos=0, angle=0,
            pen=pg.mkPen(color='#FF4444', width=1, style=pg.QtCore.Qt.DashLine),
            movable=False,
        )
        self.trigger_line.setVisible(False)
        self.plotItem.addItem(self.trigger_line)

        self.trigger_arrow = pg.ArrowItem(
            angle=0, tipAngle=30, headLen=10, tailLen=0, tailWidth=0,
            pen=pg.mkPen('#FF4444', width=1), brush=pg.mkBrush('#FF4444'),
        )
        self.trigger_arrow.setVisible(False)
        self.plotItem.addItem(self.trigger_arrow)

        # Horizontal offset marker
        self.horz_offset_line = pg.InfiniteLine(
            pos=0, angle=90,
            pen=pg.mkPen(color='#44AAFF', width=1, style=pg.QtCore.Qt.DashLine),
            movable=False,
        )
        self.horz_offset_line.setVisible(False)
        self.plotItem.addItem(self.horz_offset_line)

        self.horz_offset_arrow = pg.ArrowItem(
            angle=-90, tipAngle=30, headLen=10, tailLen=0, tailWidth=0,
            pen=pg.mkPen('#44AAFF', width=1), brush=pg.mkBrush('#44AAFF'),
        )
        self.horz_offset_arrow.setVisible(False)
        self.plotItem.addItem(self.horz_offset_arrow)

        # Scroll-wheel on axes adjusts knobs
        self.plotItem.getAxis('bottom').wheelEvent = self._axisWheel('horz_knob')
        self.plotItem.getAxis('left').wheelEvent = self._axisWheel('vert_knob')

    def _axisWheel(self, knob_attr):
        """Return a wheel-event handler that nudges the named knob by ±1."""
        def handler(event):
            knob = getattr(self.control, knob_attr, None)
            if knob is None:
                return
            delta = event.delta()
            if delta >= 120:
                knob.setValue(min(knob.value() + 1, knob.maximum()))
            elif delta <= -120:
                knob.setValue(max(knob.value() - 1, knob.minimum()))
            event.accept()
        return handler

    # ── Tick / range helpers ─────────────────────────────────────────────

    def setTicks(self, x_step, y_step, vOffset=0):
        x_ticks = [(i * x_step, f"{i * x_step:.3g}") for i in range(self.NUM_HORZ_DIVS + 1)]

        yMin = -y_step * (self.NUM_VERT_DIVS / 2) - vOffset
        yMax = y_step * (self.NUM_VERT_DIVS / 2) - vOffset

        first_idx = math.floor(yMin / y_step) if y_step else 0
        last_idx = math.ceil(yMax / y_step) if y_step else 0
        y_ticks = [(round(i * y_step, 10), f"{round(i * y_step, 10):.3g}")
                    for i in range(first_idx, last_idx + 1)]

        self.plotItem.getAxis('bottom').setTicks([x_ticks])
        self.plotItem.getAxis('left').setTicks([y_ticks])

    def setPlotRange(self, vDiv, hDiv, vOffset=0):
        half = vDiv * (self.NUM_VERT_DIVS / 2)
        self.plotItem.setRange(
            xRange=(0, self.NUM_HORZ_DIVS * hDiv),
            yRange=(round(-half - vOffset, 6), round(half - vOffset, 6)),
        )

    # ── Main update ──────────────────────────────────────────────────────

    def updateWaveform(self, waveform):
        hDiv = self.control.getHorizontalDiv()
        vDiv = self.control.getVerticalDiv()
        vOffset = self.control.getVertOffsetValue()

        self.setPlotRange(vDiv, hDiv, vOffset)
        self.setTicks(hDiv, vDiv, vOffset)

        trigger_mode = self.control.getTriggerMode()
        trigger_on = trigger_mode != 'off'

        # Trigger level indicator
        if trigger_on:
            lvl = self.control.getTriggerLevelVolts()
            self.trigger_line.setValue(lvl)
            self.trigger_line.setVisible(True)
            self.trigger_arrow.setPos(0, lvl)
            self.trigger_arrow.setVisible(True)
        else:
            self.trigger_line.setVisible(False)
            self.trigger_arrow.setVisible(False)

        # Horizontal offset marker
        h_offset = self.control.getHorzOffset()
        if h_offset != 0 and trigger_on:
            x_max = waveform[0][-1] if len(waveform[0]) > 0 else self.NUM_HORZ_DIVS * hDiv
            trigger_x = x_max * (500 + h_offset) / 1000.0
            self.horz_offset_line.setValue(trigger_x)
            self.horz_offset_line.setVisible(True)
            yMax = vDiv * (self.NUM_VERT_DIVS / 2) - vOffset
            self.horz_offset_arrow.setPos(trigger_x, yMax)
            self.horz_offset_arrow.setVisible(True)
        else:
            self.horz_offset_line.setVisible(False)
            self.horz_offset_arrow.setVisible(False)

        self.plot.setData(waveform[0], waveform[1])
