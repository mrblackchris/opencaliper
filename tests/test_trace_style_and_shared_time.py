"""Plot appearance persistence, cursor stacking and shared-t1 conversion."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from scipy.io import loadmat, savemat
from PySide6 import QtCore, QtGui, QtWidgets as Q
from PySide6.QtTest import QTest
from opencaliper import Signal, Recording, load
from opencaliper.gui import Window
from opencaliper.converterscripts import pairedexport


class SharedTimeTests(unittest.TestCase):
    def test_shared_output_has_one_axis_and_reloads_names_units_and_data(self):
        t = np.arange(8)*.001
        r = Recording([Signal('Voltage', t, t*2, 'V'), Signal('Current', t.copy(), t+3, 'A')])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'shared.mat'
            pairedexport.write(r, path, axis_mode='shared_time')
            data = loadmat(path)
            self.assertIn('t1', data)
            self.assertIn('Signal1_t1', data); self.assertIn('Signal2_t1', data)
            self.assertNotIn('Signal1_t', data); self.assertNotIn('Signal1_u', data)
            for original, restored in zip(r.signals, load(path).signals):
                self.assertEqual((original.name, original.unit), (restored.name, restored.unit))
                np.testing.assert_array_equal(original.time, restored.time)
                np.testing.assert_array_equal(original.values, restored.values)
            plain = Path(folder)/'plain.mat'
            savemat(plain, {'t1':t, 'Signal1_t1':t*3, 'Signal10_t1':t*10, 'Signal2_t1':t*2})
            self.assertEqual([s.name for s in load(plain).signals], ['Signal1','Signal2','Signal10'])

    def test_shared_export_rejects_resampling_and_frequency_without_writing(self):
        cases = [Recording([Signal('Uneven', [0,1,3], [1,2,3])]),
                 Recording([Signal('a', [0,1,2], [1,2,3]), Signal('b', [.1,1.1,2.1], [1,2,3])]),
                 Recording([Signal('f', [1,2,3], [1,2,3], domain='frequency')])]
        with tempfile.TemporaryDirectory() as folder:
            for r in cases:
                path = Path(folder)/'invalid.mat'
                with self.assertRaisesRegex(ValueError, 'Shared t1'): pairedexport.write(r, path, axis_mode='shared_time')
                self.assertFalse(path.exists())

    def test_explicit_resampling_aligns_only_overlap_and_keeps_original_samples(self):
        a=Signal('a',[0,.1,.25,.4],[0,.2,.5,.8],'V')
        b=Signal('b',[.05,.15,.3,.5],[.15,.45,.9,1.5],'A')
        before=[(s.time.copy(),s.values.copy()) for s in (a,b)]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'aligned.mat'
            pairedexport.write(Recording([a,b]),path,axis_mode='shared_time',resample=True,sample_rate=20)
            result=load(path)
            np.testing.assert_allclose(result.signals[0].time,result.signals[1].time)
            self.assertGreaterEqual(result.signals[0].time[0],.05)
            self.assertLessEqual(result.signals[0].time[-1],.4)
            np.testing.assert_allclose(np.diff(result.signals[0].time),.05)
            np.testing.assert_allclose(result.signals[0].values,result.signals[0].time*2)
            np.testing.assert_allclose(result.signals[1].values,result.signals[1].time*3)
        for s,(time,values) in zip((a,b),before):
            np.testing.assert_array_equal(s.time,time);np.testing.assert_array_equal(s.values,values)


class TraceStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = Q.QApplication.instance() or Q.QApplication([])

    def setUp(self):
        self.w = Window(); self.w.show()
        t = np.arange(16)*.01
        self.w.loaded(Recording([Signal('Voltage', t, t, 'V'),Signal('Current',t,t*2,'A')]))
        self.w.add_signal(0,self.w.plots[0]); self.app.processEvents()

    def tearDown(self):
        for d in self.w.dialogs[:]:
            while getattr(d,'busy',False): QTest.qWait(10)
            d.close()
        self.w.close(); self.app.processEvents()

    def test_real_style_dialog_and_persistence_with_color_and_undo(self):
        p=self.w.plots[0]
        def accept():
            dialog=Q.QApplication.activeModalWidget()
            spins=dialog.findChildren(Q.QDoubleSpinBox); spins[0].setValue(3.5); spins[1].setValue(9)
            boxes=dialog.findChildren(Q.QComboBox); boxes[0].setCurrentText('Dashed'); boxes[1].setCurrentText('Circle')
            dialog.accept()
        QtCore.QTimer.singleShot(0,accept)
        self.w.choose_signal_style(p,[0])
        self.assertEqual(p.curves[0].opts['pen'].style(),QtCore.Qt.PenStyle.DashLine)
        self.assertEqual(p.curves[0].opts['symbol'],'o')
        self.w.undo(); self.assertEqual(self.w.plots[0].curves[0].opts['pen'].widthF(),1.)
        self.app.processEvents()
        self.w.redo();self.app.processEvents();p=self.w.plots[0]
        with patch.object(Q.QColorDialog,'getColor',return_value=QtGui.QColor('#abcdef')): self.w.choose_signal_color(p,[0])
        self.assertEqual(p.curves[0].opts['pen'].widthF(),3.5)
        self.assertEqual(p.curves[0].opts['symbolBrush'].color().name(),'#abcdef')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'style.ocw';self.w.save_workspace(path)
            with patch.object(self.w,'error',side_effect=AssertionError):self.w.open_workspace(path)
            self.app.processEvents()
            p=self.w.plots[0]
            self.assertEqual(p.curves[0].opts['pen'].widthF(),3.5)
            self.assertEqual(p.curves[0].opts['symbol'],'o')
            self.assertEqual(p.curves[0].opts['symbolSize'],9)
            for suffix in ('svg','png','pdf'):
                out=Path(folder)/('style.'+suffix);self.w.export_plot_to(p,out);self.assertGreater(out.stat().st_size,100)

    def test_markers_only_survive_axis_move_and_cursors_stack_above_data(self):
        p=self.w.plots[0];self.w.add_signal(1,p)
        self.w.set_signal_style(p,[0,1],dict(line='None (markers only)',marker='Square',width=2,size=8,filled=False))
        self.w.set_signal_axis(p,[1],p.new_y_axis())
        self.w.draw_annotation(p,[.02,.1,'Annotation'])
        self.w.toggle_cursors(True)
        self.assertEqual(p.curves[1].opts['symbol'],'s')
        self.assertEqual(p.curves[1].opts['pen'].style(),QtCore.Qt.PenStyle.NoPen)
        for cursor in p.cursors:
            self.assertIs(cursor.parentItem(),p.cursor_layer)
            self.assertGreater(p.cursor_layer.zValue(),p.plotItem.legend.zValue())
            self.assertGreater(cursor.zValue(),max(c.zValue() for c in p.curves.values()))
            self.assertGreater(cursor.zValue(),max(item.zValue() for item in p.annotation_items))
            self.assertTrue(cursor.isVisible())
        with self.assertRaises(ValueError): self.w.set_signal_style(p,[0],dict(line='None (markers only)',marker='None'))

    def test_converter_shared_time_option_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'input.csv';source.write_text('Time,Voltage,Current\n0,1,2\n.1,3,4\n.3,5,6\n')
            d=self.w.open_converter();d.add_files([str(source)])
            d.axis_mode.setCurrentIndex(d.axis_mode.findData('shared_time'))
            self.assertTrue(d.resample_shared.isEnabled())
            d.resample_shared.setChecked(True);d.shared_rate.setValue(20);d.start()
            timer=QtCore.QElapsedTimer();timer.start()
            while d.busy and timer.elapsed()<10000:QTest.qWait(10)
            self.assertFalse(d.busy);self.assertEqual(len(d.outputs),1)
            data=loadmat(d.outputs[0]);self.assertIn('t1',data);self.assertIn('Signal2_t1',data)
            self.assertEqual(len(load(d.outputs[0]).signals),2)
            np.testing.assert_allclose(np.diff(load(d.outputs[0]).signals[0].time),.05)

    def test_smith_chart_retains_marker_only_style(self):
        self.w.loaded(Recording([Signal('S11',[1e6,2e6],[.1j,.5],domain='sparameter')]))
        p=self.w.plots[0]
        self.w.set_signal_style(p,[2],dict(line='None (markers only)',marker='Circle',size=10))
        chart=self.w.show_smith_chart(self.w.workspace)
        curve=chart.plot.listDataItems()[-1]
        self.assertEqual(curve.opts['symbol'],'o')
        self.assertEqual(curve.opts['symbolSize'],10)
        self.assertEqual(curve.opts['pen'].style(),QtCore.Qt.PenStyle.NoPen)
        chart.close()
