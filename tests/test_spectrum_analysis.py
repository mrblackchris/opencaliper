"""Unified measured/calculated spectra, file drops and old workspace migration."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from scipy.io import savemat
from PySide6 import QtCore, QtGui, QtWidgets as Q
from PySide6.QtTest import QTest
from opencaliper import Recording, Signal, load
from opencaliper.analysis import fft
from opencaliper.gui import Window


class SpectrumAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=Q.QApplication.instance() or Q.QApplication([])

    def setUp(self):
        self.w=Window(); self.w.show(); self.app.processEvents()
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'receiver.mat'
        self.freq=np.array([30e6,40e6,60e6,120e6])
        self.peak=np.array([-20.,-30.,-10.,-40.])
        savemat(self.path,dict(freq=self.freq,avg=self.peak-5,peak=self.peak))

    def tearDown(self):
        while self.w.workers: QTest.qWait(10)
        self.w.close(); self.app.processEvents()

    def drop(self,plot,mime):
        view=plot.viewport()
        enter=QtGui.QDragEnterEvent(QtCore.QPoint(30,30),QtCore.Qt.DropAction.CopyAction,
                                    mime,QtCore.Qt.MouseButton.LeftButton,QtCore.Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(view,enter)
        self.assertTrue(enter.isAccepted())
        event=QtGui.QDropEvent(QtCore.QPointF(30,30),QtCore.Qt.DropAction.CopyAction,
                              mime,QtCore.Qt.MouseButton.LeftButton,QtCore.Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(view,event); self.assertTrue(event.isAccepted())

    def test_toolbar_creates_empty_time_and_spectrum_pages(self):
        actions={a.text():a for bar in self.w.findChildren(Q.QToolBar) for a in bar.actions()}
        self.assertNotIn('New analysis',actions)
        actions['New Spectrum Analysis'].trigger()
        page=self.w.workspace
        self.assertEqual(page.kind,'spectrum')
        self.assertEqual(self.w.tabs.tabText(self.w.tabs.currentIndex()),'Spectrum')
        self.assertFalse(page.plots[0].curves)
        self.assertIsNotNone(page.recalculate)
        actions['New Time Analysis'].trigger()
        self.assertEqual(self.w.workspace.kind,'time')

    def test_time_channel_drop_calculates_fft_and_receiver_file_drop_reuses_page(self):
        w=self.w
        t=np.arange(1024)/1024
        source=Signal('Time',t,np.sin(2*np.pi*64*t),'V')
        w.loaded(Recording([source],'time.mat'))
        page=w.add_analysis('spectrum'); p=page.plots[0]
        mime=w.list.mimeData([w.signal_items[0]])
        with patch.object(w,'error',side_effect=AssertionError): self.drop(p,mime)
        np.testing.assert_allclose(p.display_signals[0].values,fft(source)[1])
        before=w.tabs.count()
        mime=QtCore.QMimeData(); mime.setUrls([QtCore.QUrl.fromLocalFile(str(self.path))])
        with patch('opencaliper.gui.fft',side_effect=AssertionError('Receiver must bypass FFT')):
            self.drop(p,mime)
            for _ in range(500):
                if not w.workers: break
                QTest.qWait(10)
            self.assertFalse(w.workers)
        self.assertEqual(w.tabs.count(),before)
        self.assertEqual(set(p.curves),{0,1,2})
        np.testing.assert_array_equal(p.display_signals[2].values,self.peak)
        original=p.display_signals[2]
        page.use_interval.setChecked(True); page.start_time.setValue(.1); page.stop_time.setValue(.5)
        page.resample_box.setChecked(True); page.sample_rate.setValue(1024)
        with patch.object(w,'error',side_effect=AssertionError): page.recalculate.click()
        self.assertIs(p.display_signals[2],original)
        np.testing.assert_array_equal(p.display_signals[2].time,self.freq)

    def test_peak_alias_and_peak_only_layout(self):
        for data,expected in ((dict(peak=self.peak),self.peak),
                              (dict(pk=self.peak),self.peak),
                              (dict(peak=self.peak,pk=self.peak+20),self.peak)):
            savemat(self.path,dict(freq=self.freq,**data))
            recording=load(self.path)
            self.assertEqual([s.name for s in recording.signals],['Peak'])
            np.testing.assert_array_equal(recording.signals[0].values,expected)

    def test_mixed_workspace_roundtrip_and_legacy_fft_migration(self):
        w=self.w
        w.loaded(load(self.path)); page=w.workspace
        t=np.arange(1024)/1024
        w.loaded(Recording([Signal('Time',t,np.sin(2*np.pi*64*t),'V')],'time.mat'))
        w.add_signal(2,page.plots[0]); page.resample_box.setChecked(True)
        page.sample_rate.setValue(1024); w.recalculate_fft(page)
        state=w.capture_state()
        old=state['pages'][state['current']]; old['kind']='fft'; old['title']='FFT 2'
        with patch.object(w,'error',side_effect=AssertionError): w.restore_state(state)
        self.assertEqual(w.workspace.kind,'spectrum')
        self.assertEqual(w.tabs.tabText(w.tabs.currentIndex()),'Spectrum')
        archive=Path(self.temp.name)/'mixed.ocw'; w.save_workspace(archive)
        other=Window()
        try:
            with patch.object(other,'error',side_effect=AssertionError): other.open_workspace(archive)
            self.assertEqual(other.workspace.kind,'spectrum')
            self.assertTrue(other.workspace.resample_box.isChecked())
            np.testing.assert_array_equal(other.plots[0].display_signals[1].values,self.peak)
            self.assertEqual(other.plots[0].display_signals[2].domain,'frequency')
        finally: other.close()

    def test_negative_receiver_levels_switch_log_y_off(self):
        page=self.w.add_analysis('spectrum'); plot=page.plots[0]
        plot.log_y_box.setChecked(True)
        self.w.loaded(load(self.path))
        self.assertIs(self.w.workspace,page)
        self.assertFalse(plot.log_y_box.isChecked())
        np.testing.assert_array_equal(plot.display_signals[1].values,self.peak)

    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'examples/esrpSpectrumfile.mat').exists(),
                         'Local receiver example is not distributed')
    def test_local_receiver_example(self):
        path=Path(__file__).resolve().parents[1]/'examples/esrpSpectrumfile.mat'
        recording=load(path)
        self.assertEqual([s.name for s in recording.signals],['Average','Peak'])
        self.assertTrue(all(s.domain=='frequency' and len(s.time)==3001 for s in recording.signals))
        with patch('opencaliper.gui.fft',side_effect=AssertionError('Unexpected FFT')):
            self.w.loaded(recording)
        self.assertEqual(self.w.workspace.kind,'spectrum')
        self.assertEqual(len(self.w.plots[0].curves),2)
