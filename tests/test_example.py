"""Verify the public acquisition example using independent timing expectations."""
from pathlib import Path
import tempfile
import unittest
import numpy as np
from scipy.io import savemat
from examples.example import create_example
from opencaliper import load
from opencaliper.acquisition import load_mat


class ExampleTests(unittest.TestCase):
    def test_generated_and_bundled_example(self):
        with tempfile.TemporaryDirectory() as folder:
            generated = create_example(Path(folder) / 'example.mat')
            bundled = Path(__file__).resolve().parents[1] / 'examples' / 'example.mat'
            for path in (generated, bundled):
                data = load_mat(path)
                recording = load(path)
                self.assertEqual([s.name for s in recording.signals],
                                 ['Channel1', 'Channel2', 'Channel3', 'Channel4'])
                channel = recording.signals[0]
                self.assertEqual(len(channel.time), 4096)
                self.assertAlmostEqual(channel.time[0], -0.001)
                self.assertAlmostEqual(channel.time[-1], 0.003095)
                np.testing.assert_allclose(channel.values,
                    np.sin(2*np.pi*10000*channel.time), atol=1e-7)
                self.assertEqual(channel.unit, 'VOLT')
                self.assertEqual(np.asarray(data['Channel1_t1']).dtype, np.float32)

    def test_unrecognized_mat_layout_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'unknown.mat'
            savemat(path, {'T': [0, 1, 2], 'A': [1, 2, 3]})
            with self.assertRaisesRegex(ValueError, 'Unsupported MAT layout'):
                load(path)
