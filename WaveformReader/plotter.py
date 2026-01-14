import pyqtgraph as pg
import numpy as np

class WaveformPlot(pg.PlotWidget):
    def __init__(self, control=None):
        super().__init__(title="Waveform Display")
        
         # --- Division counts ---
        self.NUM_HORZ_DIVS = 10  # Horizontal divisions
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

    def setTicks(self, x_step, y_step):
        x_ticks = [(i * x_step, f"{i * x_step:.3g}") for i in range(11)]
        y_ticks = [(i * y_step - 4 * y_step, f"{i * y_step - 4 * y_step:.3g}") for i in range(9)]

        self.plotItem.getAxis('bottom').setTicks([x_ticks])
        self.plotItem.getAxis('left').setTicks([y_ticks])

    def setPlotRange(self, vDiv, hDiv):
        self.plotItem.setRange(
            xRange=(0, self.NUM_HORZ_DIVS * hDiv),
            yRange=(round(-vDiv * (self.NUM_VERT_DIVS/2), 3), round(vDiv * (self.NUM_VERT_DIVS/2), 3))
        )

    def update_waveform(self, waveform):
        # Get division sizes from ControlPanel properties
        hDiv = self.control.getHorizontalDiv()
        vDiv = self.control.getVerticalDiv()
        vOffset = self.control.getVertOffset()
        
        # Set axis ticks based on division sizes
        self.setPlotRange(vDiv, hDiv)
        self.setTicks(hDiv, vDiv)
        
        self.plot.setData(waveform[0], waveform[1])

