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
        self.setCursorVisibility('1', False)
        self.setCursorVisibility('2', False)
        self._dragging_cursor = None
        self._dragging_axis = None
        self.plot_widget.scene().installEventFilter(self)

    def setCursorVisibility(self, name, visible):
        if name in self.cursors:
            self.cursors[name]['x'].setVisible(visible)
            self.cursors[name]['y'].setVisible(visible)

    def getCursorValues(self):
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

    def bringCursorToCenter(self, cursor_name):
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

            # Separate thresholds for each axis (3% of visible span)
            x_span = abs(self.plot_widget.plotItem.viewRange()[0][1] - self.plot_widget.plotItem.viewRange()[0][0])
            y_span = abs(self.plot_widget.plotItem.viewRange()[1][1] - self.plot_widget.plotItem.viewRange()[1][0])
            x_thresh = 0.03 * x_span
            y_thresh = 0.03 * y_span

            # Find the closest VISIBLE cursor using normalized distance
            best_cursor = None
            best_dist = float('inf')
            best_axis = None

            for name in ['1', '2']:
                if not self.cursors[name]['x'].isVisible():
                    continue
                cx = self.cursors[name]['x'].value()
                cy = self.cursors[name]['y'].value()

                dx_norm = abs(mx - cx) / x_thresh if x_thresh > 0 else float('inf')
                dy_norm = abs(my - cy) / y_thresh if y_thresh > 0 else float('inf')

                near_x = dx_norm < 1.0
                near_y = dy_norm < 1.0

                if near_x and near_y:
                    dist = dx_norm + dy_norm
                    if dist < best_dist:
                        best_dist = dist
                        best_cursor = name
                        best_axis = 'xy'
                elif near_x:
                    if dx_norm < best_dist:
                        best_dist = dx_norm
                        best_cursor = name
                        best_axis = 'x'
                elif near_y:
                    if dy_norm < best_dist:
                        best_dist = dy_norm
                        best_cursor = name
                        best_axis = 'y'

            if best_cursor is not None:
                self._dragging_cursor = best_cursor
                self._dragging_axis = best_axis
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