"""Launcher setup, failure handling and argument forwarding without downloads."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from scripts import launch


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='OpenCaliper launcher ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'pyproject.toml').write_text('[project]\nname="opencaliper"\n')
        self.python = self.root / '.venv' / ('Scripts/python.exe' if launch.os.name == 'nt' else 'bin/python')
        self.python.parent.mkdir(parents=True)
        self.python.touch()
        self.marker = self.root / '.venv/.opencaliper-setup'

    def test_install_once_reinstall_on_project_change_and_forward_paths(self):
        args = ['relative path/capture.mat', '/some other folder/data.raw']
        with patch.object(launch, 'ROOT', self.root), patch.object(launch.subprocess, 'run') as install, patch.object(launch.subprocess, 'call', return_value=0) as gui:
            self.assertEqual(launch.main(args), 0)
            install.assert_called_once_with([str(self.python), '-m', 'pip', 'install', '-e', str(self.root)], check=True)
            gui.assert_called_with([str(self.python), '-m', 'opencaliper', 'gui', *args])
            self.assertEqual(launch.main([]), 0)
            self.assertEqual(install.call_count, 1)
            (self.root / 'pyproject.toml').write_text('changed dependencies')
            self.assertEqual(launch.main([]), 0)
            self.assertEqual(install.call_count, 2)

    def test_failed_install_does_not_mark_setup_or_start_gui(self):
        with patch.object(launch, 'ROOT', self.root), patch.object(launch.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'pip')), patch.object(launch.subprocess, 'call') as gui:
            self.assertEqual(launch.main([]), 1)
            self.assertFalse(self.marker.exists())
            gui.assert_not_called()

    def test_missing_environment_is_created(self):
        self.python.unlink()
        with patch.object(launch, 'ROOT', self.root), patch.object(launch.venv, 'EnvBuilder') as builder, patch.object(launch.subprocess, 'run'), patch.object(launch.subprocess, 'call', return_value=0):
            self.assertEqual(launch.main([]), 0)
            builder.assert_called_once_with(with_pip=True)
            builder.return_value.create.assert_called_once_with(self.root / '.venv')
