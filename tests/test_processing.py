import tempfile
from pathlib import Path
import unittest
import numpy as np
from opencaliper.core import Signal, load
from opencaliper import processing as p


class ProcessingTests(unittest.TestCase):
    def setUp(self):
        self.t = np.arange(4096)/1024
        self.s = Signal('test',self.t,np.sin(2*np.pi*32*self.t),'V')

    def test_math_and_calculus(self):
        out = p.expression('CH0 * 2 - abs(CH0)',{'CH0':self.s})
        np.testing.assert_allclose(out.values,self.s.values*2-np.abs(self.s.values))
        ramp = Signal('ramp',self.t,self.t)
        derivative = p.expression('differentiate(CH0)',{'CH0':ramp})
        np.testing.assert_allclose(derivative.values,1)
        integral = p.expression('integrate(CH0)',{'CH0':ramp})
        np.testing.assert_allclose(integral.values,self.t**2/2)
        for text in ('__import__("os")','CH0.__class__','CH0[0]','2 ** 1000000'):
            with self.assertRaises(ValueError): p.expression(text,{'CH0':self.s})
        with self.assertRaises(ValueError): p.expression('a+b',{'a':self.s,'b':Signal('b',self.t+1,self.t)})

    def test_filters(self):
        s = Signal('mixed',self.t,self.s.values+np.sin(2*np.pi*200*self.t))
        out = p.filtered(s,'lowpass',70)
        self.assertLess(np.std(out.values[100:-100]-self.s.values[100:-100]),0.02)
        high = p.filtered(s,'highpass',100)
        self.assertLess(np.std(high.values[100:-100]-np.sin(2*np.pi*200*self.t[100:-100])),0.03)
        notch = p.filtered(self.s,'notch',32)
        self.assertLess(np.std(notch.values[1000:-1000]),0.02)
        with self.assertRaises(ValueError): p.filtered(s,'lowpass',600)

    def test_alignment_and_events(self):
        y = np.exp(-((self.t-1)/0.03)**2)
        ref = Signal('ref',self.t,y)
        shifted = Signal('late',self.t,np.exp(-((self.t-1.2)/0.03)**2))
        aligned = p.aligned(shifted,ref)
        self.assertAlmostEqual(aligned.time[np.argmax(aligned.values)],1,delta=1/1024)
        crossing = p.events(Signal('ramp',np.arange(5),np.arange(5)),'rising',1.5)
        np.testing.assert_allclose(crossing,[1.5])
        self.assertEqual(len(p.events(ref,'peaks',0.5)),1)
        self.assertEqual(len(p.events(ref,'pulses',0.5)),2)
        self.assertGreater(len(p.events(ref,'outliers',3)),0)

    def test_spectrogram(self):
        t,f,power = p.spectrogram(self.s,256)
        np.testing.assert_allclose(f[np.argmax(power,axis=0)],32)
        self.assertEqual(power.shape,(len(f),len(t)))
        self.assertTrue(np.isfinite(power).all())
        with self.assertRaises(ValueError): p.spectrogram(self.s,9999)

    def test_memory_mapped_input(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'recording.npy'
            np.save(path,np.column_stack([self.t,self.s.values]))
            s = load(path).signals[0]
            np.testing.assert_array_equal(s.values,self.s.values)
            # The views retain memory-mapped backing rather than copying samples.
            base = s.values
            while base.base is not None and not isinstance(base,np.memmap): base = base.base
            self.assertIsInstance(base,np.memmap)
