"""File conversion queue with selectable Python readers and paired MAT output."""
from pathlib import Path
from PySide6 import QtCore, QtWidgets as Q
from .converterscripts import conversion


class FileTable(Q.QTableWidget):
    """Queue accepting any local file type, including unregistered custom formats."""
    files_dropped = QtCore.Signal(list)

    def __init__(self):
        super().__init__(0, 3)
        self.setHorizontalHeaderLabels(['Input file', 'Status', 'Output MAT file'])
        self.setAcceptDrops(True); self.setDragDropMode(Q.QAbstractItemView.DragDropMode.DropOnly)
        self.setSelectionBehavior(Q.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setEditTriggers(Q.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.horizontalHeader().setSectionResizeMode(Q.QHeaderView.ResizeMode.Stretch)

    def dragEnterEvent(self, event):
        if self.isEnabled() and event.mimeData().hasUrls(): event.acceptProposedAction()
        else: event.ignore()

    def dragMoveEvent(self, event): self.dragEnterEvent(event)

    def dropEvent(self, event):
        if self.isEnabled() and event.mimeData().hasUrls():
            self.files_dropped.emit([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()])
            event.acceptProposedAction()
        else: event.ignore()


class ConversionWorker(QtCore.QThread):
    """Decode/write sequentially off the UI thread; cancellation is between files."""
    result = QtCore.Signal(int, str, str)

    def __init__(self, jobs, converter, overwrite, parent=None, axis_mode='per_signal', resample=False, sample_rate=None,
                 downsample=1, filter_kind='none', cutoff=None, filter_order=4, compress=True):
        super().__init__(parent)
        self.jobs, self.converter, self.overwrite = jobs, converter, overwrite
        self.axis_mode = axis_mode
        self.resample, self.sample_rate = resample, sample_rate
        self.processing = dict(downsample=downsample, filter_kind=filter_kind, cutoff=cutoff, filter_order=filter_order, compress=compress)

    def run(self):
        for row, (source, target) in enumerate(self.jobs):
            if self.isInterruptionRequested(): break
            self.result.emit(row, 'Converting…', '')
            try:
                path = conversion.convert_one(source, target, self.converter, self.overwrite,
                                              axis_mode=self.axis_mode, resample=self.resample, sample_rate=self.sample_rate,
                                              **self.processing)
                self.result.emit(row, 'Converted', str(path))
            except (Exception, SystemExit) as exc:
                self.result.emit(row, f'Error: {exc}', '')


class ConverterDialog(Q.QDialog):
    """Choose files, an adapter and an output folder, then optionally load results."""
    files_ready = QtCore.Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Converter — MAT files'); self.resize(1000, 650)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        self.worker = None; self.busy = False; self.outputs = []; self.paths = []
        self.folder = conversion.converter_folder()
        layout = Q.QVBoxLayout(self)
        layout.addWidget(Q.QLabel('Add or drop files, select a converter and MAT layout, then convert and load the results.'))
        buttons = Q.QHBoxLayout(); layout.addLayout(buttons)
        self.add_button = Q.QPushButton('Add files…'); self.remove_button = Q.QPushButton('Remove selected')
        self.clear_button = Q.QPushButton('Clear list')
        for button in (self.add_button, self.remove_button, self.clear_button): buttons.addWidget(button)
        buttons.addStretch()
        self.table = FileTable(); layout.addWidget(self.table, 1)
        self.table.files_dropped.connect(self.add_files)
        self.add_button.clicked.connect(self.choose_files)
        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_button.clicked.connect(self.clear_files)
        options = Q.QWidget(); form = Q.QFormLayout(options)
        scroll = Q.QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(options)
        scroll.setMinimumHeight(230); layout.addWidget(scroll, 2)
        self.converter = Q.QComboBox(); self.converter.setMinimumContentsLength(30)
        self.script_button = Q.QPushButton('Choose .py script…')
        self.refresh_button = Q.QPushButton('Refresh')
        selection = Q.QHBoxLayout(); selection.addWidget(self.converter, 1)
        selection.addWidget(self.script_button); selection.addWidget(self.refresh_button)
        form.addRow('Converter:', selection)
        self.script_path = Q.QLabel(''); self.script_path.setWordWrap(True); form.addRow(self.script_path)
        self.output_folder = Q.QLineEdit(); self.output_folder.setPlaceholderText('Blank: save beside each input file')
        self.output_button = Q.QPushButton('Output folder…')
        output = Q.QHBoxLayout(); output.addWidget(self.output_folder, 1); output.addWidget(self.output_button)
        form.addRow('Save to:', output)
        self.axis_mode = Q.QComboBox()
        self.axis_mode.addItem('Separate time/frequency vector for each signal', 'per_signal')
        self.axis_mode.addItem('One shared uniform time vector (t1)', 'shared_time')
        self.axis_mode.setToolTip('Shared t1 requires identical uniform time axes. It does not resample or align channels.')
        form.addRow('MAT layout:', self.axis_mode)
        self.resample_shared = Q.QCheckBox('Resample/align onto a shared uniform time grid')
        self.resample_shared.setEnabled(False)
        self.shared_rate = Q.QDoubleSpinBox(); self.shared_rate.setDecimals(6); self.shared_rate.setRange(0,1e12)
        self.shared_rate.setSpecialValueText('Auto (slowest median rate)'); self.shared_rate.setSuffix(' Hz'); self.shared_rate.setEnabled(False)
        self.shared_rate.setToolTip('Linear interpolation over the common time interval, without extrapolation or anti-alias filtering.')
        form.addRow(self.resample_shared); form.addRow('Shared sample rate:', self.shared_rate)
        self.axis_mode.currentIndexChanged.connect(self.update_shared_options)
        self.resample_shared.toggled.connect(self.update_shared_options)
        self.downsample = Q.QSpinBox(); self.downsample.setRange(1, 10000)
        self.downsample.setToolTip('1 keeps all samples. N applies an anti-alias low-pass, then keeps every Nth sample. Time signals only.')
        form.addRow('Downsample factor:', self.downsample)
        self.filter_kind = Q.QComboBox()
        for label, value in [('None', 'none'), ('Low-pass', 'lowpass'), ('High-pass', 'highpass')]:
            self.filter_kind.addItem(label, value)
        form.addRow('Filter before downsampling:', self.filter_kind)
        self.filter_cutoff = Q.QDoubleSpinBox(); self.filter_cutoff.setDecimals(6)
        self.filter_cutoff.setRange(.000001, 1e12); self.filter_cutoff.setValue(1000); self.filter_cutoff.setSuffix(' Hz')
        self.filter_order = Q.QSpinBox(); self.filter_order.setRange(1, 20); self.filter_order.setValue(4)
        form.addRow('Filter cutoff:', self.filter_cutoff); form.addRow('Butterworth order:', self.filter_order)
        self.filter_kind.currentIndexChanged.connect(self.update_shared_options)
        self.update_shared_options()
        hint = Q.QLabel('Processing requires uniform real time signals. Downsampling always includes anti-alias low-pass filtering.\n'
                        'Selected filters run first; shared-time alignment runs after downsampling. Filters have edge transients.')
        hint.setWordWrap(True); form.addRow(hint)
        self.overwrite = Q.QCheckBox('Replace existing output files'); form.addRow(self.overwrite)
        self.compress = Q.QCheckBox('Compress MAT output (smaller files)'); self.compress.setChecked(True)
        self.compress.setToolTip('Disable for faster large exports and less compression-buffer memory, at the cost of larger files. No samples are discarded.')
        form.addRow(self.compress)
        tools = Q.QHBoxLayout(); layout.addLayout(tools)
        self.folder_button = Q.QPushButton('Converter scripts folder…')
        self.template_button = Q.QPushButton('Create converter template…')
        tools.addWidget(self.folder_button); tools.addWidget(self.template_button); tools.addStretch()
        self.progress = Q.QProgressBar(); self.progress.setRange(0, 1); self.progress.setValue(0); layout.addWidget(self.progress)
        self.status = Q.QLabel('Drop files into the list to begin.'); self.status.setWordWrap(True); layout.addWidget(self.status)
        actions = Q.QHBoxLayout(); layout.addLayout(actions)
        self.convert_button = Q.QPushButton('Convert to MAT'); self.cancel_button = Q.QPushButton('Cancel conversion')
        self.load_button = Q.QPushButton('Load converted files'); self.close_button = Q.QPushButton('Close')
        self.cancel_button.setEnabled(False); self.load_button.setEnabled(False)
        for button in (self.convert_button, self.cancel_button, self.load_button, self.close_button): actions.addWidget(button)
        self.convert_button.clicked.connect(self.start)
        self.cancel_button.clicked.connect(self.cancel_conversion)
        self.load_button.clicked.connect(lambda: self.files_ready.emit(list(self.outputs)))
        self.close_button.clicked.connect(self.close)
        self.script_button.clicked.connect(self.choose_script)
        self.refresh_button.clicked.connect(self.refresh)
        self.output_button.clicked.connect(self.choose_output)
        self.folder_button.clicked.connect(self.choose_converter_folder)
        self.template_button.clicked.connect(self.create_template)
        self.converter.currentIndexChanged.connect(self.describe_converter)
        self.refresh()
        self.convert_button.setEnabled(False)

    def refresh(self):
        selected = self.converter.currentData()
        self.converter.clear()
        for converter in conversion.discover(self.folder): self.converter.addItem(converter.name, converter)
        index = self.converter.findData(selected)
        self.converter.setCurrentIndex(max(0, index)); self.describe_converter()

    def describe_converter(self):
        converter = self.converter.currentData()
        if converter is None: return
        if converter.script: text = str(converter.script)
        elif converter.module: text = f'Built-in: converterscripts/{converter.module}.py'
        else: text = 'Select by file extension. Choose a Python script for an unregistered format.'
        self.script_path.setText(text)

    def add_files(self, paths):
        if self.busy: return
        for value in paths:
            path = Path(value).resolve()
            if not path.is_file(): self.status.setText(f'Not a file: {path}'); continue
            if path in self.paths: continue
            row = self.table.rowCount(); self.table.insertRow(row); self.paths.append(path)
            for column, text in enumerate((str(path), 'Ready', '')):
                item = Q.QTableWidgetItem(text); item.setToolTip(text); self.table.setItem(row, column, item)
        self.convert_button.setEnabled(bool(self.paths))

    def choose_files(self):
        paths, _ = Q.QFileDialog.getOpenFileNames(self, 'Files to convert', '', 'All files (*)')
        self.add_files(paths)

    def remove_selected(self):
        if self.busy: return
        for row in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row); self.paths.pop(row)
        self.convert_button.setEnabled(bool(self.paths))

    def clear_files(self):
        if self.busy: return
        self.paths.clear(); self.table.setRowCount(0); self.outputs.clear(); self.load_button.setEnabled(False)
        self.convert_button.setEnabled(False)

    def choose_script(self):
        path, _ = Q.QFileDialog.getOpenFileName(self, 'Choose converter script', str(self.folder), 'Python converter (*.py)')
        if path: self.select_script(path)

    def select_script(self, path):
        converter = conversion.Converter(Path(path).name, script=Path(path).resolve())
        index = self.converter.findData(converter)
        if index < 0: self.converter.addItem(converter.name, converter); index = self.converter.count()-1
        self.converter.setCurrentIndex(index)

    def choose_output(self):
        folder = Q.QFileDialog.getExistingDirectory(self, 'Output folder', self.output_folder.text())
        if folder: self.output_folder.setText(folder)

    def choose_converter_folder(self):
        folder = Q.QFileDialog.getExistingDirectory(self, 'Folder containing custom converter scripts', str(self.folder))
        if folder: self.folder = Path(folder); self.refresh()

    def create_template(self):
        path, _ = Q.QFileDialog.getSaveFileName(self, 'Create converter template', str(self.folder/'my_converter.py'), 'Python converter (*.py)')
        if not path: return
        try:
            conversion.create_template(path); self.folder = Path(path).parent; self.refresh(); self.select_script(path)
            self.status.setText(f'Template created at {path}. Edit read(path), save it, then select input files and convert.')
        except Exception as exc: self.status.setText(f'Cannot create template: {exc}')

    def set_busy(self, busy):
        self.busy = busy
        for widget in (self.table, self.add_button, self.remove_button, self.clear_button,
                       self.converter, self.script_button, self.refresh_button, self.output_folder,
                       self.output_button, self.axis_mode, self.downsample, self.filter_kind, self.overwrite, self.compress, self.folder_button, self.template_button, self.close_button):
            widget.setEnabled(not busy)
        self.convert_button.setEnabled(not busy and bool(self.paths))
        self.cancel_button.setEnabled(busy); self.load_button.setEnabled(not busy and bool(self.outputs))
        self.update_shared_options()

    def update_shared_options(self):
        shared = self.axis_mode.currentData() == 'shared_time' and not self.busy
        self.resample_shared.setEnabled(shared)
        self.shared_rate.setEnabled(shared and self.resample_shared.isChecked())
        if hasattr(self, 'filter_kind'):
            enabled = not self.busy and self.filter_kind.currentData() != 'none'
            self.filter_cutoff.setEnabled(enabled); self.filter_order.setEnabled(enabled)

    def start(self):
        if self.busy or not self.paths: return
        folder = self.output_folder.text().strip()
        try:
            if folder and not Path(folder).is_dir(): raise ValueError('Choose an existing output folder')
            jobs = conversion.plan(self.paths, folder or None)
        except Exception as exc: self.status.setText(str(exc)); return
        self.outputs.clear(); self.progress.setRange(0, len(jobs)); self.progress.setValue(0)
        for row, (_, target) in enumerate(jobs):
            self.table.item(row, 1).setText('Queued'); self.table.item(row, 2).setText(str(target))
        self.set_busy(True); self.status.setText('Converting… Cancellation takes effect after the current file.')
        self.worker = ConversionWorker(jobs, self.converter.currentData(), self.overwrite.isChecked(), self,
                                       axis_mode=self.axis_mode.currentData(),
                                       resample=self.axis_mode.currentData() == 'shared_time' and self.resample_shared.isChecked(),
                                       sample_rate=self.shared_rate.value() or None,
                                       downsample=self.downsample.value(), filter_kind=self.filter_kind.currentData(),
                                       cutoff=self.filter_cutoff.value(), filter_order=self.filter_order.value(),
                                       compress=self.compress.isChecked())
        self.worker.result.connect(self.update_result)
        self.worker.finished.connect(self.conversion_finished)
        self.worker.start()

    def update_result(self, row, status, output):
        self.table.item(row, 1).setText(status); self.table.item(row, 1).setToolTip(status)
        if output: self.outputs.append(output)
        if status != 'Converting…': self.progress.setValue(row+1)

    def conversion_finished(self):
        for row in range(self.table.rowCount()):
            if self.table.item(row, 1).text() == 'Queued': self.table.item(row, 1).setText('Cancelled')
        self.worker.deleteLater(); self.worker = None; self.set_busy(False)
        self.status.setText(f'{len(self.outputs)} of {len(self.paths)} files converted. Select Load converted files to view the results.')

    def cancel_conversion(self):
        if self.worker:
            self.worker.requestInterruption(); self.cancel_button.setEnabled(False)
            self.status.setText('Cancellation requested; finishing the current file.')

    def reject(self):
        if not self.busy: super().reject()

    def closeEvent(self, event):
        if self.busy: self.status.setText('Cancel or finish conversion before closing.'); event.ignore()
        else: event.accept()
