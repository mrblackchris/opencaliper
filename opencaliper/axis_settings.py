"""Editable plot axes and physical-range settings dialog."""
import math
from PySide6 import QtCore, QtWidgets as Q
import pyqtgraph as pg


class EditableAxis(pg.AxisItem):
    """Open settings on a left double-click; retain normal axis navigation."""
    settings_requested = QtCore.Signal()

    def mouseClickEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton and event.double():
            event.accept(); self.settings_requested.emit()
        else:
            super().mouseClickEvent(event)


def constrain(view, dimension, locked):
    """Freeze one ViewBox range, including programmatic and automatic navigation."""
    low, high = view.viewRange()[0 if dimension == 'x' else 1]
    letter = dimension.upper()
    view.setLimits(**{dimension+'Min': low if locked else -math.inf,
                      dimension+'Max': high if locked else math.inf,
                      'min'+letter+'Range': high-low if locked else None,
                      'max'+letter+'Range': high-low if locked else None})
    if locked: view.enableAutoRange(axis=dimension, enable=False)


class AxisSettingsDialog(Q.QDialog):
    """Edit a selected axis in physical units; invalid input keeps the dialog open."""
    def __init__(self, window, plot, dimension, key=None):
        super().__init__(window)
        self.setWindowTitle(f'{dimension.upper()} axis settings')
        self.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(420, 250)
        self.window, self.plot, self.dimension, self.key = window, plot, dimension, key
        layout = Q.QFormLayout(self)
        axis = plot.getAxis('bottom') if dimension == 'x' else (plot.getAxis('left') if key is None else plot.extra_axes[key][0])
        unit = axis.labelUnits
        if dimension == 'x' and not unit: unit = 's' if plot.workspace.kind == 'time' else 'Hz'
        low, high = plot.physical_x_range() if dimension == 'x' else plot.physical_y_range(key)
        self.minimum = Q.QLineEdit(f'{low:.12g}')
        self.maximum = Q.QLineEdit(f'{high:.12g}')
        suffix = f' ({unit})' if unit else ''
        layout.addRow('Minimum'+suffix, self.minimum); layout.addRow('Maximum'+suffix, self.maximum)
        layout.addRow(Q.QLabel('Enter physical values, for example 1e-6.'))
        self.logarithmic = Q.QCheckBox('Logarithmic scale')
        self.logarithmic.setChecked(plot.log_x if dimension == 'x' else plot.log_y)
        layout.addRow(self.logarithmic)
        if dimension == 'y': layout.addRow(Q.QLabel('Logarithmic Y applies to all Y axes in this plot.'))
        self.lock = Q.QCheckBox('Lock X range for this analysis page' if dimension == 'x' else 'Lock all Y ranges in this plot')
        self.lock.setChecked(plot.workspace.x_locked if dimension == 'x' else plot.y_locked)
        layout.addRow(self.lock)
        self.error = Q.QLabel(); self.error.setWordWrap(True); layout.addRow(self.error)
        buttons = Q.QDialogButtonBox(Q.QDialogButtonBox.StandardButton.Ok |
                                    Q.QDialogButtonBox.StandardButton.Apply | Q.QDialogButtonBox.StandardButton.Cancel)
        layout.addRow(buttons)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept_settings)
        buttons.button(Q.QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)

    def apply(self):
        try:
            low, high = float(self.minimum.text()), float(self.maximum.text())
            if not all(map(math.isfinite, (low, high))) or low >= high:
                raise ValueError('Enter finite bounds with minimum smaller than maximum.')
            if self.logarithmic.isChecked() and low <= 0:
                raise ValueError('Logarithmic bounds must both be positive.')
            self.window.apply_axis_settings(self.plot, self.dimension, self.key, low, high,
                                            self.logarithmic.isChecked(), self.lock.isChecked())
        except ValueError as exc:
            self.error.setText(str(exc)); return False
        self.error.clear(); return True

    def accept_settings(self):
        if self.apply(): self.accept()
