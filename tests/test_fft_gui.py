"""Frequency-domain workspace uses the same interactions as time plots."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import patch
import numpy as np
from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from opencaliper import Recording, Signal
from opencaliper.analysis import fft
from opencaliper.gui import Window


class FftGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = Window()
        t = np.arange(1024)/1024
        self.sources = [Signal('Voltage', t, 3*np.sin(2*np.pi*64*t), 'V'),
                        Signal('Current', t, .2*np.sin(2*np.pi*128*t), 'A')]
        self.window.loaded(Recording(self.sources, 'tones.mat'))

    def tearDown(self):
        self.window.close()
        self.app.processEvents()

    def test_fft_opens_empty_analysis_and_drag_computes_spectra(self):
        w = self.window
        explorer = w.list
        time_page = w.workspace
        page = w.spectrum()  # A file entry, rather than a signal, is selected.
        self.assertEqual(w.tabs.count(), 2)
        self.assertEqual(page.kind, 'spectrum')
        self.assertFalse(page.plots[0].curves)
        self.assertIs(explorer, w.list)
        self.assertTrue(w.cursors_enabled.isChecked())
        self.assertEqual(page.plots[0].getAxis('bottom').labelUnits, 'Hz')
        w.list.topLevelItem(0).setExpanded(True)
        w.list.clearSelection()
        for item in w.signal_items.values(): item.setSelected(True)
        mime = w.list.mimeData(w.list.selectedItems())
        w.show(); self.app.processEvents()
        viewport = page.plots[0].viewport()
        enter = QtGui.QDragEnterEvent(QtCore.QPoint(20,20), QtCore.Qt.DropAction.CopyAction,
                                     mime, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(viewport, enter)
        drop = QtGui.QDropEvent(QtCore.QPointF(20,20), QtCore.Qt.DropAction.CopyAction,
                               mime, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(viewport, drop)
        self.assertTrue(drop.isAccepted())
        p = page.plots[0]
        self.assertEqual(set(p.curves), {0,1})
        for index, frequency, amplitude in [(0,64,3), (1,128,.2)]:
            spectrum = p.display_signals[index]
            peak = np.argmax(spectrum.values)
            self.assertEqual(spectrum.time[peak], frequency)
            self.assertAlmostEqual(spectrum.values[peak], amplitude, places=4)
            self.assertEqual(len(spectrum.time), 513)
        w.fit()
        self.assertGreaterEqual(p.physical_x_range()[1], 512)
        self.assertFalse(time_page.plots[0].curves)

    def test_selected_signal_and_frequency_cursors_are_independent_of_time(self):
        w = self.window
        w.list.setCurrentItem(w.signal_items[0])
        w.add_signal(0,w.plots[0])
        source_page = w.workspace
        w.move_cursor(0,.1); w.move_cursor(1,.2)
        page = w.spectrum()  # Disabled time cursors mean the full record.
        self.assertIn(0,page.plots[0].curves)
        w.move_cursor(0,64); w.move_cursor(1,128)
        text = page.readout.toPlainText()
        self.assertIn('A = 6.4e1 Hz',text)
        self.assertIn('Δf = 6.4e1 Hz',text)
        self.assertNotIn('Δt',text)
        self.assertNotIn('1/|Δt|',text)
        self.assertIn('Voltage: A 2.999',text)
        self.assertEqual(source_page.cursor_positions,[.1,.2])
        w.add_plot(); w.add_signal(1,w.plots[1])
        w.move_cursor(0,64)
        self.assertAlmostEqual(w.plots[0].x_from_scene(w.plots[0].cursors[0].value()),64)
        self.assertAlmostEqual(w.plots[1].x_from_scene(w.plots[1].cursors[0].value()),64)
        w.separate_signal_axes(w.plots[0],[0])
        self.assertTrue(w.plots[0].extra_axes)
        w.tabs.setCurrentIndex(0)
        np.testing.assert_array_equal(source_page.plots[0].display_signals[0].values,self.sources[0].values)

    def test_time_interval_inherited_and_recalculated_for_all_plots(self):
        w = self.window
        w.list.setCurrentItem(w.signal_items[0])
        w.cursors_enabled.setChecked(True)
        w.move_cursor(0,.125); w.move_cursor(1,.5)
        page = w.spectrum()
        self.assertEqual(page.fft_interval,(.125,.5))
        expected_f,expected_a = fft(self.sources[0],.125,.5)
        np.testing.assert_array_equal(page.plots[0].display_signals[0].time,expected_f)
        np.testing.assert_allclose(page.plots[0].display_signals[0].values,expected_a)
        w.add_plot(); w.add_signal(1,w.plots[1])
        page.use_interval.setChecked(False)
        QTest.mouseClick(page.recalculate,QtCore.Qt.MouseButton.LeftButton)
        self.assertEqual(page.fft_interval,(None,None))
        self.assertTrue(all(len(p.display_signals[i].time)==513 for p in page.plots for i in p.curves))
        # Frequency cursors must never become a time-domain FFT interval.
        w.move_cursor(0,100); w.move_cursor(1,200)
        another = w.spectrum()
        self.assertEqual(another.fft_interval,(None,None))

    def test_invalid_fft_and_recalculate_leave_existing_data_intact(self):
        w = self.window
        w.list.setCurrentItem(w.signal_items[0])
        page = w.spectrum(); p = page.plots[0]
        original = p.display_signals[0]
        page.use_interval.setChecked(True)
        page.start_time.setValue(10); page.stop_time.setValue(20)
        with patch.object(w,'error') as error:
            w.recalculate_fft(page)
            error.assert_called_once()
        self.assertEqual(page.fft_interval,(None,None))
        self.assertIs(original,p.display_signals[0])
        w.loaded(Recording([Signal('irregular',[0,1,2,4],[0,1,0,1],'V')],'bad.mat'))
        with patch.object(w,'error') as error:
            w.add_signal(2,p)
            error.assert_called_once()
        self.assertNotIn(2,p.curves)
        self.assertNotIn(2,p.display_signals)
        self.assertEqual(p.signal_list.count(),1)

    def test_delete_clear_and_unload_fft_signals(self):
        w = self.window
        page = w.spectrum(); p = page.plots[0]
        w.add_signal(0,p); w.add_signal(1,p)
        p.signal_list.setCurrentRow(0)
        QTest.keyClick(p.signal_list,QtCore.Qt.Key.Key_Delete)
        self.assertEqual(set(p.display_signals),{1})
        w.separate_signal_axes(p,[1])
        w.remove_files([0])
        self.assertFalse(p.curves)
        self.assertFalse(p.display_signals)
        self.assertFalse(p.extra_axes)
        self.assertNotIn('Current:',page.readout.toPlainText())

    def test_log_defaults_cursor_drag_and_switching_to_linear(self):
        w = self.window; page = w.spectrum(); p = page.plots[0]
        w.add_signal(0,p); w.add_signal(1,p)
        self.assertTrue(p.log_x_box.isChecked())
        self.assertFalse(p.log_y_box.isChecked())
        p.log_y_box.setChecked(True)
        self.assertTrue(p.curves[0].opts['logMode'][0])
        self.assertTrue(p.curves[0].opts['logMode'][1])
        # Dragging an InfiniteLine supplies plot coordinates, not physical Hz.
        p.cursors[0].setValue(np.log10(64))
        self.assertAlmostEqual(page.cursor_positions[0],64)
        self.assertIn('A = 6.4e1 Hz',page.readout.toPlainText())
        np.testing.assert_array_equal(p.display_signals[0].values,fft(self.sources[0])[1])
        w.separate_signal_axes(p,[1])
        axis, view = p.extra_axes[p.signal_axes[1]]
        self.assertTrue(axis.logMode)
        self.assertTrue(p.curves[1].opts['logMode'][1])
        w.show(); self.app.processEvents()
        p.log_x_box.setChecked(False); p.log_y_box.setChecked(False)
        self.assertFalse(axis.logMode)
        self.assertAlmostEqual(p.cursors[0].value(),64)
        self.assertGreaterEqual(p.viewRange()[0][1],512)
        self.assertFalse(p.curves[1].opts['logMode'][0])
        w.move_cursor(0,0)
        p.log_x_box.setChecked(True)
        self.assertFalse(p.cursors[0].isVisible())
        self.assertEqual(page.cursor_positions[0],0)
        p.log_x_box.setChecked(False)
        self.assertTrue(p.cursors[0].isVisible())

    def test_linked_frequency_ranges_work_with_mixed_log_x(self):
        w = self.window; page = w.spectrum()
        w.add_signal(0,w.plots[0]); w.add_plot(); w.add_signal(1,w.plots[1])
        first, second = w.plots
        second.log_x_box.setChecked(False)
        first.set_physical_x_range(10,200)
        np.testing.assert_allclose(second.viewRange()[0],[10,200])
        second.setXRange(32,128,padding=0)
        np.testing.assert_allclose(first.physical_x_range(),[32,128])
        w.move_cursor(0,64)
        self.assertAlmostEqual(first.cursors[0].value(),np.log10(64))
        self.assertAlmostEqual(second.cursors[0].value(),64)
        # Native plot menu and visible checkboxes remain in sync.
        first.plotItem.ctrl.logYCheck.setChecked(False)
        self.assertFalse(first.log_y_box.isChecked())
        self.assertFalse(first.log_y)

    def test_color_menu_hits_log_fft_curve_on_separate_axis(self):
        w = self.window; page = w.spectrum(); p = page.plots[0]
        w.add_signal(0,p); w.add_signal(1,p)
        p.log_y_box.setChecked(True)
        w.separate_signal_axes(p,[1]); w.show(); self.app.processEvents()
        view = p.extra_axes[p.signal_axes[1]][1]
        spectrum = p.display_signals[1]
        scene_pos = view.mapViewToScene(QtCore.QPointF(np.log10(128), np.log10(spectrum.values[128])))
        menu = w.plot_color_menu(p,scene_pos)
        chosen = QtGui.QColor('#ae68e0')
        with patch('opencaliper.gui.Q.QColorDialog.getColor',return_value=chosen):
            next(a for a in menu.actions() if a.text()=='Change color…').trigger()
        self.assertEqual(p.curves[1].opts['pen'].color(),chosen)
        self.assertNotEqual(p.curves[0].opts['pen'].color(),chosen)
        page.recalculate.click()
        self.assertEqual(p.curves[1].opts['pen'].color(),chosen)

    def test_short_interval_can_retry_full_record_without_readding(self):
        w = self.window
        w.list.setCurrentItem(w.signal_items[0])
        w.cursors_enabled.setChecked(True)
        w.move_cursor(0,0); w.move_cursor(1,1/1024)
        with patch.object(w,'error') as error:
            page = w.spectrum()
        self.assertIn('contains 2 of 1024',error.call_args.args[0])
        self.assertIn('Recalculate',error.call_args.args[0])
        self.assertEqual(page.pending_signals,{0})
        self.assertFalse(page.plots[0].curves)
        page.use_interval.setChecked(False)
        with patch.object(w,'error') as error:
            w.recalculate_fft(page)
            error.assert_not_called()
        self.assertIn(0,page.plots[0].curves)
        self.assertFalse(page.pending_signals)
        self.assertEqual(len(page.plots[0].display_signals[0].time),513)

    def test_invalid_values_can_retry_finite_contiguous_interval(self):
        w = self.window
        values = self.sources[0].values.copy(); values[0] = np.nan
        w.loaded(Recording([Signal('Missing sample',self.sources[0].time,values,'V')],'missing.mat'))
        w.list.setCurrentItem(w.signal_items[2])
        with patch.object(w,'error') as error: page = w.spectrum()
        self.assertIn('1 NaN/Inf samples out of 1024',error.call_args.args[0])
        page.use_interval.setChecked(True)
        page.start_time.setValue(0.125); page.stop_time.setValue(0.5)
        with patch.object(w,'error') as error:
            w.recalculate_fft(page)
            error.assert_not_called()
        self.assertIn(2,page.plots[0].curves)
        self.assertTrue(np.isnan(w.signals[2].values[0]))

    def test_unloading_clears_pending_fft_sources(self):
        w = self.window
        w.list.setCurrentItem(w.signal_items[0])
        w.cursors_enabled.setChecked(True)
        w.move_cursor(0,0); w.move_cursor(1,0)
        with patch.object(w,'error'): page = w.spectrum()
        w.remove_files([0])
        self.assertFalse(page.pending_signals)
        with patch.object(w,'error') as error:
            w.recalculate_fft(page)
            error.assert_not_called()
