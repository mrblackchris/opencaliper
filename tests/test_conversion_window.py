"""Selectable adapters, paired MAT output and the modeless conversion queue."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import numpy as np
from scipy.io import loadmat
from PySide6 import QtCore, QtGui, QtWidgets as Q
from PySide6.QtTest import QTest
from opencaliper import Recording, Signal, load
from opencaliper.converterscripts import conversion, pairedexport
from opencaliper.gui import Window


EMC_CSV = ('Rg;Frequency;QPK Level;PK+ Level;AVG Level;Correction;Polarization;Antenna Height;Comment\n'
           ';MHz;dBµV/m;dBµV/m;dBµV/m;dB;;m;\n'
           '1;30,0;12,1;18,0;0,8;-16,22;"V";1;measurement\n'
           '1;30,03;11,0;17,0;0,1;-16,21;"V";1;\n')


class ConversionFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder/'receiver.csv'; self.source.write_text(EMC_CSV, encoding='utf-8-sig')


class ConversionTests(ConversionFixture, unittest.TestCase):

    def test_receiver_csv_and_paired_output_preserve_frequency_units_and_levels(self):
        recording = load(self.source)
        self.assertEqual([s.name for s in recording.signals], ['Quasipeak', 'Peak', 'Average'])
        for signal in recording.signals:
            self.assertEqual((signal.domain, signal.unit), ('frequency', 'dBµV/m'))
            np.testing.assert_allclose(signal.time, [30e6, 30.03e6])
        np.testing.assert_allclose(recording.signals[0].values, [12.1, 11.])
        destination = self.folder/'converted.mat'; conversion.convert_one(self.source, destination)
        fields = loadmat(destination)
        self.assertIn('Signal1_u', fields); self.assertIn('Signal1_f', fields)
        self.assertNotIn('Signal1_t', fields)
        for a, b in zip(recording.signals, load(destination).signals):
            self.assertEqual((a.name, a.unit, a.domain), (b.name, b.unit, b.domain))
            np.testing.assert_array_equal(a.time, b.time); np.testing.assert_array_equal(a.values, b.values)
        # A generic numeric table with similar names must not require EMC metadata.
        generic = self.folder/'generic.csv'; generic.write_text('Frequency,QPK Level\n1000,1\n2000,2\n')
        self.assertEqual(load(generic).signals[0].name, 'QPK Level')

    def test_pairs_preserve_mixed_axes_complex_values_and_network_references(self):
        recording = Recording([Signal('Voltage with spaces', [0, .1], [1, 2], 'V'),
                               Signal('S11', [1e6, 2e6], [.1j, .5], domain='sparameter', reference_impedance=75)])
        path = self.folder/'mixed.mat'; pairedexport.write(recording, path)
        fields = loadmat(path); self.assertIn('Signal1_t', fields); self.assertIn('Signal2_f', fields)
        restored = load(path)
        self.assertEqual(restored.signals[1].domain, 'sparameter')
        self.assertEqual(restored.signals[1].reference_impedance, 75)
        np.testing.assert_array_equal(restored.signals[1].values, [.1j, .5])

    def test_custom_script_discovery_does_not_execute_and_reader_can_be_reloaded(self):
        script = self.folder/'custom.py'; marker = self.folder/'executed'
        code = ('from pathlib import Path\nfrom dataclasses import dataclass\n'
                'from opencaliper import Recording, Signal\nCONVERTER_NAME="Custom reader"\n'
                '@dataclass\nclass Settings:\n    value: int = 1\n'
                'def read(path):\n    return Recording([Signal("Custom", [0,1], [1,2], "V")], str(path))\n')
        script.write_text(f'PathMarker = {str(marker)!r}\n'+code+'\nPath(PathMarker).touch()\n', encoding='utf-8')
        spec = next(c for c in conversion.discover(self.folder) if c.script == script)
        self.assertFalse(marker.exists())
        target = self.folder/'custom.mat'; conversion.convert_one(self.source, target, spec)
        self.assertTrue(marker.exists()); np.testing.assert_array_equal(load(target).signals[0].values, [1, 2])
        script.write_text((f'PathMarker = {str(marker)!r}\n'+code+'\nPath(PathMarker).touch()\n').replace('[1,2]', '[3,4]'), encoding='utf-8')
        conversion.convert_one(self.source, target, spec, overwrite=True)
        np.testing.assert_array_equal(load(target).signals[0].values, [3, 4])

    def test_custom_contract_errors_and_copy_template(self):
        script = self.folder/'custom.py'
        for text, expected in [('def convert(path): return None', 'define read'),
                               ('def read(path): return []', 'nonempty Recording'),
                               ('invalid python !', 'syntax')]:
            script.write_text(text, encoding='utf-8')
            with self.subTest(text=text), self.assertRaises((ValueError, SyntaxError)):
                conversion.convert_one(self.source, self.folder/'bad.mat', conversion.Converter('Custom', script=script))
            self.assertFalse((self.folder/'bad.mat').exists())
        template = self.folder/'new_reader.py'; conversion.create_template(template)
        self.assertTrue(any(c.script == template for c in conversion.discover(self.folder)))
        with self.assertRaises(FileExistsError): conversion.create_template(template)
        numeric = self.folder/'data.unknown'; numeric.write_text('0,1\n1,2\n')
        conversion.convert_one(numeric, self.folder/'template-output.mat', conversion.Converter('Template', script=template))

    def test_overwrite_source_collisions_and_atomic_write_failure(self):
        target = self.folder/'existing.mat'; target.write_bytes(b'keep existing content')
        with self.assertRaises(FileExistsError): conversion.convert_one(self.source, target)
        with patch('opencaliper.converterscripts.pairedexport.savemat', side_effect=OSError('disk error')):
            with self.assertRaises(OSError): conversion.convert_one(self.source, target, overwrite=True)
        self.assertEqual(target.read_bytes(), b'keep existing content')
        self.assertFalse(any(p.name.startswith('tmp') for p in self.folder.iterdir()))
        with self.assertRaisesRegex(ValueError, 'must differ'): conversion.convert_one(self.source, self.source, overwrite=True)
        other = self.folder/'other'; other.mkdir()
        with self.assertRaisesRegex(ValueError, 'same output'):
            conversion.plan([self.source, other/self.source.name], self.folder)
        with self.assertRaisesRegex(ValueError, 'replace a selected input'):
            conversion.plan([self.source, self.source.with_suffix('.opencaliper.mat')])

    def test_optional_user_emc_csv(self):
        files = list((Path(__file__).resolve().parents[1]/'examples').glob('RE02*.csv'))
        if not files: self.skipTest('Local measurement is not distributed')
        recording = load(files[0])
        self.assertEqual(len(recording.signals), 3)
        self.assertEqual(len(recording.signals[0].time), 7335)
        self.assertEqual(recording.signals[0].time[0], 30e6)
        self.assertEqual(recording.signals[0].time[-1], 250e6)


class ConversionWindowTests(ConversionFixture, unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = Q.QApplication.instance() or Q.QApplication([])

    def setUp(self):
        super().setUp()
        self.window = Window(); self.window.show()
        self.dialog = self.window.open_converter(); self.app.processEvents()

    def tearDown(self):
        while self.dialog.busy: QTest.qWait(10)
        while self.window.workers: QTest.qWait(10)
        self.dialog.close(); self.window.close(); self.app.processEvents()

    def wait_conversion(self):
        timer = QtCore.QElapsedTimer(); timer.start()
        while self.dialog.busy and timer.elapsed() < 10000: QTest.qWait(10)
        self.assertFalse(self.dialog.busy)

    def test_drop_convert_and_load_result(self):
        dialog = self.dialog; table = dialog.table; view = table.viewport()
        mime = QtCore.QMimeData(); mime.setUrls([QtCore.QUrl.fromLocalFile(str(self.source))])
        enter = QtGui.QDragEnterEvent(QtCore.QPoint(20, 20), QtCore.Qt.DropAction.CopyAction, mime,
                                     QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(view, enter); self.assertTrue(enter.isAccepted())
        event = QtGui.QDropEvent(QtCore.QPointF(20, 20), QtCore.Qt.DropAction.CopyAction, mime,
                                QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(view, event); self.assertTrue(event.isAccepted())
        self.assertEqual(len(dialog.paths), 1)
        dialog.start(); self.wait_conversion()
        self.assertEqual(table.item(0, 1).text(), 'Converted')
        self.assertEqual(len(dialog.outputs), 1); self.assertTrue(dialog.load_button.isEnabled())
        dialog.load_button.click()
        while self.window.workers: QTest.qWait(10)
        self.assertEqual(self.window.workspace.kind, 'spectrum')
        self.assertEqual(len(self.window.plots[0].curves), 3)

    def test_file_picker_custom_script_and_per_file_errors(self):
        script = self.folder/'custom.py'
        script.write_text('from opencaliper import Recording, Signal\n'
                          'def read(path):\n'
                          '    if path.name == "bad.weird": raise ValueError("unsupported input content")\n'
                          '    return Recording([Signal("Custom", [0,1], [1,2])])\n')
        bad = self.folder/'bad.weird'; bad.touch()
        with patch.object(Q.QFileDialog, 'getOpenFileNames', return_value=([str(bad), str(self.source)], '')):
            self.dialog.add_button.click()
        with patch.object(Q.QFileDialog, 'getOpenFileName', return_value=(str(script), '')):
            self.dialog.script_button.click()
        self.dialog.start(); self.wait_conversion()
        self.assertIn('unsupported input content', self.dialog.table.item(0, 1).text())
        self.assertEqual(self.dialog.table.item(1, 1).text(), 'Converted')
        self.assertEqual(len(self.dialog.outputs), 1)

    def test_cancel_finishes_current_file_and_prevents_close_while_busy(self):
        second = self.folder/'second.csv'; second.write_text(EMC_CSV, encoding='utf-8')
        self.dialog.add_files([str(self.source), str(second)])
        entered, release = threading.Event(), threading.Event()
        convert = conversion.convert_one
        def blocked(*args, **kwargs):
            entered.set()
            if not release.wait(5): raise RuntimeError('Test did not release worker')
            return convert(*args, **kwargs)
        with patch('opencaliper.converter_gui.conversion.convert_one', side_effect=blocked):
            self.dialog.start()
            try:
                timer = QtCore.QElapsedTimer(); timer.start()
                while not entered.is_set() and timer.elapsed() < 3000: QTest.qWait(10)
                self.assertTrue(entered.is_set())
                self.assertFalse(self.dialog.close()); self.assertFalse(self.window.close())
                self.assertTrue(self.dialog.busy)
                self.dialog.cancel_conversion()
            finally: release.set()
            self.wait_conversion()
        self.assertEqual(self.dialog.table.item(0, 1).text(), 'Converted')
        self.assertEqual(self.dialog.table.item(1, 1).text(), 'Cancelled')
        self.assertEqual(len(self.dialog.outputs), 1)
