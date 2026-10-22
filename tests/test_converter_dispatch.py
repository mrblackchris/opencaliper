"""Dispatcher integration and contributor extension contract."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import numpy as np
from opencaliper import Recording, Signal, load, export
from opencaliper.converterscripts.convert import convert_file, detect_format
from opencaliper.converterscripts.formats import FORMATS, Format, input_filter, output_filter


class ConverterDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.recording = Recording([Signal('Voltage', [0., 0.1, 0.2, 0.3], [1., 2., 3., 4.], 'V'),
                                    Signal('Independent', [0., 0.3], [8., 9.], 'A')])

    def test_default_native_output_and_independent_channels(self):
        path = self.folder/'source.MF4'
        export(self.recording, path)
        output = convert_file(path)
        self.assertEqual(output,self.folder/'source.opencaliper.mat')
        restored = load(output)
        self.assertEqual([s.name for s in restored.signals],['Voltage','Independent'])
        for expected,actual in zip(self.recording.signals,restored.signals):
            np.testing.assert_allclose(actual.time,expected.time)
            np.testing.assert_allclose(actual.values,expected.values)
            self.assertEqual(actual.unit,expected.unit)
        with self.assertRaises(FileExistsError): convert_file(path)
        convert_file(path, overwrite=True)
        with self.assertRaisesRegex(ValueError,'must differ'): convert_file(path,path,overwrite=True)

    def test_format_errors_and_read_only_exports(self):
        self.assertEqual(detect_format('capture.WVF').reader,'wvfconvert')
        with self.assertRaisesRegex(ValueError,'Unsupported input format'): load('unknown.foo')
        for suffix in ('.npy','.bin','.unknown'):
            with self.assertRaisesRegex(ValueError,'Unsupported output format'):
                export(self.recording,self.folder/f'unsupported{suffix}')
        with self.assertRaisesRegex(ValueError,'No signals'): export(Recording([]),self.folder/'empty.mat')

    def test_registered_extension_used_by_api_and_gui_filters(self):
        module = types.ModuleType('opencaliper.converterscripts.testadapter')
        seen = []
        module.read = lambda path: self.recording
        def write(recording,path,overwrite=False):
            seen.append((recording,path,overwrite))
            path.write_bytes(b'example')
        module.write = write
        with patch.dict(FORMATS,{'.example':Format('Example','testadapter','testadapter')}), patch.dict(sys.modules,{module.__name__:module}):
            self.assertIs(load(self.folder/'source.EXAMPLE'),self.recording)
            output=self.folder/'result.example'
            self.assertEqual(export(self.recording,output),output)
            self.assertEqual(seen,[(self.recording,output,False)])
            self.assertIn('*.example',input_filter())
            self.assertIn('Example (*.example)',output_filter())
            module.read=lambda path: None
            with self.assertRaisesRegex(TypeError,'must return a Recording'): load('bad.example')

    def test_dispatcher_script_and_module_from_other_directory(self):
        source=self.folder/'source.mat'; export(self.recording,source)
        script=Path(__file__).resolve().parents[1]/'opencaliper/converterscripts/convert.py'
        for launcher in ([str(script)],['-m','opencaliper.converterscripts']):
            with self.subTest(launcher=launcher):
                output=self.folder/'converted.mat'
                output.unlink(missing_ok=True)
                result=subprocess.run([sys.executable,*launcher,str(source),str(output)],cwd=self.folder,capture_output=True,text=True,
                                      env={**os.environ,'PYTHONPATH':str(script.parents[2])})
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertEqual(len(load(output).signals),2)

    def test_existing_cli_uses_same_dispatcher(self):
        from opencaliper.cli import main
        source=self.folder/'source.mat'; export(self.recording,source)
        output=self.folder/'output.mdf'
        self.assertEqual(main(['convert',str(source),str(output)]),0)
        self.assertEqual(len(load(output).signals),2)
