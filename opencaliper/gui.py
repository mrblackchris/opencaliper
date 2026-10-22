"""Qt measurement workspace with asynchronous imports and linked plots."""
from pathlib import Path
import sys
import json

# IDEs can execute this file directly instead of importing the package.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = 'opencaliper'

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets as Q
import pyqtgraph as pg
from .core import load, export, Recording, Signal
from .analysis import statistics, fft, cursor_values
from .converterscripts.formats import input_filter, output_filter
from .workspace import WorkspaceMixin, reversible
from .tools import ToolsMixin


class Loader(QtCore.QThread):
    """Worker thread that emits a Recording or error text without touching widgets."""
    loaded = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, path, parent):
        super().__init__(parent); self.path = path

    def run(self):
        """Read the file in the worker and emit loaded or failed; QThread emits finished."""
        try: self.loaded.emit(load(self.path))
        except Exception as exc: self.failed.emit(f'{self.path}: {exc}')


SIGNAL_MIME = 'application/x-opencaliper-signals'


class SignalList(Q.QListWidget):
    """Draggable plot sidebar that emits removal requests for selected source IDs."""
    files_dropped = QtCore.Signal(list)
    remove_requested = QtCore.Signal(list)

    def __init__(self, allow_files=False, removable=False):
        super().__init__()
        self.allow_files = allow_files
        self.removable = removable
        self.setDragEnabled(True)
        self.setAcceptDrops(allow_files)
        self.setSelectionMode(Q.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDefaultDropAction(QtCore.Qt.DropAction.CopyAction)

    def mimeData(self, items):
        mime = QtCore.QMimeData()
        mime.setData(SIGNAL_MIME, json.dumps([i.data(QtCore.Qt.ItemDataRole.UserRole) for i in items]).encode())
        return mime

    def dragEnterEvent(self, event):
        if self.allow_files and event.mimeData().hasUrls(): event.acceptProposedAction()
        else: event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        if self.allow_files and event.mimeData().hasUrls():
            self.files_dropped.emit([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()])
            event.acceptProposedAction()
        else: event.ignore()

    def keyPressEvent(self, event):
        if self.removable and event.key() == QtCore.Qt.Key.Key_Delete:
            self.remove_requested.emit([i.data(QtCore.Qt.ItemDataRole.UserRole) for i in self.selectedItems()])
            event.accept()
        else: super().keyPressEvent(event)


class MeasurementExplorer(Q.QTreeWidget):
    """Shared file/channel tree supporting local-file drops and file-unload requests."""
    files_dropped = QtCore.Signal(list)
    remove_requested = QtCore.Signal(list)

    def __init__(self):
        super().__init__()
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setSelectionMode(Q.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDefaultDropAction(QtCore.Qt.DropAction.CopyAction)
        self.setToolTip('Expand a file to browse signals. Select files and press Delete to unload.')

    def drawBranches(self, painter, rect, index):
        if not index.parent().isValid() and self.model().hasChildren(index):
            box = QtCore.QRect(rect.right()-15, rect.center().y()-5, 10, 10)
            painter.save()
            painter.setPen(self.palette().color(QtGui.QPalette.ColorRole.Text))
            painter.drawRect(box)
            painter.drawLine(box.left()+2, box.center().y(), box.right()-2, box.center().y())
            if not self.isExpanded(index):
                painter.drawLine(box.center().x(), box.top()+2, box.center().x(), box.bottom()-2)
            painter.restore()

    def mimeData(self, items):
        indices = [i.data(0, QtCore.Qt.ItemDataRole.UserRole) for i in items if i.parent() is not None]
        mime = QtCore.QMimeData()
        if indices:
            mime.setData(SIGNAL_MIME, json.dumps(indices).encode())
        return mime

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: event.ignore()

    def dragMoveEvent(self, event): self.dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            self.files_dropped.emit([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()])
            event.acceptProposedAction()
        else: event.ignore()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Delete:
            self.remove_requested.emit([i.data(0, QtCore.Qt.ItemDataRole.UserRole)
                                        for i in self.selectedItems() if i.parent() is None])
            event.accept()
        else: super().keyPressEvent(event)


class SignalViewBox(pg.ViewBox):
    """Main plot view with the application signal/background color context menu."""
    color_menu = None

    def raiseContextMenu(self, event):
        if self.color_menu is None:
            return super().raiseContextMenu(event)
        position = event.screenPos().toPoint()
        menu = self.color_menu(event.scenePos())
        menu.addSeparator()
        menu.addAction('Plot options…', lambda: QtCore.QTimer.singleShot(
            0, lambda: self.getMenu(None).popup(position)))
        menu.aboutToHide.connect(menu.deleteLater)
        menu.popup(position)
        event.accept()


class Plot(pg.PlotWidget):
    """One subplot with curves, source IDs, axis assignments and display settings.
    
    Owns displayed signals and pyqtgraph objects. Source IDs refer to Window.signals.
    Extra Y axes share X with the main view. Log scene coordinates are converted
    at the view boundary; numerical analysis continues to use physical arrays."""
    dropped = QtCore.Signal(int)

    def __init__(self):
        super().__init__(viewBox=SignalViewBox()); self.setAcceptDrops(True)
        self.showGrid(x=True, y=True, alpha=0.2)
        self.setLabel('bottom', 'Time', units='s')
        self.addLegend(); self.curves = {}
        self.display_signals = {}
        self.fit_bounds = {}
        self.signal_colors = {}
        self.signal_names = {}
        self.signal_axes = {}
        self.extra_axes = {}
        self.next_axis_id = 0
        self.log_x = False
        self.log_y = False
        self.setDownsampling(auto=True, mode='peak'); self.setClipToView(True)
        self.getViewBox().sigResized.connect(self.update_axis_geometry)
        self.previous_y_range = self.getViewBox().viewRange()[1][:]
        self.getViewBox().sigYRangeChanged.connect(self.sync_y_navigation)

    def update_axis_geometry(self):
        for axis, view in self.extra_axes.values():
            view.setGeometry(self.getViewBox().sceneBoundingRect())
            view.linkedViewChanged(self.getViewBox(), pg.ViewBox.XAxis)

    def sync_y_navigation(self, view, bounds):
        old_low, old_high = self.previous_y_range
        self.previous_y_range = list(bounds)
        if old_high <= old_low: return
        low_fraction = (bounds[0]-old_low)/(old_high-old_low)
        high_fraction = (bounds[1]-old_low)/(old_high-old_low)
        for axis, extra in self.extra_axes.values():
            low, high = extra.viewRange()[1]
            extra.setYRange(low+(high-low)*low_fraction, low+(high-low)*high_fraction, padding=0)

    def new_y_axis(self):
        key = self.next_axis_id; self.next_axis_id += 1
        axis = pg.AxisItem('right')
        view = pg.ViewBox(enableMenu=False)
        view.setMouseEnabled(x=False, y=False)
        view.setAcceptedMouseButtons(QtCore.Qt.MouseButton.NoButton)
        # Keep interaction on the main view; it forwards normalized Y navigation.
        view.setZValue(self.getViewBox().zValue()-1)
        self.scene().addItem(view)
        self.plotItem.layout.addItem(axis, 2, 3+len(self.extra_axes))
        axis.linkToView(view); view.setXLink(self.getViewBox())
        self.extra_axes[key] = (axis, view)
        self.update_axis_geometry()
        return key

    def axis_view(self, key):
        return self.getViewBox() if key is None else self.extra_axes[key][1]

    def x_to_scene(self, value):
        """Convert a physical axis value into linear or log10 scene coordinates."""
        return float(np.log10(value)) if self.log_x and value > 0 else (np.nan if self.log_x else value)

    def x_from_scene(self, value):
        """Convert a scene coordinate back to physical seconds or frequency."""
        return float(10.**np.clip(value, -300, 300)) if self.log_x else value

    def physical_x_range(self):
        return [self.x_from_scene(v) for v in self.viewRange()[0]]

    def set_physical_x_range(self, low, high, padding=0):
        if self.log_x:
            positives = [s.time[s.time > 0].min() for s in self.display_signals.values() if np.any(s.time > 0)]
            if high <= 0: return
            if low <= 0: low = min(positives) if positives else high/1000
            low = min(low, high)
        self.setXRange(self.x_to_scene(low), self.x_to_scene(high), padding=padding)

    def detach_curve(self, index):
        curve = self.curves[index]
        # Avoid view-dependent clipping while Qt reparents the curve between views.
        curve.setClipToView(False)
        key = self.signal_axes[index]
        if key is None: self.removeItem(curve)
        else:
            self.extra_axes[key][1].removeItem(curve)
            self.plotItem.legend.removeItem(curve)

    def assign_axis(self, indices, key):
        """Move curves to the selected Y view, then discard unused additional axes."""
        for index in indices:
            if index not in self.curves or self.signal_axes[index] == key: continue
            self.detach_curve(index)
            self.signal_axes[index] = key
            curve = self.curves[index]
            if key is None: self.addItem(curve)
            else:
                self.extra_axes[key][1].addItem(curve)
                curve.setClipToView(True)
                self.plotItem.legend.addItem(curve, curve.name())
        self.prune_axes()

    def prune_axes(self):
        """Remove unused Y views and repack remaining axis layout columns."""
        used = set(self.signal_axes.values())
        for key in list(self.extra_axes):
            if key in used: continue
            axis, view = self.extra_axes.pop(key)
            axis.unlinkFromView(); self.plotItem.layout.removeItem(axis)
            self.scene().removeItem(axis)
            view.setXLink(None); view.close(); self.scene().removeItem(view)
            axis.deleteLater(); view.deleteLater()
        # Repack columns after removing an axis.
        for axis, view in self.extra_axes.values(): self.plotItem.layout.removeItem(axis)
        for column, (axis, view) in enumerate(self.extra_axes.values(), 3):
            self.plotItem.layout.addItem(axis, 2, column)
        self.update_axis_geometry()

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(SIGNAL_MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event): event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasFormat(SIGNAL_MIME):
            for index in json.loads(bytes(event.mimeData().data(SIGNAL_MIME))):
                self.dropped.emit(index)
            event.acceptProposedAction()


class AnalysisPage(Q.QSplitter):
    """One analysis tab owning plots, cursor positions and navigation state.
    
    kind selects time, fft or imported spectrum. For FFT, fft_interval holds source seconds while
    cursor_positions holds displayed Hz. Neither state belongs to another tab."""
    def __init__(self, kind='time', fft_interval=None):
        super().__init__(QtCore.Qt.Orientation.Vertical)
        self.kind = kind
        self.pending_signals = set()
        self.fft_resample = False
        self.fft_sample_rate = 0.
        self.fft_interval = tuple(fft_interval) if fft_interval is not None else (None, None)
        self.plots = []
        self.cursor_positions = [0., 1.]
        self.cursors_visible = False
        self.next_cursor_index = 0
        self.zoom_mode = False
        self.syncing = False
        self.syncing_x = False
        self.plot_splitter = Q.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.plot_splitter.setChildrenCollapsible(False)
        self.plot_splitter.setHandleWidth(8)
        self.addWidget(self.plot_splitter)
        self.readout = Q.QPlainTextEdit()
        self.readout.setReadOnly(True); self.readout.setMaximumHeight(160)
        self.addWidget(self.readout)
        self.setStretchFactor(0, 1); self.setStretchFactor(1, 0)
        self.setSizes([650, 110])
        if kind == 'fft':
            settings = Q.QWidget(); settings_layout = Q.QVBoxLayout(settings)
            row = Q.QHBoxLayout(); settings_layout.addLayout(row)
            row.addWidget(Q.QLabel('FFT: Hann · Mean removed · Peak amplitude'))
            self.use_interval = Q.QCheckBox('Time interval')
            self.use_interval.setChecked(self.fft_interval[0] is not None)
            row.addWidget(self.use_interval)
            self.start_time = Q.QDoubleSpinBox(); self.stop_time = Q.QDoubleSpinBox()
            for field, value in zip((self.start_time, self.stop_time), self.fft_interval):
                field.setDecimals(12); field.setRange(-1e15, 1e15)
                field.setSuffix(' s'); field.setValue(value or 0.)
                field.setEnabled(self.use_interval.isChecked())
                self.use_interval.toggled.connect(field.setEnabled)
                row.addWidget(field)
            resampling = Q.QHBoxLayout(); settings_layout.addLayout(resampling)
            self.resample_box = Q.QCheckBox('Resample (linear)')
            self.resample_box.setToolTip('Interpolate to uniform time samples before FFT; source data stays unchanged.')
            resampling.addWidget(self.resample_box)
            self.sample_rate = Q.QDoubleSpinBox(); self.sample_rate.setDecimals(6)
            self.sample_rate.setRange(0, 1e12); self.sample_rate.setSpecialValueText('Auto (median interval)')
            self.sample_rate.setSuffix(' Hz'); self.sample_rate.setEnabled(False)
            self.sample_rate.setToolTip('Auto uses the reciprocal median interval for each selected source. Interpolation adds no bandwidth and does not filter aliasing.')
            self.resample_box.toggled.connect(self.sample_rate.setEnabled)
            resampling.addWidget(Q.QLabel('Sample rate:'))
            resampling.addWidget(self.sample_rate)
            resampling.addStretch()
            self.recalculate = Q.QPushButton('Recalculate')
            self.recalculate.setToolTip('Apply the interval and resampling settings to all spectra in this tab')
            resampling.addWidget(self.recalculate)
            settings.setMaximumHeight(110)
            self.insertWidget(0, settings)
            self.setStretchFactor(0, 0); self.setStretchFactor(1, 1); self.setStretchFactor(2, 0)
            self.setSizes([85, 650, 110])


class Window(WorkspaceMixin, ToolsMixin, Q.QMainWindow):
    """Desktop controller owning shared sources and independent analysis pages.
    
    Source signals and explorer items are indexed by session-local integer IDs.
    This class connects UI events, numerical operations and view cleanup. Loading
    runs in workers; FFT and export currently execute on the GUI thread."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle('OpenCaliper'); self.resize(1450, 900)
        self.signals = {}; self.signal_items = {}; self.files = {}; self.next_signal_id = 0; self.next_file_id = 0
        self.workers = []; self.dialogs = []; self.analysis_counter = 0
        self.setAcceptDrops(True)
        bar = self.addToolBar('Measurement')
        for label, callback in [('Open files', self.open_files), ('Export all', self.save),
                                ('New analysis', lambda: self.add_analysis()), ('Add plot', self.add_plot), ('Clear plots', self.clear_plots),
                                ('Fit both axes', self.fit), ('FFT', self.spectrum), ('Statistics', self.stats)]:
            bar.addAction(label, callback)
        self.cursors_enabled = Q.QCheckBox('Diff cursors'); bar.addWidget(self.cursors_enabled)
        self.cursors_enabled.setToolTip('When enabled, left-click inside a plot to place A, then B. Drag cursors to adjust.')
        self.cursors_enabled.toggled.connect(self.toggle_cursors)
        self.addToolBarBreak()
        navigation = self.addToolBar('Zoom and navigation')
        modes = QtGui.QActionGroup(self)
        self.pan_action = navigation.addAction('Pan')
        self.zoom_action = navigation.addAction('Rectangle zoom')
        for action in (self.pan_action, self.zoom_action):
            action.setCheckable(True); modes.addAction(action)
        self.pan_action.setChecked(True)
        self.pan_action.triggered.connect(lambda: self.set_zoom_mode(False))
        self.zoom_action.triggered.connect(lambda: self.set_zoom_mode(True))
        navigation.addAction('Zoom in', lambda: self.zoom_by(0.5))
        navigation.addAction('Zoom out', lambda: self.zoom_by(2.0))
        navigation.addAction('Fit both axes', self.fit)
        navigation.addWidget(Q.QLabel('  Wheel: zoom • Drag: pan or rectangle • Drag dividers: resize plots'))
        split = Q.QSplitter(); self.setCentralWidget(split)
        left = Q.QWidget(); layout = Q.QVBoxLayout(left)
        layout.addWidget(Q.QLabel('Variable Explorer'))
        layout.addWidget(Q.QLabel('Drop measurement files here'))
        search = Q.QLineEdit(); search.setPlaceholderText('Filter signals…'); layout.addWidget(search)
        self.list = MeasurementExplorer(); layout.addWidget(self.list)
        self.list.files_dropped.connect(lambda paths: [self.open_path(p) for p in paths])
        self.list.remove_requested.connect(self.remove_files)
        self.list.itemDoubleClicked.connect(self.activate_item)
        self.list.currentItemChanged.connect(lambda *_: self.update_readout())
        self.search = search
        search.textChanged.connect(self.filter)
        split.addWidget(left)
        self.tabs = Q.QTabWidget()
        self.tabs.setMovable(True); self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_analysis)
        self.tabs.currentChanged.connect(self.analysis_changed)
        self.tabs.tabBarDoubleClicked.connect(self.rename_analysis)
        split.addWidget(self.tabs); split.setSizes([300, 1150])
        split.setCollapsible(0, False)
        self.add_analysis()
        self.init_tools()
        self.init_history()
        self.statusBar().showMessage('Open a measurement, then drag signals into a plot. Double-click adds to the first plot.')

    @property
    def workspace(self): return self.tabs.currentWidget()

    @property
    def plots(self): return self.workspace.plots

    @property
    def readout(self): return self.workspace.readout

    @property
    def cursor_positions(self): return self.workspace.cursor_positions

    def all_plots(self):
        return [p for i in range(self.tabs.count()) for p in self.tabs.widget(i).plots]

    def add_analysis(self, kind='time', fft_interval=None):
        """Create a time, FFT or Spectrum page with an initial subplot."""
        self.analysis_counter += 1
        page = AnalysisPage(kind, fft_interval)
        if kind == 'fft':
            page.cursors_visible = True
            page.recalculate.clicked.connect(lambda: self.recalculate_fft(page))
        title = 'Spectrum' if kind == 'spectrum' else (f'FFT {self.analysis_counter}' if kind == 'fft' else f'Analysis {self.analysis_counter}')
        index = self.tabs.addTab(page, title)
        self.tabs.setCurrentIndex(index)
        self.add_plot()
        return page

    def close_analysis(self, index):
        if self.tabs.count() == 1:
            self.statusBar().showMessage('Keep at least one analysis tab open')
            return
        page = self.tabs.widget(index)
        for plot in list(page.plots): self.remove_plot(plot)
        self.tabs.removeTab(index); page.deleteLater()

    def rename_analysis(self, index):
        if index < 0: return
        name, ok = Q.QInputDialog.getText(self, 'Rename analysis', 'Name:', text=self.tabs.tabText(index))
        if ok and name.strip(): self.tabs.setTabText(index, name.strip())

    def analysis_changed(self, index):
        if index < 0: return
        page = self.workspace
        with QtCore.QSignalBlocker(self.cursors_enabled):
            self.cursors_enabled.setChecked(page.cursors_visible)
        self.pan_action.setChecked(not page.zoom_mode)
        self.zoom_action.setChecked(page.zoom_mode)
        self.update_readout()

    def set_zoom_mode(self, enabled):
        self.workspace.zoom_mode = enabled
        for plot in self.plots:
            plot.getViewBox().setMouseMode(pg.ViewBox.RectMode if enabled else pg.ViewBox.PanMode)
        self.pan_action.setChecked(not enabled); self.zoom_action.setChecked(enabled)

    def zoom_by(self, factor):
        if not self.plots: return
        # Scale the shared X axis once, and each independent Y axis once.
        self.plots[0].getViewBox().scaleBy((factor, 1))
        for plot in self.plots: plot.getViewBox().scaleBy((1, factor))

    def open_files(self):
        paths, _ = Q.QFileDialog.getOpenFileNames(self, 'Open measurements', '', input_filter())
        for path in paths: self.open_path(path)

    def open_path(self, path):
        """Start and retain a Loader; connect its results to GUI-thread handlers."""
        worker = Loader(path, self); self.workers.append(worker)
        worker.loaded.connect(self.loaded); worker.failed.connect(self.error)
        worker.finished.connect(lambda: self.finished(worker))
        self.statusBar().showMessage(f'Loading {Path(path).name}…'); worker.start()

    def finished(self, worker):
        self.workers.remove(worker); worker.deleteLater()

    def loaded(self, recording):
        """Register a decoded recording with new file/signal IDs and explorer items."""
        file_id = self.next_file_id; self.next_file_id += 1
        root = Q.QTreeWidgetItem([Path(recording.source).name or 'Measurement'])
        root.setData(0, QtCore.Qt.ItemDataRole.UserRole, file_id)
        root.setToolTip(0, recording.source)
        root.setFlags(root.flags() & ~QtCore.Qt.ItemFlag.ItemIsDragEnabled)
        self.list.addTopLevelItem(root)
        ids = []
        for s in recording.signals:
            index = self.next_signal_id; self.next_signal_id += 1
            item = Q.QTreeWidgetItem([f'{s.name} [{s.unit}]'])
            item.setData(0, QtCore.Qt.ItemDataRole.UserRole, index)
            item.setToolTip(0, f'{len(s.time):,} samples | {s.time[0]:.9g} … {s.time[-1]:.9g} '+('Hz' if s.domain == 'frequency' else 's'))
            root.addChild(item)
            self.signals[index] = s; self.signal_items[index] = item; ids.append(index)
        self.files[file_id] = (root, ids)
        self.filter(self.search.text())
        self.statusBar().showMessage(f'Loaded {len(ids)} signals from {Path(recording.source).name}; expand + to browse')
        if self.list.currentItem() is None: self.list.setCurrentItem(root)
        frequency_ids = [i for i in ids if self.signals[i].domain == 'frequency']
        if frequency_ids and not getattr(self, '_restoring', False):
            page = self.add_analysis('spectrum')
            for i in frequency_ids: self.add_signal(i, page.plots[0])
            self.fit()

    def activate_item(self, item, column=0):
        if item.parent() is not None:
            if not self.plots: self.add_plot()
            self.add_signal(item.data(0, QtCore.Qt.ItemDataRole.UserRole), self.plots[0])

    def remove_files(self, file_ids):
        """Unload source IDs and their curves from every tab, without deleting files."""
        for file_id in file_ids:
            entry = self.files.pop(file_id, None)
            if entry is None: continue
            root, indices = entry
            for n in range(self.tabs.count()):
                self.tabs.widget(n).pending_signals.difference_update(indices)
            for plot in self.all_plots(): self.remove_signals(plot, indices)
            for index in indices:
                self.signals.pop(index, None); self.signal_items.pop(index, None)
            self.list.takeTopLevelItem(self.list.indexOfTopLevelItem(root))
        self.update_readout()
        self.statusBar().showMessage('Selected measurements unloaded')

    def add_plot(self):
        """Create the active page subplot, sidebar, controls, cursors and connections."""
        page = self.workspace
        plot = Plot(); plot.workspace = page
        plot.scene().sigMouseClicked.connect(lambda event: self.place_cursor(plot, event))
        plot.getViewBox().color_menu = lambda pos: self.plot_color_menu(plot, pos)
        plot.getViewBox().sigYRangeChanged.connect(lambda view, bounds: self.update_annotation_labels(plot, bounds))
        if page.kind in ('fft', 'spectrum'): plot.setLabel('bottom', 'Frequency', units='Hz')
        if page.kind == 'spectrum':
            # Receiver sweeps may have nonuniform spacing; automatic decimation
            # assumes regular X samples and can distort these spectra.
            plot.setDownsampling(ds=1, auto=False)
        plot.getViewBox().setMouseMode(pg.ViewBox.RectMode if page.zoom_mode else pg.ViewBox.PanMode)
        panel = Q.QSplitter()
        plot.panel = panel
        sidebar = Q.QWidget(); layout = Q.QVBoxLayout(sidebar)
        plot.title = Q.QLabel(f'Plot {len(self.plots)+1} signals')
        layout.addWidget(plot.title)
        layout.addWidget(Q.QLabel('Select + Delete to remove'))
        plot.signal_list = SignalList(removable=True)
        layout.addWidget(plot.signal_list)
        plot.signal_list.remove_requested.connect(lambda indices: self.remove_signals(plot, indices))
        plot.signal_list.currentItemChanged.connect(lambda item, _: self.select_signal(item))
        plot.signal_list.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        plot.signal_list.customContextMenuRequested.connect(lambda pos: self.signal_menu(plot, pos))
        fit_button = Q.QPushButton('Fit both axes')
        fit_button.clicked.connect(lambda: self.fit_plot(plot))
        layout.addWidget(fit_button)
        plot_container = Q.QWidget(); plot_layout = Q.QVBoxLayout(plot_container)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        header = Q.QHBoxLayout(); header.addStretch()
        plot.log_x_box = Q.QCheckBox('Log X'); plot.log_y_box = Q.QCheckBox('Log Y')
        header.addWidget(plot.log_x_box); header.addWidget(plot.log_y_box)
        clear_button = Q.QToolButton(); clear_button.setText('Clear plot')
        clear_button.setToolTip('Remove all signals from this plot')
        clear_button.clicked.connect(lambda: self.remove_signals(plot, list(plot.curves)))
        close_button = Q.QToolButton(); close_button.setText('×')
        close_button.setToolTip('Remove this subplot')
        close_button.clicked.connect(lambda: self.remove_plot(plot))
        plot.close_button = close_button
        header.addWidget(clear_button); header.addWidget(close_button)
        plot_layout.addLayout(header); plot_layout.addWidget(plot)
        panel.addWidget(sidebar); panel.addWidget(plot_container); panel.setSizes([220, 800])
        panel.setMinimumHeight(140)
        page.plot_splitter.addWidget(panel)
        page.plot_splitter.setSizes([max(140, page.plot_splitter.height()//page.plot_splitter.count())]*page.plot_splitter.count())
        plot.getViewBox().sigXRangeChanged.connect(
            lambda view, bounds: self.sync_time_range(page, plot, bounds))
        plot.dropped.connect(lambda index: self.add_signal(index, plot))
        plot.cursors = [pg.InfiniteLine(pos=p, angle=90, movable=True, pen=pg.mkPen(c, width=2), label=l)
                        for p,c,l in zip(self.cursor_positions, ['#ffd166','#ef476f'], ['A','B'])]
        for i, cursor in enumerate(plot.cursors):
            plot.addItem(cursor, ignoreBounds=True); cursor.setVisible(page.cursors_visible)
            cursor.sigPositionChanged.connect(lambda line, index=i, owner=page, source=plot: self.move_cursor(index, source.x_from_scene(line.value()), owner))
        self.plots.append(plot)
        plot.log_x_box.toggled.connect(lambda: self.set_plot_log(plot))
        plot.log_y_box.toggled.connect(lambda: self.set_plot_log(plot))
        plot.plotItem.ctrl.logXCheck.toggled.connect(plot.log_x_box.setChecked)
        plot.plotItem.ctrl.logYCheck.toggled.connect(plot.log_y_box.setChecked)
        if page.kind == 'fft':
            with QtCore.QSignalBlocker(plot.log_x_box), QtCore.QSignalBlocker(plot.log_y_box):
                plot.log_x_box.setChecked(True); plot.log_y_box.setChecked(True)
            self.set_plot_log(plot)
        elif page.kind == 'spectrum':
            plot.log_x_box.setChecked(True)

    def set_plot_log(self, plot):
        page = plot.workspace
        page.syncing_x = True
        try:
            plot.log_x = plot.log_x_box.isChecked(); plot.log_y = plot.log_y_box.isChecked()
            plot.setLogMode(x=plot.log_x, y=plot.log_y)
            for curve in plot.curves.values(): curve.setLogMode(plot.log_x, plot.log_y)
            for axis, view in plot.extra_axes.values(): axis.setLogMode(plot.log_y)
        finally: page.syncing_x = False
        annotations = list(getattr(plot, "annotations", []))
        self.clear_annotations(plot)
        for annotation in annotations: self.draw_annotation(plot, annotation)
        self.move_cursor(0, page.cursor_positions[0], page)
        self.move_cursor(1, page.cursor_positions[1], page)
        self.fit_plot(plot)

    def sync_time_range(self, page, source, bounds):
        if page.syncing_x or source not in page.plots: return
        page.syncing_x = True
        try:
            physical = [source.x_from_scene(v) for v in bounds]
            for other in page.plots:
                if other is not source: other.set_physical_x_range(*physical)
        finally: page.syncing_x = False

    def remove_plot(self, plot):
        page = plot.workspace
        if plot not in page.plots: return
        self.remove_signals(plot, list(plot.curves))
        x_range = plot.physical_x_range()
        page.plots.remove(plot)
        plot.setXLink(None)
        for other in page.plots: other.setXLink(None)
        if page.plots:
            page.plots[0].set_physical_x_range(*x_range)
        for number, other in enumerate(page.plots, 1): other.title.setText(f'Plot {number} signals')
        plot.panel.hide(); plot.panel.setParent(None); plot.panel.deleteLater()
        self.update_readout(page)
        self.statusBar().showMessage('Subplot removed. Use Add plot to create another.')

    def signal_menu(self, plot, pos):
        item = plot.signal_list.itemAt(pos)
        if item is None: return
        if not item.isSelected(): plot.signal_list.setCurrentItem(item)
        indices = [i.data(QtCore.Qt.ItemDataRole.UserRole) for i in plot.signal_list.selectedItems()]
        menu = self.axis_menu(plot, indices)
        try: menu.exec(plot.signal_list.viewport().mapToGlobal(pos))
        finally: menu.deleteLater()

    def axis_menu(self, plot, indices):
        menu = Q.QMenu(self)
        menu.addAction('Change color…', lambda: self.choose_signal_color(plot, indices))
        menu.addAction('Rename signal…', lambda: self.rename_signals(plot, indices))
        menu.addSeparator()
        menu.addAction('Plot on main Y axis', lambda: self.set_signal_axis(plot, indices, None))
        menu.addAction('Plot on separate Y axis', lambda: self.separate_signal_axes(plot, indices))
        same = menu.addMenu('Plot on same Y axis as')
        for target in plot.curves:
            if target in indices: continue
            key = plot.signal_axes[target]
            same.addAction(self.display_name(plot, target),
                           lambda checked=False, group=key: self.set_signal_axis(plot, indices, group))
        same.setEnabled(bool(same.actions()))
        menu.addSeparator()
        menu.addAction('Remove signal(s)', lambda: self.remove_signals(plot, indices))
        return menu

    def plot_color_menu(self, plot, scene_pos):
        # Hit testing uses the displayed curve, including log/separate-axis transforms.
        for index, data in reversed(list(plot.curves.items())):
            curve = data.curve
            if curve.mouseShape().contains(curve.mapFromScene(scene_pos)):
                return self.axis_menu(plot, [index])
        menu = Q.QMenu(self)
        colors = menu.addMenu('Change signal color')
        for index in plot.curves:
            colors.addAction(self.display_name(plot, index),
                             lambda checked=False, i=index: self.choose_signal_color(plot, [i]))
        colors.setEnabled(bool(plot.curves))
        names = menu.addMenu('Rename signal')
        for index in plot.curves:
            names.addAction(self.display_name(plot, index), lambda checked=False, i=index: self.rename_signals(plot, [i]))
        names.setEnabled(bool(plot.curves))
        menu.addAction('Background color…', lambda: self.choose_background_color(plot))
        menu.addAction('Clear annotations', lambda: self.clear_annotations(plot))
        return menu

    def display_name(self, plot, index):
        return plot.signal_names.get(index, self.signals[index].name)

    def rename_signals(self, plot, indices):
        """Set a plot-local display name; preserve original source names and data."""
        for index in indices:
            if index not in plot.curves: continue
            name, ok = Q.QInputDialog.getText(self, 'Rename signal', 'Display name:',
                                             text=self.display_name(plot, index))
            if not ok: break
            if not name.strip(): continue
            plot.signal_names[index] = name.strip()
            label = f'{name.strip()} [{self.signals[index].unit}]'
            curve = plot.curves[index]; curve.opts['name'] = label
            for sample, legend_label in plot.plotItem.legend.items:
                if sample.item is curve: legend_label.setText(label)
            for row in range(plot.signal_list.count()):
                item = plot.signal_list.item(row)
                if item.data(QtCore.Qt.ItemDataRole.UserRole) == index:
                    source = self.signal_items[index].parent().text(0)
                    item.setText(f'{label} — {source}')
        self.update_axis_labels(plot)
        self.update_readout(plot.workspace)

    def choose_signal_color(self, plot, indices):
        indices = [i for i in indices if i in plot.curves]
        if not indices: return
        initial = pg.mkPen(plot.curves[indices[0]].opts['pen']).color()
        color = Q.QColorDialog.getColor(initial, self, 'Signal color')
        if not color.isValid(): return
        for index in indices:
            plot.signal_colors[index] = QtGui.QColor(color)
            pen = pg.mkPen(plot.curves[index].opts['pen'])
            pen.setColor(color); plot.curves[index].setPen(pen)
        for row in range(plot.signal_list.count()):
            item = plot.signal_list.item(row)
            if item.data(QtCore.Qt.ItemDataRole.UserRole) in indices: item.setForeground(color)
        for sample, label in plot.plotItem.legend.items: sample.update()
        self.update_axis_labels(plot)

    def choose_background_color(self, plot):
        color = Q.QColorDialog.getColor(plot.backgroundBrush().color(), self, 'Plot background color')
        if color.isValid(): plot.setBackground(color)

    def set_signal_axis(self, plot, indices, key):
        plot.assign_axis(indices, key)
        for curve in plot.curves.values(): curve.setLogMode(plot.log_x, plot.log_y)
        for axis, view in plot.extra_axes.values(): axis.setLogMode(plot.log_y)
        self.update_axis_labels(plot)
        self.fit_plot(plot)

    def separate_signal_axes(self, plot, indices):
        for index in indices:
            if index in plot.curves:
                self.set_signal_axis(plot, [index], plot.new_y_axis())

    def update_axis_labels(self, plot):
        for key in [None, *plot.extra_axes]:
            indices = [i for i in plot.curves if plot.signal_axes[i] == key]
            units = sorted({self.signals[i].unit for i in indices if self.signals[i].unit})
            label = ' / '.join(self.display_name(plot, i) for i in indices) if key is not None else ('Peak amplitude' if plot.workspace.kind == 'fft' else 'Level' if plot.workspace.kind == 'spectrum' else 'Signals')
            axis = plot.getAxis('left') if key is None else plot.extra_axes[key][0]
            axis.setLabel(label if len(units) <= 1 else label+' ('+', '.join(units)+')',
                          units=units[0] if len(units) == 1 else '')
            if key is not None and indices:
                color = pg.mkPen(plot.curves[indices[0]].opts['pen']).color()
                axis.setPen(color); axis.setTextPen(color)
        for row in range(plot.signal_list.count()):
            item = plot.signal_list.item(row)
            index = item.data(QtCore.Qt.ItemDataRole.UserRole)
            group = plot.signal_axes[index]
            item.setToolTip('Main Y axis' if group is None else f'Separate Y axis {group+1}')

    def add_signal(self, index, plot):
        """Resolve a source ID, transform for the page and add a curve and sidebar entry."""
        if index not in self.signals or index in plot.curves: return
        try: s = self.transformed_signal(index, plot.workspace)
        except ValueError as exc:
            if plot.workspace.kind == 'fft':
                plot.workspace.pending_signals.add(index)
            self.error(f'{self.signals[index].name}: {exc}' +
                       ('\nFor a short interval, change or disable Time interval. For uneven timestamps, enable Resample (linear). Then click Recalculate.'
                        if plot.workspace.kind == 'fft' else ''))
            return
        plot.workspace.pending_signals.discard(index)
        plot.display_signals[index] = s
        y = np.abs(s.values) if np.iscomplexobj(s.values) else s.values
        color = plot.signal_colors.get(index, pg.intColor(index, hues=12))
        plot.curves[index] = plot.plot(s.time, y, pen=pg.mkPen(color, width=1), name=f'{self.display_name(plot, index)} [{s.unit}]')
        plot.curves[index].setCurveClickable(False, width=10)
        plot.signal_axes[index] = None
        source = self.signal_items[index]
        item = Q.QListWidgetItem(f'{self.display_name(plot, index)} [{s.unit}] — {source.parent().text(0)}')
        item.setData(QtCore.Qt.ItemDataRole.UserRole, index)
        item.setForeground(color)
        plot.signal_list.addItem(item)
        self.update_axis_labels(plot)
        if len(plot.curves) == 1:
            if plot.workspace.kind == 'fft':
                peak = int(np.argmax(s.values))
                self.move_cursor(0, float(s.time[peak]), plot.workspace)
                self.move_cursor(1, float(s.time[min(peak+1, len(s.time)-1)]), plot.workspace)
            else:
                self.move_cursor(0, float(s.time[0]), plot.workspace); self.move_cursor(1, float(s.time[-1]), plot.workspace)
        self.fit_plot(plot)
        self.update_readout(plot.workspace)

    def select_signal(self, item):
        if item is not None:
            self.list.setCurrentItem(self.signal_items[item.data(QtCore.Qt.ItemDataRole.UserRole)])

    def remove_signals(self, plot, indices):
        """Remove selected curves from one plot and clean unused axes and readouts."""
        for index in indices:
            if index in plot.curves:
                plot.detach_curve(index)
                del plot.curves[index]; del plot.signal_axes[index]
                del plot.display_signals[index]
                plot.fit_bounds = {key:value for key,value in plot.fit_bounds.items() if key[0] != index}
        plot.prune_axes()
        for row in range(plot.signal_list.count()-1, -1, -1):
            if plot.signal_list.item(row).data(QtCore.Qt.ItemDataRole.UserRole) in indices:
                plot.signal_list.takeItem(row)
        self.update_axis_labels(plot)
        self.update_readout(plot.workspace)

    def toggle_cursors(self, checked):
        self.workspace.cursors_visible = checked
        if checked: self.workspace.next_cursor_index = 0
        for p in self.plots:
            for i,c in enumerate(p.cursors): c.setVisible(checked and bool(np.isfinite(p.x_to_scene(self.cursor_positions[i]))))
        self.update_readout()

    def place_cursor(self, plot, event):
        """Alternate A/B on plain left clicks; drags and context menus stay intact."""
        page = plot.workspace
        if (not page.cursors_visible or event.button() != QtCore.Qt.MouseButton.LeftButton
                or event.double() or event.modifiers() != QtCore.Qt.KeyboardModifier.NoModifier):
            return
        view = plot.getViewBox()
        if not view.sceneBoundingRect().contains(event.scenePos()): return
        value = plot.x_from_scene(view.mapSceneToView(event.scenePos()).x())
        if not np.isfinite(value): return
        index = page.next_cursor_index
        self.move_cursor(index, value, page)
        page.next_cursor_index = 1-index
        self.statusBar().showMessage(f'Cursor {"AB"[index]} placed. Next left-click places {"AB"[1-index]}.')

    def move_cursor(self, index, value, page=None):
        """Synchronize a physical cursor coordinate across one page with recursion guards."""
        page = page or self.workspace
        if page.syncing: return
        page.syncing = True; page.cursor_positions[index] = value
        for p in page.plots:
            position = p.x_to_scene(value)
            p.cursors[index].setVisible(page.cursors_visible and bool(np.isfinite(position)))
            if np.isfinite(position): p.cursors[index].setValue(position)
        page.syncing = False; self.update_readout(page)

    def update_readout(self, page=None):
        """Interpolate displayed arrays at page cursors and render time/frequency differences."""
        page = page or self.workspace
        if page is None: return
        if not page.cursors_visible:
            page.readout.setPlainText('Enable Diff cursors to measure Δf and amplitude differences.' if page.kind in ('fft', 'spectrum') else 'Enable Diff cursors to measure Δt, 1/Δt and per-signal ΔY. FFT and statistics use the full record while cursors are disabled.')
            return
        a,b = page.cursor_positions; dt = b-a
        if page.kind in ('fft', 'spectrum'):
            rows = [f'A = {a:.10g} Hz    B = {b:.10g} Hz    Δf = {dt:.10g} Hz    Amplitudes: linear interpolation between frequency samples']
        else:
            rows = [f'A = {a:.10g} s    B = {b:.10g} s    Δt = {dt:.10g} s    1/|Δt| = {1/abs(dt):.10g} Hz' if dt else f'A = B = {a:.10g} s; Δt = 0; frequency undefined']
        seen = set()
        for owner in page.plots:
            for index, s in owner.display_signals.items():
                name = self.display_name(owner, index)
                if (index, name) in seen or np.iscomplexobj(s.values): continue
                seen.add((index, name))
                v = cursor_values(s,a,b)
                delta_label = 'Δamplitude' if page.kind in ('fft', 'spectrum') else 'ΔY'
                rows.append(f'{name}: A {v["a"]:.8g}   B {v["b"]:.8g}   {delta_label} {v["delta"]:.8g} {s.unit}')
        page.readout.setPlainText('\n'.join(rows))

    def selected(self):
        item = self.list.currentItem()
        if item is None or item.parent() is None: raise ValueError('Expand a measurement and select a signal first')
        return self.signals[item.data(0, QtCore.Qt.ItemDataRole.UserRole)]

    def interval(self): return self.cursor_positions if self.cursors_enabled.isChecked() else (None,None)

    def stats(self):
        try:
            s = self.selected()
            if self.workspace.kind in ('fft', 'spectrum'):
                index = self.list.currentItem().data(0, QtCore.Qt.ItemDataRole.UserRole)
                s = self.transformed_signal(index, self.workspace)
            values = statistics(s, *self.interval())
            Q.QMessageBox.information(self, f'Statistics — {s.name}', '\n'.join(f'{k}: {v:.10g}' for k,v in values.items()))
        except Exception as exc: self.error(str(exc))

    def spectrum(self):
        item = self.list.currentItem()
        selected = item.data(0, QtCore.Qt.ItemDataRole.UserRole) if item and item.parent() else None
        if (self.workspace.kind == 'spectrum' and selected is None) or (selected is not None and self.signals[selected].domain == 'frequency'):
            self.statusBar().showMessage('This is already a spectrum; no FFT is required.')
            return self.workspace
        interval = (self.workspace.fft_interval if self.workspace.kind == 'fft' else
                    self.interval() if self.workspace.kind == 'time' else (None, None))
        resample = self.workspace.fft_resample
        rate = self.workspace.fft_sample_rate
        page = self.add_analysis('fft', interval)
        page.fft_resample = resample; page.fft_sample_rate = rate
        page.resample_box.setChecked(resample); page.sample_rate.setValue(rate)
        if selected is not None: self.add_signal(selected, page.plots[0])
        self.statusBar().showMessage('FFT analysis: drag signals into a plot; cursors measure frequency and peak amplitude.')
        return page

    def transformed_signal(self, index, page, interval=None, resample=None, sample_rate=None):
        """Return source samples for time pages or calculate a spectrum for FFT pages.
        
        @param index Source ID in the shared signal registry.
        @param page AnalysisPage determining the horizontal domain.
        @param interval Optional source-time interval overriding the FFT page bounds.
        @param resample Optional override of the page's applied linear-resampling flag.
        @param sample_rate Optional Hz override; zero selects reciprocal median spacing.
        @return Source Signal, or a new Signal whose time array holds frequency in Hz.
        
        The source arrays are unchanged. Frequency cursors are not FFT input bounds."""
        source = self.signals[index]
        if page.kind == 'spectrum':
            if source.domain != 'frequency': raise ValueError('Use FFT to transform a time-domain channel before plotting a spectrum')
            return source
        if page.kind == 'time':
            if source.domain != 'time': raise ValueError('This channel belongs in a Spectrum tab')
            return source
        enabled = page.fft_resample if resample is None else resample
        rate = page.fft_sample_rate if sample_rate is None else sample_rate
        f, amplitude = fft(source, *(page.fft_interval if interval is None else interval),
                           resample=enabled, sample_rate=(rate or None) if enabled else None)
        return Signal(source.name, f, amplitude, source.unit, domain='frequency')

    def recalculate_fft(self, page):
        """Validate all requested spectra before replacing any displayed FFT arrays."""
        interval = tuple(sorted((page.start_time.value(), page.stop_time.value()))) if page.use_interval.isChecked() else (None, None)
        resample = page.resample_box.isChecked()
        rate = page.sample_rate.value()
        indices = {i for plot in page.plots for i in plot.curves} | page.pending_signals
        try:
            # Validate every spectrum before replacing any displayed data.
            calculated = {}
            for index in indices:
                calculated[index] = self.transformed_signal(index, page, interval, resample=resample, sample_rate=rate)
        except ValueError as exc:
            self.error(f'{self.signals[index].name}: {exc}')
            return
        page.fft_interval = interval
        page.fft_resample = resample; page.fft_sample_rate = rate
        for plot in page.plots:
            for index, curve in plot.curves.items():
                s = calculated[index]
                plot.display_signals[index] = s
                curve.setData(s.time, s.values)
            self.fit_plot(plot)
        if page.pending_signals and page.plots:
            for index in list(page.pending_signals):
                self.add_signal(index, page.plots[0])
        self.update_readout(page)

    def save(self):
        """Export all loaded source channels, independent of plot visibility or FFT display."""
        path,_ = Q.QFileDialog.getSaveFileName(self, 'Export all loaded signals', '', output_filter())
        if path:
            try:
                export(Recording(list(self.signals.values())),path,overwrite=True)
                self.statusBar().showMessage(f'Exported {path}')
            except Exception as exc: self.error(str(exc))

    def filter(self, text):
        text = text.casefold()
        for root, indices in self.files.values():
            file_matches = text in root.text(0).casefold()
            visible = False
            for index in indices:
                item = self.signal_items[index]
                match = file_matches or text in item.text(0).casefold()
                item.setHidden(not match); visible = visible or match
            root.setHidden(not visible and bool(text))
            root.setExpanded(bool(text) and visible)

    def fit(self):
        signals = [s for p in self.plots for s in p.display_signals.values()]
        if not signals: return
        xmin = min(s.time[0] for s in signals)
        xmax = max(s.time[-1] for s in signals)
        self.plots[0].set_physical_x_range(xmin, xmax, padding=0.02)
        for p in self.plots: self.fit_plot(p, fit_x=False)

    def fit_plot(self, plot, fit_x=True):
        if not plot.curves: return
        signals = list(plot.display_signals.values())
        if fit_x:
            plot.set_physical_x_range(min(s.time[0] for s in signals), max(s.time[-1] for s in signals), padding=0.02)
        for key in [None, *plot.extra_axes]:
            bounds = []
            for index in plot.curves:
                if plot.signal_axes[index] != key: continue
                s = plot.display_signals[index]
                cache_key = (index, plot.log_x, plot.log_y)
                cached = plot.fit_bounds.get(cache_key)
                if cached is None or cached[0] is not s:
                    # Scan in bounded chunks, including memory-mapped sources.
                    low, high = np.inf, -np.inf
                    for start in range(0, len(s.time), 262144):
                        y = s.values[start:start+262144]
                        y = np.abs(y) if np.iscomplexobj(y) else y
                        valid = np.isfinite(y)
                        if plot.log_x: valid &= s.time[start:start+262144] > 0
                        if plot.log_y: valid &= y > 0
                        finite = y[valid]
                        if plot.log_y: finite = np.log10(finite)
                        if len(finite): low, high = min(low, finite.min()), max(high, finite.max())
                    cached = (s, (float(low), float(high)))
                    plot.fit_bounds[cache_key] = cached
                if np.isfinite(cached[1]).all(): bounds.append(cached[1])
            if bounds:
                plot.axis_view(key).setYRange(float(min(b[0] for b in bounds)), float(max(b[1] for b in bounds)), padding=0.05)

    def clear_plots(self):
        """Remove curves from every plot in the active page without unloading sources."""
        for p in self.plots:
            self.remove_signals(p, list(p.curves))
        self.update_readout()

    def error(self, message): Q.QMessageBox.warning(self, 'OpenCaliper', message)

    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self,event):
        for url in event.mimeData().urls():
            if url.isLocalFile(): self.open_path(url.toLocalFile())
        event.acceptProposedAction()

    def closeEvent(self, event):
        """Refuse window closure while imports are still running."""
        if self.workers:
            self.statusBar().showMessage('Please wait for imports to finish before closing.'); event.ignore()
        else: event.accept()



# Capture composite actions once; snapshots retain array references rather than
# duplicating recordings. Navigation stays independent of structural undo.
for _method in ('loaded', 'remove_files', 'add_analysis', 'close_analysis', 'rename_analysis',
                'add_plot', 'remove_plot', 'add_signal', 'remove_signals', 'clear_plots',
                'rename_signals', 'choose_signal_color', 'choose_background_color', 'set_signal_axis',
                'separate_signal_axes', 'set_plot_log', 'recalculate_fft',
                'math_dialog', 'filter_dialog', 'align_dialog', 'annotate_dialog',
                'event_dialog', 'clear_annotations', 'zoom_by', 'fit', 'set_zoom_mode'):
    setattr(Window, _method, reversible(getattr(Window, _method)))


def run(files=()):
    """Create or reuse QApplication, show the main window and enter the event loop.
    
    @param files Iterable of input paths to load asynchronously after showing the window.
    @return Qt event-loop exit status."""
    app = Q.QApplication.instance() or Q.QApplication(sys.argv[:1])
    app.setApplicationName('OpenCaliper')
    app.setApplicationDisplayName('OpenCaliper')
    pg.setConfigOptions(background='#111924', foreground='#dce6f1', antialias=False)
    app.setStyle('Fusion')
    window = Window(); window.show()
    for path in files: window.open_path(path)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(run(sys.argv[1:]))
