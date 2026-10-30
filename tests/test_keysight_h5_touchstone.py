"""Physical Keysight scaling and complex Touchstone interoperability."""
from pathlib import Path
import io
import json
import tempfile
import unittest
from unittest.mock import patch
import h5py
import numpy as np
from opencaliper import load, export
from opencaliper.converterscripts.formats import input_filter


def write_h5(path, floating=False):
    with h5py.File(path, 'w') as f:
        f['FileType/KeysightH5FileType'] = np.bytes_('Keysight Waveform')
        for index in (1, 2):
            group = f.create_group(f'Waveforms/Channel {index}')
            group.attrs.update(XOrg=-1e-6, XInc=2e-9, YInc=.25, YOrg=1.,
                               YReference=1, NumPoints=4, XUnits='Second', YUnits='Volt')
            group[f'Channel {index}Data'] = np.array([-2, 0, 2, 4], dtype=float if floating else np.int16)


class KeysightTouchstoneTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def test_h5_integer_scaling_float_passthrough_and_optional_date(self):
        for floating in (False, True):
            path = self.folder/('scope.hdf5' if floating else 'scope.H5')
            write_h5(path, floating)
            with h5py.File(path, 'a') as f: f['Frame/TheFrame'] = np.bytes_('unknown date')
            recording = load(path)
            self.assertEqual([s.name for s in recording.signals], ['Channel 1', 'Channel 2'])
            for s in recording.signals:
                np.testing.assert_allclose(s.time, -1e-6 + np.arange(4)*2e-9)
                np.testing.assert_allclose(s.values, [-2, 0, 2, 4] if floating else [.5, 1., 1.5, 2.])
                self.assertEqual((s.domain, s.unit), ('time', 'V'))
            # File can be reopened/deleted on Windows: the reader retains no HDF5 handle.
            path.unlink()

    def test_h5_rejects_other_hdf5_and_unsupported_waveforms(self):
        path = self.folder/'bad.h5'
        with h5py.File(path, 'w') as f: f['unrelated'] = [1, 2]
        with self.assertRaisesRegex(ValueError, 'Keysight'): load(path)
        for attrs, expected in [({'NumSegments': 2}, 'segmented'), ({'WaveformType': 2}, 'normal/average'),
                                ({'XInc': -1}, 'time scaling'), ({'NumPoints': 10}, 'NumPoints')]:
            write_h5(path)
            with h5py.File(path, 'a') as f: f['Waveforms/Channel 1'].attrs.update(attrs)
            with self.assertRaisesRegex(ValueError, expected): load(path)

    def write_s2p(self, content):
        path = self.folder/'network.S2P'; path.write_text(content, encoding='utf-8')
        return path

    def test_s2p_order_units_and_all_encodings(self):
        for encoding, pairs, expected in (
            ('RI', '1 2 3 4 5 6 7 8', [1+2j, 5+6j, 3+4j, 7+8j]),
            ('MA', '1 0 2 90 3 -90 4 180', [1, -3j, 2j, -4]),
            ('DB', '0 0 20 90 -20 -90 6.020599913 180', [1, -.1j, 10j, -2]),
        ):
            recording = load(self.write_s2p(f'! comment\n# MHz S {encoding} R 75\n1 {pairs} ! inline\n2 {pairs}\n'))
            self.assertEqual([s.name for s in recording.signals], ['S11', 'S12', 'S21', 'S22'])
            for s, value in zip(recording.signals, expected):
                np.testing.assert_allclose(s.values, value, atol=1e-9)
                np.testing.assert_array_equal(s.time, [1e6, 2e6])
                self.assertEqual((s.domain, s.reference_impedance), ('sparameter', 75.))

    def test_four_port_row_order_wrapping_defaults_and_fortran_exponents(self):
        path = self.folder/'network.s4p'
        pairs = [f'{n} 0' for n in range(1, 17)]
        path.write_text('# RI\n1D0 '+ ' '.join(pairs[:4])+'\n'+
                        '\n'.join(' '.join(pairs[i:i+4]) for i in (4, 8, 12)), encoding='utf-8')
        signals = load(path).signals
        self.assertEqual(len(signals), 16)
        self.assertEqual((signals[1].name, signals[1].values[0]), ('S12', 2))
        self.assertEqual((signals[4].name, signals[4].values[0]), ('S21', 5))
        self.assertEqual(signals[0].time[0], 1e9)

    def test_version_two_references_order_and_symmetric_matrices(self):
        header = '[Version] 2.0\n# Hz S RI R 50\n[Number of Ports] 2\n[Number of Frequencies] 1\n[Reference]\n50 75\n'
        source = self.write_s2p(header+'[Two-Port Data Order] 12_21\n[Network Data]\n1 1 0 2 0 3 0 4 0\n[End]\n')
        signals = load(source).signals
        self.assertEqual([s.values[0] for s in signals], [1, 2, 3, 4])
        self.assertEqual([s.reference_impedance for s in signals], [50, 50, 75, 75])
        for matrix in ('Lower', 'Upper'):
            source.write_text(header+f'[Matrix Format] {matrix}\n[Network Data]\n1 1 0 2 0 3 0\n[Noise Data]\n0 0 0 0 0\n[End]', encoding='utf-8')
            self.assertEqual([s.values[0] for s in load(source).signals], [1, 2, 2, 3])

    def test_rejects_malformed_or_unsupported_touchstone(self):
        for content, expected in (
            ('# Hz Y RI R 50\n1 0 0', 'expected S-parameters'),
            ('# Hz S RI R 50\n1 0 0', 'Incomplete'),
            ('# Hz S RI R -50\n', 'resistance'),
            ('# Hz S RI\n1 nan 0 0 0 0 0 0 0', 'finite'),
            ('# Hz S RI\n[Mixed-Mode Order] D1,2', 'Unsupported'),
            ('# Hz S RI\n[Number of Ports] 4', 'port count'),
            ('# Hz S RI\n'+('1 0 0 0 0 0 0 0 0\n'*2), 'strictly increasing'),
        ):
            with self.subTest(content=content):
                with self.assertRaisesRegex(ValueError, expected): load(self.write_s2p(content))

    def test_native_mat_roundtrip_retains_complex_domain_and_references(self):
        source = load(self.write_s2p('# Hz S RI R 75\n1 1 2 3 4 5 6 7 8\n'))
        path = self.folder/'native.mat'; export(source, path)
        for a, b in zip(source.signals, load(path).signals):
            self.assertEqual((a.domain, a.reference_impedance), (b.domain, b.reference_impedance))
            np.testing.assert_array_equal(a.values, b.values)
        with self.assertRaisesRegex(ValueError, 'Frequency-domain'): export(source, self.folder/'bad.mf4')
        for suffix in ('*.h5', '*.hdf5', '*.s2p', '*.s4p'): self.assertIn(suffix, input_filter())

    def test_cli_reports_network_frequency_axis_in_hz(self):
        from opencaliper.cli import main
        path = self.write_s2p('# MHz S RI\n1 1 0 2 0 3 0 4 0\n')
        with patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(main(['info', str(path)]), 0)
            channels = json.loads(output.getvalue())
        self.assertTrue(all(s['axis_unit'] == 'Hz' for s in channels))

    def test_network_math_retains_reference_and_rejects_mixed_references(self):
        from opencaliper.processing import expression
        from opencaliper import Signal
        a = Signal('S11', [1, 2], [.1j, .2j], domain='sparameter', reference_impedance=75)
        result = expression('CH0 * 2', {'CH0': a})
        self.assertEqual(result.reference_impedance, 75)
        np.testing.assert_allclose(result.values, a.values*2)
        b = Signal('S22', a.time, a.values, domain='sparameter', reference_impedance=50)
        with self.assertRaisesRegex(ValueError, 'reference impedances'):
            expression('CH0 + CH1', {'CH0': a, 'CH1': b})

    def test_optional_user_examples(self):
        examples = Path(__file__).resolve().parents[1]/'examples'
        if not (examples/'1.h5').exists() or not (examples/'SCD_gen.s4p').exists():
            self.skipTest('Local oscilloscope and network examples are not distributed')
        recording = load(examples/'1.h5')
        self.assertEqual(len(recording.signals), 2)
        self.assertEqual(len(recording.signals[0].values), 7993)
        self.assertAlmostEqual(recording.signals[0].values[0], -23681*.00012755102040816328+3.0040816326530613)
        signals = load(examples/'SCD_gen.s4p').signals
        self.assertEqual(len(signals), 16)
        self.assertAlmostEqual(abs(signals[0].values[0]), 10**(-9.78697967/20))
        self.assertAlmostEqual(np.angle(signals[1].values[0], deg=True), -80.8626114)
