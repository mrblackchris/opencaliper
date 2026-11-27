"""Converter preprocessing, anti-aliasing and full-size MAT round trips."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
import numpy as np
from PySide6 import QtWidgets as Q
from PySide6.QtTest import QTest
from opencaliper import Signal, Recording, load
from opencaliper.converterscripts import pairedexport, conversion
from opencaliper.converterscripts.preprocessing import prepare
from opencaliper.converter_gui import ConverterDialog


class ConverterProcessingTests(unittest.TestCase):
    def test_shared_grid_accepts_ten_seconds_at_200_nanoseconds(self):
        rate = 1/(200e-9)
        self.assertEqual(pairedexport.shared_sample_count(0, 10-200e-9, rate), 50_000_000)
        self.assertEqual(pairedexport.shared_sample_count(0, 10, rate), 50_000_001)
        self.assertEqual(pairedexport.shared_sample_count(0, 99_999_999/rate, rate), 100_000_000)
        with self.assertRaisesRegex(ValueError, '100 million'):
            pairedexport.shared_sample_count(0, 100_000_000/rate, rate)

    def setUp(self):
        self.t = np.arange(8000)/2000
        self.low = np.sin(2*np.pi*20*self.t)
        self.high = np.sin(2*np.pi*720*self.t)
        self.r = Recording([Signal('Voltage', self.t, self.low+self.high, 'V')], 'input.mat')

    def test_filtering_precedes_downsampling_and_preserves_source(self):
        for kind, cutoff, expected in [('lowpass', 70, self.low), ('highpass', 300, self.high)]:
            result = prepare(self.r, filter_kind=kind, cutoff=cutoff).signals[0]
            np.testing.assert_allclose(result.values[500:-500], expected[500:-500], atol=.005)
            self.assertEqual((result.name, result.unit), ('Voltage', 'V'))
        result = prepare(self.r, downsample=4).signals[0]
        np.testing.assert_allclose(result.time, self.t[::4])
        np.testing.assert_allclose(result.values[100:-100], self.low[::4][100:-100], atol=.005)
        combined = prepare(self.r, downsample=4, filter_kind='highpass', cutoff=80).signals[0]
        np.testing.assert_allclose(combined.values[100:-100], 0, atol=.005)
        np.testing.assert_array_equal(self.r.signals[0].values, self.low+self.high)
        self.assertIs(prepare(self.r), self.r)

    def test_invalid_processing_does_not_write_output(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'in.mat'; target = Path(folder)/'out.mat'
            pairedexport.write(self.r, source)
            for options in [dict(downsample=0), dict(cutoff=2000, filter_kind='lowpass'),
                            dict(downsample=4, cutoff=400, filter_kind='highpass')]:
                with self.assertRaises(ValueError): conversion.convert_one(source, target, **options)
                self.assertFalse(target.exists())
        frequency = Recording([Signal('sweep', [1, 2, 3, 4], [1, 2, 3, 4], domain='frequency')])
        with self.assertRaisesRegex(ValueError, 'time-domain'): prepare(frequency, downsample=2)
        irregular = Recording([Signal('uneven', [0, .1, .3, .4], [1, 2, 3, 4])])
        with self.assertRaisesRegex(ValueError, 'Uniform'): prepare(irregular, downsample=2)

    def test_export_over_one_million_points_in_both_layouts(self):
        count = 1_100_001
        t = np.arange(count)/100000
        y = np.sin(t)
        r = Recording([Signal('Large', t, y, 'V')])
        with tempfile.TemporaryDirectory() as folder:
            for mode in ('per_signal', 'shared_time'):
                for compress in (False, True):
                    target = Path(folder)/(mode+str(compress)+'.mat')
                    pairedexport.write(r, target, axis_mode=mode, compress=compress,
                                       resample=mode == 'shared_time', sample_rate=100000)
                    restored = load(target).signals[0]
                    self.assertEqual(len(restored.time), count)
                    np.testing.assert_allclose(restored.time, t, atol=1e-12)
                    np.testing.assert_allclose(restored.values, y, atol=1e-12)


class ConverterProcessingWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = Q.QApplication.instance() or Q.QApplication([])

    def test_worker_uses_processing_controls_and_shared_layout(self):
        dialog = ConverterDialog()
        try:
            self.assertFalse(dialog.filter_cutoff.isEnabled())
            dialog.filter_kind.setCurrentIndex(1)
            self.assertTrue(dialog.filter_cutoff.isEnabled())
            dialog.filter_cutoff.setValue(30); dialog.filter_order.setValue(4)
            dialog.downsample.setValue(4); dialog.axis_mode.setCurrentIndex(1)
            dialog.compress.setChecked(False)
            with tempfile.TemporaryDirectory() as folder:
                t = np.arange(4000)/1000
                source = Path(folder)/'source.mat'
                pairedexport.write(Recording([Signal('One', t, np.sin(2*np.pi*10*t), 'V')]), source)
                dialog.add_files([source]); dialog.start()
                self.assertFalse(dialog.downsample.isEnabled())
                for _ in range(1000):
                    if not dialog.busy: break
                    QTest.qWait(10)
                self.assertFalse(dialog.busy)
                self.assertEqual(len(dialog.outputs), 1, dialog.table.item(0, 1).text())
                restored = load(dialog.outputs[0]).signals[0]
                self.assertEqual(len(restored.time), 1000)
                np.testing.assert_allclose(restored.time, t[::4])
                self.assertEqual(restored.name, 'One')
                self.assertTrue(dialog.downsample.isEnabled())
        finally:
            while dialog.busy: QTest.qWait(10)
            dialog.close(); self.app.processEvents()
