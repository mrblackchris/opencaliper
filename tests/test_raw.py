"""Regression tests for LTspice RAW export."""
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
import numpy as np
from opencaliper.acquisition import Channel, Measurement
from opencaliper.raw import write_raw


class ExtraConverterTests(unittest.TestCase):
    def measurement(self):
        return Measurement([
            Channel(2, 'VOLT', np.array([-5., -1., 0., 1., 5.]), 1., 0.),
            Channel(7, 'AMPere', np.array([-0.02, -0.01, 0., 0.01, 0.02]), 1., 0.)
        ], 5e-10, -0.0025, datetime(2026, 10, 8, 9, 41, 20))

    def test_raw_float_and_double(self):
        with tempfile.TemporaryDirectory() as folder:
            for double in (False, True):
                m = self.measurement()
                p = write_raw(m, Path(folder) / f'{double}.raw', double_precision=double, chunk_size=2)
                content = p.read_bytes()
                marker = 'Binary:\n'.encode('utf-16-le')
                hdr, raw = content.split(marker, 1)
                self.assertIn('V(Channel_2)', hdr.decode('utf-16-le'))
                dtype = np.dtype([('time', '<f8'), ('v', '<f8' if double else '<f4'),
                                  ('i', '<f8' if double else '<f4')])
                records = np.frombuffer(raw, dtype=dtype)
                np.testing.assert_array_equal(records['time'], np.arange(5) * m.xinc)
                for key, c in zip(('v', 'i'), m.channels):
                    np.testing.assert_array_equal(records[key], c.samples.astype(dtype[key]))
                with self.assertRaises(FileExistsError):
                    write_raw(m, p)

    def test_raw_rejects_negative_time_and_invalid_values(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder) / 'bad.raw'
            m = self.measurement()
            with self.assertRaises(ValueError):
                write_raw(m, p, start_at_zero=False)
            m.channels[0].samples[0] = np.inf
            with self.assertRaises(ValueError):
                write_raw(m, p)
            self.assertFalse(p.exists())



if __name__ == '__main__':
    unittest.main()
