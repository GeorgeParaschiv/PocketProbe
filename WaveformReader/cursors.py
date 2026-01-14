import pyqtgraph as pg
from PyQt5.QtCore import Qt, QObject

class CursorManager(QObject):
    def __init__(self, plot_widget):
        super().__init__()
        self.plot_widget = plot_widget
        self.cursors = {
            '1': {
                'x': pg.InfiniteLine(pos=0, angle=90, movable=True, pen=pg.mkPen(color='blue', width=3, style=Qt.DashLine)),
                'y': pg.InfiniteLine(pos=0, angle=0, movable=True, pen=pg.mkPen(color='blue', width=3, style=Qt.DashLine))
            },
            '2': {
                'x': pg.InfiniteLine(pos=0, angle=90, movable=True, pen=pg.mkPen(color='red', width=3, style=Qt.DashLine)),
                'y': pg.InfiniteLine(pos=0, angle=0, movable=True, pen=pg.mkPen(color='red', width=3, style=Qt.DashLine))
            }
        }
        for pair in self.cursors.values():
            self.plot_widget.addItem(pair['x'])
            self.plot_widget.addItem(pair['y'])
        self.set_cursor_visibility('1', False)
        self.set_cursor_visibility('2', False)
        self._dragging_cursor = None
        self._dragging_axis = None
        self.plot_widget.scene().installEventFilter(self)

    def set_cursor_visibility(self, name, visible):
        if name in self.cursors:
            self.cursors[name]['x'].setVisible(visible)
            self.cursors[name]['y'].setVisible(visible)

    def get_cursor_values(self):
        c1 = self.cursors['1']
        c2 = self.cursors['2']
        return {
            'X1': c1['x'].value(),
            'Y1': c1['y'].value(),
            'X2': c2['x'].value(),
            'Y2': c2['y'].value(),
            'Δx': abs(c2['x'].value() - c1['x'].value()),
            'Δy': abs(c2['y'].value() - c1['y'].value()),
        }

    def bring_cursor_to_center(self, cursor_name):
        plot_item = self.plot_widget.plotItem
        x_range = plot_item.viewRange()[0]
        y_range = plot_item.viewRange()[1]
        x_center = (x_range[0] + x_range[1]) / 2
        y_center = (y_range[0] + y_range[1]) / 2
        cursor = self.cursors[cursor_name]
        cursor['x'].setValue(x_center)
        cursor['y'].setValue(y_center)

    def eventFilter(self, obj, event):
        if event.type() == event.GraphicsSceneMousePress:
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(event.scenePos())
            mx, my = mouse_point.x(), mouse_point.y()
            c1x = self.cursors['1']['x'].value()
            c1y = self.cursors['1']['y'].value()
            c2x = self.cursors['2']['x'].value()
            c2y = self.cursors['2']['y'].value()
            threshold = 0.01 * max(
                abs(self.plot_widget.plotItem.viewRange()[0][1] - self.plot_widget.plotItem.viewRange()[0][0]),
                abs(self.plot_widget.plotItem.viewRange()[1][1] - self.plot_widget.plotItem.viewRange()[1][0])
            )
            # Cursor 1 checks (mutually exclusive)
            if abs(mx - c1x) < threshold and abs(my - c1y) < threshold:
                self._dragging_cursor = '1'
                self._dragging_axis = 'xy'
                return True
            elif abs(mx - c1x) < threshold and abs(my - c1y) >= threshold:
                self._dragging_cursor = '1'
                self._dragging_axis = 'x'
                return True
            elif abs(my - c1y) < threshold and abs(mx - c1x) >= threshold:
                self._dragging_cursor = '1'
                self._dragging_axis = 'y'
                return True
            # Cursor 2 checks (mutually exclusive)
            if abs(mx - c2x) < threshold and abs(my - c2y) < threshold:
                self._dragging_cursor = '2'
                self._dragging_axis = 'xy'
                return True
            elif abs(mx - c2x) < threshold and abs(my - c2y) >= threshold:
                self._dragging_cursor = '2'
                self._dragging_axis = 'x'
                return True
            elif abs(my - c2y) < threshold and abs(mx - c2x) >= threshold:
                self._dragging_cursor = '2'
                self._dragging_axis = 'y'
                return True
        elif event.type() == event.GraphicsSceneMouseMove:
            if self._dragging_cursor is not None:
                mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(event.scenePos())
                mx, my = mouse_point.x(), mouse_point.y()
                cursor = self.cursors[self._dragging_cursor]
                if self._dragging_axis == 'xy':
                    cursor['x'].setValue(mx)
                    cursor['y'].setValue(my)
                elif self._dragging_axis == 'x':
                    cursor['x'].setValue(mx)
                elif self._dragging_axis == 'y':
                    cursor['y'].setValue(my)
                return True
        elif event.type() == event.GraphicsSceneMouseRelease:
            self._dragging_cursor = None
            self._dragging_axis = None
        return False