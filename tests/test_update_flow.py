import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from main import MainApp


class UpdateFlowTest(unittest.TestCase):
    def app(self):
        app = MainApp.__new__(MainApp)
        app.root = object()
        app.main_status_label = mock.Mock()
        app.logger = mock.Mock()
        app.update_install_running = True
        app._on_close = mock.Mock()
        return app

    def test_cancel_after_download_does_not_launch_installer(self):
        app = self.app()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory) / "update"
            folder.mkdir()
            installer = folder / "MJETXHelper_Setup_v1.1.3.exe"
            installer.write_bytes(b"MZtest")
            with mock.patch("main.messagebox.askyesno", return_value=False), mock.patch("main.subprocess.Popen") as launch:
                app._offer_verified_update(installer, "1.1.3")
            launch.assert_not_called()
            app._on_close.assert_not_called()
            self.assertFalse(folder.exists())
            self.assertFalse(app.update_install_running)

    def test_confirmed_update_launches_installer_then_closes_helper(self):
        app = self.app()
        installer = Path("C:/Temp/MJETXHelper_Setup_v1.1.3.exe")
        with mock.patch("main.messagebox.askyesno", return_value=True), mock.patch("main.subprocess.Popen") as launch:
            app._offer_verified_update(installer, "1.1.3")
        launch.assert_called_once()
        self.assertEqual(launch.call_args.args[0][0], str(installer))
        self.assertIn("/NORESTART", launch.call_args.args[0])
        self.assertEqual(launch.call_args.kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")
        app._on_close.assert_called_once()

    def test_installer_gets_fresh_bootloader_environment_without_changing_parent(self):
        app = self.app()
        with mock.patch.dict(os.environ, {"PYINSTALLER_RESET_ENVIRONMENT": "0", "HELPER_TEST_VALUE": "keep"}):
            with mock.patch("main.messagebox.askyesno", return_value=True), mock.patch("main.subprocess.Popen") as launch:
                app._offer_verified_update(Path("C:/Temp/setup.exe"), "1.9")
            self.assertEqual(launch.call_args.kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")
            self.assertEqual(launch.call_args.kwargs["env"]["HELPER_TEST_VALUE"], "keep")
            self.assertEqual(os.environ["PYINSTALLER_RESET_ENVIRONMENT"], "0")

    def test_installer_resets_environment_for_updates_from_older_helpers(self):
        script = Path(__file__).parents[1].joinpath("installer.iss").read_text(encoding="utf-8")
        self.assertIn("function InitializeSetup: Boolean;", script)
        self.assertIn("SetProcessEnvironmentVariable('PYINSTALLER_RESET_ENVIRONMENT', '1')", script)


if __name__ == "__main__":
    unittest.main()
