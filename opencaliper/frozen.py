"""Standalone startup and a noninteractive release-bundle smoke test."""
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback


def self_test(report):
    """Exercise bundled GUI/resources, dynamic converters and plots without a display.

    Results go to JSON because Windows windowed executables do not have stdout.
    Source and installed-package runs use synthetic data just like frozen runs.
    """
    report = Path(report).resolve()
    result = {'status': 'failed', 'python': sys.version.split()[0], 'platform': sys.platform,
              'frozen': bool(getattr(sys, 'frozen', False))}
    window = None
    try:
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        import importlib
        import numpy as np
        from scipy.io import savemat
        from PySide6 import QtCore, QtWidgets as Q
        from .core import Signal, Recording, load, export
        from .analysis import fft
        from .converterscripts.formats import FORMATS
        from .gui import Window
        from .branding import configure_windows_identity
        configure_windows_identity()
        app = Q.QApplication.instance() or Q.QApplication([])
        app.setApplicationName('opencaliper')
        app.setDesktopFileName('opencaliper')
        time = np.arange(1024)/1024
        source = Recording([Signal('Voltage', time, np.sin(2*np.pi*64*time), 'V')])
        for format in FORMATS.values():
            for module in (format.reader, format.writer):
                if module: importlib.import_module('.'+module, 'opencaliper.converterscripts')
        with tempfile.TemporaryDirectory(prefix='OpenCaliper release check ') as folder:
            folder = Path(folder)
            checked = []
            for extension in ('mat', 'mf4', 'mdf', 'raw', 'wvf'):
                path = folder/('signal.'+extension)
                export(source, path)
                restored = load(path)
                assert restored.signals, f'No channels in {extension}'
                np.testing.assert_allclose(restored.signals[0].values, source.signals[0].values, atol=1e-4)
                checked.append(extension)
            path = folder/'columns.npy'
            np.save(path, np.column_stack((time, source.signals[0].values)))
            assert len(load(path).signals) == 1
            checked.append('npy')
            import struct
            values = np.array([0.,1.,0.,-1.], dtype='<f4')
            header = bytearray(140)
            struct.pack_into('<4I',header,0,140,1,1,4)
            struct.pack_into('<dd',header,32,.001,0.)
            struct.pack_into('<II',header,48,2,1)
            path = folder/'scope.bin'
            path.write_bytes(struct.pack('<2s2sII',b'AG',b'10',180,1)+header+
                             struct.pack('<IHHI',12,1,4,16)+values.tobytes())
            np.testing.assert_allclose(load(path).signals[0].values,values)
            checked.append('bin')
            import hdf5storage
            path = folder/'hdf.mat'
            hdf5storage.savemat(str(path),dict(signal_0_name='HDF',signal_0_unit='V',
                                signal_0_time=time,signal_0_values=source.signals[0].values),
                                format='7.3',appendmat=False)
            np.testing.assert_allclose(load(path).signals[0].values,source.signals[0].values)
            checked.append('mat-v7.3')
            path = folder/'receiver.mat'
            savemat(path, dict(freq=np.arange(1,5)*1e6, avg=[-50.,-40.,-45.,-55.], peak=[-40.,-30.,-35.,-45.]))
            receiver = load(path)
            assert [s.name for s in receiver.signals] == ['Average', 'Peak']
            assert all(s.domain == 'frequency' for s in receiver.signals)
            f, a = fft(source.signals[0])
            assert abs(f[int(np.argmax(a))]-64) < 1e-6
            window = Window()
            def fail(message): raise RuntimeError(message)
            window.error = fail
            window.show(); app.processEvents()
            assert not window.windowIcon().isNull(), 'Packaged logo is missing'
            window.loaded(source); window.add_signal(0, window.plots[0])
            window.set_signal_visibility(window.plots[0], [0], False)
            assert not window.plots[0].curves[0].isVisible()
            window.set_signal_visibility(window.plots[0], [0], True)
            for extension in ('png', 'svg', 'pdf'):
                path = folder/('plot.'+extension)
                window.export_plot_to(window.plots[0], path)
                assert path.stat().st_size > 100
            window.loaded(receiver)
            assert window.workspace.kind == 'spectrum'
            archive = folder/'session.ocw'; window.save_workspace(archive)
            window.open_workspace(archive)
            assert window.workspace.kind == 'spectrum'
            from .release_info import license_documents
            assert license_documents(), 'License documents are missing'
            result.update(status='ok', converters=checked, receiver=True, fft=True,
                          gui=True, icon=True, plot_exports=['png','svg','pdf'], workspace=True)
    except Exception:
        result['error'] = traceback.format_exc()
    finally:
        if window is not None:
            window.close()
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2), encoding='utf-8')
    return 0 if result['status'] == 'ok' else 1


def main(args=None):
    args = list(sys.argv[1:] if args is None else args)
    if args and args[0] == '--self-test':
        if len(args) != 2: return 2
        return self_test(args[1])
    from .gui import run
    return run(args)
