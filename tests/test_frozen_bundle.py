"""Release entry point and smoke-test reporting; native EXE is verified by Windows CI."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PySide6 import QtWidgets as Q
from opencaliper.frozen import main, self_test
from opencaliper.release_info import license_documents
from scripts.build_windows import build_command, main as build_main


class FrozenBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=Q.QApplication.instance() or Q.QApplication([])

    def test_full_smoke_test_writes_report(self):
        with tempfile.TemporaryDirectory() as folder:
            report=Path(folder)/'report.json'
            self.assertEqual(self_test(report),0)
            data=json.loads(report.read_text())
            self.assertEqual(data['status'],'ok')
            self.assertTrue(data['icon']); self.assertTrue(data['workspace'])
            self.assertIn('mat-v7.3',data['converters'])
            self.assertIn('bin',data['converters'])

    def test_failures_are_written_without_a_console(self):
        with tempfile.TemporaryDirectory() as folder, patch('opencaliper.core.export',side_effect=ValueError('test failure')):
            report=Path(folder)/'report.json'
            self.assertEqual(self_test(report),1)
            self.assertIn('test failure',json.loads(report.read_text())['error'])

    def test_normal_entry_forwards_measurement_paths(self):
        with patch('opencaliper.gui.run',return_value=0) as gui:
            self.assertEqual(main(['capture with spaces.mat']),0)
            gui.assert_called_once_with(['capture with spaces.mat'])
        self.assertEqual(main(['--self-test']),2)

    def test_windows_builder_uses_explicit_paths(self):
        command=build_command('/tmp/output with spaces','/tmp/work with spaces')
        self.assertEqual(command[:3],[sys.executable,'-m','PyInstaller'])
        self.assertIn(str(Path('/tmp/output with spaces').resolve()),command)
        self.assertTrue(command[-1].endswith('OpenCaliper.spec'))
        with patch('scripts.build_windows.sys.platform','linux'), patch('sys.stderr',new_callable=io.StringIO):
            with self.assertRaises(SystemExit): build_main([])

    def test_project_notices_are_accessible(self):
        documents=license_documents()
        self.assertIn('OpenCaliper / LICENSE',documents)
        self.assertIn('GNU GENERAL PUBLIC LICENSE',documents['OpenCaliper / LICENSE'])
