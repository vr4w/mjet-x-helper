import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from update_service import (
    LEGACY_UPDATE_URL,
    RELEASE_API_URL,
    download_verified_installer,
    is_installable_release,
    load_update_info,
    parse_github_release,
)


class FakeResponse(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data)
        self.url = url

    def geturl(self):
        return self.url


class UpdateServiceTest(unittest.TestCase):
    def release(self, content=b"MZinstaller"):
        version = "1.1.3"
        return {
            "tag_name": f"v{version}",
            "draft": False,
            "prerelease": False,
            "body": "Testversion",
            "assets": [{
                "name": f"MJETXHelper_Setup_v{version}.exe",
                "browser_download_url": (
                    f"https://github.com/vr4w/mjet-x-helper/releases/download/v{version}/"
                    f"MJETXHelper_Setup_v{version}.exe"
                ),
                "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
            }],
        }

    def test_published_release_is_installable(self):
        info = parse_github_release(self.release())
        self.assertEqual(info["version"], "1.1.3")
        self.assertTrue(is_installable_release(info))

    def test_missing_digest_or_foreign_asset_is_rejected(self):
        release = self.release()
        release["assets"][0]["digest"] = ""
        with self.assertRaises(ValueError):
            parse_github_release(release)
        release = self.release()
        release["assets"][0]["browser_download_url"] = "https://example.com/update.exe"
        with self.assertRaises(ValueError):
            parse_github_release(release)
        release = self.release()
        release["draft"] = True
        with self.assertRaises(ValueError):
            parse_github_release(release)

    def test_legacy_config_reads_latest_github_release(self):
        import json

        raw = json.dumps(self.release()).encode("utf-8")
        with mock.patch("update_service.urlopen", return_value=FakeResponse(raw, RELEASE_API_URL)) as request:
            info = load_update_info(LEGACY_UPDATE_URL)
        self.assertEqual(request.call_args.args[0].full_url, RELEASE_API_URL)
        self.assertTrue(is_installable_release(info))

    def test_verified_download_and_checksum_failure(self):
        content = b"MZreal installer bytes"
        info = parse_github_release(self.release(content))
        with tempfile.TemporaryDirectory() as directory:
            target_dir = Path(directory) / "update"
            target_dir.mkdir()
            with mock.patch("update_service.tempfile.mkdtemp", return_value=str(target_dir)), mock.patch(
                "update_service.urlopen", return_value=FakeResponse(content, info["url"])
            ):
                installer = download_verified_installer(info)
            self.assertEqual(installer.read_bytes(), content)

            installer.unlink()
            with mock.patch("update_service.tempfile.mkdtemp", return_value=str(target_dir)), mock.patch(
                "update_service.urlopen", return_value=FakeResponse(b"different content", info["url"])
            ):
                with self.assertRaisesRegex(ValueError, "Prüfsumme"):
                    download_verified_installer(info)
            self.assertFalse(target_dir.exists())

    def test_non_executable_asset_is_rejected_even_with_matching_checksum(self):
        content = b"not an executable"
        info = parse_github_release(self.release(content))
        with tempfile.TemporaryDirectory() as directory:
            target_dir = Path(directory) / "update"
            target_dir.mkdir()
            with mock.patch("update_service.tempfile.mkdtemp", return_value=str(target_dir)), mock.patch(
                "update_service.urlopen", return_value=FakeResponse(content, info["url"])
            ):
                with self.assertRaisesRegex(ValueError, "kein Windows-Installer"):
                    download_verified_installer(info)
            self.assertFalse(target_dir.exists())

    def test_custom_manifest_cannot_install_executable(self):
        info = parse_github_release(self.release())
        info["source"] = "custom"
        self.assertFalse(is_installable_release(info))
        with self.assertRaises(ValueError):
            download_verified_installer(info)


if __name__ == "__main__":
    unittest.main()
