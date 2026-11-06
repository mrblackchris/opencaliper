"""Manual physical bounds, axis double-clicks and independent scale locks."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
import numpy as np
from PySide6 import QtCore, QtWidgets as Q
from PySide6.QtTest import QTest
from opencaliper import Signal, Recording
from opencaliper.gui import Window


class AxisSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = Q.QApplication.instance() or Q.QApplication([])

    def setUp(self):
        self.w = Window(); self.w.show()
        self.errors = []; self.w.error = self.errors.append
        t = np.linspace(1e-6, 1e-3, 100)
        self.w.loaded(Recording([Signal('Voltage', t, np.linspace(1, 10, 100), 'V'),
                                 Signal('Current', t, np.linspace(100, 1000, 100), 'A')]))
        self.w.add_signal(0, self.w.plots[0]); self.app.processEvents()

    def tearDown(self):
        for dialog in self.w.dialogs[:]: dialog.close()
        self.w.close(); self.app.processEvents()

    def test_axis_double_click_opens_dialog_and_accepts_scientific_bounds(self):
        p = self.w.plots[0]
        for side, dimension, bounds in [('bottom', 'x', ('2e-6', '8e-4')), ('left', 'y', ('-2e1', '3e1'))]:
            axis = p.getAxis(side)
            scene = axis.mapToScene(axis.geometry().size().width()/2, axis.geometry().size().height()/2)
            point = p.mapFromScene(scene)
            QTest.mouseDClick(p.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=point)
            QTest.mouseRelease(p.viewport(), QtCore.Qt.MouseButton.LeftButton, pos=point)
            self.app.processEvents()
            self.assertTrue(self.w.dialogs, f'No dialog for {side} axis')
            dialog = self.w.dialogs[-1]
            self.assertEqual(dialog.dimension, dimension)
            dialog.minimum.setText(bounds[0]); dialog.maximum.setText(bounds[1])
            self.assertTrue(dialog.apply())
            actual = p.physical_x_range() if dimension == 'x' else p.physical_y_range()
            np.testing.assert_allclose(actual, list(map(float, bounds)))
            dialog.close(); self.app.processEvents()

    def test_locks_are_independent_and_hold_against_navigation_fit_and_new_data(self):
        p = self.w.plots[0]
        self.w.set_scale_locks(p, True, False)
        old = p.viewRange()
        self.w.zoom_by(.5)
        np.testing.assert_allclose(p.viewRange()[0], old[0])
        self.assertAlmostEqual(np.ptp(p.viewRange()[1])/np.ptp(old[1]), .5)
        self.w.set_scale_locks(p, False, True)
        old = p.viewRange(); self.w.zoom_by(.5)
        np.testing.assert_allclose(p.viewRange()[1], old[1])
        self.assertAlmostEqual(np.ptp(p.viewRange()[0])/np.ptp(old[0]), .5)
        self.w.set_scale_locks(p, True, True)
        old = p.viewRange()
        self.w.fit(); self.w.add_signal(1, p)
        p.getViewBox().translateBy(x=.1, y=100)
        p.getViewBox().setRange(xRange=(-10, 10), yRange=(-50, 50))
        self.app.processEvents()
        np.testing.assert_allclose(p.viewRange(), old)
        self.w.set_scale_locks(p, False, False); self.w.fit()
        self.assertGreater(np.ptp(p.viewRange()[1]), np.ptp(old[1]))

    def test_x_lock_is_shared_y_locks_are_plot_local_and_new_plot_inherits_x(self):
        p = self.w.plots[0]
        self.w.apply_axis_settings(p, 'x', None, 2e-5, 4e-4, False, True)
        self.w.add_plot(); second = self.w.plots[1]; self.w.add_signal(0, second)
        np.testing.assert_allclose(second.physical_x_range(), [2e-5, 4e-4])
        self.assertTrue(second.lock_x_box.isChecked())
        second.lock_y_box.setChecked(True)
        before = [plot.viewRange() for plot in self.w.plots]
        self.w.zoom_by(.5)
        for plot in self.w.plots: np.testing.assert_allclose(plot.physical_x_range(), [2e-5, 4e-4])
        np.testing.assert_allclose(second.viewRange()[1], before[1][1])
        self.assertAlmostEqual(np.ptp(p.viewRange()[1])/np.ptp(before[0][1]), .5)
        second.lock_x_box.setChecked(False)
        self.assertFalse(p.lock_x_box.isChecked())
        self.w.zoom_by(.5)
        self.assertLess(np.ptp(p.physical_x_range()), 4e-4-2e-5)

    def test_log_bounds_are_physical_and_invalid_values_change_nothing(self):
        p = self.w.plots[0]
        self.w.apply_axis_settings(p, 'x', None, 1e-6, 1e-3, True, True)
        np.testing.assert_allclose(p.viewRange()[0], [-6, -3])
        dialog = self.w.edit_axis(p, 'x')
        before = p.physical_x_range()
        for low, high in [('nan', '1'), ('2', '1'), ('-1', '1'), ('0', '1')]:
            dialog.minimum.setText(low); dialog.maximum.setText(high)
            self.assertFalse(dialog.apply()); self.assertTrue(dialog.error.text())
            np.testing.assert_allclose(p.physical_x_range(), before)
        dialog.minimum.setText('2e-6'); dialog.maximum.setText('5e-4')
        self.assertTrue(dialog.apply())
        np.testing.assert_allclose(p.physical_x_range(), [2e-6, 5e-4])
        self.w.add_plot(); second = self.w.plots[-1]
        np.testing.assert_allclose(second.physical_x_range(), [2e-6, 5e-4])
        self.assertTrue(second.lock_x_box.isChecked())
        dialog.close()

    def test_extra_y_axis_manual_bounds_and_lock(self):
        p = self.w.plots[0]; self.w.add_signal(1, p)
        key = p.new_y_axis(); self.w.set_signal_axis(p, [1], key)
        original_main = p.physical_y_range()
        self.w.apply_axis_settings(p, 'y', key, 100, 2000, False, True)
        np.testing.assert_allclose(p.physical_y_range(key), [100, 2000])
        np.testing.assert_allclose(p.physical_y_range(), original_main)
        self.w.zoom_by(.5); self.w.fit()
        np.testing.assert_allclose(p.physical_y_range(key), [100, 2000])
        self.w.apply_axis_settings(p, 'y', key, 10, 1e4, True, True)
        np.testing.assert_allclose(p.extra_axes[key][1].viewRange()[1], [1, 4])
        p.extra_axes[key][0].settings_requested.emit()
        self.assertEqual(self.w.dialogs[-1].key, key)

    def test_workspace_and_history_retain_ranges_locks_and_log_modes(self):
        p = self.w.plots[0]
        self.w.apply_axis_settings(p, 'x', None, 1e-6, 1e-3, True, True)
        self.w.apply_axis_settings(p, 'y', None, 1, 100, True, True)
        self.w.undo(); self.assertFalse(self.w.plots[0].y_locked)
        self.w.redo(); p = self.w.plots[0]; self.assertTrue(p.y_locked)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'axes.ocw'
            self.w.save_workspace(path); self.w.open_workspace(path)
        self.assertFalse(self.errors)
        p = self.w.plots[0]
        self.assertTrue(p.lock_x_box.isChecked()); self.assertTrue(p.lock_y_box.isChecked())
        self.assertTrue(p.log_x); self.assertTrue(p.log_y)
        np.testing.assert_allclose(p.physical_x_range(), [1e-6, 1e-3])
        np.testing.assert_allclose(p.physical_y_range(), [1, 100])
        self.w.zoom_by(.5); self.w.fit()
        np.testing.assert_allclose(p.physical_y_range(), [1, 100])
