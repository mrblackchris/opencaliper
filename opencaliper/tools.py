"""Interactive processing, annotations, spectrograms and plot export."""
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets as Q
import pyqtgraph as pg
from .core import Signal, Recording
from . import processing


class ToolsMixin:
    def init_tools(self):
        file = self.menuBar().addMenu('Workspace')
        file.addAction('Save workspace…', lambda: self.save_workspace()).setShortcut('Ctrl+Shift+S')
        file.addAction('Open workspace…', lambda: self.open_workspace()).setShortcut('Ctrl+Shift+O')
        file.addAction('Export plot…', self.export_plot)
        tools = self.menuBar().addMenu('Signal tools')
        for text,fn in [('Signal math…',self.math_dialog),('Filter…',self.filter_dialog),
                        ('Align recording…',self.align_dialog),('Detect events…',self.event_dialog),
                        ('Annotate cursor interval…',self.annotate_dialog),('Spectrogram…',self.spectrogram_dialog)]:
            tools.addAction(text,fn)

    def form(self,title,fields):
        dialog = Q.QDialog(self); dialog.setWindowTitle(title)
        layout = Q.QFormLayout(dialog)
        for label,widget in fields: layout.addRow(label,widget)
        buttons = Q.QDialogButtonBox(Q.QDialogButtonBox.StandardButton.Ok | Q.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject); layout.addRow(buttons)
        try:
            return dialog.exec() == Q.QDialog.DialogCode.Accepted
        finally:
            # Callers read these controls after this helper returns. Detach
            # them before destroying the dialog, which otherwise owns them.
            for _, widget in fields:
                widget.setParent(None)
            dialog.deleteLater()

    def channel_combo(self):
        box = Q.QComboBox()
        for i,s in self.signals.items(): box.addItem(f'CH{i}: {s.name} [{s.unit}]',i)
        item = self.list.currentItem()
        if item and item.parent(): box.setCurrentIndex(box.findData(item.data(0,QtCore.Qt.ItemDataRole.UserRole)))
        return box

    def derived(self,signal):
        self.loaded(Recording([signal],'Derived signals'))
        if self.workspace.kind != 'time': self.add_analysis()
        if not self.plots: self.add_plot()
        self.add_signal(self.next_signal_id-1,self.plots[0])

    def math_dialog(self):
        if not self.signals: self.error('Load signals first'); return
        expression = Q.QLineEdit(); expression.setPlaceholderText('CH0 - CH1; integrate(CH0); differentiate(CH0)')
        name = Q.QLineEdit('Math'); unit = Q.QLineEdit()
        channels = Q.QPlainTextEdit('\n'.join(f'CH{i} = {s.name} [{s.unit}]' for i,s in self.signals.items()))
        channels.setReadOnly(True)
        if self.form('Signal math',[('Channels',channels),('Expression',expression),('Name',name),('Output unit',unit)]):
            try: self.derived(processing.expression(expression.text(),{f'CH{i}':s for i,s in self.signals.items()},name.text(),unit.text()))
            except Exception as exc: self.error(str(exc))

    def filter_dialog(self):
        if not self.signals: self.error('Load signals first'); return
        channel = self.channel_combo(); kind = Q.QComboBox(); kind.addItems(['lowpass','highpass','notch'])
        frequency = Q.QDoubleSpinBox(); frequency.setDecimals(6); frequency.setRange(0.000001,1e15); frequency.setValue(50); frequency.setSuffix(' Hz')
        order = Q.QSpinBox(); order.setRange(1,12); order.setValue(4)
        quality = Q.QDoubleSpinBox(); quality.setRange(0.1,10000); quality.setValue(30)
        if self.form('Zero-phase filter',[('Channel',channel),('Type',kind),('Cutoff / notch',frequency),('Butterworth order',order),('Notch Q',quality)]):
            try: self.derived(processing.filtered(self.signals[channel.currentData()],kind.currentText(),frequency.value(),order.value(),quality.value()))
            except Exception as exc: self.error(str(exc))

    def align_dialog(self):
        if not self.signals: self.error('Load signals first'); return
        source = self.channel_combo(); reference = self.channel_combo()
        mode = Q.QComboBox(); mode.addItems(['Manual shift','Cross-correlation','Rising edge'])
        shift = Q.QDoubleSpinBox(); shift.setDecimals(12); shift.setRange(-1e15,1e15); shift.setSuffix(' s')
        level = Q.QDoubleSpinBox(); level.setRange(-1e15,1e15); level.setDecimals(8)
        whole = Q.QCheckBox('Shift every channel from the source recording'); whole.setChecked(True)
        if not self.form('Align recording',[('Source',source),('Reference',reference),('Method',mode),('Manual offset',shift),('Edge threshold',level),('',whole)]): return
        try:
            s,r = self.signals[source.currentData()],self.signals[reference.currentData()]
            offset = shift.value()
            if mode.currentIndex() == 1: offset = processing.aligned(s,r).time[0]-s.time[0]
            if mode.currentIndex() == 2:
                a,b = processing.events(s,'rising',level.value()),processing.events(r,'rising',level.value())
                if not len(a) or not len(b): raise ValueError('Both channels need a rising threshold crossing')
                offset = b[0]-a[0]
            ids = [source.currentData()]
            if whole.isChecked(): ids = next(ids for root,ids in self.files.values() if source.currentData() in ids)
            shifted = [Signal(f'{self.signals[i].name} shifted {offset:+g} s',self.signals[i].time+offset,self.signals[i].values,self.signals[i].unit) for i in ids]
            start = self.next_signal_id; self.loaded(Recording(shifted,'Aligned recording'))
            if self.workspace.kind != 'time': self.add_analysis()
            if not self.plots: self.add_plot()
            for i in range(start,self.next_signal_id): self.add_signal(i,self.plots[0])
        except Exception as exc: self.error(str(exc))

    def draw_annotation(self,plot,annotation):
        if not hasattr(plot,'annotations'): plot.annotations = []; plot.annotation_items = []
        a,b,text = annotation
        plot.annotations.append(list(annotation))
        if plot.log_x and (a <= 0 or b <= 0): return
        if a == b:
            item = pg.InfiniteLine(plot.x_to_scene(a),angle=90,pen=pg.mkPen('#90e0ef'),label=text)
        else:
            item = pg.LinearRegionItem([plot.x_to_scene(a),plot.x_to_scene(b)],movable=False,brush=(80,180,220,35))
        plot.addItem(item,ignoreBounds=True)
        label = pg.TextItem(text,color='#90e0ef',anchor=(0,0)); label.setPos(plot.x_to_scene(a),plot.viewRange()[1][1])
        plot.addItem(label,ignoreBounds=True)
        plot.annotation_items.extend([item,label])

    def update_annotation_labels(self, plot, bounds):
        for label in getattr(plot, 'annotation_items', [])[1::2]:
            label.setPos(label.pos().x(), bounds[1])

    def annotate_dialog(self):
        if not self.plots: self.error('Add a plot first'); return
        text,ok = Q.QInputDialog.getText(self,'Annotation','Label for the current A–B cursor interval:')
        if ok and text.strip(): self.draw_annotation(self.plots[0],[*sorted(self.cursor_positions),text.strip()])

    def clear_annotations(self,plot):
        for item in getattr(plot,'annotation_items',[]): plot.removeItem(item)
        plot.annotations = []; plot.annotation_items = []

    def event_dialog(self):
        if self.workspace.kind != 'time': self.error('Use a time analysis tab to detect events'); return
        if not self.signals or not self.plots: self.error('Load a signal and add a plot first'); return
        channel = self.channel_combo(); kind = Q.QComboBox(); kind.addItems(['rising','falling','peaks','pulses','outliers'])
        threshold = Q.QDoubleSpinBox(); threshold.setRange(-1e15,1e15); threshold.setDecimals(8); threshold.setValue(1)
        distance = Q.QSpinBox(); distance.setRange(1,100000000); distance.setValue(1)
        if not self.form('Detect events',[('Channel',channel),('Type',kind),('Threshold (outliers: std multiples)',threshold),('Peak separation (samples)',distance)]): return
        try:
            times = processing.events(self.signals[channel.currentData()],kind.currentText(),threshold.value(),distance.value())
            if len(times)>1000: raise ValueError(f'{len(times)} events found; refine the threshold to show at most 1000 markers')
            for t in times: self.draw_annotation(self.plots[0],[float(t),float(t),kind.currentText()])
            self.readout.setPlainText(f'{len(times)} {kind.currentText()} events (seconds):\n'+'\n'.join(f'{t:.12g}' for t in times))
        except Exception as exc: self.error(str(exc))

    def spectrogram_dialog(self):
        if not self.signals: self.error('Load signals first'); return
        channel = self.channel_combo(); segment = Q.QSpinBox(); segment.setRange(4,1048576); segment.setValue(256)
        overlap = Q.QDoubleSpinBox(); overlap.setRange(0,0.99); overlap.setSingleStep(0.05); overlap.setValue(0.5)
        if not self.form('Spectrogram',[('Channel',channel),('Samples per segment',segment),('Overlap fraction',overlap)]): return
        try:
            s = self.signals[channel.currentData()]
            t,f,power = processing.spectrogram(s,segment.value(),overlap.value())
            dialog = Q.QDialog(self); dialog.setWindowTitle(f'Spectrogram — {s.name}'); dialog.resize(1000,650)
            layout = Q.QVBoxLayout(dialog)
            graphics = pg.GraphicsLayoutWidget(); layout.addWidget(graphics)
            plot = graphics.addPlot(); plot.setLabel('bottom','Time',units='s'); plot.setLabel('left','Frequency',units='Hz')
            image = pg.ImageItem(axisOrder='row-major'); plot.addItem(image); image.setImage(power,autoLevels=True)
            dt = (segment.value()-int(segment.value()*overlap.value()))/processing.uniform(s)
            df = f[1]-f[0]
            image.setRect(QtCore.QRectF(t[0]-dt/2,f[0]-df/2,len(t)*dt,len(f)*df))
            color = pg.ColorBarItem(values=(float(power.max()-100),float(power.max())),colorMap=pg.colormap.get('viridis'),label=f'PSD dB re 1 {s.unit or "unit"}²/Hz')
            color.setImageItem(image,insert_in=plot)
            layout.addWidget(Q.QLabel('Hann window · Per-segment mean removed · Power spectral density · Drag to pan, wheel to zoom'))
            dialog.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
            self.dialogs.append(dialog); dialog.destroyed.connect(lambda: self.dialogs.remove(dialog) if dialog in self.dialogs else None)
            dialog.show()
        except Exception as exc: self.error(str(exc))

    def export_plot(self):
        if not self.plots: self.error('Add a plot first'); return
        number,ok = Q.QInputDialog.getInt(self,'Export plot','Plot number:',1,1,len(self.plots))
        if not ok: return
        path,_ = Q.QFileDialog.getSaveFileName(self,'Export plot','','PNG (*.png);;SVG (*.svg);;PDF (*.pdf)')
        if not path: return
        try: self.export_plot_to(self.plots[number-1],path)
        except Exception as exc: self.error(str(exc))

    def export_plot_to(self,plot,path):
        from pathlib import Path
        from PySide6 import QtSvg
        suffix = Path(path).suffix.lower()
        size = QtCore.QSize(2400,1400)
        if suffix == '.png':
            device = QtGui.QImage(size,QtGui.QImage.Format.Format_ARGB32); device.fill(plot.backgroundBrush().color())
        elif suffix == '.svg':
            device = QtSvg.QSvgGenerator(); device.setFileName(str(path)); device.setSize(size); device.setViewBox(QtCore.QRect(QtCore.QPoint(),size))
        elif suffix == '.pdf':
            device = QtGui.QPdfWriter(str(path)); device.setResolution(300)
            device.setPageSize(QtGui.QPageSize(QtGui.QPageSize.PageSizeId.A4)); device.setPageOrientation(QtGui.QPageLayout.Orientation.Landscape)
        else: raise ValueError('Choose .png, .svg or .pdf')
        painter = QtGui.QPainter(device)
        try:
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            width, height = device.width(), device.height()
            footer = []
            page = plot.workspace
            if page.cursors_visible:
                from .analysis import cursor_values
                a,b = page.cursor_positions
                axis_unit = 'Hz' if page.kind == 'fft' else 's'
                footer.append(f'A = {a:.9g} {axis_unit}   B = {b:.9g} {axis_unit}   Δ = {b-a:.9g} {axis_unit}')
                for s in plot.display_signals.values():
                    if np.iscomplexobj(s.values): continue
                    values = cursor_values(s,a,b)
                    footer.append(f'{s.name}: A {values["a"]:.7g}  B {values["b"]:.7g}  ΔY {values["delta"]:.7g} {s.unit}')
            font = QtGui.QFont(); font.setPixelSize(max(14,int(width/100)))
            footer_height = min(height/3, (len(footer)+1)*width/70) if footer else 0
            painter.fillRect(QtCore.QRectF(0,0,width,height),plot.backgroundBrush())
            from pyqtgraph.exporters.Exporter import Exporter
            exporter = Exporter(plot.plotItem)
            tick_font = Q.QApplication.font()
            tick_font.setPixelSize(QtGui.QFontInfo(tick_font).pixelSize())
            painter.setFont(tick_font)
            try:
                exporter.setExportMode(True,dict(antialias=True,background=plot.backgroundBrush().color(),
                                                 painter=painter,resolutionScale=width/plot.width()))
                plot.scene().render(painter,QtCore.QRectF(0,0,width,height-footer_height),exporter.getSourceRect())
            finally: exporter.setExportMode(False)
            painter.setFont(font)
            painter.setPen(plot.getAxis('bottom').textPen())
            if footer:
                painter.drawText(QtCore.QRectF(20,height-footer_height,width-40,footer_height),
                                 QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop,
                                 '\n'.join(footer))
        finally: painter.end()
        if suffix == '.png':
            device.setDotsPerMeterX(11811); device.setDotsPerMeterY(11811)
            if not device.save(str(path)): raise OSError('Could not save PNG')
        self.statusBar().showMessage(f'Exported {path}')
