"""CSV dialect/header detection and coexistence of supported MAT signal layouts."""
from datetime import datetime
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from scipy.io import savemat
from opencaliper import load, export
from opencaliper.converterscripts.matpreparse import detect_layouts
from opencaliper.converterscripts.formats import input_filter


class CsvAndPairedMatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def csv(self, text, encoding='utf-8'):
        path = self.folder/'measurement.CSV'; path.write_bytes(text.encode(encoding))
        return load(path)

    def mat(self, data, v73=False):
        path = self.folder/'measurement.mat'
        if v73:
            import hdf5storage
            path.unlink(missing_ok=True)
            hdf5storage.savemat(str(path), data, format='7.3', appendmat=False)
        else: savemat(path, data)
        return load(path)

    def test_csv_common_separators_names_and_units(self):
        for separator in (',', ';', '\t', '|', ' '):
            with self.subTest(separator=separator):
                text = '\n'.join(separator.join(row) for row in
                                 [('Time', 'Voltage', 'Current'), ('0', '1', '2'), ('0.1', '3', '4')])
                recording = self.csv(text)
                self.assertEqual([s.name for s in recording.signals], ['Voltage', 'Current'])
                np.testing.assert_allclose(recording.signals[0].time, [0, .1])
                np.testing.assert_array_equal(recording.signals[1].values, [2, 4])
        recording = self.csv('Time [ms];Voltage [mV]\n0;1\n2;3\n')
        np.testing.assert_allclose(recording.signals[0].time, [0, .002])
        self.assertEqual((recording.signals[0].name, recording.signals[0].unit), ('Voltage', 'mV'))
        self.assertIn('*.csv', input_filter())

    def test_two_metadata_rows_numeric_third_row(self):
        for text in ('Measurement name: supply\nA comment about the measurement\n0,1\n1,2\n',
                     'Time,Supply\nThis is an unmarked comment\n0,1\n1,2\n',
                     'Time,Supply\n# comment,not another signal\n0,1\n1,2\n',
                     'Time,Supply\nmeasurement comment,more text\n0,1\n1,2\n'):
            with self.subTest(text=text):
                recording = self.csv(text)
                self.assertEqual(len(recording.signals), 1)
                np.testing.assert_array_equal(recording.signals[0].time, [0, 1])
                np.testing.assert_array_equal(recording.signals[0].values, [1, 2])
        self.assertEqual(self.csv('Supply\nA comment\n0,1\n1,2\n').signals[0].name, 'Supply')

    def test_csv_quotes_units_row_decimal_comma_and_encodings(self):
        text = 'Capture: bench test\nTime;"Voltage, supply"\nms;V\n0,0;1,25\n2,5;2,75\n'
        for encoding in ('utf-8-sig', 'utf-16', 'cp1252'):
            with self.subTest(encoding=encoding):
                signal = self.csv(text, encoding).signals[0]
                self.assertEqual((signal.name, signal.unit), ('Voltage, supply', 'V'))
                np.testing.assert_allclose(signal.time, [0, .0025])
                np.testing.assert_allclose(signal.values, [1.25, 2.75])
        signal = self.csv('# frequency [MHz],Peak [dBm]\n1,-40\n2,-30\n').signals[0]
        self.assertEqual((signal.domain, signal.unit), ('frequency', 'dBm'))
        np.testing.assert_array_equal(signal.time, [1e6, 2e6])
        signal = self.csv('Time [µs];Voltage [µV]\n0;1\n2;3\n', 'cp1252').signals[0]
        self.assertEqual(signal.unit, 'µV')
        np.testing.assert_allclose(signal.time, [0, 2e-6])
        signal = self.csv('MHz,V\n1,2\n3,4\n').signals[0]
        self.assertEqual(signal.domain, 'frequency')
        np.testing.assert_array_equal(signal.time, [1e6, 3e6])
        self.assertEqual(self.csv('sep=;\nTime;Voltage\n0;1\n2;3\n').signals[0].name, 'Voltage')

    def test_headerless_table_missing_amplitudes_and_extra_index(self):
        recording = self.csv('0,1,2,\n1,,N/A,\n2,3,4,\n')
        self.assertEqual([s.name for s in recording.signals], ['Channel1', 'Channel2'])
        self.assertTrue(np.isnan(recording.signals[0].values[1]))
        recording = self.csv('Index,Time [us],Voltage [V]\n0,0,1\n1,2,3\n')
        self.assertEqual(len(recording.signals), 1)
        np.testing.assert_allclose(recording.signals[0].time, [0, 2e-6])

    def test_csv_paired_independent_axes_and_mixed_domains(self):
        recording = self.csv('Signal1_t [ms],Signal1_u [V],Signal2_f [MHz],Signal2_u [dB]\n'
                             '0,1,1,-40\n2,3,2,-30\n4,5,,\n')
        self.assertEqual([s.name for s in recording.signals], ['Signal1', 'Signal2'])
        np.testing.assert_allclose(recording.signals[0].time, [0, .002, .004])
        np.testing.assert_array_equal(recording.signals[1].time, [1e6, 2e6])
        self.assertEqual(recording.signals[1].domain, 'frequency')

    def test_csv_rejects_bad_body_and_invalid_axes(self):
        for text, expected in (
            ('Time,V\n0,1\n1,bad\n2,3\n', 'line 3'),
            ('Time,V\n0,1\n1,2,3\n', 'line 3'),
            ('Time,V\n0,1\n,2\n', 'coordinate'),
            ('Time,V\n1,1\n0,2\n', 'nondecreasing'),
            ('Frequency,V\n-1,2\n0,3\n', 'nonnegative'),
            ('Time [bananas],V\n0,1\n1,2\n', 'axis unit'),
            ('Time,Frequency,V\n0,1,2\n1,2,3\n', 'multiple shared axes'),
            ('Signal1_u,Other\n1,2\n3,4\n', 'exactly one'),
            ('Signal1_t,Signal1_t,Signal1_u\n0,0,1\n1,1,2\n', 'duplicate'),
        ):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, expected): self.csv(text)

    def test_paired_mat_time_frequency_complex_and_numeric_order(self):
        data = dict(Signal10_u=np.array([1+2j, 3+4j]), Signal10_f=[1, 2], Signal10_f_unit='MHz',
                    Signal2_u=np.array([[5], [6], [7]]), Signal2_t=[0, 2, 4], Signal2_t_unit='ms',
                    Signal2_unit='V', Signal2_name='Supply', date='unknown', time='unsupported')
        for v73 in (False, True):
            with self.subTest(v73=v73):
                recording = self.mat(data, v73)
                self.assertEqual([s.name for s in recording.signals], ['Supply', 'Signal10'])
                self.assertEqual(recording.timestamp, datetime(1970, 1, 1))
                np.testing.assert_allclose(recording.signals[0].time, [0, .002, .004])
                np.testing.assert_allclose(recording.signals[1].time, [1e6, 2e6])
                np.testing.assert_array_equal(recording.signals[1].values, [1+2j, 3+4j])
                self.assertEqual(recording.signals[1].domain, 'frequency')

    def test_preparser_merges_supported_mat_layouts_and_retains_old_formats(self):
        native = dict(signal_0_values=[1, 2], signal_0_name='Native', signal_0_time=[0, 1], signal_0_unit='A')
        paired = dict(Signal1_u=[3, 4], Signal1_t=[0, 1])
        receiver = dict(freq=[1e6, 2e6], peak=[-40, -30])
        acquisition = dict(points=2, xinc=.1, Channel1_t1=np.array([5., 6.]), Channel1_unit='V')
        self.assertEqual(detect_layouts({**native, **paired, **receiver, **acquisition}),
                         ('native', 'paired', 'receiver', 'acquisition'))
        for layout in (native, paired, receiver, acquisition):
            self.assertEqual(len(self.mat(layout).signals), 1)
        self.assertEqual([s.name for s in self.mat({**native, **paired, **receiver, **acquisition}).signals],
                         ['Native', 'Signal1', 'Peak', 'Channel1'])

    def test_paired_mat_rejects_ambiguous_missing_or_invalid_pairs(self):
        for data, expected in (
            (dict(Signal1_u=[1, 2]), 'exactly one'),
            (dict(Signal1_u=[1, 2], Signal1_t=[0, 1], Signal1_f=[1, 2]), 'exactly one'),
            (dict(Signal1_u=[1, 2], Signal1_t=[0, 1, 2]), 'mismatched'),
            (dict(Signal1_u=np.ones((2, 2)), Signal1_t=[0, 1, 2, 3]), 'vector'),
            (dict(Signal1_u=[1, 2], Signal1_t=[0, np.nan]), 'finite'),
            (dict(Signal1_u=[1, 2], Signal1_t=[0, 1j]), 'must be real'),
            (dict(Signal1_u=[1, 2], Signal1_f=[-1, 1]), 'nonnegative'),
        ):
            with self.subTest(data=data):
                with self.assertRaisesRegex(ValueError, expected): self.mat(data)

    def test_csv_cli_and_native_mat_conversion(self):
        from opencaliper.cli import main
        self.csv('Frequency [MHz],Peak [dBm]\n1,-40\n2,-30\n')
        source = self.folder/'measurement.CSV'; destination = self.folder/'native.mat'
        with patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(main(['convert', str(source), str(destination)]), 0)
        signal = load(destination).signals[0]
        self.assertEqual((signal.domain, signal.name, signal.unit), ('frequency', 'Peak', 'dBm'))
        np.testing.assert_array_equal(signal.time, [1e6, 2e6])
        with self.assertRaisesRegex(ValueError, 'Unsupported output format'):
            export(load(destination), self.folder/'export.csv')

    def test_new_inputs_route_frequency_signals_to_spectrum_without_fft(self):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        from PySide6 import QtWidgets as Q
        from opencaliper.gui import Window
        app = Q.QApplication.instance() or Q.QApplication([])
        recording = self.mat(dict(Signal1_u=[1, 2], Signal1_t=[0, .1],
                                  Signal2_u=[1+2j, 3+4j], Signal2_f=[1e6, 2e6]))
        window = Window()
        try:
            with patch.object(window, 'error', side_effect=AssertionError), patch('opencaliper.gui.fft', side_effect=AssertionError('Unexpected FFT')):
                window.loaded(recording)
                self.assertEqual(window.workspace.kind, 'spectrum')
                np.testing.assert_allclose(window.plots[0].display_signals[1].values, [np.sqrt(5), 5])
                page = window.add_analysis('time'); window.add_signal(0, page.plots[0])
                np.testing.assert_array_equal(page.plots[0].display_signals[0].values, [1, 2])
                window.loaded(self.csv('Frequency [MHz],Peak [dB]\n1,-40\n2,-30\n'))
                self.assertEqual(window.workspace.kind, 'spectrum')
                self.assertEqual(len(window.plots[0].curves), 1)
        finally:
            window.close(); app.processEvents()
