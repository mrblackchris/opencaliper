"""Real mouse gestures for recovering off-screen cursors after zooming."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
import numpy as np
from unittest.mock import patch
from PySide6 import QtCore, QtWidgets as Q
from PySide6.QtTest import QTest
from opencaliper import Recording, Signal
from opencaliper.gui import Window


class CursorClickTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = Q.QApplication.instance() or Q.QApplication([])

    def setUp(self):
        self.w = Window()
        t = np.arange(1000)/100
        self.w.loaded(Recording([Signal('test',t,np.sin(t),'V')],'test.mat'))
        self.w.add_signal(0,self.w.plots[0])
        self.w.show(); self.app.processEvents()

    def tearDown(self):
        self.w.close(); self.app.processEvents()

    def point(self,plot,fraction,y_fraction=0.35):
        rect=plot.getViewBox().sceneBoundingRect()
        return plot.mapFromScene(QtCore.QPointF(rect.left()+rect.width()*fraction,
                                               rect.top()+rect.height()*y_fraction))

    def click(self,plot,fraction):
        pos=self.point(plot,fraction)
        expected=plot.x_from_scene(plot.getViewBox().mapSceneToView(plot.mapToScene(pos)).x())
        QTest.mouseClick(plot.viewport(),QtCore.Qt.MouseButton.LeftButton,pos=pos)
        self.app.processEvents()
        return expected

    def test_alternate_clicks_recover_cursors_and_sync_subplots(self):
        w=self.w
        w.add_plot(); w.add_signal(0,w.plots[1]); self.app.processEvents()
        w.cursors_enabled.setChecked(True)
        w.move_cursor(0,-100); w.move_cursor(1,100)
        w.plots[0].setXRange(2,4,padding=0)
        for plot,fraction,index in [(w.plots[0],.25,0),(w.plots[1],.7,1),(w.plots[0],.4,0)]:
            expected=self.click(plot,fraction)
            self.assertAlmostEqual(w.cursor_positions[index],expected)
            for p in w.plots: self.assertAlmostEqual(p.cursors[index].value(),expected)
        self.assertTrue(all(2 <= value <= 4 for value in w.cursor_positions))

    def test_disabled_cursors_and_axis_clicks_do_not_move_them(self):
        w=self.w; p=w.plots[0]; original=w.cursor_positions[:]
        self.click(p,.3)
        self.assertEqual(w.cursor_positions,original)
        w.cursors_enabled.setChecked(True)
        bounds=p.getViewBox().sceneBoundingRect()
        position=p.mapFromScene(QtCore.QPointF(bounds.center().x(),bounds.bottom()+10))
        QTest.mouseClick(p.viewport(),QtCore.Qt.MouseButton.LeftButton,pos=position)
        self.assertEqual(w.cursor_positions,original)

    def test_log_frequency_click_uses_hz_and_tab_sequence_is_independent(self):
        w=self.w; w.cursors_enabled.setChecked(True)
        self.click(w.plots[0],.3)
        first=w.workspace
        page=w.add_analysis('spectrum')
        w.cursors_enabled.setChecked(True)
        p=w.plots[0]; p.set_physical_x_range(1e3,1e6)
        self.app.processEvents()
        expected=self.click(p,.5)
        self.assertAlmostEqual(page.cursor_positions[0],expected)
        self.assertTrue(1e4 < expected < 1e5)
        self.assertAlmostEqual(p.cursors[0].value(),np.log10(expected))
        w.tabs.setCurrentWidget(first)
        expected=self.click(w.plots[0],.6)
        self.assertAlmostEqual(first.cursor_positions[1],expected)
        w.cursors_enabled.setChecked(False); w.cursors_enabled.setChecked(True)
        expected=self.click(w.plots[0],.4)
        self.assertAlmostEqual(first.cursor_positions[0],expected)

    def test_rectangle_drag_keeps_cursors_and_click_still_places_them(self):
        w=self.w; p=w.plots[0]; w.cursors_enabled.setChecked(True)
        w.move_cursor(0,-100); w.move_cursor(1,100)
        original=w.cursor_positions[:]
        w.set_zoom_mode(True)
        old=p.viewRange()
        start=self.point(p,.25,.25); stop=self.point(p,.75,.75)
        QTest.mousePress(p.viewport(),QtCore.Qt.MouseButton.LeftButton,pos=start)
        QTest.mouseMove(p.viewport(),stop,delay=30)
        QTest.mouseRelease(p.viewport(),QtCore.Qt.MouseButton.LeftButton,pos=stop)
        self.app.processEvents()
        self.assertEqual(w.cursor_positions,original)
        self.assertLess(np.ptp(p.viewRange()[0]),np.ptp(old[0]))
        expected=self.click(p,.4)
        self.assertAlmostEqual(w.cursor_positions[0],expected)

    def test_right_click_still_opens_context_menu(self):
        w=self.w; p=w.plots[0]; w.cursors_enabled.setChecked(True)
        original=w.cursor_positions[:]
        with patch.object(w,'plot_color_menu',wraps=w.plot_color_menu) as menu:
            QTest.mouseClick(p.viewport(),QtCore.Qt.MouseButton.RightButton,pos=self.point(p,.4))
            self.app.processEvents()
            menu.assert_called_once()
        self.assertEqual(w.cursor_positions,original)
        for menu in w.findChildren(Q.QMenu): menu.close()

    def test_cursor_drag_does_not_consume_click_sequence(self):
        w=self.w; p=w.plots[0]; w.cursors_enabled.setChecked(True)
        p.setXRange(0,10,padding=0); w.move_cursor(0,3); w.move_cursor(1,8)
        self.app.processEvents()
        view=p.getViewBox()
        middle=np.mean(view.viewRange()[1])
        start=p.mapFromScene(view.mapViewToScene(QtCore.QPointF(3,middle)))
        stop=p.mapFromScene(view.mapViewToScene(QtCore.QPointF(4,middle)))
        QTest.mouseMove(p.viewport(),self.point(p,.1,.2),delay=30)
        QTest.qWait(30)
        QTest.mouseMove(p.viewport(),start,delay=30); QTest.qWait(30)
        QTest.mousePress(p.viewport(),QtCore.Qt.MouseButton.LeftButton,pos=start)
        QTest.mouseMove(p.viewport(),stop,delay=30)
        QTest.mouseRelease(p.viewport(),QtCore.Qt.MouseButton.LeftButton,pos=stop)
        self.app.processEvents()
        self.assertAlmostEqual(w.cursor_positions[0],4,delta=.05)
        self.assertEqual(w.workspace.next_cursor_index,0)
        expected=self.click(p,.2)
        self.assertAlmostEqual(w.cursor_positions[0],expected)
