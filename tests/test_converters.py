"""Ausführen: python -m unittest discover -s tests -v"""
from datetime import datetime
from pathlib import Path
import struct
import tempfile
import os
import unittest
import warnings

import numpy as np
from scipy.io import savemat
from opencaliper.acquisition import read_measurement, write_wdf, write_wvf


# Absichtlich unabhängiger Leser: weder Header-Generator noch Quantisierung importieren.
def parse_header(content):
    return {p[0]: p[1:] for line in content.splitlines()
            if (p := line.split()) and not p[0].startswith(('//', '$'))}


def decode_samples(raw, hdr):
    result = []
    pos = int(hdr['DataOffset'][0])
    dtype = '>i2' if hdr['Endian'][0] == 'Big' else '<i2'
    for i in range(int(hdr['TraceNumber'][0])):
        n = int(hdr['BlockSize'][i])
        adc = np.frombuffer(raw, dtype=dtype, count=n, offset=pos)
        values = adc.astype(float) * float(hdr['VResolution'][i]) + float(hdr['VOffset'][i])
        values[adc == -32768] = np.nan
        result.append(values)
        pos += n * 2
    return result


def read_wdf(path):
    raw = path.read_bytes()
    assert raw[:4] == b'%WDF'
    pos = struct.unpack_from('>I', raw, 4)[0]
    chunks = {}
    while pos < len(raw):
        tag = raw[pos:pos + 4]
        length = struct.unpack_from('>Q', raw, pos + 4)[0]
        end = pos + 12 + length
        assert end + 4 <= len(raw)
        assert raw[end:end + 4] == b'\xff' * 4
        chunks[tag] = (pos + 12, raw[pos + 12:end])
        pos = end + 4
    assert pos == len(raw) and tag == b'FeND'
    hdr = parse_header(chunks[b'XHDR'][1].decode('ascii'))
    start, payload = chunks[b'DrAW']
    assert int(hdr['DataOffset'][0]) == start + 8
    size, number = struct.unpack_from('>II', payload)
    assert size == len(payload) - 8 and number == 0xffffffff
    return raw, hdr


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vd = dict(points=5, xinc=1e-6, xorg=-0.001, xref=2,
                       date='202453', time='95331',
                       Channel2_t1=np.array([-2., -1., 0., 1., 2.], dtype=np.float32),
                       Channel2_unit='V', Channel2_yinc=0.1, Channel2_offset=0,
                       Channel7_t1=np.full(5, 42.5), Channel7_unit='A',
                       Channel7_yinc=0.2, Channel7_offset=0)

    def tearDown(self):
        self.tmp.cleanup()

    def save(self, vd=None):
        path = self.root / 'signal.mat'
        savemat(path, self.vd if vd is None else vd)
        return path

    def check_exports(self, path, expected):
        _, meas = read_measurement(path)
        self.assertEqual([c.number for c in meas.channels], [2, 7])
        self.assertEqual(meas.timestamp, datetime(2024, 5, 3, 9, 53, 31))
        self.assertAlmostEqual(meas.xoffset, -0.001002)
        wvf, hdr_path = write_wvf(meas, self.root / 'out.wvf')
        hdr = parse_header(hdr_path.read_text())
        self.assertEqual(hdr['TraceName'], ['Channel_2', 'Channel_7'])
        self.assertEqual(wvf.stat().st_size, 20)
        wdf = write_wdf(meas, self.root / 'out.wdf')
        raw, whdr = read_wdf(wdf)
        for h, content in [(hdr, wvf.read_bytes()), (whdr, raw)]:
            self.assertAlmostEqual(float(h['HOffset'][0]), -0.001002)
            for i, values in enumerate(decode_samples(content, h)):
                np.testing.assert_allclose(values, np.asarray(expected[i], dtype=np.float64), rtol=0,
                                           atol=float(h['VResolution'][i]) / 2 + 1e-12)
        with self.assertRaises(FileExistsError):
            write_wvf(meas, wvf)
        with self.assertRaises(FileExistsError):
            write_wdf(meas, wdf)

    def test_scaled_v5(self):
        self.check_exports(self.save(), [self.vd['Channel2_t1'], self.vd['Channel7_t1']])

    def test_raw_byte_and_word(self):
        self.vd['Channel2_t1'] = np.array([0, 64, 128, 192, 255], dtype=np.uint8)
        self.vd['Channel7_t1'] = np.array([0, 10000, 32768, 40000, 65535], dtype=np.uint16)
        self.vd['Channel2_offset'] = 4.0
        self.vd['Channel7_offset'] = -3.0
        self.check_exports(self.save(), [(self.vd['Channel2_t1'].astype(float)-128)*0.1+4,
                                        (self.vd['Channel7_t1'].astype(float)-32768)*0.2-3])

    def test_hdf5storage_write(self):
        import hdf5storage
        path = self.root / 'signal.mat'
        hdf5storage.write(self.vd, '.', filename=str(path), matlab_compatible=True, compression='gzip')
        self.check_exports(path, [self.vd['Channel2_t1'], self.vd['Channel7_t1']])

    def test_v73(self):
        import hdf5storage
        path = self.root / 'signal.mat'
        hdf5storage.savemat(str(path), self.vd, format='7.3')
        self.check_exports(path, [self.vd['Channel2_t1'], self.vd['Channel7_t1']])

    def test_one_channel_nonfinite(self):
        vd = {k: v for k, v in self.vd.items() if not k.startswith('Channel7')}
        vd['Channel2_t1'] = np.array([np.nan, np.inf, -np.inf, 1., 1.])
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            _, meas = read_measurement(self.save(vd))
        wvf, hdr_path = write_wvf(meas, self.root / 'single.wvf')
        hdr = parse_header(hdr_path.read_text())
        values = decode_samples(wvf.read_bytes(), hdr)[0]
        self.assertTrue(np.isnan(values[:3]).all())
        np.testing.assert_array_equal(values[3:], [1, 1])
        self.assertEqual(hdr['TraceNumber'], ['1'])

    def test_reject_bad_inputs(self):
        path = self.save()
        for field, value in [('points', 4), ('xinc', 0), ('date', '2024111'),
                             ('time', '12345'), ('Channel2_t1', np.ones((2, 3)))]:
            vd = self.vd.copy()
            vd[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                read_measurement(self.save(vd))
        self.vd['date'] = '2024111'
        _, meas = read_measurement(self.save(), date_override='2024-11-01')
        self.assertEqual(meas.timestamp.month, 11)

    def test_reference_wdf_matches_wvf_exactly(self):
        directory = os.getenv('OPENCALIPER_TEST_DATA_DIR')
        if not directory: self.skipTest('Optional local WDF fixture is not included')
        base = Path(directory)
        ref = base / 'sample.wdf'
        if not ref.exists():
            self.skipTest('Referenzdatei nicht vorhanden')
        raw, hdr = read_wdf(ref)
        count = sum(int(n) for n in hdr['BlockSize'])
        adc = np.frombuffer(raw, dtype='>i2', count=count, offset=int(hdr['DataOffset'][0]))
        external = np.fromfile(base / 'sample.wvf', dtype='<i2')
        np.testing.assert_array_equal(adc, external)


if __name__ == '__main__':
    unittest.main()
