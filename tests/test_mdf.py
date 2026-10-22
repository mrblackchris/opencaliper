"""Real MDF files, including conversions commonly found in acquisition data."""
from pathlib import Path
import tempfile
import unittest
import numpy as np
from asammdf import MDF, Signal as MSignal
from opencaliper.core import load


class MdfTests(unittest.TestCase):
    def test_numeric_conversions_and_labelled_states(self):
        with tempfile.TemporaryDirectory() as folder:
            for version, extension in [('3.30', 'mdf'), ('4.10', 'mf4')]:
                with self.subTest(version=version):
                    path = Path(folder) / f'acquisition.{extension}'
                    time = np.arange(4, dtype=float)
                    with MDF(version=version) as m:
                        m.append([
                            MSignal(np.array([0, 1, 0, 1], dtype=np.uint8), time, name='Switch',
                                    conversion={'val_0': 0, 'text_0': b'Off', 'val_1': 1, 'text_1': b'On'}),
                            MSignal(np.arange(4, dtype=np.int16), time, name='Voltage', unit='V',
                                    conversion={'a': 2.5, 'b': -1}),
                            MSignal(np.array([b'a', b'b', b'c', b'd']), time, name='Text', encoding='utf-8'),
                        ])
                        m.save(path, overwrite=True)
                    channels = {s.name: s for s in load(path).signals}
                    self.assertEqual(set(channels), {'Switch', 'Voltage'})
                    np.testing.assert_array_equal(channels['Switch'].values, [0, 1, 0, 1])
                    np.testing.assert_allclose(channels['Voltage'].values, [-1, 1.5, 4, 6.5])
                    np.testing.assert_array_equal(channels['Voltage'].time, time)
                    self.assertEqual(channels['Voltage'].unit, 'V')

    def test_text_only_file_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as folder:
            for version, extension in [('3.30', 'mdf'), ('4.10', 'mf4')]:
                with self.subTest(version=version):
                    path = Path(folder) / f'text.{extension}'
                    with MDF(version=version) as m:
                        m.append([MSignal(np.array([b'a', b'b']), np.array([0., 1.]), name='Text', encoding='utf-8')])
                        m.save(path, overwrite=True)
                    with self.assertRaisesRegex(ValueError, 'no supported nonempty numeric scalar channels'):
                        load(path)
