"""Portable workspace archives and reversible desktop state."""
import io
import json
import os
from pathlib import Path
import tempfile
import zipfile
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets as Q
import pyqtgraph as pg
from .core import Signal, Recording


class WorkspaceMixin:
    """Persist portable channel/view snapshots and provide structural undo/redo.

    The versioned JSON/NPY archive contract is documented in docs/WORKSPACE_FORMAT.md.
    Snapshots share source arrays; widgets are rebuilt only on restoration.
    """
    def capture_state(self):
        """Capture source references and copied serializable view state on the GUI thread."""
        pages = []
        for n in range(self.tabs.count()):
            page = self.tabs.widget(n)
            plots = []
            for p in page.plots:
                plots.append(dict(hidden=[i for i in p.curves if i in p.hidden_signals], names={i:name for i,name in p.signal_names.items() if i in p.curves}, ids=list(p.curves), colors={i: pg.mkPen(c.opts['pen']).color().name() for i,c in p.curves.items()},
                                  axes=dict(p.signal_axes), ranges={k: p.axis_view(k).viewRange()[1][:] for k in [None,*p.extra_axes]},
                                  x=p.physical_x_range(), log=[p.log_x,p.log_y], background=p.backgroundBrush().color().name(),
                                  annotations=list(getattr(p, 'annotations', [])), sizes=p.panel.sizes()))
            pages.append(dict(title=self.tabs.tabText(n), kind=page.kind, interval=page.fft_interval,
                              representation=page.sparameter_representation,
                              pending=list(page.pending_signals), resample=page.fft_resample, sample_rate=page.fft_sample_rate,
                              cursors=list(page.cursor_positions), visible=page.cursors_visible, zoom=page.zoom_mode,
                              sizes=page.plot_splitter.sizes(), plots=plots))
        return dict(signals=dict(self.signals), files=[(r.text(0), list(ids)) for r,ids in self.files.values()],
                    pages=pages, current=self.tabs.currentIndex())

    def restore_state(self, state):
        """Rebuild views from a snapshot while suppressing history and spectrum auto-plot."""
        self._restoring = True
        self.tabs.blockSignals(True)
        try:
            while self.tabs.count():
                page = self.tabs.widget(0)
                for p in list(page.plots): self.remove_plot(p)
                self.tabs.removeTab(0); page.deleteLater()
            self.list.clear(); self.signals = {}; self.signal_items = {}; self.files = {}
            self.next_signal_id = 0; self.next_file_id = 0
            remap = {}
            for name, ids in state['files']:
                start = self.next_signal_id
                self.loaded(Recording([state['signals'][i] for i in ids], name))
                # Retain channel identifiers across undo and portable reloads.
                restored = [(old, self.signals.pop(start+j), self.signal_items.pop(start+j))
                            for j,old in enumerate(ids)]
                for old,signal,item in restored:
                    self.signals[old] = signal; self.signal_items[old] = item
                    item.setData(0, QtCore.Qt.ItemDataRole.UserRole, old)
                    remap[old] = old
                file_id = self.next_file_id-1
                self.files[file_id] = (self.files[file_id][0], list(ids))
                self.next_signal_id = max(self.signals, default=-1)+1
            for saved in state['pages']:
                page = self.add_analysis(saved['kind'], saved['interval'])
                title = saved['title']
                if saved['kind'] == 'fft' and title.startswith('FFT ') and title[4:].isdigit():
                    title = 'Spectrum'
                self.tabs.setTabText(self.tabs.currentIndex(), title)
                page.zoom_mode = saved['zoom']
                page.fft_resample = saved.get('resample', False)
                page.fft_sample_rate = saved.get('sample_rate', 0.)
                if page.kind == 'spectrum':
                    page.resample_box.setChecked(page.fft_resample)
                    page.sample_rate.setValue(page.fft_sample_rate)
                if page.kind == 'sparameter':
                    self.set_sparameter_representation(page, saved.get('representation', 'Magnitude (dB)'))
                for p in list(page.plots): self.remove_plot(p)
                for spec in saved['plots']:
                    self.add_plot(); p = page.plots[-1]
                    p.setBackground(spec['background'])
                    p.log_x_box.setChecked(spec['log'][0]); p.log_y_box.setChecked(spec['log'][1])
                    p.signal_names = {remap[i]:name for i,name in spec.get('names', {}).items()}
                    for old in spec['ids']:
                        i = remap[old]
                        p.signal_colors[i] = QtGui.QColor(spec['colors'][old])
                        self.add_signal(i,p)
                    groups = {}
                    for old,key in spec['axes'].items():
                        if key is not None:
                            if key not in groups: groups[key] = p.new_y_axis()
                            self.set_signal_axis(p,[remap[old]],groups[key])
                    self.set_signal_visibility(p, [remap[i] for i in spec.get('hidden', [])], False)
                    self.set_zoom_mode(saved['zoom'])
                    for annotation in spec.get('annotations', []): self.draw_annotation(p, annotation)
                    p.set_physical_x_range(*spec['x'])
                    for key,bounds in spec['ranges'].items():
                        p.axis_view(None if key is None else groups[key]).setYRange(*bounds,padding=0)
                    p.panel.setSizes(spec['sizes'])
                page.pending_signals = {remap[i] for i in saved.get('pending', [])}
                page.plot_splitter.setSizes(saved['sizes'])
                page.cursors_visible = saved['visible']
                for j,value in enumerate(saved['cursors']): self.move_cursor(j,value,page)
            self.tabs.setCurrentIndex(state['current'])
        finally:
            self.tabs.blockSignals(False)
            self._restoring = False
        self.analysis_changed(self.tabs.currentIndex())

    def init_history(self):
        self._restoring = False; self._history_depth = 0
        self._undo = []; self._redo = []
        edit = self.menuBar().addMenu('Edit')
        self.undo_action = edit.addAction('Undo', self.undo); self.undo_action.setShortcut(QtGui.QKeySequence.StandardKey.Undo)
        self.redo_action = edit.addAction('Redo', self.redo); self.redo_action.setShortcut(QtGui.QKeySequence.StandardKey.Redo)
        self.update_history_actions()

    def update_history_actions(self):
        self.undo_action.setEnabled(bool(self._undo)); self.redo_action.setEnabled(bool(self._redo))

    def undo(self):
        if self.workers or not self._undo: return
        self._redo.append(self.capture_state()); self.restore_state(self._undo.pop()); self.update_history_actions()

    def redo(self):
        if self.workers or not self._redo: return
        self._undo.append(self.capture_state()); self.restore_state(self._redo.pop()); self.update_history_actions()

    def save_workspace(self, path=None):
        """Write embedded source arrays and applied view state; prompt if path is absent.

        Uses version 1 ZIP/JSON/NPY and replaces the destination after successful
        serialization. Refuses active imports; errors are shown through the GUI.
        """
        if self.workers:
            self.error('Wait for imports to finish before saving a workspace'); return
        if not path: path,_ = Q.QFileDialog.getSaveFileName(self,'Save workspace','','OpenCaliper workspace (*.ocw)')
        if not path: return
        state = self.capture_state()
        # JSON represents ID/axis mappings as pairs to preserve integer and None keys.
        metadata = {k:v for k,v in state.items() if k != 'signals'}
        metadata['version'] = 1
        metadata['channels'] = {i:dict(name=s.name,unit=s.unit,domain=s.domain,reference_impedance=s.reference_impedance) for i,s in state['signals'].items()}
        for page in metadata['pages']:
            for p in page['plots']:
                for key in ('colors','axes','ranges','names'): p[key] = list(p[key].items())
        temp = None
        try:
            with tempfile.NamedTemporaryFile(dir=Path(path).resolve().parent,delete=False) as f: temp = f.name
            with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,allowZip64=True) as z:
                z.writestr('workspace.json',json.dumps(metadata,allow_nan=False))
                for i,s in state['signals'].items():
                    for kind,arr in [('time',s.time),('values',s.values)]:
                        with z.open(f'{i}-{kind}.npy','w',force_zip64=True) as f: np.lib.format.write_array(f,arr,allow_pickle=False)
            os.replace(temp,path); temp = None
            self.statusBar().showMessage(f'Saved workspace {path}')
        except Exception as exc: self.error(str(exc))
        finally:
            if temp: Path(temp).unlink(missing_ok=True)

    def open_workspace(self, path=None):
        """Load a portable archive and restore previous state on failure.

        Successful replacement is undoable. Optional domain, names and FFT settings
        have compatibility defaults. Source arrays use allow_pickle=False.
        """
        if self.workers:
            self.error('Wait for imports to finish before opening a workspace'); return
        if not path: path,_ = Q.QFileDialog.getOpenFileName(self,'Open workspace','','OpenCaliper workspace (*.ocw)')
        if not path: return
        previous = self.capture_state()
        try:
            with zipfile.ZipFile(path) as z:
                state = json.loads(z.read('workspace.json'))
                if state['version'] != 1: raise ValueError('Unsupported workspace version')
                signals = {}
                for i,info in state['channels'].items():
                    arrays = [np.load(io.BytesIO(z.read(f'{i}-{kind}.npy')),allow_pickle=False) for kind in ('time','values')]
                    signals[int(i)] = Signal(info['name'],*arrays,info['unit'],domain=info.get('domain', 'time'),
                                             reference_impedance=info.get('reference_impedance'))
                state['signals'] = signals
                if not state['pages']: raise ValueError('Workspace has no analysis pages')
                for page in state['pages']:
                    if page['kind'] not in ('time','fft','spectrum','sparameter'): raise ValueError('Unknown analysis type')
                    for p in page['plots']:
                        for key in ('colors','axes','ranges','names'): p[key] = dict(p.get(key, []))
            self.restore_state(state)
            self._undo.append(previous); self._redo.clear(); self.update_history_actions()
        except Exception as exc:
            self.restore_state(previous); self.error(f'Could not open workspace: {exc}')


def reversible(method):
    """Record one state per outermost user action, sharing original arrays."""
    def wrapped(self,*args,**kwargs):
        if not hasattr(self,'_undo') or self._restoring: return method(self,*args,**kwargs)
        outer = self._history_depth == 0
        before = self.capture_state() if outer else None
        self._history_depth += 1
        try: return method(self,*args,**kwargs)
        finally:
            self._history_depth -= 1
            if outer:
                after = self.capture_state()
                same_sources = before['signals'].keys() == after['signals'].keys() and all(
                    before['signals'][i] is after['signals'][i] for i in before['signals'])
                changed = not same_sources or any(before[k] != after[k] for k in ('files', 'pages', 'current'))
                if changed:
                    self._undo.append(before); self._undo = self._undo[-50:]
                    self._redo.clear(); self.update_history_actions()
    wrapped.__name__ = method.__name__
    wrapped.__doc__ = method.__doc__
    return wrapped
