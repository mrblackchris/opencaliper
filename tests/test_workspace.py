import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets as Q
from opencaliper.gui import Window
from opencaliper.core import Signal, Recording


class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = Q.QApplication.instance() or Q.QApplication([])

    def setUp(self):
        self.w = Window(); self.w.show(); self.app.processEvents()
        t = np.arange(1024)/1024
        self.w.loaded(Recording([Signal('tone',t,np.sin(2*np.pi*32*t),'V')],'source.mat'))
        self.w.add_signal(0,self.w.plots[0])

    def tearDown(self):
        self.w.close(); self.app.processEvents()

    def test_portable_roundtrip(self):
        w = self.w; p = w.plots[0]
        p.signal_colors[0] = QtGui.QColor('#abcdef'); p.curves[0].setPen('#abcdef')
        w.separate_signal_axes(p,[0]); w.draw_annotation(p,[0.2,0.3,'pulse'])
        w.move_cursor(0,0.1); w.move_cursor(1,0.4); w.toggle_cursors(True)
        p.setXRange(0.1,0.8,padding=0)
        w.spectrum(); w.tabs.setCurrentIndex(0)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'session.ocw'
            w.save_workspace(path)
            other = Window()
            with patch.object(other,'error',side_effect=AssertionError): other.open_workspace(path)
            self.assertEqual(other.tabs.count(),2)
            self.assertEqual(other.signals[0].name,'tone')
            p = other.plots[0]
            self.assertEqual(p.annotations,[[0.2,0.3,'pulse']])
            self.assertEqual(p.curves[0].opts['pen'].color().name(),'#abcdef')
            self.assertIsNotNone(p.signal_axes[0])
            np.testing.assert_allclose(other.cursor_positions,[0.1,0.4])
            np.testing.assert_allclose(p.physical_x_range(),[0.1,0.8])
            self.assertTrue(other.workspace.cursors_visible)
            other.close()

    def test_undo_redo_removal_and_source_unload(self):
        w = self.w
        w.remove_signals(w.plots[0],[0]); self.assertFalse(w.plots[0].curves)
        w.undo(); self.assertIn(0,w.plots[0].curves)
        w.redo(); self.assertFalse(w.plots[0].curves)
        w.undo(); w.remove_files([0]); self.assertFalse(w.signals)
        w.undo(); self.assertIn(0,w.signals); self.assertIn(0,w.plots[0].curves)

    def test_invalid_workspace_preserves_current(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'bad.ocw'; path.write_text('bad archive')
            with patch.object(self.w,'error') as error: self.w.open_workspace(path)
            error.assert_called_once()
            self.assertIn(0,self.w.plots[0].curves)

    def test_export_formats(self):
        with tempfile.TemporaryDirectory() as folder:
            for suffix in ('png','svg','pdf'):
                path = Path(folder)/f'plot.{suffix}'
                self.w.export_plot_to(self.w.plots[0],path)
                self.assertGreater(path.stat().st_size,1000)
                if suffix == 'png': self.assertEqual(QtGui.QImage(str(path)).width(),2400)

    def test_processing_dialogs_and_spectrogram(self):
        w = self.w
        def math_form(title, fields):
            dict(fields)['Expression'].setText('CH0 * 2')
            return True
        with patch.object(w,'form',side_effect=math_form), patch.object(w,'error',side_effect=AssertionError):
            w.math_dialog()
        np.testing.assert_allclose(w.signals[1].values,2*w.signals[0].values)
        with patch.object(w,'form',return_value=True), patch.object(w,'error',side_effect=AssertionError):
            w.filter_dialog()
            w.align_dialog()
            w.event_dialog()
            w.spectrogram_dialog()
        self.assertEqual(len(w.dialogs),1)
        self.app.processEvents()
        w.dialogs[0].close()

    def test_cancel_keeps_redo(self):
        w = self.w
        w.remove_signals(w.plots[0],[0]); w.undo()
        with patch.object(Q.QColorDialog,'getColor',return_value=QtGui.QColor()):
            w.choose_signal_color(w.plots[0],[0])
        self.assertTrue(w.redo_action.isEnabled())

    def test_export_with_cursor_measurements(self):
        w = self.w; w.toggle_cursors(True)
        w.move_cursor(0,0.1); w.move_cursor(1,0.2)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'with-cursors.svg'
            w.export_plot_to(w.plots[0],path)
            svg = path.read_text(encoding='utf-8')
            self.assertIn('1e-1',svg)
            import xml.etree.ElementTree as ET
            text = ''.join(ET.fromstring(svg).itertext())
            self.assertIn('ΔY',''.join(text.split()))

    def test_sparse_channel_identifiers_survive_restore(self):
        w = self.w
        t = np.arange(16,dtype=float)
        w.loaded(Recording([Signal('other',t,t)],'other.mat'))
        w.remove_files([0])
        w.add_signal(1,w.plots[0])
        w.remove_signals(w.plots[0],[1]); w.undo()
        self.assertEqual(set(w.signals),{1})
        self.assertIn(1,w.plots[0].curves)
        self.assertEqual(w.next_signal_id,2)

    def test_form_fields_survive_real_modal_dialog(self):
        for accepted in (True, False):
            with self.subTest(accepted=accepted):
                channel = self.w.channel_combo()
                value = Q.QDoubleSpinBox(); value.setValue(12.5)
                def finish():
                    dialog = Q.QApplication.activeModalWidget()
                    dialog.accept() if accepted else dialog.reject()
                QtCore.QTimer.singleShot(0, finish)
                self.assertEqual(self.w.form('Lifetime check', [('Channel',channel),('Value',value)]),accepted)
                # Read after the helper returns, just as the processing actions do.
                self.assertEqual(channel.currentData(),0)
                self.assertEqual(value.value(),12.5)
                self.assertIsNone(channel.parent())
                self.app.sendPostedEvents(None,QtCore.QEvent.Type.DeferredDelete)
                self.assertEqual(channel.currentData(),0)

    def test_filter_with_real_modal_dialog(self):
        w = self.w
        for _ in range(2):
            QtCore.QTimer.singleShot(0, lambda: Q.QApplication.activeModalWidget().accept())
            with patch.object(w,'error',side_effect=AssertionError): w.filter_dialog()
        self.assertEqual(len(w.signals),3)
        self.assertEqual(len(w.plots[0].curves),3)
        self.app.sendPostedEvents(None,QtCore.QEvent.Type.DeferredDelete)
        self.assertFalse(w.findChildren(Q.QDialog))
