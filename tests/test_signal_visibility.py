"""Visibility is view state, including keyboard control and scientific readouts."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import unittest
from PySide6 import QtCore, QtGui, QtWidgets as Q
from PySide6.QtTest import QTest
import numpy as np
from opencaliper import Recording, Signal
from opencaliper.gui import Window
from opencaliper.display import scientific
from scripts.create_desktop_launcher import create_launcher


class SignalVisibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=Q.QApplication.instance() or Q.QApplication([])

    def setUp(self):
        self.w=Window()
        t=np.arange(100)*1e-6
        self.w.loaded(Recording([Signal('Small',t,np.ones(100),'V'),
                                 Signal('Large',t,np.full(100,1000.),'V')],'test.mat'))
        self.w.add_signal(0,self.w.plots[0]); self.w.add_signal(1,self.w.plots[0])
        self.w.show(); self.app.processEvents()

    def tearDown(self):
        self.w.close(); self.app.processEvents()

    def test_checkbox_and_space_hide_without_removing_and_sync_legend(self):
        w=self.w; p=w.plots[0]
        p.signal_list.item(0).setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.assertFalse(p.curves[0].isVisible()); self.assertIn(0,p.display_signals)
        self.assertEqual(len(w.signals),2)
        p.signal_list.selectAll()
        QTest.keyClick(p.signal_list,QtCore.Qt.Key.Key_Space)
        self.assertTrue(p.curves[0].isVisible()); self.assertFalse(p.curves[1].isVisible())
        # The native pyqtgraph legend uses setVisible; checkboxes must follow it.
        p.curves[1].setVisible(True)
        self.assertEqual(p.signal_list.item(1).checkState(),QtCore.Qt.CheckState.Checked)
        w.separate_signal_axes(p,[1])
        p.signal_list.item(1).setCheckState(QtCore.Qt.CheckState.Unchecked)
        self.assertFalse(p.curves[1].isVisible())

    def test_hidden_channels_are_excluded_from_readout_and_fit(self):
        w=self.w; p=w.plots[0]
        w.set_signal_visibility(p,[1],False)
        w.cursors_enabled.setChecked(True); w.move_cursor(0,1e-6); w.move_cursor(1,2e-6)
        text=w.readout.toPlainText()
        self.assertIn('A = 1e-6 s',text); self.assertIn('1/|Δt| = 1e6 Hz',text)
        self.assertIn('Small:',text); self.assertNotIn('Large:',text)
        self.assertIn('A: 1e-6 s',p.cursors[0].label.toPlainText())
        w.fit()
        self.assertLess(p.viewRange()[1][1],10)
        w.set_signal_visibility(p,[0],False)
        w.fit()  # All hidden is valid and leaves the view in place.
        self.assertEqual(set(p.curves),{0,1})

    def test_plot_local_visibility_undo_and_workspace_roundtrip(self):
        w=self.w; w.add_plot(); w.add_signal(0,w.plots[1])
        w.set_signal_visibility(w.plots[0],[0],False)
        self.assertTrue(w.plots[1].curves[0].isVisible())
        w.undo(); self.assertTrue(w.plots[0].curves[0].isVisible())
        w.redo(); self.assertFalse(w.plots[0].curves[0].isVisible())
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'visibility.ocw'; w.save_workspace(path)
            other=Window()
            try:
                other.open_workspace(path)
                self.assertFalse(other.plots[0].curves[0].isVisible())
                self.assertTrue(other.plots[1].curves[0].isVisible())
                self.assertEqual(other.plots[0].signal_list.item(0).checkState(),QtCore.Qt.CheckState.Unchecked)
            finally: other.close()

    def test_scientific_frequency_readout_and_export_omit_hidden_channels(self):
        w=self.w
        w.loaded(Recording([Signal('Spectrum',[1e6,2e6,3e6],[-20,-30,-40],'dBm',domain='frequency')],'spectrum.mat'))
        self.app.processEvents()
        w.move_cursor(0,1e6); w.move_cursor(1,2e6)
        self.assertIn('Δf = 1e6 Hz',w.readout.toPlainText())
        w.set_signal_visibility(w.plots[0],[2],False)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'hidden.svg'; w.export_plot_to(w.plots[0],path)
            import xml.etree.ElementTree as ET
            text=''.join(ET.parse(path).getroot().itertext())
            self.assertNotIn('Spectrum: A',text)

    def test_packaged_logo_and_application_icon(self):
        from opencaliper.branding import ICON_PATH
        image=QtGui.QImage(str(ICON_PATH))
        self.assertFalse(image.isNull()); self.assertTrue(image.hasAlphaChannel())
        self.assertEqual(image.pixelColor(0,0).alpha(),0)
        self.assertFalse(self.w.windowIcon().isNull())
        self.assertFalse(self.app.windowIcon().isNull())


class DisplayAndLauncherTests(unittest.TestCase):
    def test_scientific_formatting(self):
        for value,expected in [(1e-6,'1e-6'),(64,'6.4e1'),(0,'0e0'),(-.0002,'-2e-4'),(1.23456789e-6,'1.23456789e-6')]:
            self.assertEqual(scientific(value),expected)
        self.assertEqual(scientific(np.nan),'nan')
        self.assertEqual(scientific(np.inf),'inf')

    def test_desktop_launcher_uses_current_python_and_icon(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'opencaliper.desktop'
            create_launcher(path,interpreter='/example path/python')
            content=path.read_text(encoding='utf-8')
            self.assertIn('Exec="/example path/python"',content)
            from scripts.create_desktop_launcher import ROOT, desktop_value
            self.assertIn('Icon='+desktop_value(ROOT/'opencaliper/assets/opencaliper.png'),content)
            self.assertIn('StartupWMClass=opencaliper',content)
            with self.assertRaises(FileExistsError): create_launcher(path)

    def test_windows_taskbar_identity_is_set_before_startup(self):
        import ctypes
        from unittest.mock import patch
        from opencaliper.branding import configure_windows_identity, APP_ID
        with patch('opencaliper.branding.sys.platform','win32'), patch.object(ctypes,'windll',create=True) as native:
            configure_windows_identity()
            native.shell32.SetCurrentProcessExplicitAppUserModelID.assert_called_once_with(APP_ID)
