"""Sidebar drops, ordering, stacking and workspace persistence across analyses."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
from pathlib import Path
import unittest
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets as Q
from opencaliper import Signal, Recording
from opencaliper.gui import Window


class SignalOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = Q.QApplication.instance() or Q.QApplication([])

    def setUp(self):
        self.w = Window()
        t = np.arange(32.) / 32
        self.w.loaded(Recording([Signal(f'channel{i}', t, np.sin(t*20)+i, 'V')
                                 for i in range(3)], 'test.mat'))
        self.w.show(); self.app.processEvents()

    def tearDown(self):
        self.w.close(); self.app.processEvents()

    def test_explorer_drop_on_sidebar_and_internal_reorder(self):
        w = self.w
        for kind in ('time', 'spectrum'):
            page = w.add_analysis(kind)
            plot = page.plots[0]; widget = plot.signal_list
            mime = w.list.mimeData([w.signal_items[i] for i in (0, 1, 2)])
            enter = QtGui.QDragEnterEvent(QtCore.QPoint(5, 5), QtCore.Qt.DropAction.CopyAction,
                                         mime, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
            Q.QApplication.sendEvent(widget.viewport(), enter)
            self.assertTrue(enter.isAccepted())
            event = QtGui.QDropEvent(QtCore.QPointF(5, 5), QtCore.Qt.DropAction.CopyAction,
                                    mime, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
            Q.QApplication.sendEvent(widget.viewport(), event)
            self.assertTrue(event.isAccepted())
            self.assertEqual(list(plot.curves), [0, 1, 2])
            self.app.processEvents()
            mime = widget.mimeData([widget.item(2)])
            event = QtGui.QDropEvent(QtCore.QPointF(5, 1), QtCore.Qt.DropAction.CopyAction,
                                    mime, QtCore.Qt.MouseButton.LeftButton, QtCore.Qt.KeyboardModifier.NoModifier)
            widget.dropEvent(event)
            self.assertEqual(list(plot.curves), [2, 0, 1])
            self.assertGreater(plot.curves[2].zValue(), plot.curves[0].zValue())
            self.assertEqual(len(plot.plotItem.legend.items), 3)
            self.assertEqual(len(w.signals), 3)

    def test_cross_subplot_copy_retains_visibility_and_source(self):
        w = self.w; source = w.plots[0]
        w.drop_signals(source, [0, 1, 2], 0)
        w.set_signal_visibility(source, [1], False)
        w.drop_signals(source, [1], 0)
        self.assertIn(1, source.hidden_signals)
        self.assertFalse(source.curves[1].isVisible())
        w.add_plot(); target = w.plots[1]
        w.drop_signals(target, [1, 0], 0)
        self.assertEqual(list(source.curves), [1, 0, 2])
        self.assertEqual(list(target.curves), [1, 0])
        self.assertTrue(target.curves[1].isVisible())
        w.drop_signals(target, [1, 0], 2)
        self.assertEqual(target.signal_list.count(), 2)

    def test_order_survives_undo_workspace_and_sparameter_representation(self):
        w = self.w
        f = np.arange(1., 6.) * 1e6
        w.loaded(Recording([Signal(name, f, np.full(5, .1+.1j), '', domain='sparameter', reference_impedance=50.)
                            for name in ('S11', 'S21', 'S22')], 'test.s2p'))
        page = w.add_analysis('sparameter'); plot = page.plots[0]
        w.drop_signals(plot, [3, 4, 5], 0)
        w.drop_signals(plot, [5, 3], 0)
        self.assertEqual(list(plot.curves), [5, 3, 4])
        self.app.processEvents()
        w.undo(); self.app.processEvents()
        self.assertEqual(list(w.plots[0].curves), [3, 4, 5])
        w.redo(); self.app.processEvents()
        self.assertEqual(list(w.plots[0].curves), [5, 3, 4])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'order.ocw'
            w.save_workspace(path); w.open_workspace(path)
            self.app.processEvents()
        self.assertEqual(list(w.plots[0].curves), [5, 3, 4])
        w.set_sparameter_representation(w.workspace, 'Phase (degrees)')
        self.assertEqual(list(w.plots[0].curves), [5, 3, 4])


if __name__ == '__main__': unittest.main()
