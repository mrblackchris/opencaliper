"""AC RAW complex samples, physical Hz axes and Spectrum integration."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from PySide6 import QtWidgets as Q
from opencaliper import load, export
from opencaliper.gui import Window


def write_ac(path, encoding='utf-8', binary=False):
    header = ('Title: synthetic AC fixture\nDate: Sun Nov 1 08:16:44 2026\n'
              'Plotname: AC Analysis\nFlags: complex forward log\n'
              'No. Variables: 3\nNo. Points: 4\nOffset: 0\n'
              'Command: LTspice\nVariables:\n'
              '\t0\tfrequency\tfrequency\n\t1\tV(out)\tvoltage\n\t2\tI(R1)\tcurrent\n')
    frequency = np.array([1e3, 2e3, 3e3, 4e3])
    voltage = np.array([1+2j, 3-4j, -1j, 0j])
    current = voltage*.01
    if binary:
        data = np.column_stack((frequency, voltage, current)).astype('<c16')
        path.write_bytes((header+'Binary:\n').encode(encoding)+data.tobytes())
    else:
        rows = ''.join(f'{i}\t{f},0\n\t{v.real},{v.imag}\n\t{a.real},{a.imag}\n'
                       for i, (f, v, a) in enumerate(zip(frequency, voltage, current)))
        path.write_bytes((header+'Values:\n'+rows).encode(encoding))
    return frequency, voltage, current


class RawACTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def test_ascii_and_binary_complex_samples_and_mat_roundtrip(self):
        for encoding, binary in [('utf-8', False), ('utf-16-le', True)]:
            with self.subTest(encoding=encoding, binary=binary):
                path = self.folder/'ac.raw'
                frequency, voltage, current = write_ac(path, encoding, binary)
                recording = load(path)
                self.assertEqual([s.name for s in recording.signals], ['V(out)', 'I(R1)'])
                for signal, expected, unit in zip(recording.signals, (voltage, current), ('V', 'A')):
                    np.testing.assert_array_equal(signal.time, frequency)
                    np.testing.assert_allclose(signal.values, expected)
                    self.assertEqual((signal.domain, signal.unit), ('frequency', unit))
                mat = self.folder/'ac.mat'; export(recording, mat, overwrite=True)
                np.testing.assert_allclose(load(mat).signals[0].values, voltage)
                with self.assertRaisesRegex(ValueError, 'Frequency-domain'):
                    export(recording, self.folder/'bad.raw')

    def test_ac_opens_in_spectrum_with_magnitude_and_cursor_readouts(self):
        app = Q.QApplication.instance() or Q.QApplication([])
        path = self.folder/'ac.raw'; frequency, voltage, _ = write_ac(path)
        window = Window()
        try:
            with patch.object(window, 'error', side_effect=AssertionError):
                window.loaded(load(path))
                self.assertEqual(window.workspace.kind, 'spectrum')
                plot = window.plots[0]
                np.testing.assert_allclose(plot.display_signals[0].values, np.abs(voltage))
                np.testing.assert_allclose(window.signals[0].values, voltage)
                window.move_cursor(0, frequency[0]); window.move_cursor(1, frequency[1])
                self.assertIn('V(out): A', window.readout.toPlainText())
                window.recalculate_fft(window.workspace)
                np.testing.assert_allclose(plot.display_signals[0].values, np.abs(voltage))
        finally:
            window.close(); app.processEvents()

    def test_optional_reported_file(self):
        fixture = os.environ.get('OPENCALIPER_AC_RAW_FIXTURE')
        if not fixture: self.skipTest('Set OPENCALIPER_AC_RAW_FIXTURE to the reported local simulation')
        path = Path(fixture)
        recording = load(path)
        self.assertEqual(len(recording.signals), 4)
        self.assertEqual(len(recording.signals[0].values), 501)
        self.assertEqual(recording.signals[0].domain, 'frequency')
        self.assertEqual(recording.signals[0].time[0], 1e3)
        self.assertAlmostEqual(recording.signals[0].values[0].real, .4998898306616842)
        self.assertAlmostEqual(recording.signals[0].values[0].imag, -.004961386709731610)
