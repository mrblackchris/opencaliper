"""Explicit FFT resampling for irregular acquisition timestamps."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets as Q
from PySide6.QtTest import QTest
from opencaliper import Signal, Recording, export
from opencaliper.analysis import fft
from opencaliper.gui import Window


def irregular_tone():
    base=np.arange(4096)/1024
    time=base+0.08/1024*np.sin(np.arange(len(base))*1.7)
    time[0]=base[0]; time[-1]=base[-1]
    return Signal('Irregular',time,3*np.sin(2*np.pi*64*time),'V')


class ResampleTests(unittest.TestCase):
    def test_interpolated_fft_recovers_known_tone_without_changing_source(self):
        source=irregular_tone(); time=source.time.copy(); values=source.values.copy()
        with self.assertRaisesRegex(ValueError,'Resample'): fft(source)
        f,a=fft(source,resample=True,sample_rate=1024)
        self.assertAlmostEqual(f[np.argmax(a)],64,places=8)
        self.assertAlmostEqual(a.max(),3,delta=.02)
        np.testing.assert_array_equal(source.time,time)
        np.testing.assert_array_equal(source.values,values)

    def test_auto_rate_uses_median_interval(self):
        source=irregular_tone()
        auto=fft(source,resample=True)
        explicit=fft(source,resample=True,sample_rate=1/np.median(np.diff(source.time)))
        np.testing.assert_allclose(auto,explicit)
        self.assertAlmostEqual(auto[0][np.argmax(auto[1])],64,delta=.3)

    def test_uniform_fft_is_unchanged(self):
        time=np.arange(1024)/1024
        source=Signal('uniform',time,np.sin(2*np.pi*64*time))
        normal=fft(source); resampled=fft(source,resample=True,sample_rate=1024)
        np.testing.assert_allclose(normal,resampled,atol=1e-12)

    def test_invalid_resampling_settings_and_samples(self):
        source=irregular_tone()
        for rate in (0,-1,np.nan,np.inf):
            with self.subTest(rate=rate), self.assertRaisesRegex(ValueError,'finite and positive'):
                fft(source,resample=True,sample_rate=rate)
        with self.assertRaisesRegex(ValueError,'10 million'): fft(source,resample=True,sample_rate=1e12)
        with self.assertRaisesRegex(ValueError,'fewer than four'): fft(source,resample=True,sample_rate=.01)
        with self.assertRaisesRegex(ValueError,'Enable resampling'): fft(source,sample_rate=1024)
        with self.assertRaisesRegex(ValueError,'duplicate timestamps'):
            fft(Signal('duplicate',[0,1,1,2],[0,1,2,3]),resample=True)
        with self.assertRaisesRegex(ValueError,'NaN/Inf'):
            fft(Signal('missing',[0,1,2,3],[0,1,np.nan,3]),resample=True)


class ResampleGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=Q.QApplication.instance() or Q.QApplication([])

    def setUp(self):
        self.w=Window(); self.source=irregular_tone()
        self.w.loaded(Recording([self.source],'irregular.mat'))
        self.w.list.setCurrentItem(self.w.signal_items[0])

    def tearDown(self): self.w.close(); self.app.processEvents()

    def test_retry_pending_fft_and_keep_settings_on_new_tab(self):
        w=self.w
        with patch.object(w,'error') as error: page=w.spectrum()
        self.assertIn('Resample',error.call_args.args[0]); self.assertEqual(page.pending_signals,{0})
        page.resample_box.setChecked(True); page.sample_rate.setValue(1024)
        with patch.object(w,'error',side_effect=AssertionError): page.recalculate.click()
        self.assertFalse(page.pending_signals); self.assertTrue(page.fft_resample)
        self.assertIn(0,page.plots[0].curves)
        spectrum=page.plots[0].display_signals[0]
        self.assertAlmostEqual(spectrum.time[np.argmax(spectrum.values)],64)
        with patch.object(w,'error',side_effect=AssertionError): other=w.spectrum()
        self.assertTrue(other.fft_resample); self.assertEqual(other.fft_sample_rate,1024)
        self.assertIn(0,other.plots[0].curves)

    def test_workspace_roundtrip_and_failed_recalculation_are_atomic(self):
        w=self.w
        with patch.object(w,'error'): page=w.spectrum()
        page.resample_box.setChecked(True); page.sample_rate.setValue(1024)
        w.recalculate_fft(page)
        original=page.plots[0].display_signals[0]
        page.sample_rate.setValue(.01)
        with patch.object(w,'error') as error: w.recalculate_fft(page)
        error.assert_called_once()
        self.assertEqual(page.fft_sample_rate,1024)
        self.assertIs(page.plots[0].display_signals[0],original)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'resampled.ocw'; w.save_workspace(path)
            other=Window()
            try:
                with patch.object(other,'error',side_effect=AssertionError): other.open_workspace(path)
                self.assertTrue(other.workspace.fft_resample)
                self.assertEqual(other.workspace.sample_rate.value(),1024)
                np.testing.assert_allclose(other.plots[0].display_signals[0].values,original.values)
            finally: other.close()

    def test_cli_resampling(self):
        from opencaliper.cli import main
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'input.mat'; destination=Path(folder)/'fft.csv'
            export(Recording([self.source]),source)
            self.assertEqual(main(['fft',str(source),str(destination),'--resample','--sample-rate','1024']),0)
            result=np.loadtxt(destination,delimiter=',',skiprows=1)
            self.assertAlmostEqual(result[np.argmax(result[:,1]),0],64)

    def test_visible_checkbox_and_one_click_retry_after_nonuniform_fft_failure(self):
        w = self.w; w.resize(1050, 700); w.show()
        with patch.object(w, 'error'): page = w.spectrum()
        self.app.processEvents()
        self.assertTrue(page.resample_box.isEnabled())
        self.assertTrue(page.resample_retry.isVisible())
        self.assertIn('uniform samples', page.fft_problem.text())
        # Plot/readout dividers cannot collapse the settings above them.
        page.content_splitter.moveSplitter(0, 1); self.app.processEvents()
        center = page.resample_box.mapToGlobal(QtCore.QPoint(8, page.resample_box.height()//2))
        self.assertIs(Q.QApplication.widgetAt(center), page.resample_box)
        QTest.mouseClick(page.resample_box, QtCore.Qt.MouseButton.LeftButton,
                         pos=QtCore.QPoint(8, page.resample_box.height()//2))
        self.assertTrue(page.resample_box.isChecked()); self.assertTrue(page.sample_rate.isEnabled())
        page.resample_box.setChecked(False)
        time, values = self.source.time.copy(), self.source.values.copy()
        with patch.object(w, 'error', side_effect=AssertionError):
            QTest.mouseClick(page.resample_retry, QtCore.Qt.MouseButton.LeftButton)
        self.assertTrue(page.fft_resample); self.assertFalse(page.pending_signals)
        self.assertFalse(page.resample_retry.isVisible()); self.assertFalse(page.fft_problem.isVisible())
        spectrum = page.plots[0].display_signals[0]
        self.assertAlmostEqual(spectrum.time[np.argmax(spectrum.values)], 64, delta=.3)
        np.testing.assert_array_equal(self.source.time, time)
        np.testing.assert_array_equal(self.source.values, values)

    def test_settings_remain_visible_with_large_font(self):
        font = QtGui.QFont(self.w.font()); font.setPointSize(28)
        self.w.setFont(font); self.w.resize(1200, 800); self.w.show()
        page = self.w.add_analysis('spectrum'); self.app.processEvents()
        for control in (page.resample_box, page.sample_rate, page.recalculate):
            self.assertTrue(page.fft_settings.rect().contains(control.mapTo(page.fft_settings, control.rect().bottomRight())))
        self.assertGreaterEqual(page.fft_settings.height(), page.fft_settings.minimumSizeHint().height())
