"""Read published MJET-X releases and verify their Windows installer."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


RELEASE_API_URL = "https://api.github.com/repos/vr4w/mjet-x-helper/releases/latest"
LEGACY_UPDATE_URL = "https://raw.githubusercontent.com/vr4w/mjet-x-helper/main/update_info.json"
RELEASE_DOWNLOAD_ROOT = "https://github.com/vr4w/mjet-x-helper/releases/download"
MAX_INSTALLER_BYTES = 512 * 1024 * 1024
VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
SHA256_RE = re.compile(r"[0-9a-fA-F]{64}")


def installer_name(version: str) -> str:
    if not VERSION_RE.fullmatch(version):
        raise ValueError("Ungültige Versionsnummer im Update.")
    return f"MJETXHelper_Setup_v{version}.exe"


def parse_github_release(data: dict) -> dict:
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        raise ValueError("Kein veröffentlichtes stabiles Release gefunden.")
    tag = str(data.get("tag_name", "")).strip()
    if not tag.startswith("v") or not VERSION_RE.fullmatch(tag[1:]):
        raise ValueError("Das Release hat keine passende Versionsnummer.")
    version = tag[1:]
    name = installer_name(version)
    asset = next((item for item in data.get("assets", []) if isinstance(item, dict) and item.get("name") == name), None)
    if asset is None:
        raise ValueError(f"Im Release {tag} fehlt der Windows-Installer {name}.")
    digest = str(asset.get("digest", ""))
    sha256 = digest.split(":", 1)[1] if digest.startswith("sha256:") else ""
    if not SHA256_RE.fullmatch(sha256):
        raise ValueError("Für den Installer fehlt die SHA-256-Prüfsumme.")
    info = {
        "version": version,
        "url": str(asset.get("browser_download_url", "")),
        "sha256": sha256.lower(),
        "notes": str(data.get("body", "") or "")[:1200],
        "source": "github_release",
    }
    if not is_installable_release(info):
        raise ValueError("Die Installer-Adresse gehört nicht zum erwarteten GitHub-Release.")
    return info


def load_update_info(source: str) -> dict:
    source = source.strip()
    if not source:
        raise ValueError("Keine Prüfung auf neue Version eingerichtet.")
    if source == LEGACY_UPDATE_URL:
        source = RELEASE_API_URL
    if re.match(r"^https?://", source, re.IGNORECASE):
        request = Request(source, headers={"Accept": "application/vnd.github+json", "User-Agent": "MJET-X-Helper"})
        with urlopen(request, timeout=10) as response:
            raw = response.read(512_001)
        if len(raw) > 512_000:
            raise ValueError("Versionsinformation ist zu groß.")
        data = json.loads(raw.decode("utf-8"))
    else:
        data = json.loads(Path(source).read_text(encoding="utf-8"))
    if source == RELEASE_API_URL:
        return parse_github_release(data)
    if not isinstance(data, dict) or not str(data.get("version", "")).strip():
        raise ValueError("Versionsinformation enthält keine Versionsnummer.")
    result = dict(data)
    result["source"] = "custom"
    return result


def is_installable_release(info: dict) -> bool:
    version = str(info.get("version", ""))
    if info.get("source") != "github_release" or not VERSION_RE.fullmatch(version):
        return False
    expected_url = f"{RELEASE_DOWNLOAD_ROOT}/v{version}/{installer_name(version)}"
    return (
        str(info.get("url", "")) == expected_url
        and bool(SHA256_RE.fullmatch(str(info.get("sha256", ""))))
    )


def download_verified_installer(info: dict) -> Path:
    if not is_installable_release(info):
        raise ValueError("Dieses Update stammt nicht aus einem geprüften MJET-X-Release.")
    version = str(info["version"])
    work_dir = Path(tempfile.mkdtemp(prefix="MJETXHelper-update-"))
    part_path = work_dir / (installer_name(version) + ".part")
    final_path = work_dir / installer_name(version)
    try:
        request = Request(str(info["url"]), headers={"User-Agent": "MJET-X-Helper"})
        digest = hashlib.sha256()
        total = 0
        with urlopen(request, timeout=30) as response, part_path.open("wb") as output:
            if urlparse(response.geturl()).scheme != "https":
                raise ValueError("Der Installer wurde nicht über HTTPS geladen.")
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_INSTALLER_BYTES:
                    raise ValueError("Der Installer ist ungewöhnlich groß. Download abgebrochen.")
                output.write(chunk)
                digest.update(chunk)
        if not total or digest.hexdigest() != str(info["sha256"]).lower():
            raise ValueError("Die Prüfsumme des Installers stimmt nicht. Es wurde nichts gestartet.")
        with part_path.open("rb") as downloaded:
            if downloaded.read(2) != b"MZ":
                raise ValueError("Die geladene Datei ist kein Windows-Installer.")
        part_path.replace(final_path)
        return final_path
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
