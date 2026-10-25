"""Receiver spectra are native frequency data, never FFT input."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from scipy.io import savemat
from PySide6 import QtWidgets as Q
from opencaliper import Signal, Recording, load, export
from opencaliper.analysis import fft
from opencaliper.processing import filtered, expression
from opencaliper.gui import Window


class EsrpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = Q.QApplication.instance() or Q.QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'esrp.mat'
        self.freq = np.array([1e6, 2e6, 4e6, 8e6])
        self.avg = np.array([-50., -40., -60., -30.])
        savemat(self.path,dict(freq=self.freq[None,:],avg=self.avg[:,None],pk=self.avg+10,qpk=self.avg+5))

    def window(self):
        w = Window(); self.addCleanup(w.close)
        return w

    def test_detector_vectors_and_defaults(self):
        recording = load(self.path)
        self.assertEqual([s.name for s in recording.signals],['Average','Peak','Quasipeak'])
        for s,offset in zip(recording.signals,[0,10,5]):
            self.assertEqual(s.domain,'frequency'); self.assertEqual(s.unit,'')
            np.testing.assert_array_equal(s.time,self.freq)
            np.testing.assert_array_equal(s.values,self.avg+offset)

    def test_v73_units_and_missing_detectors(self):
        import hdf5storage
        self.path.unlink()
        hdf5storage.savemat(self.path,dict(freq=self.freq/1e6,pk=self.avg,freq_unit='MHz',pk_unit='dBm'),format='7.3',appendmat=False)
        s = load(self.path).signals[0]
        self.assertEqual(s.name,'Peak'); self.assertEqual(s.unit,'dBm')
        np.testing.assert_array_equal(s.time,self.freq)

    def test_invalid_vector_shapes_lengths_and_axis(self):
        for variables in (dict(freq=self.freq,avg=[1,2]),dict(freq=[[1,2],[3,4]],avg=self.avg),
                          dict(freq=[1,2,2,4],avg=self.avg),dict(freq=[1,np.nan,3,4],avg=self.avg),
                          dict(freq=self.freq,avg=np.ones((2,2)))):
            with self.subTest(variables=variables):
                savemat(self.path,variables)
                with self.assertRaises(ValueError): load(self.path)

    def test_native_conversion_preserves_domain(self):
        destination = self.path.with_name('native.mat')
        export(load(self.path),destination)
        restored = load(destination)
        self.assertEqual(restored.signals[0].domain,'frequency')
        np.testing.assert_array_equal(restored.signals[0].time,self.freq)
        with self.assertRaisesRegex(ValueError,'Frequency-domain'):
            export(restored,self.path.with_suffix('.mf4'))
        with self.assertRaisesRegex(ValueError,'already frequency-domain'): fft(restored.signals[0])
        with self.assertRaisesRegex(ValueError,'requires time-domain'): filtered(restored.signals[0],'lowpass',1)
        result = expression('a+1',{'a':restored.signals[0]})
        self.assertEqual(result.domain,'frequency')

    def test_auto_plot_frequency_cursor_and_no_fft(self):
        w = self.window()
        with patch('opencaliper.gui.fft',side_effect=AssertionError('Unexpected FFT')):
            w.loaded(load(self.path))
            self.assertEqual(w.workspace.kind,'spectrum')
            self.assertEqual(w.tabs.tabText(w.tabs.currentIndex()),'Spectrum')
            p = w.plots[0]
            self.assertEqual(set(p.curves),{0,1,2})
            self.assertEqual(p.getAxis('bottom').labelUnits,'Hz')
            self.assertFalse(p.log_y)
            self.assertFalse(p.curves[0].opts['autoDownsample'])
            np.testing.assert_array_equal(p.display_signals[0].values,self.avg)
            w.cursors_enabled.setChecked(True)
            w.move_cursor(0,1e6); w.move_cursor(1,2e6)
            self.assertIn('Hz',w.readout.toPlainText()); self.assertIn('Δf',w.readout.toPlainText())
            self.assertNotIn('Δt',w.readout.toPlainText())
            another=w.spectrum()
            self.assertEqual(another.kind,'spectrum')
            self.assertEqual(w.tabs.count(),3)

    def test_plot_rename_menu_undo_and_workspace(self):
        w = self.window(); w.loaded(load(self.path))
        p = w.plots[0]
        w.add_plot(); w.add_signal(0,w.plots[1])
        menu = w.axis_menu(p,[0])
        with patch.object(Q.QInputDialog,'getText',return_value=('My average',True)):
            next(a for a in menu.actions() if a.text()=='Rename signal…').trigger()
        self.assertEqual(w.display_name(p,0),'My average')
        self.assertEqual(w.display_name(w.plots[1],0),'Average')
        self.assertEqual(w.signals[0].name,'Average')
        self.assertIn('My average',p.signal_list.item(0).text())
        self.assertIn('My average',p.curves[0].name())
        self.assertIn('My average',p.plotItem.legend.items[0][1].text)
        w.cursors_enabled.setChecked(True)
        self.assertIn('My average',w.readout.toPlainText())
        w.undo(); self.assertEqual(w.display_name(w.plots[0],0),'Average')
        w.redo(); self.assertEqual(w.display_name(w.plots[0],0),'My average')
        archive=self.path.with_suffix('.ocw'); w.save_workspace(archive)
        other=self.window()
        with patch.object(other,'error',side_effect=AssertionError): other.open_workspace(archive)
        self.assertEqual(other.workspace.kind,'spectrum')
        self.assertEqual(other.signals[0].domain,'frequency')
        self.assertEqual(other.display_name(other.plots[0],0),'My average')
        self.assertEqual(other.tabs.count(),2)
        menu.deleteLater()

    def test_renamed_source_unload_can_be_undone(self):
        w=self.window(); w.loaded(load(self.path))
        with patch.object(Q.QInputDialog,'getText',return_value=('My average',True)):
            w.rename_signals(w.plots[0],[0])
        w.remove_files([0]); w.undo()
        self.assertEqual(w.display_name(w.plots[0],0),'My average')

    def test_time_channel_fft_does_not_use_spectrum_cursors(self):
        w=self.window()
        time=np.arange(32)/32
        w.loaded(Recording([Signal('Time',time,np.sin(2*np.pi*4*time)),
                            Signal('Spectrum',self.freq,self.avg,domain='frequency')],'mixed.mat'))
        self.assertEqual(w.workspace.kind,'spectrum')
        w.cursors_enabled.setChecked(True)
        w.move_cursor(0,1e6); w.move_cursor(1,2e6)
        w.list.setCurrentItem(w.signal_items[0])
        with patch.object(w,'error',side_effect=AssertionError): page=w.spectrum()
        self.assertEqual(page.kind,'spectrum')
        self.assertEqual(page.fft_interval,(None,None))
        self.assertIn(0,page.plots[0].curves)

    def test_renaming_second_subplot_updates_its_readout_and_axis(self):
        w=self.window(); w.loaded(load(self.path))
        w.add_plot(); w.add_signal(0,w.plots[1])
        with patch.object(Q.QInputDialog,'getText',return_value=('Second plot average',True)):
            w.rename_signals(w.plots[1],[0])
        w.separate_signal_axes(w.plots[1],[0])
        axis = w.plots[1].extra_axes[w.plots[1].signal_axes[0]][0]
        self.assertIn('Second plot average',axis.labelText)
        w.cursors_enabled.setChecked(True)
        self.assertIn('Average:',w.readout.toPlainText())
        self.assertIn('Second plot average:',w.readout.toPlainText())
