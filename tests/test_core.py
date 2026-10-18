import tempfile
import os
from pathlib import Path
import unittest
import numpy as np
from opencaliper import Signal, Recording, load, export
from opencaliper.analysis import fft, statistics, cursor_values


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        t = np.arange(1024)/1024
        self.signal = Signal('voltage', t, 3*np.sin(2*np.pi*64*t), 'V')
        self.record = Recording([self.signal])

    def tearDown(self): self.tmp.cleanup()

    def test_analysis(self):
        f,a = fft(self.signal)
        self.assertEqual(f[np.argmax(a)],64)
        self.assertAlmostEqual(a.max(),3,places=4)
        self.assertAlmostEqual(statistics(self.signal)['rms'],3/np.sqrt(2))
        self.assertEqual(statistics(self.signal,0,0.125)['count'],129)
        self.assertAlmostEqual(cursor_values(self.signal,0,1/256)['b'],3)

    def test_roundtrips(self):
        for ext in ['mat','raw','mf4','mdf','wvf']:
            with self.subTest(ext=ext):
                p = self.root / ('out.'+ext)
                export(self.record,p)
                restored = load(p)
                np.testing.assert_allclose(restored.signals[0].time,self.signal.time,atol=1e-12)
                np.testing.assert_allclose(restored.signals[0].values,self.signal.values,atol=0.0001)
                self.assertEqual(restored.signals[0].unit,'V')
                with self.assertRaises(FileExistsError): export(self.record,p)

    def test_independent_time_axes(self):
        other = Signal('slow',self.signal.time[::2],self.signal.values[::2],'V')
        r = Recording([self.signal,other])
        p = self.root/'multi.mat'; export(r,p)
        self.assertEqual(len(load(p).signals[1].time),512)
        with self.assertRaises(ValueError): export(r,self.root/'bad.raw')

    def test_mat_preserves_numeric_channel_order(self):
        recording = Recording([Signal(f'Channel {i}',self.signal.time,self.signal.values,'V') for i in range(12)])
        path = self.root/'many.mat'
        export(recording,path)
        restored = load(path)
        self.assertEqual([s.name for s in restored.signals],[s.name for s in recording.signals])

    def test_fft_rejects_irregular_and_nonfinite(self):
        with self.assertRaises(ValueError): fft(Signal('bad',[0,1,2,4],[0,1,0,1]))
        with self.assertRaises(ValueError): fft(Signal('bad',[0,1,2,3],[0,1,np.nan,1]))

    @unittest.skipUnless(os.getenv('OPENCALIPER_TEST_DATA_DIR'), 'Optional local file fixtures are not included')
    def test_sample_files(self):
        root = Path(os.environ['OPENCALIPER_TEST_DATA_DIR'])
        files = [root / ('sample.'+ext) for ext in ['mat','bin','wvf','mf4']]
        existing = [path for path in files if path.exists()]
        self.assertTrue(existing, 'No sample.mat/bin/wvf/mf4 files in fixture directory')
        for path in existing:
            with self.subTest(filename=path.name):
                recording = load(path)
                self.assertGreater(len(recording.signals),0)
                self.assertTrue(all(len(s.time)>0 for s in recording.signals))


if __name__ == '__main__': unittest.main()
