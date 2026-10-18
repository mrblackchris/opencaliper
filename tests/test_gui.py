import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
import numpy as np
from PySide6.QtWidgets import QApplication
from PySide6 import QtCore, QtGui
from PySide6.QtTest import QTest
from unittest.mock import patch
from opencaliper.gui import Window
from opencaliper import Recording, Signal


class GuiTests(unittest.TestCase):
    def test_workspace_and_cursors(self):
        app = QApplication.instance() or QApplication([])
        w = Window()
        w.loaded(Recording([Signal('test',np.arange(20)*0.1,np.arange(20),'V')],'test.mat'))
        w.add_signal(0,w.plots[0]); w.add_plot(); w.add_signal(0,w.plots[1])
        w.cursors_enabled.setChecked(True)
        w.move_cursor(0,0.2); w.move_cursor(1,0.5)
        self.assertAlmostEqual(w.plots[1].cursors[0].value(),0.2)
        self.assertIn('ΔY 3',w.readout.toPlainText())
        w.clear_plots(); self.assertFalse(w.plots[0].curves)
        w.close(); app.processEvents()

    def test_delete_removes_only_selected_plot_signals(self):
        app = QApplication.instance() or QApplication([])
        w = Window()
        t = np.arange(20)*0.1
        w.loaded(Recording([Signal('one',t,t,'V'), Signal('two',t,t*2,'V')], 'test.mat'))
        first = w.plots[0]
        w.add_signal(0,first); w.add_signal(1,first)
        w.add_plot(); w.add_signal(0,w.plots[1])
        first.signal_list.selectAll()
        QTest.keyClick(first.signal_list, QtCore.Qt.Key.Key_Delete)
        self.assertFalse(first.curves)
        self.assertEqual(first.signal_list.count(),0)
        self.assertEqual(first.plotItem.legend.items,[])
        self.assertIn(0,w.plots[1].curves)
        self.assertEqual(w.list.topLevelItem(0).childCount(),2)
        w.add_signal(0,first)
        self.assertEqual(first.signal_list.count(),1)
        w.close(); app.processEvents()

    def test_fit_uses_full_data_and_ignores_cursors(self):
        app = QApplication.instance() or QApplication([])
        w = Window()
        t = np.arange(1000,dtype=float)
        y = np.zeros(1000); y[-1] = 500
        w.loaded(Recording([Signal('spike',t,y,'V')], 'test.mat'))
        p = w.plots[0]; w.add_signal(0,p)
        p.setXRange(0,10); p.setYRange(-1,1)
        w.move_cursor(1,1e9); w.cursors_enabled.setChecked(True)
        w.fit(); app.processEvents()
        x,y_range = p.viewRange()
        self.assertLessEqual(x[0],0); self.assertGreaterEqual(x[1],999)
        self.assertLess(x[1],2000)
        self.assertLessEqual(y_range[0],0); self.assertGreaterEqual(y_range[1],500)
        w.close()

    def test_explorer_accepts_files_and_multi_signal_drag(self):
        app = QApplication.instance() or QApplication([])
        w = Window()
        t = np.arange(5,dtype=float)
        w.loaded(Recording([Signal('one',t,t,'V'), Signal('two',t,t,'V')], 'test.mat'))
        w.list.topLevelItem(0).setExpanded(True)
        w.list.clearSelection()
        for item in w.signal_items.values(): item.setSelected(True)
        mime = w.list.mimeData(w.list.selectedItems())
        event = QtGui.QDropEvent(QtCore.QPointF(10,10), QtCore.Qt.DropAction.CopyAction,
                                mime, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
        w.show(); app.processEvents()
        viewport = w.plots[0].viewport()
        enter = QtGui.QDragEnterEvent(QtCore.QPoint(10,10), QtCore.Qt.DropAction.CopyAction,
                                     mime, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(viewport, enter)
        self.assertTrue(enter.isAccepted())
        QApplication.sendEvent(viewport, event)
        self.assertTrue(event.isAccepted())
        self.assertEqual(set(w.plots[0].curves),{0,1})
        files = QtCore.QMimeData()
        files.setUrls([QtCore.QUrl.fromLocalFile('/tmp/measurement.mat')])
        drop = QtGui.QDropEvent(QtCore.QPointF(10,10), QtCore.Qt.DropAction.CopyAction,
                               files, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
        with patch.object(w,'open_path') as open_path:
            w.list.dropEvent(drop)
            open_path.assert_called_once_with('/tmp/measurement.mat')
        w.close(); app.processEvents()

    def test_unload_file_keeps_other_file_ids_valid(self):
        app = QApplication.instance() or QApplication([])
        w = Window(); t = np.arange(5,dtype=float)
        for name in ['first.mat','second.mat']:
            w.loaded(Recording([Signal(name,t,t,'V')],name))
        self.assertFalse(w.list.topLevelItem(0).isExpanded())
        w.add_signal(0,w.plots[0]); w.add_signal(1,w.plots[0])
        w.list.setCurrentItem(w.list.topLevelItem(0))
        QTest.keyClick(w.list,QtCore.Qt.Key.Key_Delete)
        self.assertEqual(w.list.topLevelItemCount(),1)
        self.assertEqual(w.list.topLevelItem(0).text(0),'second.mat')
        self.assertEqual(set(w.signals),{1})
        self.assertEqual(set(w.plots[0].curves),{1})
        self.assertEqual(w.plots[0].signal_list.count(),1)
        w.remove_signals(w.plots[0],[1]); w.add_signal(1,w.plots[0])
        self.assertIn(1,w.plots[0].curves)
        w.close(); app.processEvents()

    def test_drop_refits_after_zoom_and_linked_empty_plot(self):
        app = QApplication.instance() or QApplication([])
        w = Window(); t = 100+np.arange(10,dtype=float)
        w.loaded(Recording([Signal('offset',t,1000+t,'V')],'offset.mat'))
        w.add_plot(); p = w.plots[1]
        w.show(); app.processEvents()
        p.setXRange(-1,1); p.setYRange(-1,1)
        w.add_signal(0,p); app.processEvents()
        xr,yr = p.viewRange()
        self.assertLessEqual(xr[0],100); self.assertGreaterEqual(xr[1],109)
        self.assertLessEqual(yr[0],1100); self.assertGreaterEqual(yr[1],1109)
        w.remove_signals(p,[0]); p.setXRange(-1,1)
        w.add_signal(0,p); app.processEvents()
        self.assertGreaterEqual(p.viewRange()[0][1],109)
        w.close()

    def test_tabs_keep_explorer_but_isolate_plots_cursors_and_zoom(self):
        app = QApplication.instance() or QApplication([])
        w = Window(); t = np.arange(100,dtype=float)
        w.loaded(Recording([Signal('shared',t,t,'V')],'shared.mat'))
        explorer = w.list
        first = w.workspace; w.add_signal(0,w.plots[0])
        w.cursors_enabled.setChecked(True); w.move_cursor(0,10); w.move_cursor(1,30)
        w.set_zoom_mode(True)
        first.plots[0].setXRange(10,20,padding=0)
        second = w.add_analysis()
        self.assertIs(w.list,explorer)
        self.assertEqual(w.list.topLevelItemCount(),1)
        self.assertFalse(w.cursors_enabled.isChecked())
        self.assertFalse(w.zoom_action.isChecked())
        w.add_signal(0,w.plots[0]); w.move_cursor(0,50)
        second.plots[0].setXRange(60,70,padding=0)
        w.tabs.setCurrentIndex(0)
        self.assertIs(w.workspace,first)
        self.assertTrue(w.cursors_enabled.isChecked())
        self.assertTrue(w.zoom_action.isChecked())
        self.assertEqual(w.cursor_positions,[10,30])
        np.testing.assert_allclose(first.plots[0].viewRange()[0],[10,20])
        self.assertEqual(second.cursor_positions[0],50)
        w.clear_plots()
        self.assertFalse(first.plots[0].curves)
        self.assertIn(0,second.plots[0].curves)
        w.remove_files([0])
        self.assertFalse(second.plots[0].curves)
        self.assertNotIn('shared:',second.readout.toPlainText())
        w.close_analysis(1)
        self.assertEqual(w.tabs.count(),1)
        w.close_analysis(0)
        self.assertEqual(w.tabs.count(),1)
        w.close(); app.processEvents()

    def test_resize_subplots_and_zoom_shared_time_only_once(self):
        app = QApplication.instance() or QApplication([])
        w = Window(); t = np.arange(100,dtype=float)
        w.loaded(Recording([Signal('test',t,t,'V')],'test.mat'))
        w.add_signal(0,w.plots[0]); w.add_plot(); w.add_signal(0,w.plots[1])
        w.show(); app.processEvents()
        splitter = w.workspace.plot_splitter
        before = splitter.sizes()
        splitter.moveSplitter(before[0]+60,1); app.processEvents()
        after = splitter.sizes()
        self.assertGreater(after[0],before[0]); self.assertLess(after[1],before[1])
        w.fit(); app.processEvents()
        old = [p.viewRange() for p in w.plots]
        w.zoom_by(0.5); app.processEvents()
        for i,p in enumerate(w.plots):
            now = p.viewRange()
            self.assertAlmostEqual(np.ptp(now[0])/np.ptp(old[i][0]),0.5,places=3)
            self.assertAlmostEqual(np.ptp(now[1])/np.ptp(old[i][1]),0.5,places=3)
        w.set_zoom_mode(True)
        import pyqtgraph as pg
        self.assertTrue(all(p.getViewBox().state['mouseMode']==pg.ViewBox.RectMode for p in w.plots))
        w.close(); app.processEvents()

    def test_rectangle_zoom_with_mouse(self):
        app = QApplication.instance() or QApplication([])
        w = Window(); t = np.arange(100,dtype=float)
        w.loaded(Recording([Signal('test',t,t,'V'),Signal('small',t,t/10000,'A')],'test.mat'))
        p = w.plots[0]; w.add_signal(0,p); w.add_signal(1,p)
        w.separate_signal_axes(p,[1])
        extra = p.extra_axes[p.signal_axes[1]][1]
        w.show(); app.processEvents(); w.set_zoom_mode(True)
        bounds = p.getViewBox().sceneBoundingRect()
        start = p.mapFromScene(QtCore.QPointF(bounds.left()+bounds.width()*0.25,bounds.top()+bounds.height()*0.25))
        stop = p.mapFromScene(QtCore.QPointF(bounds.left()+bounds.width()*0.75,bounds.top()+bounds.height()*0.75))
        old = p.viewRange(); old_extra = extra.viewRange()[1]
        QTest.mousePress(p.viewport(),QtCore.Qt.MouseButton.LeftButton,pos=start)
        QTest.mouseMove(p.viewport(),stop,delay=30)
        QTest.mouseRelease(p.viewport(),QtCore.Qt.MouseButton.LeftButton,pos=stop)
        app.processEvents()
        now = p.viewRange()
        self.assertLess(np.ptp(now[0]),np.ptp(old[0])*0.75)
        self.assertLess(np.ptp(now[1]),np.ptp(old[1])*0.75)
        self.assertLess(np.ptp(extra.viewRange()[1]),np.ptp(old_extra)*0.75)
        w.close(); app.processEvents()

    def test_close_subplot_relinks_time_axis_and_allows_empty_tab(self):
        app = QApplication.instance() or QApplication([])
        w = Window(); t = np.arange(100,dtype=float)
        w.loaded(Recording([Signal('test',t,t,'V')],'test.mat'))
        for number in range(3):
            if number: w.add_plot()
            w.add_signal(0,w.plots[number])
        first, second, third = w.plots
        w.show(); app.processEvents()
        first.setXRange(20,40,padding=0)
        QTest.mouseClick(first.close_button,QtCore.Qt.MouseButton.LeftButton)
        app.processEvents()
        self.assertEqual(w.plots,[second,third])
        second.setXRange(30,50,padding=0); app.processEvents()
        np.testing.assert_allclose(third.viewRange()[0],[30,50],atol=0.5)
        self.assertEqual(w.workspace.plot_splitter.count(),2)
        self.assertEqual(len(w.signals),1)
        w.remove_plot(third); w.remove_plot(second)
        self.assertFalse(w.plots)
        w.activate_item(w.signal_items[0])
        self.assertEqual(len(w.plots),1)
        self.assertIn(0,w.plots[0].curves)
        w.close(); app.processEvents()

    def test_separate_axes_share_and_remove_without_losing_curves(self):
        app = QApplication.instance() or QApplication([])
        w = Window(); t = np.arange(100,dtype=float)
        w.loaded(Recording([Signal('voltage',t,t,'V'), Signal('current',t,t/10000,'A'),
                            Signal('current2',t,t/20000,'A')],'test.mat'))
        p = w.plots[0]
        for i in range(3): w.add_signal(i,p)
        w.show(); app.processEvents()
        menu = w.axis_menu(p,[1])
        next(a for a in menu.actions() if a.text()=='Plot on separate Y axis').trigger()
        app.processEvents()
        group = p.signal_axes[1]
        self.assertIsNotNone(group)
        axis, view = p.extra_axes[group]
        self.assertIn(p.curves[1],view.addedItems)
        self.assertNotIn(p.curves[1],p.getViewBox().addedItems)
        self.assertLess(np.ptp(view.viewRange()[1]),0.02)
        self.assertGreater(np.ptp(p.viewRange()[1]),90)
        self.assertEqual(len(p.plotItem.legend.items),3)
        same = next(a.menu() for a in w.axis_menu(p,[2]).actions() if a.text()=='Plot on same Y axis as')
        next(a for a in same.actions() if a.text()=='current').trigger()
        self.assertEqual(p.signal_axes[2],group)
        self.assertIn(p.curves[2],view.addedItems)
        w.remove_signals(p,[1])
        self.assertIn(group,p.extra_axes)
        self.assertEqual(len(p.plotItem.legend.items),2)
        w.set_signal_axis(p,[2],None)
        self.assertFalse(p.extra_axes)
        self.assertIn(p.curves[2],p.getViewBox().addedItems)
        self.assertEqual(len(p.plotItem.legend.items),2)
        self.assertEqual(len(p.signal_list.selectedItems()),0)
        w.close(); app.processEvents()

    def test_independent_axis_follows_zoom_and_cleans_up_on_clear(self):
        app = QApplication.instance() or QApplication([])
        w = Window(); t = np.arange(100,dtype=float)
        w.loaded(Recording([Signal('big',t,t,'V'), Signal('small',t,t/10000,'A')],'test.mat'))
        p = w.plots[0]
        w.add_signal(0,p); w.add_signal(1,p)
        w.separate_signal_axes(p,[1]); w.show(); app.processEvents()
        axis,view = p.extra_axes[p.signal_axes[1]]
        old_primary = p.viewRange()[1]; old_extra = view.viewRange()[1]
        w.zoom_by(0.5); app.processEvents()
        self.assertAlmostEqual(np.ptp(view.viewRange()[1])/np.ptp(old_extra),0.5,places=3)
        self.assertAlmostEqual(np.ptp(p.viewRange()[1])/np.ptp(old_primary),0.5,places=3)
        np.testing.assert_allclose(view.viewRange()[0],p.viewRange()[0],atol=0.5)
        self.assertAlmostEqual(view.geometry().width(),p.getViewBox().sceneBoundingRect().width(),places=2)
        w.clear_plots(); app.processEvents()
        self.assertFalse(p.extra_axes); self.assertFalse(p.signal_axes)
        self.assertFalse(p.plotItem.legend.items)
        w.close(); app.processEvents()

    def test_signal_color_updates_curve_list_axis_and_survives_readd(self):
        app = QApplication.instance() or QApplication([])
        w = Window(); t = np.arange(10,dtype=float)
        w.loaded(Recording([Signal('one',t,t,'V')],'test.mat'))
        p = w.plots[0]; w.add_signal(0,p)
        w.add_plot(); other = w.plots[1]; w.add_signal(0,other)
        previous_other = other.curves[0].opts['pen'].color()
        w.separate_signal_axes(p,[0])
        chosen = QtGui.QColor('#32b9ad')
        before_range = p.viewRange()
        with patch('opencaliper.gui.Q.QColorDialog.getColor', return_value=chosen):
            menu = w.axis_menu(p,[0])
            next(a for a in menu.actions() if a.text()=='Change color…').trigger()
        self.assertEqual(p.curves[0].opts['pen'].color(),chosen)
        self.assertEqual(p.signal_list.item(0).foreground().color(),chosen)
        self.assertEqual(p.extra_axes[p.signal_axes[0]][0].pen().color(),chosen)
        self.assertEqual(p.plotItem.legend.items[0][0].item.opts['pen'].color(),chosen)
        self.assertEqual(other.curves[0].opts['pen'].color(),previous_other)
        np.testing.assert_allclose(p.viewRange(),before_range)
        w.set_signal_axis(p,[0],None)
        self.assertEqual(p.curves[0].opts['pen'].color(),chosen)
        w.remove_signals(p,[0]); w.add_signal(0,p)
        self.assertEqual(p.curves[0].opts['pen'].color(),chosen)
        with patch('opencaliper.gui.Q.QColorDialog.getColor', return_value=QtGui.QColor()):
            w.choose_signal_color(p,[0])
        self.assertEqual(p.curves[0].opts['pen'].color(),chosen)
        w.close(); app.processEvents()

    def test_right_click_curve_opens_color_menu(self):
        app = QApplication.instance() or QApplication([])
        w = Window(); t = np.arange(20,dtype=float)
        w.loaded(Recording([Signal('one',t,t,'V')],'test.mat'))
        p = w.plots[0]; w.add_signal(0,p)
        w.show(); app.processEvents()
        scene_pos = p.getViewBox().mapViewToScene(QtCore.QPointF(10,10))
        point = p.mapFromScene(scene_pos)
        menus = []
        original = w.plot_color_menu
        def capture(plot,pos):
            result = original(plot,pos); menus.append(result); return result
        with patch.object(w,'plot_color_menu',side_effect=capture), patch('opencaliper.gui.Q.QMenu.popup') as popup:
            QTest.mouseClick(p.viewport(),QtCore.Qt.MouseButton.RightButton,pos=point)
            app.processEvents()
            popup.assert_called_once()
        self.assertEqual(len(menus),1)
        self.assertIn('Change color…',[a.text() for a in menus[0].actions()])
        chosen = QtGui.QColor('#b0bec5')
        with patch('opencaliper.gui.Q.QColorDialog.getColor',return_value=chosen):
            w.choose_background_color(p)
        self.assertEqual(p.backgroundBrush().color(),chosen)
        w.close(); app.processEvents()
