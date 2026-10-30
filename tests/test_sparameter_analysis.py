"""S-parameter pages, view transforms, portable state and Smith chart exports."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets as Q
from PySide6.QtTest import QTest
from opencaliper import Recording, Signal
from opencaliper.gui import Window
from opencaliper.sparameters import REPRESENTATIONS, displayed, smith_grid


class SParameterAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = Q.QApplication.instance() or Q.QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.w = Window(); self.w.show(); self.app.processEvents()
        self.errors = []; self.w.error = self.errors.append
        self.freq = np.array([1e6, 2e6, 3e6])
        self.samples = np.array([.5, .25j, -.1])
        self.recording = Recording([Signal(name, self.freq, self.samples.copy(), domain='sparameter', reference_impedance=75)
                                    for name in ('S11', 'S12', 'S21', 'S22')], 'network.s2p')

    def tearDown(self):
        while self.w.workers: QTest.qWait(10)
        for dialog in self.w.dialogs[:]: dialog.close()
        self.w.close(); self.app.processEvents()

    def test_new_page_toolbar_auto_route_and_domain_rejection(self):
        actions = {a.text(): a for bar in self.w.findChildren(Q.QToolBar) for a in bar.actions()}
        actions['New S Parameter Analysis'].trigger()
        page = self.w.workspace
        self.assertEqual(page.kind, 'sparameter')
        self.assertEqual(len(page.plots[0].curves), 0)
        self.w.loaded(self.recording)
        self.assertIs(self.w.workspace, page)
        self.assertEqual(len(page.plots[0].curves), 4)
        self.assertTrue(page.plots[0].log_x)
        self.assertEqual(page.plots[0].getAxis('bottom').labelUnits, 'Hz')
        time = self.w.add_analysis('time')
        self.w.add_signal(0, time.plots[0])
        self.assertIn('S Parameter', self.errors[-1])
        self.assertFalse(time.plots[0].curves)
        self.w.loaded(Recording([Signal('Voltage', [0, 1], [1, 2])]))
        self.w.add_signal(4, page.plots[0])
        self.assertIn('requires Touchstone', self.errors[-1])

    def test_representations_preserve_source_and_visibility_and_cursor_units(self):
        self.w.loaded(self.recording)
        page = self.w.workspace; plot = self.w.plots[0]
        self.w.set_signal_visibility(plot, [1], False)
        for mode in REPRESENTATIONS:
            page.representation.setCurrentText(mode)
            expected = displayed(self.recording.signals[0], mode)
            np.testing.assert_allclose(plot.curves[0].getOriginalDataset()[1], expected.values)
            self.assertEqual(plot.display_signals[0].unit, expected.unit)
            self.assertFalse(plot.curves[1].isVisible())
            np.testing.assert_array_equal(self.w.signals[0].values, self.samples)
        self.w.toggle_cursors(True)
        self.w.move_cursor(0, 1e6); self.w.move_cursor(1, 2e6)
        text = self.w.readout.toPlainText()
        self.assertIn('Hz', text); self.assertIn('Δf', text); self.assertIn('S11', text)
        self.assertNotIn('Δt', text)
        self.assertIn('Hz', plot.cursors[0].label.format)

    def test_workspace_roundtrip_and_undo_preserve_complex_data_and_view(self):
        self.w.loaded(self.recording)
        page = self.w.workspace; plot = self.w.plots[0]
        page.representation.setCurrentText('Phase (degrees)')
        self.w.undo()
        self.assertEqual(self.w.workspace.sparameter_representation, 'Magnitude (dB)')
        self.w.redo()
        self.assertEqual(self.w.workspace.representation.currentText(), 'Phase (degrees)')
        plot = self.w.plots[0]
        with patch.object(Q.QInputDialog, 'getText', return_value=('Input reflection', True)):
            self.w.rename_signals(plot, [0])
        self.w.set_signal_visibility(plot, [1], False)
        path = self.folder/'network.ocw'; self.w.save_workspace(path)
        self.w.open_workspace(path)
        self.assertFalse(self.errors)
        self.assertEqual(self.w.workspace.kind, 'sparameter')
        self.assertEqual(self.w.workspace.representation.currentText(), 'Phase (degrees)')
        self.assertEqual(self.w.signals[0].reference_impedance, 75)
        np.testing.assert_array_equal(self.w.signals[0].values, self.samples)
        self.assertEqual(self.w.plots[0].signal_names[0], 'Input reflection')
        self.assertFalse(self.w.plots[0].curves[1].isVisible())

    def test_file_drop_targets_new_sparameter_page_and_uses_reader(self):
        path = self.folder/'network.s2p'
        path.write_text('# MHz S RI R 50\n1 .5 0 0 0 0 0 .2 0\n2 .2 0 0 0 0 0 .1 0', encoding='utf-8')
        page = self.w.add_analysis('sparameter'); plot = page.plots[0]
        mime = QtCore.QMimeData(); mime.setUrls([QtCore.QUrl.fromLocalFile(str(path))])
        enter = QtGui.QDragEnterEvent(QtCore.QPoint(30, 30), QtCore.Qt.DropAction.CopyAction, mime,
                                     QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(plot.viewport(), enter); self.assertTrue(enter.isAccepted())
        drop = QtGui.QDropEvent(QtCore.QPointF(30, 30), QtCore.Qt.DropAction.CopyAction, mime,
                               QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(plot.viewport(), drop)
        while self.w.workers: QTest.qWait(10)
        self.assertEqual(len(plot.curves), 4); self.assertFalse(self.errors)
        self.assertEqual(self.w.tabs.count(), 2)

    def test_smith_reflections_grid_hover_and_chart_export(self):
        self.w.loaded(self.recording)
        self.w.set_signal_visibility(self.w.plots[0], [3], False)
        chart = self.w.show_smith_chart(self.w.workspace); self.app.processEvents()
        self.assertEqual(len(chart.traces), 1)
        self.assertIn('75', chart.traces[0][0])
        gamma = chart.traces[0][1].values[0]
        position = chart.plot.getViewBox().mapViewToScene(QtCore.QPointF(gamma.real, gamma.imag))
        chart.hover(position)
        self.assertIn('1e6 Hz', chart.readout.text())
        self.assertIn('2.25e2', chart.readout.text())  # Gamma=.5 at Z0=75 -> Z=225 ohms.
        for x, y in smith_grid(): self.assertLessEqual(float(np.max(np.hypot(x, y))), 1.00000001)
        for suffix in ('png', 'svg', 'pdf'):
            path = self.folder/('smith.'+suffix)
            self.w.export_plot_to(chart.plot, path)
            self.assertGreater(path.stat().st_size, 100)
        chart.close()

    def test_zero_magnitude_and_unwrapped_phase(self):
        signal = Signal('S11', [1, 2, 3], np.exp(1j*np.deg2rad([170, -170, -150])), domain='sparameter')
        np.testing.assert_allclose(displayed(signal, 'Unwrapped phase (degrees)').values, [170, 190, 210])
        zero = Signal('S11', [1], [0j], domain='sparameter')
        self.assertEqual(displayed(zero, 'Magnitude (dB)').values[0], -np.inf)
