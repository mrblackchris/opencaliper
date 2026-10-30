"""S-parameter display transforms and a normalized impedance Smith chart."""
import re
from types import SimpleNamespace
import numpy as np
from PySide6 import QtCore, QtWidgets as Q
import pyqtgraph as pg
from .core import Signal
from .display import scientific


REPRESENTATIONS = ('Magnitude (dB)', 'Magnitude (linear)', 'Phase (degrees)',
                   'Unwrapped phase (degrees)', 'Real', 'Imaginary')


def displayed(source, representation):
    """Materialize one real display vector without modifying complex source samples."""
    if source.domain != 'sparameter':
        raise ValueError('S Parameter analysis requires Touchstone S-parameter channels')
    values, unit = source.values, ''
    if representation == 'Magnitude (dB)':
        with np.errstate(divide='ignore'): values = 20*np.log10(np.abs(values))
        unit = 'dB'
    elif representation == 'Magnitude (linear)': values = np.abs(values)
    elif representation == 'Phase (degrees)': values, unit = np.angle(values, deg=True), 'deg'
    elif representation == 'Unwrapped phase (degrees)': values, unit = np.rad2deg(np.unwrap(np.angle(values))), 'deg'
    elif representation == 'Real': values = np.real(values)
    elif representation == 'Imaginary': values = np.imag(values)
    else: raise ValueError('Unknown S-parameter representation')
    return Signal(source.name, source.time, values, unit, domain='sparameter',
                  reference_impedance=source.reference_impedance)


def smith_grid():
    """Yield normalized constant-resistance/reactance curves inside the unit circle.

    Coordinates are reflection coefficient Gamma = (z-1)/(z+1), where z=Z/Z0.
    Curves are constructed analytically; no RF plotting dependency is required.
    """
    theta = np.linspace(0, 2*np.pi, 721)
    yield np.cos(theta), np.sin(theta)
    yield np.array([-1., 1.]), np.array([0., 0.])
    for resistance in (.2, .5, 1., 2., 5.):
        radius = 1/(resistance+1)
        yield resistance/(resistance+1)+radius*np.cos(theta), radius*np.sin(theta)
    resistance = np.r_[0., np.geomspace(1e-4, 1e5, 1000)]
    for reactance in (.2, .5, 1., 2., 5.):
        for sign in (-1, 1):
            z = resistance+1j*sign*reactance
            gamma = (z-1)/(z+1)
            yield gamma.real, gamma.imag


class SmithChart(Q.QDialog):
    """Snapshot of visible diagonal Sii traces; hover reports nearest sample and Z.

    Each trace uses its own positive real reference resistance, retained from
    Touchstone. Active reflections outside the unit circle remain visible.
    """
    def __init__(self, window, page):
        super().__init__(window)
        self.setWindowTitle('Smith chart — reflection coefficients')
        self.resize(850, 850)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        layout = Q.QVBoxLayout(self)
        layout.addWidget(Q.QLabel('Normalized impedance Smith chart · Reflection coefficients Sii · Hover for frequency and impedance'))
        self.plot = pg.PlotWidget()
        self.plot.workspace = SimpleNamespace(cursors_visible=False)
        self.plot.setLabel('bottom', 'Real Γ'); self.plot.setLabel('left', 'Imaginary Γ')
        self.plot.setAspectLocked(True)
        self.plot.addLegend()
        for x, y in smith_grid(): self.plot.plot(x, y, pen=pg.mkPen('#708090', width=.7))
        for x, y, label in ((-1, 0, 'short'), (0, 0, 'matched'), (1, 0, 'open')):
            text = pg.TextItem(label, color='#aab6c4', anchor=(.5, 1))
            text.setPos(x, y); self.plot.addItem(text)
        self.traces = []
        seen = set()
        for plot in page.plots:
            for index in plot.curves:
                source = window.signals[index]
                if index in seen or index in plot.hidden_signals or not re.fullmatch(r'S([1-4])\1', source.name):
                    continue
                seen.add(index)
                label = f'{window.display_name(plot, index)} ({source.reference_impedance:g} Ω)'
                self.plot.plot(source.values.real, source.values.imag, pen=plot.curves[index].opts['pen'], name=label)
                self.traces.append((label, source))
        self.plot.setRange(xRange=(-1.1, 1.1), yRange=(-1.1, 1.1), padding=0)
        if self.traces: self.plot.enableAutoRange()
        layout.addWidget(self.plot)
        self.readout = Q.QLabel('Move the mouse over a reflection trace.')
        self.readout.setWordWrap(True); layout.addWidget(self.readout)
        export = Q.QPushButton('Export chart…'); layout.addWidget(export)
        def save():
            path, _ = Q.QFileDialog.getSaveFileName(self, 'Export Smith chart', '', 'PNG (*.png);;SVG (*.svg);;PDF (*.pdf)')
            if path:
                try: window.export_plot_to(self.plot, path)
                except Exception as exc: window.error(str(exc))
        export.clicked.connect(save)
        self.plot.scene().sigMouseMoved.connect(self.hover)

    def hover(self, position):
        if not self.traces or not self.plot.getViewBox().sceneBoundingRect().contains(position): return
        point = self.plot.getViewBox().mapSceneToView(position)
        gamma = point.x()+1j*point.y()
        candidates = []
        for label, signal in self.traces:
            index = int(np.argmin(abs(signal.values-gamma)))
            candidates.append((abs(signal.values[index]-gamma), label, signal, index))
        _, label, source, index = min(candidates, key=lambda item: item[0])
        value = source.values[index]
        impedance = source.reference_impedance*(1+value)/(1-value) if abs(1-value) > 1e-15 else None
        z = f'{scientific(impedance.real)} {impedance.imag:+.6e}j Ω' if impedance is not None else 'open (infinite impedance)'
        self.readout.setText(f'{label} · f={scientific(source.time[index])} Hz · Γ={scientific(value.real)} {value.imag:+.6e}j · Z={z}')
