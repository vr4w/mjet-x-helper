from __future__ import annotations

import ast
import copy
import csv
import ctypes
import datetime as dt
import html
import json
import operator
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import parse_qs
from urllib.request import urlopen


APP_NAME = "MJET-X Helper"
APP_VERSION = "1.1.1"
APP_AUTHOR = "AE / Marvin Schöffel"
APP_CONTACT = "ms@graphic-druck.de"
CONFIG_NAME = "helper_config.json"
COLOR_NS = "urn:schemas-colorgate-com:colortable"
PREFERRED_OUTPUT_SUFFIXES = {".info", ".tif", ".tiff", ".bmp", ".tmp", ".log"}

THEME = {
    "window": "#e7e9ec",
    "panel": "#f6f7f8",
    "panel_alt": "#eef1f4",
    "border": "#c8cdd3",
    "text": "#20242a",
    "muted": "#626b75",
    "button": "#d8e1ec",
    "button_active": "#c7d5e5",
    "button_text": "#1d3348",
    "danger": "#d8b7b7",
    "danger_active": "#cca3a3",
    "green": "#2f8f4e",
    "yellow": "#c9901a",
    "red": "#bd3f3f",
    "gray": "#8c939b",
    "entry": "#ffffff",
}


DEFAULT_CONFIG = {
    "nas_root": r"Z:\_MPRINT_4c",
    "color_root": r"Z:\_MPRINT_4c\Maschinenfarben",
    "single_color_dir": r"Z:\_MPRINT_4c\Maschinenfarben\Einzelfarben",
    "backup_dir": r"Z:\_MPRINT_4c\Maschinenfarben\Backup",
    "master_cct": r"Z:\_MPRINT_4c\Maschinenfarben\mprint4c-master.cct",
    "colorgate_root": r"C:\ProgramData\ColorGATE Software\Productionserver25",
    "colorgate_ini": r"C:\ProgramData\ColorGATE Software\Productionserver25\Productionserver25.INI",
    "colorgate_cos": r"C:\ProgramData\ColorGATE Software\Productionserver25\Settings\mprint mlabel.cos",
    "colorgate_jobdir": r"C:\ProgramData\ColorGATE Software\Productionserver25\JobDir\mprint mlabel",
    "output_printdata_dir": r"C:\Users\user\Desktop\OUTPUT_PRINTDATA",
    "expected_profiles": [
        "600DPI_S3200-U1",
        "775X600 DPI MJET-X",
        "900X600 DPI MJET-X",
        "1200X600 DPI MJET-X",
    ],
    "expected_master_path": r"Z:\_MPRINT_4c\Maschinenfarben\mprint4c-master.cct",
    "color_overview_csv": r"work\MPRINT_Farbuebersicht_daten.csv",
    "legacy_color_overview_csv": r"Z:\_MPRINT_4c\MPRINT_Farbuebersicht.csv",
    "color_overview_html": r"Z:\_MPRINT_4c\MPRINT_Farbuebersicht.html",
    "color_request_server_enabled": True,
    "color_request_server_host": "0.0.0.0",
    "color_request_server_port": 8765,
    "color_request_submit_url": "",
    "auto_clean_output_printdata": True,
    "output_clean_delay_seconds": 120,
    "output_clean_interval_seconds": 60,
    "always_on_top": True,
    "window_width": 260,
    "update_check_enabled": True,
    "update_check_url": "https://raw.githubusercontent.com/vr4w/mjet-x-helper/main/update_info.json",
    "known_processes": [
        "Productionserver25.exe",
        "lp2000i.exe",
    ],
    "pdf_reduce_dpi": 3600,
    "pdf_reduce_detect_dpi": 300,
    "pdf_reduce_variants_pt": [0.05, 0.07, 0.1, 0.15],
    "pdf_reduce_code_protect_margin_mm": 3.0,
    "pdf_reduce_abort_if_no_codes_found": True,
    "pdf_reduce_foreground_threshold": 8,
    "pdf_reduce_edge_threshold": 24,
    "pdf_reduce_tile_size": 8,
    "pdf_reduce_tile_density": 0.08,
    "pdf_reduce_component_density": 0.08,
    "pdf_reduce_min_code_size_mm": 5.0,
    "pdf_reduce_max_code_size_mm": 120.0,
    "pdf_reduce_max_code_ratio": 12.0,
    "pdf_reduce_vector_detection": True,
    "pdf_reduce_vector_module_max_pt": 4.0,
    "pdf_reduce_vector_module_cluster_gap_pt": 2.0,
    "pdf_reduce_vector_module_min_count": 20,
    "pdf_reduce_vector_barcode_min_items": 40,
}


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


APP_DIR = app_dir()
CONFIG_PATH = APP_DIR / CONFIG_NAME


def merge_defaults(config: dict, defaults: dict) -> dict:
    merged = dict(defaults)
    merged.update(config)
    return merged


def load_config() -> dict:
    load_config.created_default = False  # type: ignore[attr-defined]
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(
            json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        load_config.created_default = True  # type: ignore[attr-defined]
        return dict(DEFAULT_CONFIG)

    try:
        loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        backup_path = CONFIG_PATH.with_suffix(f".broken-{int(time.time())}.json")
        shutil.copy2(CONFIG_PATH, backup_path)
        raise RuntimeError(
            f"Config konnte nicht gelesen werden. Kopie liegt hier: {backup_path}"
        ) from exc

    merged = merge_defaults(loaded, DEFAULT_CONFIG)
    if merged != loaded:
        save_config(merged)
    return merged


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def default_config_created() -> bool:
    return bool(load_config.created_default)  # type: ignore[attr-defined]


load_config.created_default = False  # type: ignore[attr-defined]


def as_path(value: str | os.PathLike[str]) -> Path:
    return Path(str(value)).expanduser()


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def filename_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def format_pt_value(width_pt: float) -> str:
    return f"{float(width_pt):.2f}".replace(".", ",")


class HelperLogger:
    def __init__(self, config: dict):
        self.config = config
        self.lock = threading.Lock()
        self.lines: list[str] = []
        self.callbacks: list[callable] = []
        self.log_dir = self._choose_log_dir()

    def _choose_log_dir(self) -> Path:
        backup_value = str(self.config.get("backup_dir", ""))
        if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", backup_value):
            preferred = APP_DIR / "helper_logs"
        else:
            preferred = as_path(backup_value) / "helper_logs"
        fallback = APP_DIR / "helper_logs"
        for path in (preferred, fallback):
            try:
                path.mkdir(parents=True, exist_ok=True)
                return path
            except Exception:
                continue
        return fallback

    def add_callback(self, callback: callable) -> None:
        self.callbacks.append(callback)

    def _log_file(self) -> Path:
        today = dt.datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"helper_{today}.log"

    def log(self, message: str, level: str = "INFO") -> None:
        line = f"{now_stamp()} [{level}] {message}"
        with self.lock:
            self.lines.append(line)
            self.lines = self.lines[-500:]
            try:
                self.log_dir.mkdir(parents=True, exist_ok=True)
                with self._log_file().open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
            except Exception:
                pass

        for callback in self.callbacks:
            try:
                callback(line)
            except Exception:
                pass

    def recent_text(self, limit: int = 200) -> str:
        with self.lock:
            return "\n".join(self.lines[-limit:])


@dataclass
class SyncResult:
    severity: str
    message: str
    colors: list[str] = field(default_factory=list)
    profiles: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    master_snippets: list[str] = field(default_factory=list)
    autoreplace_snippets: list[str] = field(default_factory=list)
    master_hits: list[str] = field(default_factory=list)


@dataclass
class CosCheckResult:
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    profiles: list[str] = field(default_factory=list)
    master_snippets: list[str] = field(default_factory=list)
    autoreplace_snippets: list[str] = field(default_factory=list)
    master_hits: list[str] = field(default_factory=list)


class ColorTableManager:
    def __init__(self, config: dict, logger: HelperLogger):
        self.config = config
        self.logger = logger
        self.overview_lock = threading.RLock()
        ET.register_namespace("", COLOR_NS)

    def rebuild_master(self, write_master: bool = True) -> SyncResult:
        action = "Farbabgleich gestartet" if write_master else "Farbabgleich-Prüfung gestartet"
        self.logger.log(action)
        warnings: list[str] = []
        errors: list[str] = []
        color_names: list[str] = []
        profiles: list[str] = []
        source_files: list[str] = []

        color_root = as_path(self.config["color_root"])
        single_dir = as_path(self.config["single_color_dir"])
        backup_dir = as_path(self.config["backup_dir"])
        master_path = as_path(self.config["master_cct"])

        if not color_root.exists():
            error = f"Maschinenfarben nicht erreichbar: {color_root}"
            self.logger.log(error, "ERROR")
            return SyncResult("red", error, errors=[error])
        if not single_dir.exists():
            error = f"Ordner für einzelne Kundenfarben fehlt: {single_dir}"
            self.logger.log(error, "ERROR")
            return SyncResult("red", error, errors=[error])

        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            error = f"Backup-Ordner konnte nicht erstellt werden: {backup_dir} ({exc})"
            self.logger.log(error, "ERROR")
            return SyncResult("red", error, errors=[error])

        color_files = self._find_color_files(single_dir, master_path)
        source_files = [str(path) for path in color_files]
        self.logger.log(f"Gefundene Einzeldateien: {len(color_files)}")

        if not color_files:
            error = f"Keine .cct/.ct-Dateien in {single_dir} gefunden"
            self.logger.log(error, "ERROR")
            return SyncResult("red", error, errors=[error])

        unique_entries: list[ET.Element] = []
        seen_by_name: dict[str, tuple[str, int, Path, float]] = {}
        duplicate_same = 0

        for color_file in color_files:
            file_mtime = self._safe_mtime(color_file)
            try:
                tree = ET.parse(color_file)
            except ET.ParseError as exc:
                errors.append(f"XML fehlerhaft in {color_file.name}: {exc}")
                self.logger.log(f"XML fehlerhaft in {color_file}: {exc}", "ERROR")
                continue
            except Exception as exc:
                errors.append(f"Datei konnte nicht gelesen werden: {color_file.name}: {exc}")
                self.logger.log(f"Datei konnte nicht gelesen werden: {color_file}: {exc}", "ERROR")
                continue

            entries = [
                copy.deepcopy(elem)
                for elem in tree.getroot().iter()
                if local_name(elem.tag) == "ColorEntry"
            ]
            self.logger.log(f"{color_file.name}: {len(entries)} ColorEntry-Einträge")

            for entry in entries:
                name = self._color_entry_name(entry)
                content = self._entry_signature(entry)
                if name in seen_by_name:
                    previous_content, previous_index, previous_file, previous_mtime = seen_by_name[name]
                    if previous_content == content:
                        duplicate_same += 1
                        self.logger.log(f"Doppelte Farbe identisch übersprungen: {name}")
                    else:
                        warning = f"Doppelte Farbe: {name} - bitte prüfen."
                        warnings.append(warning)
                        if file_mtime >= previous_mtime:
                            unique_entries[previous_index] = entry
                            seen_by_name[name] = (content, previous_index, color_file, file_mtime)
                            winner = color_file
                            loser = previous_file
                        else:
                            winner = previous_file
                            loser = color_file
                        self.logger.log(
                            f"{warning} Gewinner: {winner.name}; übersprungen: {loser.name}",
                            "WARNING",
                        )
                    continue
                seen_by_name[name] = (content, len(unique_entries), color_file, file_mtime)
                unique_entries.append(entry)
                color_names.append(name)

        if errors:
            return SyncResult(
                "red",
                "Farbabgleich abgebrochen: XML-/Lesefehler",
                color_names,
                profiles,
                warnings,
                errors,
                source_files,
            )

        if write_master:
            try:
                self._write_master_atomically(master_path, backup_dir, unique_entries)
            except Exception as exc:
                error = f"Master konnte nicht geschrieben werden: {exc}"
                self.logger.log(error, "ERROR")
                return SyncResult(
                    "red",
                    error,
                    color_names,
                    profiles,
                    warnings,
                    errors + [error],
                    source_files,
                )
        else:
            self.logger.log("Nur Prüfung: Master wurde nicht geschrieben")

        try:
            master_names = color_names if write_master else self._master_color_names(master_path)
            overview_warning = self._write_color_overview(color_names, master_names)
            if overview_warning:
                warnings.append(overview_warning)
        except Exception as exc:
            warning = f"Farbübersicht konnte nicht geschrieben werden: {exc}"
            warnings.append(warning)
            self.logger.log(warning, "WARNING")

        self.logger.log(f"Übernommene Farben: {len(unique_entries)}")
        if duplicate_same:
            self.logger.log(f"Identische doppelte Farben übersprungen: {duplicate_same}")

        if errors:
            return SyncResult(
                "red",
                "Farbabgleich fehlgeschlagen",
                color_names,
                profiles,
                warnings,
                errors,
                source_files,
            )
        operation_done = "Master gebaut" if write_master else "Master geprüft"
        if warnings:
            return SyncResult(
                "yellow",
                f"{operation_done}, aber Warnungen vorhanden",
                color_names,
                profiles,
                warnings,
                errors,
                source_files,
            )
        return SyncResult(
            "green",
            "Master erfolgreich gebaut" if write_master else "Master-Prüfung erfolgreich",
            color_names,
            profiles,
            warnings,
            errors,
            source_files,
        )

    def check_master_status(self) -> SyncResult:
        self.logger.log("Startprüfung Farbabgleich")
        warnings: list[str] = []
        errors: list[str] = []
        color_names: list[str] = []

        color_root = as_path(self.config["color_root"])
        single_dir = as_path(self.config["single_color_dir"])
        master_path = as_path(self.config["master_cct"])

        if not color_root.exists():
            error = f"Maschinenfarben nicht erreichbar: {color_root}"
            self.logger.log(error, "ERROR")
            return SyncResult("red", error, errors=[error])
        if not single_dir.exists():
            error = f"Ordner für einzelne Kundenfarben fehlt: {single_dir}"
            self.logger.log(error, "ERROR")
            return SyncResult("red", error, errors=[error])
        if not master_path.exists():
            warning = "Masterdatei fehlt - Farbabgleich starten"
            self.logger.log(warning, "WARNING")
            return SyncResult("yellow", warning, warnings=[warning])

        color_files = self._find_color_files(single_dir, master_path)
        source_files = [str(path) for path in color_files]
        if not color_files:
            error = f"Keine .cct/.ct-Dateien in {single_dir} gefunden"
            self.logger.log(error, "ERROR")
            return SyncResult("red", error, errors=[error], files=source_files)

        single_signatures: dict[str, str] = {}
        seen_sources: dict[str, Path] = {}
        for color_file in color_files:
            try:
                tree = ET.parse(color_file)
            except ET.ParseError as exc:
                errors.append(f"XML fehlerhaft in {color_file.name}: {exc}")
                continue
            except Exception as exc:
                errors.append(f"Datei konnte nicht gelesen werden: {color_file.name}: {exc}")
                continue

            for entry in tree.getroot().iter():
                if local_name(entry.tag) != "ColorEntry":
                    continue
                name = self._color_entry_name(entry)
                signature = self._entry_signature(entry)
                if name in single_signatures:
                    if single_signatures[name] != signature:
                        warnings.append(f"Doppelte Farbe: {name} - bitte prüfen.")
                    continue
                single_signatures[name] = signature
                seen_sources[name] = color_file
                color_names.append(name)

        if errors:
            for error in errors:
                self.logger.log(error, "ERROR")
            return SyncResult(
                "red",
                "Startprüfung abgebrochen: XML-/Lesefehler",
                color_names,
                warnings=warnings,
                errors=errors,
                files=source_files,
            )

        master_signatures = self._master_entry_signatures(master_path)
        missing_or_changed = [
            name
            for name, signature in single_signatures.items()
            if master_signatures.get(name) != signature
        ]

        try:
            overview_warning = self._write_color_overview(color_names, list(master_signatures.keys()))
            if overview_warning:
                warnings.append(overview_warning)
        except Exception as exc:
            warning = f"Farbübersicht konnte nicht geschrieben werden: {exc}"
            warnings.append(warning)
            self.logger.log(warning, "WARNING")

        if missing_or_changed:
            warning = f"{len(missing_or_changed)} Farbe(n) noch nicht in der Masterdatei"
            warnings.insert(0, warning)
            self.logger.log(warning, "WARNING")
            return SyncResult(
                "yellow",
                "Farbabgleich nötig",
                color_names,
                warnings=warnings,
                files=source_files,
            )

        if warnings:
            return SyncResult(
                "yellow",
                "Master aktuell, aber Warnungen vorhanden",
                color_names,
                warnings=warnings,
                files=source_files,
            )

        return SyncResult(
            "green",
            "Master aktuell",
            color_names,
            files=source_files,
        )

    def _find_color_files(self, single_dir: Path, master_path: Path) -> list[Path]:
        files: list[Path] = []
        master_name = master_path.name.lower()
        for path in sorted(single_dir.iterdir(), key=lambda item: item.name.lower()):
            if not path.is_file():
                continue
            name_lower = path.name.lower()
            suffix_lower = path.suffix.lower()
            if suffix_lower not in {".cct", ".ct"}:
                continue
            if name_lower == master_name:
                continue
            if self._is_ignored_file(path):
                continue
            if "backup" in [part.lower() for part in path.parts]:
                continue
            files.append(path)
        return files

    def _is_ignored_file(self, path: Path) -> bool:
        name = path.name
        lower = name.lower()
        if name.startswith(".") or name.startswith("~"):
            return True
        if lower in {".ds_store", "thumbs.db"}:
            return True
        if lower.endswith((".tmp", ".temp", ".bak", ".part", ".crdownload")):
            return True
        if os.name == "nt":
            try:
                attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
                if attrs != -1 and attrs & 0x2:
                    return True
            except Exception:
                pass
        return False

    def _color_entry_name(self, entry: ET.Element) -> str:
        for attr in ("Name", "name", "ColorName", "colorName"):
            value = entry.attrib.get(attr)
            if value:
                return value.strip()

        for child in entry:
            if local_name(child.tag).lower() in {"name", "colorname"} and child.text:
                return child.text.strip()

        content = ET.tostring(entry, encoding="unicode")
        compact = re.sub(r"\s+", " ", content).strip()
        return compact[:80] or f"ColorEntry-{id(entry)}"

    def _entry_signature(self, entry: ET.Element) -> str:
        def normalize(node: ET.Element) -> tuple:
            attrs = tuple(sorted((local_name(key), str(value).strip()) for key, value in node.attrib.items()))
            text = (node.text or "").strip()
            children = tuple(normalize(child) for child in list(node))
            return (local_name(node.tag), attrs, text, children)

        return repr(normalize(entry))

    def _master_entry_signatures(self, master_path: Path) -> dict[str, str]:
        try:
            tree = ET.parse(master_path)
        except Exception as exc:
            self.logger.log(f"Master konnte nicht gelesen werden: {master_path} ({exc})", "ERROR")
            return {}

        signatures: dict[str, str] = {}
        for entry in tree.getroot().iter():
            if local_name(entry.tag) == "ColorEntry":
                signatures[self._color_entry_name(entry)] = self._entry_signature(entry)
        return signatures

    def _master_color_names(self, master_path: Path) -> list[str]:
        return list(self._master_entry_signatures(master_path).keys())

    def _write_color_overview(self, single_names: list[str], master_names: list[str]) -> str | None:
        csv_path = self._overview_csv_path()
        html_path = as_path(self.config.get("color_overview_html", ""))
        if not str(html_path):
            return None
        single_info = self._single_color_info()

        existing_rows, existing_fields = self._read_color_overview_with_legacy(csv_path)
        name_column = self._find_name_column(existing_fields) or "Farbbezeichnung"
        generated_fields = [
            "Farbbezeichnung",
            "Status",
            "Angelegt am",
            "Gedruckt am",
            "Abgeglichen am",
            "CMYK",
            "Einzelfarbe vorhanden",
            "In Masterdatei",
            "Letzter Abgleich",
            "Quelle",
            "created_at",
            "last_printed_at",
            "last_synced_at",
            "legacy_created_at",
            "legacy_printed_at",
        ]
        extra_fields = [
            field
            for field in existing_fields
            if field and field not in generated_fields and field != name_column
        ]
        fieldnames = generated_fields + extra_fields

        single_lookup = {name.casefold(): name for name in single_names}
        master_lookup = {name.casefold(): name for name in master_names}
        row_lookup: dict[str, dict[str, str]] = {}
        display_names: dict[str, str] = {}

        for row in existing_rows:
            raw_name = (row.get(name_column) or row.get("Farbbezeichnung") or "").strip()
            if not raw_name:
                continue
            key = raw_name.casefold()
            row_lookup.setdefault(key, row)
            display_names.setdefault(key, raw_name)

        for name in single_names + master_names:
            key = name.casefold()
            display_names[key] = name

        now_text = now_stamp()
        rows: list[dict[str, str]] = []
        for key in sorted(display_names, key=lambda item: display_names[item].casefold()):
            name = display_names[key]
            existing = row_lookup.get(key, {})
            in_single = key in single_lookup
            in_master = key in master_lookup
            info = single_info.get(key, {})
            if in_single and in_master:
                status = "MPRINT angepasst / druckbar"
            elif in_single:
                status = "Einzelfarbe vorhanden - Farbabgleich offen"
            elif in_master:
                status = "In Masterdatei - Einzelfarbe fehlt"
            else:
                status = "Noch nicht an MPRINT gedruckt"

            existing_source = existing.get("Quelle", "").strip().casefold()
            was_prepress_row = key in row_lookup and existing_source != "mprint"
            if was_prepress_row and in_single:
                source = "Vorstufe + MPRINT"
            elif in_single or in_master:
                source = "MPRINT"
            else:
                source = "Vorstufe"

            legacy_created_at = (
                existing.get("legacy_created_at", "").strip()
                or existing.get("Angelegt am", "").strip()
                or existing.get("AngelegtAm", "").strip()
            )
            legacy_printed_at = (
                existing.get("legacy_printed_at", "").strip()
                or existing.get("Gedruckt am", "").strip()
                or existing.get("GedrucktAm", "").strip()
            )
            created_at = existing.get("created_at", "").strip()
            if not created_at and not existing:
                created_at = now_text
            last_printed_at = existing.get("last_printed_at", "").strip()
            last_synced_at = now_text
            cmyk = str(info.get("cmyk", "") or existing.get("CMYK", "")).strip()

            output_row = {field: existing.get(field, "") for field in extra_fields}
            output_row.update(
                {
                    "Farbbezeichnung": name,
                    "Status": status,
                    "Angelegt am": created_at,
                    "Gedruckt am": last_printed_at,
                    "Abgeglichen am": last_synced_at,
                    "CMYK": cmyk,
                    "Einzelfarbe vorhanden": "ja" if in_single else "nein",
                    "In Masterdatei": "ja" if in_master else "nein",
                    "Letzter Abgleich": last_synced_at,
                    "Quelle": source,
                    "created_at": created_at,
                    "last_printed_at": last_printed_at,
                    "last_synced_at": last_synced_at,
                    "legacy_created_at": legacy_created_at,
                    "legacy_printed_at": legacy_printed_at,
                }
            )
            rows.append(output_row)

        with self.overview_lock:
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            self._backup_color_overview_before_timestamp_migration(csv_path, existing_fields)
            temp_csv = csv_path.with_suffix(csv_path.suffix + ".tmp")
            with temp_csv.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=";")
                writer.writeheader()
                writer.writerows(rows)
            os.replace(temp_csv, csv_path)
            self.logger.log(f"Interne Farbdaten geschrieben: {csv_path}")

            self._write_color_overview_html(html_path, rows)
        return None

    def add_requested_color(self, color_name: str) -> str:
        cleaned = re.sub(r"\s+", " ", color_name).strip()
        if not cleaned:
            return "Bitte eine Farbbezeichnung eintragen."
        if len(cleaned) > 160:
            return "Die Farbbezeichnung ist zu lang."

        csv_path = self._overview_csv_path()
        with self.overview_lock:
            rows, fields = self._read_color_overview_with_legacy(csv_path)
            name_column = self._find_name_column(fields) or "Farbbezeichnung"
            if "Farbbezeichnung" not in fields:
                fields = ["Farbbezeichnung"] + [field for field in fields if field != name_column]
                name_column = "Farbbezeichnung"
            if "Quelle" not in fields:
                fields.append("Quelle")
            for field in ("created_at", "last_printed_at", "last_synced_at"):
                if field not in fields:
                    fields.append(field)

            existing_keys = {
                (row.get(name_column) or row.get("Farbbezeichnung") or "").strip().casefold()
                for row in rows
            }
            if cleaned.casefold() not in existing_keys:
                created_at = now_stamp()
                rows.append(
                    {
                        "Farbbezeichnung": cleaned,
                        "Quelle": "Vorstufe",
                        "created_at": created_at,
                        "last_printed_at": "",
                        "last_synced_at": created_at,
                    }
                )
                csv_path.parent.mkdir(parents=True, exist_ok=True)
                temp_csv = csv_path.with_suffix(csv_path.suffix + ".tmp")
                with temp_csv.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";")
                    writer.writeheader()
                    for row in rows:
                        normalized = dict(row)
                        if name_column != "Farbbezeichnung":
                            normalized["Farbbezeichnung"] = row.get(name_column, "")
                        writer.writerow({field: normalized.get(field, "") for field in fields})
                os.replace(temp_csv, csv_path)
                self.logger.log(f"Kundenfarbe eingetragen: {cleaned}")
            else:
                return f"Kundenfarbe ist bereits in der Übersicht: {cleaned}"

        self.refresh_color_overview()
        return f"Kundenfarbe eingetragen: {cleaned}"

    def delete_overview_color(self, color_name: str) -> str:
        cleaned = re.sub(r"\s+", " ", color_name).strip()
        if not cleaned:
            return "Keine Farbbezeichnung übergeben."

        csv_path = self._overview_csv_path()
        with self.overview_lock:
            rows, fields = self._read_color_overview_with_legacy(csv_path)
            name_column = self._find_name_column(fields) or "Farbbezeichnung"
            remaining_rows = []
            removed = 0
            for row in rows:
                raw_name = (row.get(name_column) or row.get("Farbbezeichnung") or "").strip()
                if raw_name.casefold() == cleaned.casefold():
                    removed += 1
                    continue
                remaining_rows.append(row)

            if removed:
                if "Farbbezeichnung" not in fields:
                    fields = ["Farbbezeichnung"] + [field for field in fields if field != name_column]
                    name_column = "Farbbezeichnung"
                csv_path.parent.mkdir(parents=True, exist_ok=True)
                temp_csv = csv_path.with_suffix(csv_path.suffix + ".tmp")
                with temp_csv.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields, delimiter=";")
                    writer.writeheader()
                    for row in remaining_rows:
                        normalized = dict(row)
                        if name_column != "Farbbezeichnung":
                            normalized["Farbbezeichnung"] = row.get(name_column, "")
                        writer.writerow({field: normalized.get(field, "") for field in fields})
                os.replace(temp_csv, csv_path)
                self.logger.log(f"Farbübersicht-Eintrag gelöscht: {cleaned}")

        self.refresh_color_overview()
        if removed:
            return f"Eintrag gelöscht: {cleaned}"
        return f"Eintrag nicht gefunden oder wird von Einzelfarben/Master wieder erzeugt: {cleaned}"

    def _backup_color_overview_before_timestamp_migration(
        self,
        csv_path: Path,
        existing_fields: list[str],
    ) -> None:
        if not csv_path.exists():
            return
        required_fields = {"created_at", "last_printed_at", "last_synced_at"}
        if required_fields.issubset(set(existing_fields)):
            return
        backup_path = csv_path.with_name(
            f"{csv_path.stem}_backup_vor_timestamp_migration_{filename_stamp()}{csv_path.suffix}"
        )
        try:
            shutil.copy2(csv_path, backup_path)
            self.logger.log(f"Backup vor Zeitstempel-Migration geschrieben: {backup_path}")
        except Exception as exc:
            self.logger.log(f"Backup vor Zeitstempel-Migration fehlgeschlagen: {exc}", "WARN")

    def refresh_color_overview(self) -> None:
        single_names = self._single_color_names()
        master_path = as_path(self.config["master_cct"])
        master_names = self._master_color_names(master_path) if master_path.exists() else []
        self._write_color_overview(single_names, master_names)

    def _single_color_names(self) -> list[str]:
        return [info["name"] for info in self._single_color_info().values()]

    def _single_color_info(self) -> dict[str, dict[str, str]]:
        single_dir = as_path(self.config["single_color_dir"])
        master_path = as_path(self.config["master_cct"])
        if not single_dir.exists():
            return {}

        info_by_key: dict[str, dict[str, str]] = {}
        for color_file in self._find_color_files(single_dir, master_path):
            try:
                tree = ET.parse(color_file)
            except Exception:
                continue
            for entry in tree.getroot().iter():
                if local_name(entry.tag) != "ColorEntry":
                    continue
                name = self._color_entry_name(entry)
                key = name.casefold()
                if key not in info_by_key:
                    info_by_key[key] = {
                        "name": name,
                        "cmyk": self._color_entry_cmyk(entry),
                    }
        return info_by_key

    def _color_entry_cmyk(self, entry: ET.Element) -> str:
        color_out = None
        for elem in entry.iter():
            if local_name(elem.tag) == "ColorOut":
                color_out = elem
                break
        if color_out is None:
            return ""

        values_text = ""
        for elem in color_out.iter():
            if local_name(elem.tag) == "ComponentValues" and elem.text:
                values_text = elem.text.strip()
                break
        if not values_text:
            return ""

        parts = re.findall(r"-?\d+(?:[.,]\d+)?", values_text)
        if len(parts) < 4:
            return re.sub(r"\s+", " ", values_text)
        c, m, y, k = [part.replace(".", ",") for part in parts[:4]]
        return f"C {c} / M {m} / Y {y} / K {k}"

    def _overview_csv_path(self) -> Path:
        configured = str(self.config.get("color_overview_csv", "")).strip()
        if not configured:
            return APP_DIR / "work" / "MPRINT_Farbuebersicht_daten.csv"
        path = Path(configured)
        if path.is_absolute() or re.match(r"^[A-Za-z]:[\\/]", configured):
            return path
        return APP_DIR / path

    def _read_color_overview_with_legacy(self, csv_path: Path) -> tuple[list[dict[str, str]], list[str]]:
        rows, fields = self._read_color_overview(csv_path)
        if rows or csv_path.exists():
            return rows, fields

        legacy_value = str(self.config.get("legacy_color_overview_csv", "")).strip()
        if not legacy_value:
            return rows, fields
        legacy_path = Path(legacy_value)
        if legacy_path == csv_path:
            return rows, fields
        legacy_rows, legacy_fields = self._read_color_overview(legacy_path)
        if legacy_rows:
            self.logger.log(f"Alte Server-CSV einmalig übernommen: {legacy_path}")
            return legacy_rows, legacy_fields
        return rows, fields

    def _read_color_overview(self, csv_path: Path) -> tuple[list[dict[str, str]], list[str]]:
        if not csv_path.exists():
            return [], []

        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                text = csv_path.read_text(encoding=encoding)
                break
            except Exception:
                text = ""
        if not text.strip():
            return [], []

        first_line = text.splitlines()[0] if text.splitlines() else ""
        if ";" in first_line:
            delimiter = ";"
        elif "," in first_line:
            delimiter = ","
        else:
            delimiter = ";" if text.count(";") >= text.count(",") else ","
        reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
        rows = [{key: value for key, value in row.items() if key} for row in reader]
        return rows, list(reader.fieldnames or [])

    def _find_name_column(self, fields: list[str]) -> str | None:
        preferred = {
            "farbbezeichnung",
            "farbe",
            "farbname",
            "color",
            "name",
            "sonderfarbe",
            "spotfarbe",
        }
        for field in fields:
            normalized = re.sub(r"[^a-z0-9äöüß]", "", field.casefold())
            if normalized in preferred:
                return field
        return fields[0] if fields else None

    def _write_color_overview_html(
        self,
        html_path: Path,
        rows: list[dict[str, str]],
    ) -> None:
        submit_url = self._color_request_submit_url()
        delete_url = submit_url.rsplit("/", 1)[0] + "/farbe-loeschen"
        status_url = submit_url.rsplit("/", 1)[0] + "/status"
        submit_url_json = json.dumps(submit_url)
        delete_url_json = json.dumps(delete_url)
        status_url_json = json.dumps(status_url)
        body_rows = []
        for row in rows:
            name = str(row.get("Farbbezeichnung", ""))
            status = row.get("Status", "")
            angelegt_am = str(row.get("Angelegt am", ""))
            gedruckt_am = str(row.get("Gedruckt am", ""))
            abgeglichen_am = str(row.get("Abgeglichen am", "") or row.get("Letzter Abgleich", ""))
            cmyk = str(row.get("CMYK", ""))
            if "druckbar" in status:
                css = "ok"
            elif "offen" in status:
                css = "wait"
            elif "Noch nicht" in status:
                css = "new"
            else:
                css = "warn"
            escaped_name = html.escape(name)
            escaped_status = html.escape(str(status))
            escaped_angelegt_am = html.escape(angelegt_am or "nicht erfasst")
            escaped_gedruckt_am = html.escape(gedruckt_am or "nicht erfasst")
            escaped_abgeglichen_am = html.escape(abgeglichen_am or "nicht erfasst")
            escaped_cmyk = html.escape(cmyk)
            button_name = html.escape(name, quote=True)
            body_rows.append(
                f"<tr class=\"{css}\">"
                f"<td><span class=\"dot\" aria-hidden=\"true\"></span></td>"
                f"<td class=\"name\">{escaped_name}</td>"
                f"<td><button type=\"button\" class=\"copy\" data-name=\"{button_name}\">Kopieren</button></td>"
                f"<td>{escaped_status}</td>"
                f"<td>{escaped_angelegt_am}</td>"
                f"<td>{escaped_gedruckt_am}</td>"
                f"<td>{escaped_abgeglichen_am}</td>"
                f"<td>{escaped_cmyk}</td>"
                f"<td class=\"adminOnly\"><button type=\"button\" class=\"delete\" data-name=\"{button_name}\">Löschen</button></td>"
                f"</tr>"
            )

        document = f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <title>MPRINT Farbübersicht</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; color: #20242a; background: #f4f5f6; }}
    h1 {{ margin: 0 0 6px; font-size: 24px; }}
    .meta {{ margin: 0 0 18px; color: #626b75; }}
    .entry {{ display: flex; gap: 8px; margin: 0 0 18px; max-width: 720px; }}
    input {{ flex: 1; padding: 10px 12px; border: 1px solid #c8cdd3; font-size: 15px; }}
    button {{ border: 1px solid #b7c0ca; background: #d8e1ec; color: #1d3348; padding: 9px 12px; cursor: pointer; font-weight: 600; }}
    button:hover {{ background: #c7d5e5; }}
    .connection {{ display: inline-flex; align-items: center; gap: 8px; margin: -8px 0 16px; color: #626b75; font-size: 14px; }}
    .connection::before {{ content: ""; width: 10px; height: 10px; border-radius: 50%; background: #8c939b; }}
    .connection.ok::before {{ background: #2f8f4e; }}
    .connection.down::before {{ background: #bd3f3f; }}
    .connection.checking::before {{ background: #c9901a; }}
    #entryStatus {{ margin: -8px 0 16px; color: #626b75; min-height: 20px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; box-shadow: 0 0 0 1px #c8cdd3; }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid #dfe3e7; text-align: left; font-size: 14px; vertical-align: top; }}
    th {{ background: #e7e9ec; }}
    th.indicator, td:first-child {{ width: 34px; text-align: center; }}
    .name {{ font-weight: 600; }}
    .copy {{ padding: 6px 9px; font-size: 12px; }}
    td:nth-child(5), td:nth-child(6), td:nth-child(7), td:nth-child(8) {{ color: #626b75; white-space: nowrap; }}
    .delete {{ padding: 6px 9px; font-size: 12px; background: #d8b7b7; color: #3e1f1f; }}
    .adminOnly {{ display: none; }}
    body.admin .adminOnly {{ display: table-cell; }}
    .dot {{ display: inline-block; width: 14px; height: 14px; border-radius: 50%; background: #8c939b; }}
    tr.ok .dot {{ background: #2f8f4e; }}
    tr.wait .dot {{ background: #c9901a; }}
    tr.new .dot, tr.warn .dot {{ background: #bd3f3f; }}
  </style>
</head>
<body>
  <h1 id="title">MPRINT Farbübersicht</h1>
  <p class="meta">Automatisch aktualisiert: {html.escape(now_stamp())}</p>
  <form class="entry" method="post" action="{html.escape(submit_url, quote=True)}" target="submitFrame">
    <input name="farbe" id="farbe" autocomplete="off" placeholder="Kundenfarbe eintragen">
    <button type="submit">Eintragen</button>
  </form>
  <div id="connectionStatus" class="connection checking">Verbindung wird geprüft</div>
  <div id="entryStatus"></div>
  <iframe name="submitFrame" style="display:none"></iframe>
  <table>
    <thead><tr><th class="indicator"></th><th>Farbbezeichnung</th><th></th><th>Status</th><th>Angelegt am</th><th>Gedruckt am</th><th>Abgeglichen am</th><th>CMYK</th><th class="adminOnly"></th></tr></thead>
    <tbody>{''.join(body_rows)}</tbody>
  </table>
  <script>
    function fetchWithTimeout(url, options, timeoutMs) {{
      if (!window.AbortController) {{
        return fetch(url, options);
      }}
      var controller = new AbortController();
      var timeout = window.setTimeout(function() {{ controller.abort(); }}, timeoutMs || 8000);
      var merged = Object.assign({{}}, options || {{}}, {{ signal: controller.signal }});
      return fetch(url, merged).finally(function() {{ window.clearTimeout(timeout); }});
    }}
    function responseTextOrError(response) {{
      return response.text().then(function(text) {{
        if (!response.ok) {{
          var error = new Error(text || ('Servermeldung ' + response.status));
          error.status = response.status;
          throw error;
        }}
        return text;
      }});
    }}
    function friendlyFetchError(error) {{
      var message = error && error.message ? error.message : '';
      if (error && error.name === 'AbortError') {{
        return 'Die Verbindung zur MJET hat zu lange gedauert.';
      }}
      if (error instanceof TypeError || /Failed to fetch|NetworkError|Load failed/i.test(message)) {{
        return 'Die MJET beziehungsweise der Little MPRINT Helper ist derzeit nicht erreichbar. Die Farbe konnte nicht gespeichert werden.';
      }}
      return message || 'Die Farbe konnte nicht gespeichert werden.';
    }}
    function setConnectionStatus(kind, text) {{
      var node = document.getElementById('connectionStatus');
      node.className = 'connection ' + kind;
      node.textContent = text;
    }}
    function checkConnection() {{
      if (!window.fetch) {{
        setConnectionStatus('down', 'MJET-Verbindung kann mit diesem Browser nicht geprüft werden');
        return;
      }}
      setConnectionStatus('checking', 'Verbindung wird geprüft');
      fetchWithTimeout({status_url_json}, {{ method: 'GET', cache: 'no-store' }}, 5000)
        .then(responseTextOrError)
        .then(function() {{ setConnectionStatus('ok', 'MJET erreichbar'); }})
        .catch(function() {{ setConnectionStatus('down', 'MJET nicht erreichbar'); }});
    }}
    checkConnection();
    window.setInterval(checkConnection, 15000);
    document.querySelectorAll('.copy').forEach(function(button) {{
      button.addEventListener('click', function() {{
        var name = button.getAttribute('data-name') || '';
        if (navigator.clipboard) {{
          navigator.clipboard.writeText(name);
        }}
        button.textContent = 'Kopiert';
        window.setTimeout(function() {{ button.textContent = 'Kopieren'; }}, 1200);
      }});
    }});
    document.querySelectorAll('.delete').forEach(function(button) {{
      button.addEventListener('click', function() {{
        var name = button.getAttribute('data-name') || '';
        var status = document.getElementById('entryStatus');
        if (!window.fetch) {{
          status.textContent = 'Löschen braucht einen aktuellen Browser.';
          return;
        }}
        if (!window.confirm('Eintrag wirklich löschen?\\n\\n' + name)) {{
          return;
        }}
        status.textContent = 'Eintrag wird gelöscht...';
        fetchWithTimeout({delete_url_json}, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' }},
          body: new URLSearchParams({{ farbe: name }}).toString()
        }}, 8000)
        .then(responseTextOrError)
        .then(function(text) {{
          status.textContent = text || 'Eintrag gelöscht.';
          window.setTimeout(function() {{ window.location.reload(); }}, 700);
        }})
        .catch(function(error) {{
          status.textContent = 'Eintrag nicht gelöscht: ' + friendlyFetchError(error);
        }});
      }});
    }});
    (function() {{
      var clicks = 0;
      var timer = null;
      document.getElementById('title').addEventListener('click', function() {{
        clicks += 1;
        window.clearTimeout(timer);
        timer = window.setTimeout(function() {{ clicks = 0; }}, 1800);
        if (clicks >= 5) {{
          document.body.classList.toggle('admin');
          document.getElementById('entryStatus').textContent = document.body.classList.contains('admin')
            ? 'Adminmodus aktiv: Einträge können gelöscht werden.'
            : '';
          clicks = 0;
        }}
      }});
    }})();
    document.querySelector('.entry').addEventListener('submit', function(event) {{
      if (!window.fetch) {{
        return;
      }}
      event.preventDefault();
      var input = document.getElementById('farbe');
      var status = document.getElementById('entryStatus');
      var value = input.value.trim();
      if (!value) {{
        status.textContent = 'Bitte eine Farbbezeichnung eintragen.';
        return;
      }}
      status.textContent = 'Eintrag wird gesendet...';
      fetchWithTimeout({submit_url_json}, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' }},
        body: new URLSearchParams({{ farbe: value }}).toString()
      }}, 8000)
      .then(responseTextOrError)
      .then(function(text) {{
        status.textContent = text || 'Kundenfarbe eingetragen.';
        input.value = '';
        checkConnection();
        window.setTimeout(function() {{ window.location.reload(); }}, 900);
      }})
      .catch(function(error) {{
        status.textContent = 'Eintrag nicht gespeichert: ' + friendlyFetchError(error);
        checkConnection();
      }});
    }});
  </script>
</body>
</html>
"""
        html_path.parent.mkdir(parents=True, exist_ok=True)
        temp_html = html_path.with_suffix(html_path.suffix + ".tmp")
        temp_html.write_text(document, encoding="utf-8")
        os.replace(temp_html, html_path)
        self.logger.log(f"Farbübersicht HTML geschrieben: {html_path}")

    def _color_request_submit_url(self) -> str:
        configured = str(self.config.get("color_request_submit_url", "")).strip()
        if configured:
            return configured
        host = socket.gethostname() or "localhost"
        port = int(self.config.get("color_request_server_port", 8765))
        return f"http://{host}:{port}/farbe"

    def _safe_mtime(self, path: Path) -> float:
        try:
            return path.stat().st_mtime
        except Exception:
            return 0.0

    def _write_master_atomically(
        self,
        master_path: Path,
        backup_dir: Path,
        entries: list[ET.Element],
    ) -> None:
        root = ET.Element(
            f"{{{COLOR_NS}}}ColorTable",
            {
                "Name": "mprint4c-master",
                "Version": "3",
            },
        )
        for entry in entries:
            root.append(copy.deepcopy(entry))

        master_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix="mprint4c-master-",
            suffix=".tmp",
            dir=str(master_path.parent),
        )
        os.close(fd)
        temp_path = Path(temp_name)

        try:
            ET.ElementTree(root).write(
                temp_path,
                encoding="utf-8",
                xml_declaration=True,
                short_empty_elements=True,
            )
            ET.parse(temp_path)

            if master_path.exists():
                backup_name = f"{master_path.stem}_{filename_stamp()}{master_path.suffix}"
                backup_path = backup_dir / backup_name
                shutil.copy2(master_path, backup_path)
                self.logger.log(f"Master Backup erstellt: {backup_path}")
            else:
                self.logger.log("Keine alte Masterdatei vorhanden, Backup übersprungen")

            os.replace(temp_path, master_path)
            self.logger.log(f"Master geschrieben: {master_path}")
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    def _check_cos(self, cos_path: Path) -> CosCheckResult:
        result = CosCheckResult()

        if not cos_path.exists():
            error = f"ColorGate .cos fehlt: {cos_path}"
            self.logger.log(error, "ERROR")
            result.errors.append(error)
            return result

        try:
            raw = cos_path.read_bytes()
        except Exception as exc:
            error = f"ColorGate .cos konnte nicht gelesen werden: {exc}"
            self.logger.log(error, "ERROR")
            result.errors.append(error)
            return result

        decoded_texts = self._decode_cos_bytes(raw)
        display_text = "\n".join(decoded_texts)
        normalized = "\n".join(self._normalize_for_search(text) for text in decoded_texts)
        expected_master = self._normalize_for_search(self.config["expected_master_path"])
        expected_master_name = self._normalize_for_search(Path(self.config["expected_master_path"]).name)

        for profile in self.config.get("expected_profiles", []):
            profile_norm = self._normalize_for_search(profile)
            if profile_norm in normalized:
                result.profiles.append(profile)
            else:
                error = f"Profil fehlt in .cos: {profile}"
                result.errors.append(error)
                self.logger.log(error, "ERROR")

        master_path_found = expected_master in normalized if expected_master else False
        master_name_found = expected_master_name in normalized if expected_master_name else False
        if master_path_found:
            result.master_hits.append(str(self.config["expected_master_path"]))
        if master_name_found:
            result.master_hits.append(Path(self.config["expected_master_path"]).name)

        result.master_snippets = self._extract_snippets(display_text, "mprint4c-master.cct")
        result.autoreplace_snippets = self._extract_snippets(display_text, "autoreplace")

        if not master_path_found and not master_name_found:
            error = "Masterpfad/Masterdatei nicht in .cos gefunden"
            result.errors.append(error)
            self.logger.log(error, "ERROR")

        if not self._has_autoreplace_true(normalized):
            warning = "AutoReplace nicht eindeutig geprüft"
            result.warnings.append(warning)
            self.logger.log(warning, "WARNING")

        if result.master_hits:
            self.logger.log(f"Master in .cos gefunden: {', '.join(result.master_hits)}")
        if result.autoreplace_snippets:
            self.logger.log("AutoReplace-Hinweise in .cos gefunden")

        return result

    def _decode_cos_bytes(self, raw: bytes) -> list[str]:
        texts: list[str] = []
        for encoding in ("utf-8", "utf-16-le", "latin-1"):
            try:
                text = raw.decode(encoding, errors="ignore")
            except Exception:
                continue
            text = text.replace("\x00", "")
            text = re.sub(r"[ \t]+", " ", text)
            if text.strip() and text not in texts:
                texts.append(text)
        return texts or [raw.decode("latin-1", errors="ignore").replace("\x00", "")]

    def _normalize_for_search(self, text: str) -> str:
        normalized = text.replace("\x00", "").replace("/", "\\").replace("\r\n", "\n").lower()
        normalized = re.sub(r"\\+", r"\\", normalized)
        return normalized

    def _has_autoreplace_true(self, text: str) -> bool:
        return bool(
            re.search(r"autoreplace.{0,160}(true|1|yes)", text, re.IGNORECASE | re.DOTALL)
        )

    def _extract_snippets(self, text: str, needle: str, limit: int = 8) -> list[str]:
        snippets: list[str] = []
        pattern = re.compile(re.escape(needle), re.IGNORECASE)
        for match in pattern.finditer(text):
            start = max(0, match.start() - 100)
            end = min(len(text), match.end() + 140)
            snippet = re.sub(r"\s+", " ", text[start:end]).strip()
            if snippet and snippet not in snippets:
                snippets.append(snippet)
            if len(snippets) >= limit:
                break
        return snippets


class SafeCleaner:
    def __init__(self, config: dict, logger: HelperLogger):
        self.config = config
        self.logger = logger

    def output_status(self) -> tuple[str, str]:
        directory = as_path(self.config["output_printdata_dir"])
        if not directory.exists():
            return "red", "fehlt"
        files = self._files_only(directory)
        if not files:
            return "green", "leer"
        delay = int(self.config.get("output_clean_delay_seconds", 120))
        newest_age = min(time.time() - self._safe_stat_mtime(path) for path in files)
        if newest_age < delay:
            remaining = max(0, int(delay - newest_age))
            return "yellow", f"wartet {remaining}s"
        return "yellow", "enthält Daten"

    def jobdir_status(self) -> tuple[str, str]:
        directory = as_path(self.config["colorgate_jobdir"])
        if not directory.exists():
            return "red", "fehlt"
        files = self._files_only(directory)
        if files:
            return "yellow", f"{len(files)} Datei(en)"
        return "green", "aufgeräumt"

    def clean_output(
        self,
        manual: bool = False,
        cancel_event: threading.Event | None = None,
    ) -> tuple[int, list[str]]:
        directory = as_path(self.config["output_printdata_dir"])
        delay = int(self.config.get("output_clean_delay_seconds", 120))
        return self._clean_directory(
            directory,
            delay,
            preferred_output=True,
            label="OUTPUT_PRINTDATA",
            cancel_event=cancel_event,
        )

    def clean_jobdir(self, cancel_event: threading.Event | None = None) -> tuple[int, list[str]]:
        directory = as_path(self.config["colorgate_jobdir"])
        delay = int(self.config.get("output_clean_delay_seconds", 120))
        return self._clean_directory(
            directory,
            delay,
            preferred_output=False,
            label="JobDir",
            cancel_event=cancel_event,
        )

    def contains_files(self, directory_value: str) -> bool:
        directory = as_path(directory_value)
        return directory.exists() and bool(self._files_only(directory))

    def _clean_directory(
        self,
        directory: Path,
        delay_seconds: int,
        preferred_output: bool,
        label: str,
        cancel_event: threading.Event | None = None,
    ) -> tuple[int, list[str]]:
        if not directory.exists():
            message = f"{label} fehlt: {directory}"
            self.logger.log(message, "ERROR")
            return 0, [message]

        files = self._files_only(directory)
        if preferred_output:
            preferred = [path for path in files if path.suffix.lower() in PREFERRED_OUTPUT_SUFFIXES]
            targets = preferred if preferred else files
        else:
            targets = files

        deleted = 0
        skipped: list[str] = []
        now = time.time()

        for path in targets:
            if cancel_event and cancel_event.is_set():
                skipped.append("Aufräumen abgebrochen")
                self.logger.log(f"{label}: Aufräumen abgebrochen", "WARNING")
                break
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            except Exception as exc:
                skipped.append(f"{path.name}: Status nicht lesbar ({exc})")
                continue

            age = now - stat.st_mtime
            if age < delay_seconds:
                skipped.append(f"{path.name}: noch nicht alt genug ({int(age)}s)")
                continue

            if cancel_event and cancel_event.is_set():
                skipped.append("Aufräumen abgebrochen")
                self.logger.log(f"{label}: Aufräumen abgebrochen", "WARNING")
                break
            if not self._is_size_stable(path, cancel_event=cancel_event):
                skipped.append(f"{path.name}: wird wahrscheinlich noch geschrieben")
                continue

            try:
                path.unlink()
                deleted += 1
                self.logger.log(f"{label} gelöscht: {path}")
            except Exception as exc:
                skipped.append(f"{path.name}: konnte nicht gelöscht werden ({exc})")
                self.logger.log(f"{label} konnte nicht gelöscht werden: {path} ({exc})", "ERROR")

        if deleted == 0 and not skipped:
            self.logger.log(f"{label}: nichts zu löschen")
        return deleted, skipped

    def _is_size_stable(
        self,
        path: Path,
        cancel_event: threading.Event | None = None,
    ) -> bool:
        try:
            size_before = path.stat().st_size
            for _ in range(20):
                if cancel_event and cancel_event.is_set():
                    return False
                time.sleep(0.1)
            size_after = path.stat().st_size
            return size_before == size_after
        except FileNotFoundError:
            return False
        except Exception:
            return False

    def _files_only(self, directory: Path) -> list[Path]:
        try:
            return [path for path in directory.iterdir() if path.is_file()]
        except Exception:
            return []

    def _safe_stat_mtime(self, path: Path) -> float:
        try:
            return path.stat().st_mtime
        except Exception:
            return time.time()


class SafeCalculator:
    OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def evaluate(self, expression: str) -> float:
        expression = expression.strip().replace(",", ".")
        if not expression:
            raise ValueError("Leerer Ausdruck")
        if len(expression) > 120:
            raise ValueError("Ausdruck zu lang")
        tree = ast.parse(expression, mode="eval")
        return self._eval_node(tree.body)

    def _eval_node(self, node: ast.AST) -> float:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in self.OPS:
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            if isinstance(node.op, ast.Div) and right == 0:
                raise ValueError("Division durch 0")
            return float(self.OPS[type(node.op)](left, right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in self.OPS:
            return float(self.OPS[type(node.op)](self._eval_node(node.operand)))
        raise ValueError("Nur Zahlen, + - * / und Klammern sind erlaubt")

    def pt_to_mm(self, value: float) -> float:
        return value * 25.4 / 72.0

    def mm_to_pt(self, value: float) -> float:
        return value * 72.0 / 25.4


class ColorRequestServer:
    def __init__(self, config: dict, logger: HelperLogger, color_manager: ColorTableManager):
        self.config = config
        self.logger = logger
        self.color_manager = color_manager
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.config.get("color_request_server_enabled", True):
            return

        host = str(self.config.get("color_request_server_host", "0.0.0.0"))
        port = int(self.config.get("color_request_server_port", 8765))
        color_manager = self.color_manager
        logger = self.logger

        class Handler(BaseHTTPRequestHandler):
            def do_OPTIONS(self) -> None:
                self.send_response(204)
                self._send_common_headers(0)
                self.end_headers()

            def do_POST(self) -> None:
                path = self.path.split("?", 1)[0]
                if path not in {"/farbe", "/farbe-loeschen"}:
                    self.send_error(404)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    body = self.rfile.read(min(length, 8192)).decode("utf-8", errors="replace")
                    values = parse_qs(body)
                    color_name = values.get("farbe", [""])[0]
                    if path == "/farbe-loeschen":
                        if not color_name.strip():
                            self._send_text("Keine Farbbezeichnung übergeben.", status=400)
                            return
                        message = color_manager.delete_overview_color(color_name)
                        if message.startswith("Eintrag nicht gefunden"):
                            self._send_text(message, status=404)
                            return
                    else:
                        if not color_name.strip():
                            self._send_text("Bitte eine Farbbezeichnung eintragen.", status=400)
                            return
                        if len(re.sub(r"\s+", " ", color_name).strip()) > 160:
                            self._send_text("Die Farbbezeichnung ist zu lang.", status=400)
                            return
                        message = color_manager.add_requested_color(color_name)
                        if message.startswith("Kundenfarbe ist bereits"):
                            self._send_text(message, status=409)
                            return
                    self._send_text(message)
                except Exception as exc:
                    logger.log(f"Kundenfarbe konnte nicht übernommen werden: {exc}", "ERROR")
                    self._send_text(f"Fehler: {exc}", status=500)

            def do_GET(self) -> None:
                if self.path.split("?", 1)[0] == "/status":
                    self._send_text(f"{APP_NAME} bereit")
                    return
                self.send_error(404)

            def log_message(self, _format: str, *_args: object) -> None:
                return

            def _send_text(self, text: str, status: int = 200) -> None:
                data = text.encode("utf-8")
                self.send_response(status)
                self._send_common_headers(len(data))
                self.end_headers()
                self.wfile.write(data)

            def _send_common_headers(self, length: int) -> None:
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS, GET")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")
                self.send_header("Content-Length", str(length))

        try:
            self.server = ThreadingHTTPServer((host, port), Handler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            self.logger.log(f"Kundenfarben-Empfang aktiv: {host}:{port}")
        except Exception as exc:
            self.server = None
            self.logger.log(f"Kundenfarben-Empfang konnte nicht gestartet werden: {exc}", "ERROR")

    def stop(self) -> None:
        if not self.server:
            return
        try:
            self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass
        self.server = None


class PdfReductionError(RuntimeError):
    pass


@dataclass
class PdfSpotColor:
    name: str
    cmyk: tuple[float, float, float, float]


class PdfReducer:
    def __init__(
        self,
        config: dict,
        logger: HelperLogger,
        status_callback: callable | None = None,
        cancel_event: threading.Event | None = None,
        variants_pt: list[float] | None = None,
        missing_codes_callback: callable | None = None,
        confirm_without_codes_callback: callable | None = None,
    ):
        self.config = config
        self.logger = logger
        self.status_callback = status_callback
        self.cancel_event = cancel_event or threading.Event()
        self.missing_codes_callback = missing_codes_callback
        self.confirm_without_codes_callback = confirm_without_codes_callback
        self.allow_without_codes = False
        self.dpi = int(config.get("pdf_reduce_dpi", 3600))
        self.detect_dpi = int(config.get("pdf_reduce_detect_dpi", 300))
        configured_variants = variants_pt if variants_pt is not None else config.get("pdf_reduce_variants_pt", [0.05, 0.07, 0.1, 0.15])
        self.variants = [float(value) for value in configured_variants]
        self.margin_mm = float(config.get("pdf_reduce_code_protect_margin_mm", 3.0))

    def reduce_pdf(self, pdf_path: Path) -> list[Path]:
        try:
            import fitz
            from PIL import Image, ImageChops, ImageFilter
        except Exception as exc:
            raise PdfReductionError(
                "PDF-Reduktion braucht PyMuPDF und Pillow. Bitte mit PyInstaller einpacken "
                "oder auf dem Rechner installieren: python -m pip install PyMuPDF Pillow"
            ) from exc

        if not pdf_path.exists():
            raise PdfReductionError(f"PDF fehlt: {pdf_path}")
        if not self.variants:
            raise PdfReductionError("Keine PDF-Reduktionsvarianten in der Config gefunden")

        output_dir = pdf_path.with_name(f"{pdf_path.stem}_reduziert")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_paths = [
            output_dir / f"{pdf_path.stem}_reduce_{self._variant_label(width_pt)}pt.pdf"
            for width_pt in self.variants
        ]

        source_doc = fitz.open(pdf_path)
        spot_color = self._find_source_spot_color(source_doc)
        if not spot_color:
            source_doc.close()
            raise PdfReductionError(
                "Keine Volltonfarbe in der Quell-PDF gefunden. "
                "PDF-Reduktion wurde gestoppt, damit keine RGB-Ausgabe entsteht."
            )

        output_docs = [fitz.open() for _ in self.variants]
        try:
            if source_doc.page_count == 0:
                raise PdfReductionError("PDF hat keine Seiten")

            self._status(f"PDF-Reduktion gestartet: {pdf_path.name}")
            self.logger.log(f"PDF-Reduktion gestartet: {pdf_path}")
            self.logger.log(f"PDF-Reduktion nutzt Volltonfarbe: {spot_color.name}")

            for page_index in range(source_doc.page_count):
                self._check_cancel()
                page = source_doc[page_index]
                self._status(f"PDF Seite {page_index + 1}/{source_doc.page_count}: Codes suchen...")

                detect_image = self._render_page(page, self.detect_dpi, fitz, Image)
                code_boxes_detect = self._detect_code_boxes_for_page(page, detect_image)
                if not code_boxes_detect and self.config.get("pdf_reduce_abort_if_no_codes_found", True):
                    if self.allow_without_codes:
                        self.allow_without_codes = True
                        self.logger.log(
                            f"PDF Seite {page_index + 1}: keine Codes erkannt, Bediener hat trotzdem reduziert",
                            "WARNING",
                        )
                    else:
                        manual_boxes = self._resolve_missing_codes(page_index + 1, detect_image)
                        if manual_boxes is None:
                            raise PdfReductionError(
                                f"Seite {page_index + 1}: Kein QR/EAN-Code sicher erkannt. "
                                "PDF wurde nicht verändert."
                            )
                        if manual_boxes:
                            code_boxes_detect = manual_boxes
                            self.logger.log(
                                f"PDF Seite {page_index + 1}: {len(manual_boxes)} manuelle Code-Schutzbereich(e) übernommen",
                                "WARNING",
                            )
                        else:
                            self.allow_without_codes = True
                            self.logger.log(
                                f"PDF Seite {page_index + 1}: keine Codes erkannt, Bediener hat trotzdem reduziert",
                                "WARNING",
                            )

                self.logger.log(
                    f"PDF Seite {page_index + 1}: {len(code_boxes_detect)} Code-Schutzbereich(e) erkannt"
                )
                self._status(f"PDF Seite {page_index + 1}: {self.dpi}-dpi-Raster wird erzeugt...")
                high_image = self._render_page(page, self.dpi, fitz, Image)
                code_boxes_high = self._scale_boxes(
                    code_boxes_detect,
                    detect_image.size,
                    high_image.size,
                    self._margin_px(),
                )

                for variant_index, width_pt in enumerate(self.variants):
                    self._check_cancel()
                    self._status(
                        f"PDF Seite {page_index + 1}: Variante {self._format_pt(width_pt)} pt..."
                    )
                    reduced = self._apply_white_reduction(
                        high_image,
                        width_pt,
                        code_boxes_high,
                        Image,
                        ImageChops,
                        ImageFilter,
                    )
                    spot_layer = self._blank_protected_boxes(reduced, code_boxes_high, Image)
                    tint_image = self._rgb_to_spot_tint_image(spot_layer, Image, ImageChops)
                    output_page = output_docs[variant_index].new_page(
                        width=page.rect.width,
                        height=page.rect.height,
                    )
                    self._insert_spot_tint_image(
                        output_docs[variant_index],
                        output_page,
                        page.rect,
                        tint_image,
                        spot_color,
                    )
                    self._insert_protected_code_crops(
                        output_page,
                        page.rect,
                        high_image,
                        code_boxes_high,
                    )
                    spot_layer.close()
                    tint_image.close()
                    reduced.close()

                high_image.close()
                detect_image.close()

            saved_paths: list[Path] = []
            for output_doc, output_path in zip(output_docs, output_paths):
                self._check_cancel()
                output_doc.save(output_path, garbage=4, deflate=True)
                saved_paths.append(output_path)
                self.logger.log(f"PDF-Reduktion geschrieben: {output_path}")

            self._status("PDF-Reduktion fertig")
            return saved_paths
        finally:
            source_doc.close()
            for output_doc in output_docs:
                output_doc.close()

    def _render_page(self, page: object, dpi: int, fitz: object, Image: object) -> object:
        scale = dpi / 72.0
        matrix = fitz.Matrix(scale, scale)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False, colorspace=fitz.csRGB)
        return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)

    def _find_source_spot_color(self, doc: object) -> PdfSpotColor | None:
        spots: list[PdfSpotColor] = []
        for xref in range(1, doc.xref_length()):
            try:
                text = doc.xref_object(xref, compressed=False)
            except Exception:
                continue
            if "/Separation" not in text:
                continue
            spot = self._parse_separation_color(text)
            if spot and spot.name.lower() not in {"all", "none", "registration"}:
                spots.append(spot)

        if len(spots) > 1:
            names = ", ".join(spot.name for spot in spots)
            self.logger.log(
                f"Mehrere Volltonfarben gefunden, nutze erste: {spots[0].name} ({names})",
                "WARNING",
            )
        return spots[0] if spots else None

    def _parse_separation_color(self, text: str) -> PdfSpotColor | None:
        match = re.search(r"/Separation\s*/([^\s<>\[\]\(\)/]+)\s*/DeviceCMYK", text)
        if not match:
            return None
        name = self._decode_pdf_name(match.group(1))
        c1_match = re.search(r"/C1\s*\[\s*([^\]]+)\]", text)
        if not c1_match:
            return PdfSpotColor(name=name, cmyk=(0.0, 0.0, 0.0, 1.0))
        values = self._parse_pdf_number_list(c1_match.group(1))
        if len(values) < 4:
            return PdfSpotColor(name=name, cmyk=(0.0, 0.0, 0.0, 1.0))
        cmyk = tuple(max(0.0, min(1.0, float(value))) for value in values[:4])
        return PdfSpotColor(name=name, cmyk=cmyk)

    def _parse_pdf_number_list(self, text: str) -> list[float]:
        values: list[float] = []
        for match in re.finditer(r"[-+]?(?:\d+\.\d+|\d+|\.\d+)", text):
            try:
                values.append(float(match.group(0)))
            except ValueError:
                continue
        return values

    def _decode_pdf_name(self, value: str) -> str:
        def replace(match: re.Match[str]) -> str:
            try:
                return bytes.fromhex(match.group(1)).decode("latin-1")
            except Exception:
                return match.group(0)

        return re.sub(r"#([0-9A-Fa-f]{2})", replace, value)

    def _encode_pdf_name(self, value: str) -> str:
        safe = []
        for char in value:
            code = ord(char)
            if (
                33 <= code <= 126
                and char not in "#%()/<>[]{}"
                and not char.isspace()
            ):
                safe.append(char)
            elif code <= 255:
                safe.append(f"#{code:02X}")
            else:
                for byte in char.encode("utf-8"):
                    safe.append(f"#{byte:02X}")
        return "".join(safe) or "MPRINT#20Spot"

    def _spot_color_space_object(self, spot_color: PdfSpotColor) -> str:
        name = self._encode_pdf_name(spot_color.name)
        c, m, y, k = (self._pdf_number(value) for value in spot_color.cmyk)
        return (
            f"[ /Separation /{name} /DeviceCMYK "
            f"<< /FunctionType 2 /Domain [ 0 1 ] /C0 [ 0 0 0 0 ] "
            f"/C1 [ {c} {m} {y} {k} ] /N 1 "
            f"/Range [ 0 1 0 1 0 1 0 1 ] >> ]"
        )

    def _pdf_number(self, value: float) -> str:
        text = f"{float(value):.6f}".rstrip("0").rstrip(".")
        if text == "-0":
            return "0"
        if text.startswith("0."):
            return text[1:]
        if text.startswith("-0."):
            return "-" + text[2:]
        return text or "0"

    def _detect_code_boxes_for_page(self, page: object, image: object) -> list[tuple[int, int, int, int]]:
        boxes: list[tuple[int, int, int, int]] = []
        if self.config.get("pdf_reduce_vector_detection", True):
            boxes.extend(self._detect_vector_code_boxes(page, image.size))
        boxes.extend(self._detect_code_boxes(image))
        return self._merge_boxes(boxes, padding=max(2, int(round(self.detect_dpi / 72.0))))

    def _detect_vector_code_boxes(self, page: object, image_size: tuple[int, int]) -> list[tuple[int, int, int, int]]:
        try:
            drawings = page.get_drawings()
        except Exception:
            return []

        module_rects: list[object] = []
        direct_code_rects: list[object] = []
        module_max_pt = float(self.config.get("pdf_reduce_vector_module_max_pt", 4.0))
        barcode_min_items = int(self.config.get("pdf_reduce_vector_barcode_min_items", 40))

        for drawing in drawings:
            rect = drawing.get("rect")
            if rect is None or drawing.get("fill") is None:
                continue
            width = max(0.0, rect.x1 - rect.x0)
            height = max(0.0, rect.y1 - rect.y0)
            if width <= 0 or height <= 0:
                continue

            item_count = len(drawing.get("items", []))
            ratio = max(width / height, height / width)

            if (
                item_count >= barcode_min_items
                and width >= 10
                and height >= 3
                and 2.0 <= ratio <= float(self.config.get("pdf_reduce_max_code_ratio", 12.0))
            ):
                direct_code_rects.append(rect)
                continue

            if (
                item_count <= 4
                and 0.2 <= min(width, height)
                and max(width, height) <= module_max_pt * 3
                and min(width, height) <= module_max_pt
            ):
                module_rects.append(rect)

        clustered_rects = self._cluster_vector_modules(module_rects)
        page_boxes = direct_code_rects + clustered_rects
        pixel_boxes = [self._page_rect_to_image_box(page, rect, image_size) for rect in page_boxes]
        return self._merge_boxes([box for box in pixel_boxes if box], padding=max(2, int(round(self.detect_dpi / 72.0))))

    def _cluster_vector_modules(self, rects: list[object]) -> list[object]:
        if not rects:
            return []
        gap = float(self.config.get("pdf_reduce_vector_module_cluster_gap_pt", 2.0))
        min_count = int(self.config.get("pdf_reduce_vector_module_min_count", 20))
        remaining = list(rects)
        clusters: list[tuple[object, int]] = []

        while remaining:
            cluster_rect = remaining.pop()
            count = 1
            changed = True
            while changed:
                changed = False
                next_remaining = []
                for rect in remaining:
                    if self._rects_near(cluster_rect, rect, gap):
                        cluster_rect = cluster_rect | rect
                        count += 1
                        changed = True
                    else:
                        next_remaining.append(rect)
                remaining = next_remaining
            clusters.append((cluster_rect, count))

        result = []
        for rect, count in clusters:
            if count < min_count:
                continue
            width = max(0.0, rect.x1 - rect.x0)
            height = max(0.0, rect.y1 - rect.y0)
            width_mm = width / 72.0 * 25.4
            height_mm = height / 72.0 * 25.4
            if min(width_mm, height_mm) < float(self.config.get("pdf_reduce_min_code_size_mm", 5.0)):
                continue
            if max(width_mm, height_mm) > float(self.config.get("pdf_reduce_max_code_size_mm", 120.0)):
                continue
            if max(width / max(1e-6, height), height / max(1e-6, width)) > float(self.config.get("pdf_reduce_max_code_ratio", 12.0)):
                continue
            result.append(rect)
        return result

    def _rects_near(self, first: object, second: object, gap: float) -> bool:
        return not (
            first.x1 + gap < second.x0
            or second.x1 + gap < first.x0
            or first.y1 + gap < second.y0
            or second.y1 + gap < first.y0
        )

    def _page_rect_to_image_box(
        self,
        page: object,
        rect: object,
        image_size: tuple[int, int],
    ) -> tuple[int, int, int, int] | None:
        page_rect = page.rect
        scale_x = image_size[0] / max(1e-6, page_rect.width)
        scale_y = image_size[1] / max(1e-6, page_rect.height)
        x0 = int(round((rect.x0 - page_rect.x0) * scale_x))
        y0 = int(round((rect.y0 - page_rect.y0) * scale_y))
        x1 = int(round((rect.x1 - page_rect.x0) * scale_x))
        y1 = int(round((rect.y1 - page_rect.y0) * scale_y))
        if x1 <= x0 or y1 <= y0:
            return None
        return (
            max(0, min(image_size[0], x0)),
            max(0, min(image_size[1], y0)),
            max(0, min(image_size[0], x1)),
            max(0, min(image_size[1], y1)),
        )

    def _detect_code_boxes(self, image: object) -> list[tuple[int, int, int, int]]:
        from PIL import ImageChops, ImageFilter

        rgb = image.convert("RGB")
        edge = None
        for channel in rgb.split():
            channel_edge = channel.filter(ImageFilter.FIND_EDGES)
            edge = channel_edge if edge is None else ImageChops.lighter(edge, channel_edge)
        edge = edge.filter(ImageFilter.MaxFilter(3))

        edge_threshold = int(self.config.get("pdf_reduce_edge_threshold", 24))
        mask = edge.point(lambda value: 255 if value >= edge_threshold else 0, "L")
        tile_size = max(4, int(self.config.get("pdf_reduce_tile_size", 8)))
        tile_density = float(self.config.get("pdf_reduce_tile_density", 0.08))
        width, height = mask.size
        cols = (width + tile_size - 1) // tile_size
        rows = (height + tile_size - 1) // tile_size

        grid: list[list[bool]] = []
        for row in range(rows):
            row_values: list[bool] = []
            y0 = row * tile_size
            y1 = min(height, y0 + tile_size)
            for col in range(cols):
                x0 = col * tile_size
                x1 = min(width, x0 + tile_size)
                tile = mask.crop((x0, y0, x1, y1))
                histogram = tile.histogram()
                active_pixels = sum(histogram[1:])
                row_values.append(active_pixels >= ((x1 - x0) * (y1 - y0) * tile_density))
            grid.append(row_values)

        grid = self._dilate_grid(grid, rows, cols)
        components = self._grid_components(grid, rows, cols)
        boxes: list[tuple[int, int, int, int]] = []
        for min_col, min_row, max_col, max_row, count in components:
            x0 = max(0, min_col * tile_size)
            y0 = max(0, min_row * tile_size)
            x1 = min(width, (max_col + 1) * tile_size)
            y1 = min(height, (max_row + 1) * tile_size)
            if self._looks_like_code_box((x0, y0, x1, y1), count, tile_size, image.size):
                boxes.append((x0, y0, x1, y1))
        return self._merge_boxes(boxes, padding=tile_size * 2)

    def _dilate_grid(self, grid: list[list[bool]], rows: int, cols: int) -> list[list[bool]]:
        dilated = [[False for _ in range(cols)] for _ in range(rows)]
        for row in range(rows):
            for col in range(cols):
                if not grid[row][col]:
                    continue
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        nr = row + dy
                        nc = col + dx
                        if 0 <= nr < rows and 0 <= nc < cols:
                            dilated[nr][nc] = True
        return dilated

    def _grid_components(
        self,
        grid: list[list[bool]],
        rows: int,
        cols: int,
    ) -> list[tuple[int, int, int, int, int]]:
        visited = [[False for _ in range(cols)] for _ in range(rows)]
        components: list[tuple[int, int, int, int, int]] = []
        for row in range(rows):
            for col in range(cols):
                if visited[row][col] or not grid[row][col]:
                    continue
                stack = [(row, col)]
                visited[row][col] = True
                min_row = max_row = row
                min_col = max_col = col
                count = 0
                while stack:
                    current_row, current_col = stack.pop()
                    count += 1
                    min_row = min(min_row, current_row)
                    max_row = max(max_row, current_row)
                    min_col = min(min_col, current_col)
                    max_col = max(max_col, current_col)
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nr = current_row + dy
                        nc = current_col + dx
                        if 0 <= nr < rows and 0 <= nc < cols and not visited[nr][nc] and grid[nr][nc]:
                            visited[nr][nc] = True
                            stack.append((nr, nc))
                components.append((min_col, min_row, max_col, max_row, count))
        return components

    def _looks_like_code_box(
        self,
        box: tuple[int, int, int, int],
        component_tiles: int,
        tile_size: int,
        image_size: tuple[int, int],
    ) -> bool:
        x0, y0, x1, y1 = box
        width = max(1, x1 - x0)
        height = max(1, y1 - y0)
        width_mm = width / self.detect_dpi * 25.4
        height_mm = height / self.detect_dpi * 25.4
        min_size = float(self.config.get("pdf_reduce_min_code_size_mm", 5.0))
        max_size = float(self.config.get("pdf_reduce_max_code_size_mm", 120.0))
        if min(width_mm, height_mm) < min_size:
            return False
        if max(width_mm, height_mm) > max_size:
            return False

        ratio = max(width / height, height / width)
        if ratio > float(self.config.get("pdf_reduce_max_code_ratio", 12.0)):
            return False

        page_area = max(1, image_size[0] * image_size[1])
        if (width * height) / page_area > 0.35:
            return False

        box_tiles = max(1, ((width + tile_size - 1) // tile_size) * ((height + tile_size - 1) // tile_size))
        density = component_tiles / box_tiles
        return density >= float(self.config.get("pdf_reduce_component_density", 0.08))

    def _merge_boxes(
        self,
        boxes: list[tuple[int, int, int, int]],
        padding: int,
    ) -> list[tuple[int, int, int, int]]:
        merged: list[tuple[int, int, int, int]] = []
        for box in boxes:
            expanded = (box[0] - padding, box[1] - padding, box[2] + padding, box[3] + padding)
            for index, existing in enumerate(merged):
                if self._boxes_overlap(expanded, existing):
                    merged[index] = (
                        min(existing[0], expanded[0]),
                        min(existing[1], expanded[1]),
                        max(existing[2], expanded[2]),
                        max(existing[3], expanded[3]),
                    )
                    break
            else:
                merged.append(expanded)
        return [(max(0, x0), max(0, y0), max(0, x1), max(0, y1)) for x0, y0, x1, y1 in merged]

    def _boxes_overlap(
        self,
        first: tuple[int, int, int, int],
        second: tuple[int, int, int, int],
    ) -> bool:
        return not (
            first[2] < second[0]
            or second[2] < first[0]
            or first[3] < second[1]
            or second[3] < first[1]
        )

    def _scale_boxes(
        self,
        boxes: list[tuple[int, int, int, int]],
        detect_size: tuple[int, int],
        target_size: tuple[int, int],
        margin_px: int,
    ) -> list[tuple[int, int, int, int]]:
        scale_x = target_size[0] / max(1, detect_size[0])
        scale_y = target_size[1] / max(1, detect_size[1])
        scaled: list[tuple[int, int, int, int]] = []
        for x0, y0, x1, y1 in boxes:
            scaled.append(
                (
                    max(0, int(x0 * scale_x) - margin_px),
                    max(0, int(y0 * scale_y) - margin_px),
                    min(target_size[0], int(x1 * scale_x) + margin_px),
                    min(target_size[1], int(y1 * scale_y) + margin_px),
                )
            )
        return scaled

    def _apply_white_reduction(
        self,
        image: object,
        width_pt: float,
        protect_boxes: list[tuple[int, int, int, int]],
        Image: object,
        ImageChops: object,
        ImageFilter: object,
    ) -> object:
        rgb = image.convert("RGB")
        white = Image.new("RGB", rgb.size, (255, 255, 255))
        diff = ImageChops.difference(rgb, white).convert("L")
        foreground_threshold = int(self.config.get("pdf_reduce_foreground_threshold", 8))
        foreground = diff.point(lambda value: 255 if value > foreground_threshold else 0, "L")
        radius = max(1, int(round(width_pt * self.dpi / 72.0)))
        kernel = radius * 2 + 1
        eroded = foreground.filter(ImageFilter.MinFilter(kernel))
        removed = ImageChops.subtract(foreground, eroded)
        reduced = rgb.copy()
        reduced.paste((255, 255, 255), mask=removed)
        for box in protect_boxes:
            reduced.paste(rgb.crop(box), box)
        return reduced

    def _blank_protected_boxes(
        self,
        image: object,
        protect_boxes: list[tuple[int, int, int, int]],
        Image: object,
    ) -> object:
        spot_layer = image.copy()
        white = Image.new("RGB", spot_layer.size, (255, 255, 255))
        for box in protect_boxes:
            spot_layer.paste(white.crop(box), box)
        return spot_layer

    def _rgb_to_spot_tint_image(self, image: object, Image: object, ImageChops: object) -> object:
        rgb = image.convert("RGB")
        white = Image.new("RGB", rgb.size, (255, 255, 255))
        diff_channels = ImageChops.difference(rgb, white).split()
        tint = ImageChops.lighter(ImageChops.lighter(diff_channels[0], diff_channels[1]), diff_channels[2])
        max_tint = tint.getextrema()[1]
        if max_tint <= 0:
            return tint
        return tint.point(lambda value: min(255, int(round(value * 255 / max_tint))), "L")

    def _insert_spot_tint_image(
        self,
        output_doc: object,
        output_page: object,
        page_rect: object,
        tint_image: object,
        spot_color: PdfSpotColor,
    ) -> None:
        stream = self._image_to_png_stream(tint_image)
        image_xref = output_page.insert_image(page_rect, stream=stream)
        color_space_xref = output_doc.get_new_xref()
        output_doc.update_object(color_space_xref, self._spot_color_space_object(spot_color))
        output_doc.xref_set_key(image_xref, "ColorSpace", f"{color_space_xref} 0 R")
        output_doc.xref_set_key(image_xref, "Interpolate", "false")

    def _insert_protected_code_crops(
        self,
        output_page: object,
        page_rect: object,
        high_image: object,
        protect_boxes: list[tuple[int, int, int, int]],
    ) -> None:
        if not protect_boxes:
            return
        for box in protect_boxes:
            x0, y0, x1, y1 = box
            if x1 <= x0 or y1 <= y0:
                continue
            crop = high_image.crop(box)
            crop_stream = self._image_to_png_stream(crop)
            crop.close()
            output_page.insert_image(
                self._image_box_to_page_rect(box, high_image.size, page_rect),
                stream=crop_stream,
            )

    def _image_box_to_page_rect(
        self,
        box: tuple[int, int, int, int],
        image_size: tuple[int, int],
        page_rect: object,
    ) -> object:
        import fitz

        image_width, image_height = image_size
        scale_x = page_rect.width / max(1, image_width)
        scale_y = page_rect.height / max(1, image_height)
        x0, y0, x1, y1 = box
        return fitz.Rect(
            page_rect.x0 + x0 * scale_x,
            page_rect.y0 + y0 * scale_y,
            page_rect.x0 + x1 * scale_x,
            page_rect.y0 + y1 * scale_y,
        )

    def _image_to_png_stream(self, image: object) -> bytes:
        stream = BytesIO()
        image.save(stream, format="PNG", optimize=False)
        return stream.getvalue()

    def _margin_px(self) -> int:
        return max(0, int(round(self.margin_mm / 25.4 * self.dpi)))

    def _variant_label(self, width_pt: float) -> str:
        return self._format_pt(width_pt).replace(",", "")

    def _format_pt(self, width_pt: float) -> str:
        return format_pt_value(width_pt)

    def _status(self, text: str) -> None:
        if self.status_callback:
            self.status_callback(text)

    def _check_cancel(self) -> None:
        if self.cancel_event.is_set():
            raise PdfReductionError("PDF-Reduktion abgebrochen")

    def _resolve_missing_codes(
        self,
        page_number: int,
        detect_image: object,
    ) -> list[tuple[int, int, int, int]] | None:
        if self.missing_codes_callback:
            try:
                result = self.missing_codes_callback(page_number, detect_image.copy())
            except Exception as exc:
                self.logger.log(f"PDF-Reduktion: Code-Markierung fehlgeschlagen: {exc}", "ERROR")
                return None
            return self._normalize_manual_boxes(result)

        if self._confirm_without_codes(page_number):
            return []
        return None

    def _normalize_manual_boxes(self, result: object) -> list[tuple[int, int, int, int]] | None:
        if result is None or result is False:
            return None
        if result is True:
            return []

        boxes: list[tuple[int, int, int, int]] = []
        try:
            for box in result:
                x0, y0, x1, y1 = [int(round(float(value))) for value in box]
                if x1 > x0 and y1 > y0:
                    boxes.append((x0, y0, x1, y1))
        except Exception as exc:
            self.logger.log(f"PDF-Reduktion: manuelle Code-Boxen unlesbar: {exc}", "ERROR")
            return None
        return boxes

    def _confirm_without_codes(self, page_number: int) -> bool:
        if not self.confirm_without_codes_callback:
            return False
        try:
            return bool(self.confirm_without_codes_callback(page_number))
        except Exception as exc:
            self.logger.log(f"PDF-Reduktion: Bestätigung ohne Codes fehlgeschlagen: {exc}", "ERROR")
            return False


class StatusRow:
    COLORS = {
        "green": THEME["green"],
        "yellow": THEME["yellow"],
        "red": THEME["red"],
        "gray": THEME["gray"],
    }

    def __init__(self, parent: tk.Widget, title: str, emphasis: bool = False):
        self.emphasis = emphasis
        self.frame = tk.Frame(
            parent,
            bg=THEME["panel"],
            highlightbackground=THEME["border"],
            highlightthickness=1 if emphasis else 0,
            padx=4 if emphasis else 0,
            pady=4 if emphasis else 0,
        )
        self.frame.pack(fill="x", pady=5 if emphasis else 3)
        dot_size = 20 if emphasis else 14
        self.dot = tk.Canvas(
            self.frame,
            width=dot_size,
            height=dot_size,
            bg=THEME["panel"],
            highlightthickness=0,
        )
        self.dot.pack(side="left", padx=(0, 8))
        self.oval = self.dot.create_oval(
            2,
            2,
            dot_size - 2,
            dot_size - 2,
            fill=self.COLORS["gray"],
            outline="",
        )
        self.title = tk.Label(
            self.frame,
            text=title,
            bg=THEME["panel"],
            fg=THEME["text"],
            anchor="w",
            font=("Segoe UI", 11 if emphasis else 9, "bold" if emphasis else "normal"),
        )
        self.title.pack(side="left", fill="x", expand=True)
        self.value = tk.Label(
            self.frame,
            text="-",
            bg=THEME["panel"],
            fg=THEME["muted"],
            anchor="e",
            font=("Segoe UI", 11 if emphasis else 9, "bold" if emphasis else "normal"),
        )
        self.value.pack(side="right")

    def set(self, color: str, text: str) -> None:
        self.dot.itemconfigure(self.oval, fill=self.COLORS.get(color, self.COLORS["gray"]))
        self.value.configure(text=text)


class SetupDialog(tk.Toplevel):
    FIELD_DEFINITIONS = [
        (
            "work",
            "Wichtige Arbeitsorte",
            "",
            "",
            "section",
        ),
        (
            "nas_root",
            "Hauptordner der Maschine",
            "dir",
            "Der gemeinsame Ordner, in dem die MJET-X ihre Farbdaten und die Übersicht ablegt.",
            "normal",
        ),
        (
            "color_root",
            "Ordner für Maschinenfarben",
            "dir",
            "Hier liegen die Farbdaten der Maschine, inklusive Master-Farbtabelle und einzelne Kundenfarben.",
            "normal",
        ),
        (
            "single_color_dir",
            "Ordner für einzelne Kundenfarben",
            "dir",
            "Dort landen einzelne Spotfarben mit Kundennamen, zum Beispiel Weingut_Beispiel_Blau.",
            "normal",
        ),
        (
            "backup_dir",
            "Backup-Ordner",
            "dir",
            "Vor Änderungen speichert der Helper hier Sicherungskopien, damit nichts endgültig verloren geht.",
            "normal",
        ),
        (
            "master_cct",
            "Master-Farbtabelle",
            "file",
            "Die Sammeldatei für alle Kundenfarben. Der Helper überträgt neue Farbnamen automatisch dorthin.",
            "normal",
        ),
        (
            "output_printdata_dir",
            "Druckdaten-Übergabeordner",
            "dir",
            "Hier legt ColorGate fertige Druckdaten ab, die in LP2000i geöffnet werden. Der Helper räumt alte Dateien automatisch auf.",
            "normal",
        ),
        (
            "color_overview_html",
            "Farbübersicht für die Vorstufe",
            "save_file",
            "Eine gut lesbare HTML-Datei mit Kundenfarbnamen, Status, Datum und CMYK-Werten.",
            "normal",
        ),
        (
            "colorgate",
            "ColorGate - meistens automatisch erkannt",
            "",
            "Diese Felder nur ändern, wenn die automatische Erkennung falsch ist.",
            "section",
        ),
        (
            "colorgate_root",
            "ColorGate-Programmordner",
            "dir",
            "Der Installationsordner von ColorGate auf dem Maschinenrechner.",
            "advanced",
        ),
        (
            "colorgate_ini",
            "ColorGate-Einstellungsdatei",
            "file",
            "Interne Einstellungsdatei von ColorGate. Normalerweise muss hier nichts geändert werden.",
            "advanced",
        ),
        (
            "colorgate_cos",
            "ColorGate-Profil-/Auftragsdatei",
            "file",
            "Datei mit dem MPRINT-Auftrag beziehungsweise Profil. Normalerweise wird sie automatisch gefunden.",
            "advanced",
        ),
        (
            "colorgate_jobdir",
            "ColorGate-Jobordner",
            "dir",
            "ColorGate-Arbeitsordner für Jobs. Der Helper zeigt den Status, leert ihn aber nicht automatisch.",
            "advanced",
        ),
        (
            "updates",
            "Updates",
            "",
            "",
            "section",
        ),
        (
            "update_check_url",
            "Prüfung auf neue Version",
            "file",
            "Quelle, über die der Helper nur prüft, ob eine neue Version bereitliegt. Es wird nichts automatisch installiert.",
            "advanced",
        ),
    ]

    def __init__(self, parent: tk.Tk, config: dict, required: bool = False):
        super().__init__(parent)
        self.result = False
        self.config = config
        self.vars: dict[str, tk.StringVar] = {}
        self.field_labels = {
            key: label
            for key, label, _kind, _help_text, mode in self.FIELD_DEFINITIONS
            if mode != "section"
        }
        self.title(f"{APP_NAME} Setup")
        self.configure(bg=THEME["window"])
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)
        self.geometry("780x620")

        header = tk.Frame(self, bg=THEME["window"], padx=14, pady=12)
        header.pack(fill="x")
        title = "Ersteinrichtung" if required else "Setup / Pfade ändern"
        tk.Label(
            header,
            text=title,
            bg=THEME["window"],
            fg=THEME["text"],
            anchor="w",
            font=("Segoe UI", 15, "bold"),
        ).pack(fill="x")
        tk.Label(
            header,
            text="Beim ersten Start werden nur die Orte festgelegt, an denen die Maschine arbeitet. Wenn ein Vorschlag passt, einfach so lassen.",
            bg=THEME["window"],
            fg=THEME["muted"],
            anchor="w",
            justify="left",
            wraplength=720,
            font=("Segoe UI", 9),
        ).pack(fill="x", pady=(4, 0))

        canvas = tk.Canvas(self, bg=THEME["window"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        form = tk.Frame(canvas, bg=THEME["window"], padx=14, pady=4)
        form.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=form, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        row_index = 0
        for key, label, kind, help_text, mode in self.FIELD_DEFINITIONS:
            if mode == "section":
                tk.Label(
                    form,
                    text=label,
                    bg=THEME["window"],
                    fg=THEME["button_text"],
                    anchor="w",
                    font=("Segoe UI", 10, "bold"),
                ).grid(row=row_index, column=0, columnspan=3, sticky="ew", pady=(12, 3))
                if help_text:
                    row_index += 1
                    tk.Label(
                        form,
                        text=help_text,
                        bg=THEME["window"],
                        fg=THEME["muted"],
                        anchor="w",
                        justify="left",
                        wraplength=720,
                        font=("Segoe UI", 8),
                    ).grid(row=row_index, column=0, columnspan=3, sticky="ew", pady=(0, 4))
                row_index += 1
                continue

            fg = THEME["muted"] if mode == "advanced" else THEME["text"]
            entry_bg = THEME["panel_alt"] if mode == "advanced" else THEME["entry"]
            tk.Label(
                form,
                text=label,
                bg=THEME["window"],
                fg=fg,
                anchor="w",
                font=("Segoe UI", 9, "bold"),
            ).grid(row=row_index, column=0, sticky="w", pady=(5, 1))
            var = tk.StringVar(value=str(config.get(key, "")))
            self.vars[key] = var
            entry = tk.Entry(form, textvariable=var, bg=entry_bg, fg=fg, relief="solid", bd=1)
            entry.grid(row=row_index, column=1, sticky="ew", padx=(8, 6), pady=(5, 1), ipady=3)
            ttk.Button(
                form,
                text="Ändern" if mode == "advanced" else "Wählen",
                command=lambda field_key=key, field_kind=kind: self.choose_path(field_key, field_kind),
            ).grid(row=row_index, column=2, sticky="ew", pady=(5, 1))
            row_index += 1
            tk.Label(
                form,
                text=help_text,
                bg=THEME["window"],
                fg=THEME["muted"],
                anchor="w",
                justify="left",
                wraplength=500,
                font=("Segoe UI", 8),
            ).grid(row=row_index, column=1, sticky="ew", padx=(8, 6), pady=(0, 4))
            row_index += 1
        form.columnconfigure(1, weight=1)

        button_bar = tk.Frame(self, bg=THEME["window"], padx=14, pady=12)
        button_bar.pack(fill="x", side="bottom")
        ttk.Button(button_bar, text="Ordner automatisch suchen", command=self.apply_detected_paths).pack(side="left")
        ttk.Button(button_bar, text="Abbrechen", command=self.cancel).pack(side="right")
        ttk.Button(button_bar, text="Speichern", command=self.save).pack(side="right", padx=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.update_idletasks()
        self.wait_window(self)

    def choose_path(self, key: str, kind: str) -> None:
        current = self.vars[key].get().strip()
        title = f"{self.field_labels.get(key, key)} wählen"
        if kind == "dir":
            selected = filedialog.askdirectory(parent=self, title=title, initialdir=self._initial_dir(current))
        elif kind == "save_file":
            selected = filedialog.asksaveasfilename(
                parent=self,
                title=title,
                initialdir=self._initial_dir(current),
                initialfile=Path(current).name or "MPRINT_Farbuebersicht.html",
                defaultextension=".html",
                filetypes=[("HTML", "*.html"), ("Alle Dateien", "*.*")],
            )
        else:
            selected = filedialog.askopenfilename(
                parent=self,
                title=title,
                initialdir=self._initial_dir(current),
                filetypes=[("Alle Dateien", "*.*")],
            )
        if selected:
            self.vars[key].set(selected)
            self._derive_related_paths(key, selected)

    def apply_detected_paths(self) -> None:
        detected = detect_setup_paths(self.config)
        for key, value in detected.items():
            if value:
                self.vars[key].set(str(value))

    def save(self) -> None:
        for key, var in self.vars.items():
            self.config[key] = var.get().strip()
        self.result = True
        self.destroy()

    def cancel(self) -> None:
        self.result = False
        self.destroy()

    def _initial_dir(self, current: str) -> str:
        if not current:
            return str(APP_DIR)
        path = Path(current)
        if path.is_dir():
            return str(path)
        if path.parent.exists():
            return str(path.parent)
        return str(APP_DIR)

    def _derive_related_paths(self, key: str, value: str) -> None:
        path = Path(value)
        if key == "nas_root":
            self._set_if_empty_or_default("color_root", str(path / "Maschinenfarben"))
            self._set_if_empty_or_default("color_overview_html", str(path / "MPRINT_Farbuebersicht.html"))
        if key == "color_root":
            self._set_if_empty_or_default("single_color_dir", str(path / "Einzelfarben"))
            self._set_if_empty_or_default("backup_dir", str(path / "Backup"))
            self._set_if_empty_or_default("master_cct", str(path / "mprint4c-master.cct"))
        if key == "colorgate_root":
            self._set_if_empty_or_default("colorgate_ini", str(path / "Productionserver25.INI"))
            self._set_if_empty_or_default("colorgate_cos", str(path / "Settings" / "mprint mlabel.cos"))
            self._set_if_empty_or_default("colorgate_jobdir", str(path / "JobDir" / "mprint mlabel"))

    def _set_if_empty_or_default(self, key: str, value: str) -> None:
        current = self.vars[key].get().strip()
        default = str(DEFAULT_CONFIG.get(key, ""))
        if not current or current == default or not Path(current).exists():
            self.vars[key].set(value)


def detect_setup_paths(config: dict) -> dict[str, str]:
    detected: dict[str, str] = {}
    root_candidates = [
        Path(r"Z:\_MPRINT_4c"),
        Path(r"Y:\_MPRINT_4c"),
        Path(r"X:\_MPRINT_4c"),
        Path("/Volumes/NAS_Public/_MPRINT_4c"),
    ]
    for root in root_candidates:
        if root.exists():
            detected["nas_root"] = str(root)
            detected["color_root"] = str(root / "Maschinenfarben")
            detected["single_color_dir"] = str(root / "Maschinenfarben" / "Einzelfarben")
            detected["backup_dir"] = str(root / "Maschinenfarben" / "Backup")
            detected["master_cct"] = str(root / "Maschinenfarben" / "mprint4c-master.cct")
            detected["color_overview_html"] = str(root / "MPRINT_Farbuebersicht.html")
            break

    colorgate_candidates = [
        Path(r"C:\ProgramData\ColorGATE Software\Productionserver25"),
        Path(str(config.get("colorgate_root", ""))),
    ]
    for root in colorgate_candidates:
        if root.exists():
            detected["colorgate_root"] = str(root)
            detected["colorgate_ini"] = str(root / "Productionserver25.INI")
            detected["colorgate_cos"] = str(root / "Settings" / "mprint mlabel.cos")
            detected["colorgate_jobdir"] = str(root / "JobDir" / "mprint mlabel")
            break

    output_candidates = [
        Path(r"C:\Users\user\Desktop\OUTPUT_PRINTDATA"),
        Path.home() / "Desktop" / "OUTPUT_PRINTDATA",
        Path(str(config.get("output_printdata_dir", ""))),
    ]
    for output_path in output_candidates:
        if output_path.exists():
            detected["output_printdata_dir"] = str(output_path)
            break

    return detected


def parse_version(value: str) -> tuple[int, ...]:
    parts = re.findall(r"\d+", str(value))
    return tuple(int(part) for part in parts[:4]) or (0,)


def is_newer_version(candidate: str, current: str) -> bool:
    candidate_parts = parse_version(candidate)
    current_parts = parse_version(current)
    max_len = max(len(candidate_parts), len(current_parts))
    candidate_parts += (0,) * (max_len - len(candidate_parts))
    current_parts += (0,) * (max_len - len(current_parts))
    return candidate_parts > current_parts


def load_update_info(update_source: str) -> dict:
    source = update_source.strip()
    if not source:
        raise ValueError("Keine Prüfung auf neue Version eingerichtet.")
    if re.match(r"^https?://", source, re.IGNORECASE):
        with urlopen(source, timeout=6) as response:
            raw = response.read(512_000).decode("utf-8")
    else:
        raw = Path(source).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Versionsinformation konnte nicht gelesen werden.")
    if not str(data.get("version", "")).strip():
        raise ValueError("Versionsinformation enthält keine Versionsnummer.")
    return data


class MainApp:
    def __init__(self, root: tk.Tk, config: dict, logger: HelperLogger):
        self.root = root
        self.config = config
        self.logger = logger
        self.color_manager = ColorTableManager(config, logger)
        self.color_request_server = ColorRequestServer(config, logger, self.color_manager)
        self.cleaner = SafeCleaner(config, logger)
        self.calculator = SafeCalculator()
        self.expert_visible = False
        self.output_clean_running = False
        self.output_clean_cancel_event = threading.Event()
        self.pdf_reduce_running = False
        self.pdf_reduce_cancel_event = threading.Event()
        self.last_sync_result: SyncResult | None = None
        self.last_auto_clean_at = 0.0

        self.logger.add_callback(self._on_log_line)
        self._configure_root()
        self._build_ui()
        self.color_request_server.start()
        self._schedule_status_refresh()
        self.root.after(400, self.maybe_open_initial_setup)
        self.root.after(700, self.startup_color_check)
        self.root.after(1800, self.check_for_updates_startup)
        self.logger.log("Start Tool")

    def _configure_root(self) -> None:
        self.root.title(APP_NAME)
        self.root.configure(bg=THEME["window"])
        self.root.minsize(240, 620)
        width = int(self.config.get("window_width", 260))
        geometry = self.config.get("window_geometry")
        if geometry:
            self.root.geometry(geometry)
        else:
            self.root.update_idletasks()
            screen_width = self.root.winfo_screenwidth()
            height = min(820, max(700, self.root.winfo_screenheight() - 60))
            x_pos = max(0, screen_width - width - 8)
            self.root.geometry(f"{width}x{height}+{x_pos}+20")
        self.root.attributes("-topmost", bool(self.config.get("always_on_top", True)))
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self.container = tk.Frame(self.root, bg=THEME["window"], padx=10, pady=10)
        self.container.pack(fill="both", expand=True)

        self.normal_frame = tk.Frame(self.container, bg=THEME["window"])
        self.normal_frame.pack(fill="x")

        title_row = tk.Frame(self.normal_frame, bg=THEME["window"])
        title_row.pack(fill="x", pady=(0, 10))
        self.title_label = tk.Label(
            title_row,
            text=APP_NAME,
            bg=THEME["window"],
            fg=THEME["text"],
            anchor="w",
            font=("Segoe UI", 13, "bold"),
        )
        self.title_label.pack(side="left", fill="x", expand=True)
        self._small_button(title_row, "...", self.toggle_expert).pack(side="right")

        status_box = tk.Frame(
            self.normal_frame,
            bg=THEME["panel"],
            padx=8,
            pady=8,
            highlightbackground=THEME["border"],
            highlightthickness=1,
        )
        status_box.pack(fill="x", pady=(0, 10))
        self.status_match = StatusRow(status_box, "Farbabgleich", emphasis=True)
        self.status_output = StatusRow(status_box, "OUTPUT", emphasis=True)
        secondary_status = tk.Frame(status_box, bg=THEME["panel"])
        secondary_status.pack(fill="x", pady=(3, 0))
        self.status_network = StatusRow(secondary_status, "Netzwerk")
        self.status_local = StatusRow(secondary_status, "ColorGate")

        self.main_status_label = tk.Label(
            self.normal_frame,
            text="Bereit",
            bg=THEME["window"],
            fg=THEME["muted"],
            anchor="w",
            wraplength=230,
            justify="left",
            font=("Segoe UI", 9),
        )
        self.main_status_label.pack(fill="x", pady=(0, 10))

        self._button(self.normal_frame, "Farbabgleich starten", self.start_color_sync)
        self._button(self.normal_frame, "Druckdaten-Ordner leeren", self.clean_output_manual)
        self._build_pdf_controls(self.normal_frame)
        self.cancel_output_button = self._button(
            self.normal_frame,
            "Aufräumen stoppen",
            self.cancel_output_cleaning,
            style="secondary",
            pack_now=False,
        )
        self.rechner_button = self._button(self.normal_frame, "Rechner", self.toggle_calculator)

        self.calc_frame = self._build_calculator(self.normal_frame)
        self.calc_frame.pack_forget()

        spacer = tk.Frame(self.normal_frame, height=12, bg=THEME["window"])
        spacer.pack(fill="x")
        self._button(
            self.normal_frame,
            "Feierabend / Herunterfahren",
            self.shutdown_flow,
            style="danger",
        )

        self.expert_frame = self._build_expert_frame(self.container)
        self.expert_frame.pack_forget()

    def _button(
        self,
        parent: tk.Widget,
        text: str,
        command: callable,
        style: str = "normal",
        pack_now: bool = True,
    ) -> tk.Button:
        if style == "danger":
            bg = THEME["danger"]
            active = THEME["danger_active"]
            fg = "#3e1f1f"
        elif style == "secondary":
            bg = THEME["panel_alt"]
            active = THEME["border"]
            fg = THEME["text"]
        else:
            bg = THEME["button"]
            active = THEME["button_active"]
            fg = THEME["button_text"]
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active,
            activeforeground=fg,
            relief="solid",
            bd=1,
            highlightthickness=0,
            padx=8,
            pady=8,
            font=("Segoe UI", 9, "bold"),
            wraplength=max(180, int(self.config.get("window_width", 260)) - 50),
        )
        if pack_now:
            button.pack(fill="x", pady=3)
        return button

    def _build_pdf_controls(self, parent: tk.Widget) -> None:
        frame = tk.Frame(
            parent,
            bg=THEME["panel"],
            padx=8,
            pady=8,
            highlightbackground=THEME["border"],
            highlightthickness=1,
        )
        frame.pack(fill="x", pady=(7, 4))
        tk.Label(
            frame,
            text="PDF verfeinern",
            bg=THEME["panel"],
            fg=THEME["text"],
            anchor="w",
            font=("Segoe UI", 10, "bold"),
        ).pack(fill="x", pady=(0, 5))

        button_grid = tk.Frame(frame, bg=THEME["panel"])
        button_grid.pack(fill="x")
        pdf_variants = [float(value) for value in self.config.get("pdf_reduce_variants_pt", [0.05, 0.07, 0.1, 0.15])]
        for index, width_pt in enumerate(pdf_variants):
            button = tk.Button(
                button_grid,
                text=f"{format_pt_value(width_pt)} pt",
                command=lambda value=width_pt: self.choose_pdf_for_reduction(value),
                bg=THEME["button"],
                fg=THEME["button_text"],
                activebackground=THEME["button_active"],
                activeforeground=THEME["button_text"],
                relief="solid",
                bd=1,
                highlightthickness=0,
                padx=4,
                pady=7,
                font=("Segoe UI", 9, "bold"),
            )
            button.grid(row=index // 2, column=index % 2, sticky="ew", padx=2, pady=2)
        button_grid.columnconfigure(0, weight=1)
        button_grid.columnconfigure(1, weight=1)

        self.cancel_pdf_button = self._button(
            frame,
            "PDF stoppen",
            self.cancel_pdf_reduction,
            style="secondary",
            pack_now=False,
        )

    def _small_button(self, parent: tk.Widget, text: str, command: callable) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=THEME["window"],
            fg=THEME["muted"],
            activebackground=THEME["panel_alt"],
            activeforeground=THEME["text"],
            relief="flat",
            padx=4,
            pady=1,
            font=("Segoe UI", 8),
            width=3,
        )

    def _build_calculator(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(
            parent,
            bg=THEME["panel"],
            padx=8,
            pady=8,
            highlightbackground=THEME["border"],
            highlightthickness=1,
        )
        self.calc_entry = tk.Entry(
            frame,
            bg=THEME["entry"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            relief="solid",
            bd=1,
            font=("Segoe UI", 12),
            justify="right",
        )
        self.calc_entry.pack(fill="x", ipady=5)
        self.calc_result = tk.Label(
            frame,
            text="",
            bg=THEME["panel"],
            fg=THEME["text"],
            anchor="w",
            wraplength=220,
            font=("Segoe UI", 10, "bold"),
        )
        self.calc_result.pack(fill="x", pady=(6, 4))

        keypad = tk.Frame(frame, bg=THEME["panel"])
        keypad.pack(fill="x")
        rows = [
            ("7", "8", "9", "/"),
            ("4", "5", "6", "*"),
            ("1", "2", "3", "-"),
            ("0", ".", "=", "+"),
        ]
        for row_index, row_values in enumerate(rows):
            for col_index, label in enumerate(row_values):
                command = self.calculate_expression if label == "=" else lambda value=label: self._append_calc(value)
                self._calc_button(keypad, label, command).grid(
                    row=row_index,
                    column=col_index,
                    sticky="nsew",
                    padx=2,
                    pady=2,
                )
        for index in range(4):
            keypad.columnconfigure(index, weight=1, uniform="calc")

        utility_row = tk.Frame(frame, bg=THEME["panel"])
        utility_row.pack(fill="x", pady=(4, 0))
        self._calc_button(utility_row, "C", self._clear_calc).pack(side="left", fill="x", expand=True, padx=(0, 2))
        self._calc_button(utility_row, "pt → mm", self.convert_pt_to_mm).pack(side="left", fill="x", expand=True, padx=2)
        self._calc_button(utility_row, "mm → pt", self.convert_mm_to_pt).pack(side="left", fill="x", expand=True, padx=(2, 0))
        self.calc_entry.bind("<Return>", lambda _event: self.calculate_expression())
        return frame

    def _calc_button(self, parent: tk.Widget, text: str, command: callable) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=THEME["panel_alt"],
            fg=THEME["text"],
            activebackground=THEME["button_active"],
            activeforeground=THEME["text"],
            relief="solid",
            bd=1,
            highlightthickness=0,
            padx=5,
            pady=6,
            font=("Segoe UI", 10, "bold"),
        )

    def _append_calc(self, value: str) -> None:
        self.calc_entry.insert("end", value)
        self.calc_entry.focus_set()

    def _clear_calc(self) -> None:
        self.calc_entry.delete(0, "end")
        self.calc_result.configure(text="")
        self.calc_entry.focus_set()

    def _build_expert_frame(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(parent, bg=THEME["window"])
        tk.Label(
            frame,
            text="Expertmodus",
            bg=THEME["window"],
            fg=THEME["text"],
            anchor="w",
            font=("Segoe UI", 11, "bold"),
        ).pack(fill="x", pady=(10, 6))

        self.expert_jobdir_label = tk.Label(
            frame,
            text="JobDir: -",
            bg=THEME["window"],
            fg=THEME["muted"],
            anchor="w",
            font=("Segoe UI", 9),
        )
        self.expert_jobdir_label.pack(fill="x", pady=(0, 4))

        path_grid = tk.Frame(frame, bg=THEME["window"])
        path_grid.pack(fill="x")
        path_buttons = [
            ("Setup", self.open_setup_dialog),
            ("Konfig", lambda: self.open_path(CONFIG_PATH)),
            ("Backup", lambda: self.open_path(self.config["backup_dir"])),
            ("Farben", lambda: self.open_path(self.config["color_root"])),
            ("CG Profil", lambda: self.open_path(Path(self.config["colorgate_cos"]).parent)),
            ("Druckdaten", lambda: self.open_path(self.config["output_printdata_dir"])),
            ("CG Jobs", lambda: self.open_path(self.config["colorgate_jobdir"])),
            ("Info", self.show_about),
            ("Update", self.check_for_updates_manual),
        ]
        for index, (label, command) in enumerate(path_buttons):
            button = tk.Button(
                path_grid,
                text=label,
                command=command,
                bg=THEME["panel_alt"],
                fg=THEME["text"],
                activebackground=THEME["button_active"],
                activeforeground=THEME["text"],
                relief="solid",
                bd=1,
                highlightthickness=0,
                padx=4,
                pady=5,
                font=("Segoe UI", 8),
            )
            button.grid(row=index // 2, column=index % 2, sticky="ew", padx=2, pady=2)
        path_grid.columnconfigure(0, weight=1)
        path_grid.columnconfigure(1, weight=1)

        action_grid = tk.Frame(frame, bg=THEME["window"])
        action_grid.pack(fill="x", pady=(6, 4))
        ttk.Button(action_grid, text="Nur prüfen", command=self.check_color_sync).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(action_grid, text="Master neu bauen", command=self.start_color_sync).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(action_grid, text="JobDir leeren", command=self.clean_jobdir_manual).grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(action_grid, text="Shutdown erzwingen", command=self.force_shutdown).grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        action_grid.columnconfigure(0, weight=1)
        action_grid.columnconfigure(1, weight=1)

        self.paths_text = tk.Text(
            frame,
            height=7,
            bg=THEME["entry"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            relief="flat",
            font=("Consolas", 8),
            wrap="word",
        )
        self.paths_text.pack(fill="x", pady=(4, 0))
        self.paths_text.insert("end", self._path_summary())
        self.paths_text.configure(state="disabled")

        details = tk.PanedWindow(frame, orient="horizontal", bg=THEME["window"], sashwidth=4)
        details.pack(fill="both", expand=True, pady=(6, 0))
        self.colors_text = tk.Text(
            details,
            height=8,
            width=24,
            bg=THEME["entry"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            relief="flat",
            font=("Consolas", 9),
            wrap="word",
        )
        self.profiles_text = tk.Text(
            details,
            height=8,
            width=24,
            bg=THEME["entry"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            relief="flat",
            font=("Consolas", 9),
            wrap="word",
        )
        details.add(self.colors_text)
        details.add(self.profiles_text)

        self.log_text = tk.Text(
            frame,
            height=10,
            bg=THEME["entry"],
            fg=THEME["text"],
            insertbackground=THEME["text"],
            relief="flat",
            font=("Consolas", 9),
            wrap="word",
        )
        self.log_text.pack(fill="both", expand=True, pady=(6, 0))
        self.log_text.insert("end", self.logger.recent_text())
        self.log_text.configure(state="disabled")
        return frame

    def _schedule_status_refresh(self) -> None:
        self.refresh_statuses()
        self.root.after(5000, self._schedule_status_refresh)

    def refresh_statuses(self) -> None:
        nas_root = as_path(self.config["nas_root"])
        color_root = as_path(self.config["color_root"])
        local_paths = [
            as_path(self.config["colorgate_root"]),
            as_path(self.config["colorgate_ini"]),
            as_path(self.config["colorgate_cos"]),
        ]

        self.status_network.set(
            "green" if nas_root.exists() and color_root.exists() else "red",
            "ok" if nas_root.exists() and color_root.exists() else "fehlt",
        )
        local_ok = all(path.exists() for path in local_paths)
        self.status_local.set("green" if local_ok else "red", "ok" if local_ok else "fehlt")

        if self.last_sync_result:
            self.status_match.set(
                self.last_sync_result.severity,
                self._sync_short_text(self.last_sync_result),
            )
        else:
            self.status_match.set("gray", "nicht geprüft")

        output_color, output_text = self.cleaner.output_status()
        job_color, job_text = self.cleaner.jobdir_status()
        self.status_output.set(output_color, output_text)
        if hasattr(self, "expert_jobdir_label"):
            self.expert_jobdir_label.configure(text=f"JobDir: {job_text}")
        self._maybe_auto_clean_output()

    def _maybe_auto_clean_output(self) -> None:
        if not self.config.get("auto_clean_output_printdata", True):
            return
        interval = int(self.config.get("output_clean_interval_seconds", 60))
        if self.output_clean_running:
            return
        if time.time() - self.last_auto_clean_at < interval:
            return

        self.last_auto_clean_at = time.time()
        output_color, output_text = self.cleaner.output_status()
        if output_color == "yellow" and "enthält" in output_text:
            self._start_output_clean(manual=False)

    def toggle_calculator(self) -> None:
        if self.calc_frame.winfo_ismapped():
            self.calc_frame.pack_forget()
        else:
            self.calc_frame.pack(fill="x", pady=(4, 8))
            self.calc_entry.focus_set()

    def calculate_expression(self) -> None:
        try:
            result = self.calculator.evaluate(self.calc_entry.get())
            self.calc_result.configure(text=f"Ergebnis: {self._format_number(result)}")
        except Exception as exc:
            self.calc_result.configure(text=f"Fehler: {exc}")

    def convert_pt_to_mm(self) -> None:
        try:
            value = self.calculator.evaluate(self.calc_entry.get())
            self.calc_result.configure(text=f"{self._format_number(self.calculator.pt_to_mm(value))} mm")
        except Exception as exc:
            self.calc_result.configure(text=f"Fehler: {exc}")

    def convert_mm_to_pt(self) -> None:
        try:
            value = self.calculator.evaluate(self.calc_entry.get())
            self.calc_result.configure(text=f"{self._format_number(self.calculator.mm_to_pt(value))} pt")
        except Exception as exc:
            self.calc_result.configure(text=f"Fehler: {exc}")

    def _format_number(self, value: float) -> str:
        return f"{value:.4f}".rstrip("0").rstrip(".")

    def start_color_sync(self) -> None:
        self.main_status_label.configure(text="Farbabgleich läuft...")
        self._run_background(self._sync_worker, write_master=True)

    def startup_color_check(self) -> None:
        if self.setup_required():
            return
        if self.last_sync_result is not None:
            return
        self.main_status_label.configure(text="Farbabgleich wird geprüft...")
        self._run_background(self._startup_color_check_worker)

    def _startup_color_check_worker(self) -> None:
        result = self.color_manager.check_master_status()
        self.root.after(0, lambda: self._apply_sync_result_no_dialog(result))

    def check_color_sync(self) -> None:
        self.main_status_label.configure(text="Farbabgleich-Prüfung läuft...")
        self._run_background(self._sync_worker, write_master=False)

    def _sync_worker(self, write_master: bool = True) -> None:
        if write_master:
            result = self.color_manager.rebuild_master(write_master=True)
        else:
            result = self.color_manager.check_master_status()
        self.root.after(0, lambda: self._apply_sync_result(result))

    def _apply_sync_result(self, result: SyncResult) -> None:
        self.last_sync_result = result
        self.main_status_label.configure(text=self._sync_detail_text(result))
        self.status_match.set(result.severity, self._sync_short_text(result))
        self._update_expert_details(result)
        if result.severity == "red":
            messagebox.showerror(APP_NAME, result.message + self._detail_suffix(result))
        elif result.severity == "yellow":
            messagebox.showwarning(APP_NAME, result.message + self._detail_suffix(result))
        else:
            messagebox.showinfo(APP_NAME, result.message)

    def _detail_suffix(self, result: SyncResult) -> str:
        details = result.errors or result.warnings
        if not details:
            return ""
        return "\n\n" + "\n".join(details[:8])

    def _update_expert_details(self, result: SyncResult) -> None:
        if not hasattr(self, "colors_text"):
            return
        self.colors_text.configure(state="normal")
        self.colors_text.delete("1.0", "end")
        self.colors_text.insert("end", "ColorEntry-Namen\n\n" + "\n".join(result.colors))
        self.colors_text.configure(state="disabled")

        profile_lines = [
            "Profilprüfung:",
            f"Im normalen Farbabgleich für Version {APP_VERSION} deaktiviert.",
            "",
            "ColorGate übernimmt Änderungen an mprint4c-master.cct beim Import neuer Jobs.",
        ]
        if result.warnings:
            profile_lines.append("")
            profile_lines.append("Warnungen:")
            profile_lines.extend(result.warnings)
        if result.errors:
            profile_lines.append("")
            profile_lines.append("Fehler:")
            profile_lines.extend(result.errors)
        self.profiles_text.configure(state="normal")
        self.profiles_text.delete("1.0", "end")
        self.profiles_text.insert("end", "Profile / Zusatzprüfung\n\n" + "\n".join(profile_lines))
        self.profiles_text.configure(state="disabled")

    def clean_output_manual(self) -> None:
        self._start_output_clean(manual=True)

    def _start_output_clean(self, manual: bool) -> None:
        if self.output_clean_running:
            return
        self.output_clean_cancel_event.clear()
        self.output_clean_running = True
        self.status_output.set("yellow", "wird geleert")
        self.main_status_label.configure(text="Output wird geleert...")
        if hasattr(self, "cancel_output_button") and not self.cancel_output_button.winfo_ismapped():
            self.cancel_output_button.pack(fill="x", pady=3, before=self.rechner_button)
        self._run_background(self._clean_output_worker, manual=manual)

    def cancel_output_cleaning(self) -> None:
        if self.output_clean_running:
            self.output_clean_cancel_event.set()
            self.main_status_label.configure(text="Aufräumen wird gestoppt...")

    def _clean_output_worker(self, manual: bool = False) -> None:
        deleted = 0
        skipped: list[str] = []
        try:
            deleted, skipped = self.cleaner.clean_output(
                manual=manual,
                cancel_event=self.output_clean_cancel_event,
            )
        except Exception as exc:
            skipped = [f"Fehler beim Aufräumen: {exc}"]
            self.logger.log(skipped[0], "ERROR")
        finally:
            self.output_clean_running = False
        self.root.after(0, lambda: self._after_clean("OUTPUT_PRINTDATA", deleted, skipped, manual))

    def clean_jobdir_manual(self) -> None:
        if not messagebox.askyesno(
            APP_NAME,
            "JobDir wirklich leeren?\n\nEs werden nur stabile Dateien gelöscht, keine Ordner.",
        ):
            return
        self.main_status_label.configure(text="JobDir wird geprüft...")
        self._run_background(self._clean_jobdir_worker)

    def _clean_jobdir_worker(self) -> None:
        deleted, skipped = self.cleaner.clean_jobdir()
        self.root.after(0, lambda: self._after_clean("JobDir", deleted, skipped, True))

    def _after_clean(self, label: str, deleted: int, skipped: list[str], show_dialog: bool) -> None:
        if hasattr(self, "cancel_output_button") and self.cancel_output_button.winfo_ismapped():
            self.cancel_output_button.pack_forget()
        text = f"{label}: {deleted} Datei(en) gelöscht"
        if skipped:
            text += f", {len(skipped)} übersprungen"
        self.main_status_label.configure(text=text)
        self.refresh_statuses()
        if show_dialog:
            if skipped:
                messagebox.showwarning(APP_NAME, text + "\n\n" + "\n".join(skipped[:10]))
            else:
                messagebox.showinfo(APP_NAME, text)

    def choose_pdf_for_reduction(self, width_pt: float) -> None:
        if self.pdf_reduce_running:
            messagebox.showwarning(APP_NAME, "PDF-Reduktion läuft bereits.")
            return
        width_label = format_pt_value(width_pt)
        pdf_names = filedialog.askopenfilenames(
            title=f"PDF reduzieren - {width_label} pt",
            filetypes=[("PDF-Dateien", "*.pdf"), ("Alle Dateien", "*.*")],
        )
        if not pdf_names:
            return
        self.pdf_reduce_cancel_event.clear()
        self.pdf_reduce_running = True
        if hasattr(self, "cancel_pdf_button") and not self.cancel_pdf_button.winfo_ismapped():
            self.cancel_pdf_button.pack(fill="x", pady=(6, 0))
        self.main_status_label.configure(text=f"PDF-Reduktion {width_label} pt startet...")
        self.logger.log(f"PDF-Reduktion {width_label} pt ausgewählt: {len(pdf_names)} PDF(s)")
        self._run_background(
            self._pdf_reduce_worker,
            pdf_paths=[Path(pdf_name) for pdf_name in pdf_names],
            width_pt=width_pt,
        )

    def cancel_pdf_reduction(self) -> None:
        if self.pdf_reduce_running:
            self.pdf_reduce_cancel_event.set()
            self.main_status_label.configure(text="PDF-Reduktion wird gestoppt...")

    def _pdf_reduce_worker(self, pdf_paths: list[Path], width_pt: float) -> None:
        saved_paths: list[Path] = []
        errors: list[str] = []
        try:
            total = len(pdf_paths)
            for index, pdf_path in enumerate(pdf_paths, start=1):
                if self.pdf_reduce_cancel_event.is_set():
                    errors.append("PDF-Reduktion wurde gestoppt.")
                    break
                self.root.after(
                    0,
                    lambda current=index, count=total, name=pdf_path.name: self.main_status_label.configure(
                        text=f"PDF {current}/{count}: {name}"
                    ),
                )
                try:
                    reducer = PdfReducer(
                        self.config,
                        self.logger,
                        status_callback=lambda text: self.root.after(0, lambda: self.main_status_label.configure(text=text)),
                        cancel_event=self.pdf_reduce_cancel_event,
                        variants_pt=[width_pt],
                        missing_codes_callback=self._resolve_missing_pdf_codes,
                        confirm_without_codes_callback=self._confirm_pdf_reduce_without_codes,
                    )
                    saved_paths.extend(reducer.reduce_pdf(pdf_path))
                except Exception as exc:
                    error = f"{pdf_path.name}: {exc}"
                    errors.append(error)
                    self.logger.log(f"PDF-Reduktion fehlgeschlagen: {error}", "ERROR")
        finally:
            self.pdf_reduce_running = False
        self.root.after(0, lambda: self._after_pdf_reduction(saved_paths, errors))

    def _after_pdf_reduction(self, saved_paths: list[Path], errors: list[str]) -> None:
        if hasattr(self, "cancel_pdf_button") and self.cancel_pdf_button.winfo_ismapped():
            self.cancel_pdf_button.pack_forget()
        if not saved_paths:
            self.main_status_label.configure(text="Keine PDF-Dateien erzeugt")
            detail = "\n\n" + "\n".join(errors[:8]) if errors else ""
            messagebox.showwarning(APP_NAME, "Keine PDF-Dateien erzeugt." + detail)
            return
        if errors:
            self.main_status_label.configure(text=f"PDF-Reduktion fertig: {len(saved_paths)} Datei(en), Warnungen")
            messagebox.showwarning(
                APP_NAME,
                f"PDF-Reduktion fertig: {len(saved_paths)} Datei(en)\n\n"
                "Nicht verarbeitet:\n"
                + "\n".join(errors[:8]),
            )
        else:
            self.main_status_label.configure(text=f"PDF-Reduktion fertig: {len(saved_paths)} Datei(en)")
            messagebox.showinfo(
                APP_NAME,
                "PDF-Reduktion fertig:\n\n" + "\n".join(str(path) for path in saved_paths),
            )

    def _confirm_pdf_reduce_without_codes(self, page_number: int) -> bool:
        decision = {"value": False}
        finished = threading.Event()

        def ask() -> None:
            decision["value"] = messagebox.askyesno(
                APP_NAME,
                f"Auf Seite {page_number} wurde kein QR/EAN-Code sicher erkannt.\n\n"
                "Trotzdem reduzieren?\n\n"
                "Nur mit Ja fortfahren, wenn diese PDF wirklich keine Codes enthält.",
            )
            finished.set()

        self.root.after(0, ask)
        finished.wait()
        return decision["value"]

    def _resolve_missing_pdf_codes(
        self,
        page_number: int,
        detect_image: object,
    ) -> list[tuple[int, int, int, int]] | None:
        decision: dict[str, list[tuple[int, int, int, int]] | None] = {"value": None}
        finished = threading.Event()

        def ask() -> None:
            try:
                decision["value"] = self._show_manual_code_dialog(page_number, detect_image)
            finally:
                finished.set()

        self.root.after(0, ask)
        finished.wait()
        return decision["value"]

    def _show_manual_code_dialog(
        self,
        page_number: int,
        detect_image: object,
    ) -> list[tuple[int, int, int, int]] | None:
        try:
            from PIL import Image as PILImage
            from PIL import ImageTk
        except Exception:
            if self._confirm_pdf_reduce_without_codes(page_number):
                return []
            return None

        result: dict[str, list[tuple[int, int, int, int]] | None] = {"value": None}
        original_width, original_height = detect_image.size
        screen_width = max(640, self.root.winfo_screenwidth())
        screen_height = max(480, self.root.winfo_screenheight())
        max_width = min(960, screen_width - 120)
        max_height = min(680, screen_height - 230)
        scale = min(max_width / max(1, original_width), max_height / max(1, original_height), 1.0)
        preview_size = (
            max(1, int(round(original_width * scale))),
            max(1, int(round(original_height * scale))),
        )

        preview_image = detect_image.convert("RGB")
        if preview_size != detect_image.size:
            resample = getattr(getattr(PILImage, "Resampling", PILImage), "LANCZOS")
            preview_image = preview_image.resize(preview_size, resample)

        dialog = tk.Toplevel(self.root)
        dialog.title("QR/EAN markieren")
        dialog.configure(bg=THEME["window"])
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(True, True)

        message = tk.Label(
            dialog,
            text=(
                f"Seite {page_number}: Kein QR/EAN-Code sicher erkannt.\n"
                "Ziehe einen oder mehrere Kästen um QR/EAN-Codes. Bei EAN bitte die Zahlen mit einschließen."
            ),
            bg=THEME["window"],
            fg=THEME["text"],
            justify="left",
            anchor="w",
            wraplength=max(360, preview_size[0]),
            font=("Segoe UI", 10),
        )
        message.pack(fill="x", padx=12, pady=(12, 8))

        canvas_frame = tk.Frame(dialog, bg=THEME["window"])
        canvas_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        canvas = tk.Canvas(
            canvas_frame,
            width=preview_size[0],
            height=preview_size[1],
            bg=THEME["entry"],
            highlightbackground=THEME["border"],
            highlightthickness=1,
            cursor="crosshair",
        )
        canvas.pack(fill="both", expand=True)

        photo = ImageTk.PhotoImage(preview_image)
        canvas.create_image(0, 0, anchor="nw", image=photo)
        canvas.image = photo

        status_label = tk.Label(
            dialog,
            text="Noch keine Markierung.",
            bg=THEME["window"],
            fg=THEME["muted"],
            anchor="w",
            font=("Segoe UI", 9),
        )
        status_label.pack(fill="x", padx=12, pady=(0, 8))

        boxes: list[tuple[int, int, int, int]] = []
        rect_ids: list[int] = []
        drag_state: dict[str, int | None] = {
            "x": None,
            "y": None,
            "rect": None,
        }

        def clamp(value: int, minimum: int, maximum: int) -> int:
            return max(minimum, min(maximum, value))

        def update_status() -> None:
            count = len(boxes)
            if count == 1:
                status_label.configure(text="1 Schutzbereich markiert.")
            else:
                status_label.configure(text=f"{count} Schutzbereiche markiert.")

        def to_original_box(x0: int, y0: int, x1: int, y1: int) -> tuple[int, int, int, int]:
            return (
                clamp(int(round(x0 / scale)), 0, original_width),
                clamp(int(round(y0 / scale)), 0, original_height),
                clamp(int(round(x1 / scale)), 0, original_width),
                clamp(int(round(y1 / scale)), 0, original_height),
            )

        def canvas_xy(event: tk.Event) -> tuple[int, int]:
            return (
                clamp(int(canvas.canvasx(event.x)), 0, preview_size[0]),
                clamp(int(canvas.canvasy(event.y)), 0, preview_size[1]),
            )

        def on_press(event: tk.Event) -> None:
            x, y = canvas_xy(event)
            drag_state["x"] = x
            drag_state["y"] = y
            rect_id = canvas.create_rectangle(x, y, x, y, outline="#d11d1d", width=2)
            drag_state["rect"] = rect_id

        def on_drag(event: tk.Event) -> None:
            rect_id = drag_state.get("rect")
            start_x = drag_state.get("x")
            start_y = drag_state.get("y")
            if rect_id is None or start_x is None or start_y is None:
                return
            x, y = canvas_xy(event)
            canvas.coords(rect_id, start_x, start_y, x, y)

        def on_release(event: tk.Event) -> None:
            rect_id = drag_state.get("rect")
            start_x = drag_state.get("x")
            start_y = drag_state.get("y")
            if rect_id is None or start_x is None or start_y is None:
                return
            end_x, end_y = canvas_xy(event)
            x0, x1 = sorted((int(start_x), end_x))
            y0, y1 = sorted((int(start_y), end_y))
            drag_state["x"] = None
            drag_state["y"] = None
            drag_state["rect"] = None
            if x1 - x0 < 6 or y1 - y0 < 6:
                canvas.delete(rect_id)
                return
            canvas.coords(rect_id, x0, y0, x1, y1)
            rect_ids.append(int(rect_id))
            boxes.append(to_original_box(x0, y0, x1, y1))
            update_status()

        def delete_last() -> None:
            if not boxes:
                return
            boxes.pop()
            rect_id = rect_ids.pop()
            canvas.delete(rect_id)
            update_status()

        def accept_boxes() -> None:
            if not boxes:
                messagebox.showwarning(
                    APP_NAME,
                    "Bitte erst einen Kasten ziehen oder bewusst ohne Code reduzieren.",
                    parent=dialog,
                )
                return
            result["value"] = list(boxes)
            dialog.destroy()

        def accept_without_codes() -> None:
            if messagebox.askyesno(
                APP_NAME,
                "Wirklich ohne QR/EAN-Schutz reduzieren?\n\n"
                "Nur mit Ja fortfahren, wenn diese PDF keine Codes enthält oder die Codes egal sind.",
                parent=dialog,
            ):
                result["value"] = []
                dialog.destroy()

        def cancel() -> None:
            result["value"] = None
            dialog.destroy()

        canvas.bind("<ButtonPress-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        canvas.bind("<ButtonRelease-1>", on_release)

        button_row = tk.Frame(dialog, bg=THEME["window"])
        button_row.pack(fill="x", padx=12, pady=(0, 12))
        ttk.Button(button_row, text="Abbrechen", command=cancel).pack(side="left")
        ttk.Button(button_row, text="Letzte löschen", command=delete_last).pack(side="left", padx=(8, 0))
        ttk.Button(button_row, text="Trotzdem ohne Code reduzieren", command=accept_without_codes).pack(side="right")
        ttk.Button(button_row, text="Markierung übernehmen", command=accept_boxes).pack(side="right", padx=(0, 8))

        dialog.protocol("WM_DELETE_WINDOW", cancel)
        dialog.update_idletasks()
        x_pos = max(0, (screen_width - dialog.winfo_width()) // 2)
        y_pos = max(0, (screen_height - dialog.winfo_height()) // 3)
        dialog.geometry(f"+{x_pos}+{y_pos}")
        dialog.focus_force()
        self.root.wait_window(dialog)
        return result["value"]

    def shutdown_flow(self) -> None:
        self.main_status_label.configure(text="Feierabend läuft. Sie müssen nichts mehr tun.")
        self._run_background(self._shutdown_prepare_worker)

    def _shutdown_prepare_worker(self) -> None:
        sync_result = self.color_manager.rebuild_master(write_master=True)
        deleted, skipped = self.cleaner.clean_output(manual=True)
        self.root.after(0, lambda: self._continue_shutdown(sync_result, deleted, skipped))

    def _continue_shutdown(self, sync_result: SyncResult, deleted: int, skipped: list[str]) -> None:
        self._apply_sync_result_no_dialog(sync_result)
        if sync_result.severity == "red":
            self.logger.log(
                "Feierabend: Farbabgleich rot, Shutdown wird trotzdem ohne Rückfrage gestartet",
                "ERROR",
            )

        if skipped:
            self.logger.log(
                f"Feierabend: OUTPUT_PRINTDATA übersprungen: {len(skipped)} Datei(en)",
                "WARNING",
            )

        open_processes = self._close_known_processes()
        if open_processes:
            self.logger.log(
                "Feierabend: Prozesse noch offen: " + ", ".join(open_processes),
                "WARNING",
            )

        self.main_status_label.configure(text="Rechner wird jetzt heruntergefahren. Sie müssen nichts mehr tun.")
        self._run_windows_shutdown(force=False)

    def _apply_sync_result_no_dialog(self, result: SyncResult) -> None:
        self.last_sync_result = result
        self.status_match.set(result.severity, self._sync_short_text(result))
        self.main_status_label.configure(text=self._sync_detail_text(result))
        self._update_expert_details(result)

    def _sync_short_text(self, result: SyncResult) -> str:
        if result.severity == "green":
            return "OK"
        if result.severity == "yellow":
            return "Warnung"
        if result.severity == "red":
            return "Fehler"
        return "unbekannt"

    def _sync_detail_text(self, result: SyncResult) -> str:
        if result.severity == "red":
            return result.message
        if result.severity == "yellow":
            if result.warnings:
                return "; ".join(result.warnings[:2])
            return "Prüfung mit Warnung abgeschlossen"
        return result.message

    def force_shutdown(self) -> None:
        if not self.expert_visible:
            return
        if messagebox.askyesno(
            APP_NAME,
            "Shutdown erzwingen?\n\nDas ist nur für den Expertmodus gedacht.",
        ):
            self._run_windows_shutdown(force=True)

    def _close_known_processes(self) -> list[str]:
        if os.name != "nt":
            self.logger.log("Prozess-Schließen übersprungen: nicht Windows", "WARNING")
            return []

        remaining: list[str] = []
        for process_name in self.config.get("known_processes", []):
            if not process_name:
                continue
            if not self._is_process_running(process_name):
                continue
            self.logger.log(f"Versuche Prozess sauber zu schließen: {process_name}")
            try:
                subprocess.run(
                    ["taskkill", "/IM", process_name],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except Exception as exc:
                self.logger.log(f"taskkill fehlgeschlagen für {process_name}: {exc}", "ERROR")
            time.sleep(3)
            if self._is_process_running(process_name):
                remaining.append(process_name)
        return remaining

    def _is_process_running(self, process_name: str) -> bool:
        try:
            completed = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
                check=False,
                capture_output=True,
                text=True,
                timeout=8,
            )
            return process_name.lower() in completed.stdout.lower()
        except Exception:
            return False

    def _run_windows_shutdown(self, force: bool = False) -> None:
        if os.name != "nt":
            messagebox.showwarning(APP_NAME, "Shutdown wird nur auf Windows ausgefuehrt.")
            self.logger.log("Shutdown übersprungen: nicht Windows", "WARNING")
            return

        command = ["shutdown", "/s", "/t", "5", "/c", f"{APP_NAME}: Feierabend"]
        if force:
            command.insert(2, "/f")
        try:
            subprocess.Popen(command)
            self.logger.log("Windows-Shutdown gestartet")
            self.main_status_label.configure(text="Rechner wird jetzt heruntergefahren. Sie müssen nichts mehr tun.")
        except Exception as exc:
            self.logger.log(f"Shutdown fehlgeschlagen: {exc}", "ERROR")
            messagebox.showerror(APP_NAME, f"Shutdown fehlgeschlagen:\n{exc}")

    def toggle_expert(self, _event: object | None = None) -> None:
        self.expert_visible = not self.expert_visible
        if self.expert_visible:
            self.expert_frame.pack(fill="both", expand=True)
            self.root.minsize(520, 620)
            current_height = max(self.root.winfo_height(), 720)
            self.root.geometry(f"520x{current_height}")
        else:
            self.expert_frame.pack_forget()
            width = int(self.config.get("window_width", 260))
            self.root.minsize(240, 520)
            current_height = max(self.root.winfo_height(), 620)
            self.root.geometry(f"{width}x{current_height}")

    def show_about(self) -> None:
        messagebox.showinfo(
            f"Info - {APP_NAME}",
            "\n".join(
                [
                    f"{APP_NAME} {APP_VERSION}",
                    "",
                    "Hilfstool für MJET-X / ColorGate / LP2000i.",
                    "",
                    "Funktionen:",
                    "- Kundenfarben in die Master-Farbtabelle übertragen",
                    "- Druckdaten-Übergabeordner sicher aufräumen",
                    "- PDF-Verfeinerung mit QR/EAN-Schutz",
                    "- Farbübersicht für die Vorstufe schreiben",
                    "",
                    f"by {APP_AUTHOR}",
                    APP_CONTACT,
                ]
            ),
        )

    def check_for_updates_startup(self) -> None:
        if not self.config.get("update_check_enabled", True):
            return
        if not str(self.config.get("update_check_url", "")).strip():
            return
        self._run_background(self._update_check_worker, show_if_current=False)

    def check_for_updates_manual(self) -> None:
        self.main_status_label.configure(text="Update wird geprüft...")
        self._run_background(self._update_check_worker, show_if_current=True)

    def _update_check_worker(self, show_if_current: bool = False) -> None:
        try:
            info = load_update_info(str(self.config.get("update_check_url", "")))
            latest_version = str(info.get("version", "")).strip()
            is_new = is_newer_version(latest_version, APP_VERSION)
            self.root.after(0, lambda: self._apply_update_check_result(info, is_new, show_if_current))
        except Exception as exc:
            self.logger.log(f"Update-Prüfung fehlgeschlagen: {exc}", "WARNING")
            if show_if_current:
                self.root.after(0, lambda: messagebox.showwarning(APP_NAME, f"Update-Prüfung fehlgeschlagen:\n{exc}"))
            self.root.after(0, lambda: self.main_status_label.configure(text="Update-Prüfung nicht möglich"))

    def _apply_update_check_result(self, info: dict, is_new: bool, show_if_current: bool) -> None:
        latest_version = str(info.get("version", "")).strip()
        download_url = str(info.get("url", "") or info.get("download_url", "")).strip()
        notes = str(info.get("notes", "") or info.get("hinweis", "")).strip()
        if is_new:
            message_lines = [
                f"Neue Version verfügbar: {latest_version}",
                f"Aktuelle Version: {APP_VERSION}",
            ]
            if download_url:
                message_lines.extend(["", f"Quelle: {download_url}"])
            if notes:
                message_lines.extend(["", notes])
            self.main_status_label.configure(text=f"Update verfügbar: {latest_version}")
            messagebox.showinfo(APP_NAME, "\n".join(message_lines))
            return

        self.main_status_label.configure(text=f"{APP_NAME} ist aktuell")
        if show_if_current:
            messagebox.showinfo(APP_NAME, f"{APP_NAME} ist aktuell.\n\nInstalliert: {APP_VERSION}")

    def maybe_open_initial_setup(self) -> None:
        if os.name != "nt" and not default_config_created():
            return
        if default_config_created() or self.setup_required():
            self.open_setup_dialog(required=True)

    def setup_required(self) -> bool:
        required_paths = [
            "color_root",
            "single_color_dir",
            "backup_dir",
            "output_printdata_dir",
        ]
        if not str(self.config.get("master_cct", "")).strip():
            return True
        if not str(self.config.get("color_overview_html", "")).strip():
            return True
        for key in required_paths:
            value = str(self.config.get(key, "")).strip()
            if not value:
                return True
            if key in {"color_root", "single_color_dir"} and not as_path(value).exists():
                return True
        return False

    def open_setup_dialog(self, required: bool = False) -> None:
        dialog = SetupDialog(self.root, self.config, required=required)
        if not dialog.result:
            return
        save_config(self.config)
        self._apply_config_after_setup()
        self.main_status_label.configure(text="Setup gespeichert")
        self.refresh_statuses()

    def _apply_config_after_setup(self) -> None:
        self.color_request_server.stop()
        self.color_manager = ColorTableManager(self.config, self.logger)
        self.color_request_server = ColorRequestServer(self.config, self.logger, self.color_manager)
        self.cleaner = SafeCleaner(self.config, self.logger)
        self.color_request_server.start()
        if hasattr(self, "paths_text"):
            self.paths_text.configure(state="normal")
            self.paths_text.delete("1.0", "end")
            self.paths_text.insert("end", self._path_summary())
            self.paths_text.configure(state="disabled")
        self.last_sync_result = None

    def open_path(self, value: str | os.PathLike[str]) -> None:
        path = Path(value)
        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Konnte nicht öffnen:\n{path}\n\n{exc}")

    def _path_summary(self) -> str:
        keys = [
            "nas_root",
            "color_root",
            "single_color_dir",
            "backup_dir",
            "master_cct",
            "colorgate_cos",
            "colorgate_jobdir",
            "output_printdata_dir",
        ]
        return "Pfade\n\n" + "\n".join(f"{key}: {self.config.get(key, '')}" for key in keys)

    def _on_log_line(self, line: str) -> None:
        if not hasattr(self, "log_text"):
            return

        def update() -> None:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", line + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        self.root.after(0, update)

    def _run_background(self, target: callable, **kwargs: object) -> None:
        thread = threading.Thread(target=target, kwargs=kwargs, daemon=True)
        thread.start()

    def _on_close(self) -> None:
        self.config["window_geometry"] = self.root.geometry()
        save_config(self.config)
        self.color_request_server.stop()
        self.root.destroy()


def main() -> None:
    try:
        config = load_config()
    except Exception as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(APP_NAME, str(exc))
        return

    logger = HelperLogger(config)
    root = tk.Tk()
    MainApp(root, config, logger)
    root.mainloop()


if __name__ == "__main__":
    main()
