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
        app._on_close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
