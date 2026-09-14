from __future__ import annotations

import ast
import copy
import csv
import ctypes
import datetime as dt
import argparse
import fnmatch
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
import unicodedata
import webbrowser
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import parse_qs
from urllib.request import urlopen

from color_mixer import ColorMixerWindow


APP_NAME = "MJET-X Helper"
APP_VERSION = "1.1.2"
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
    "color_export_json": r"export\mprint_colors.json",
    "hidden_colors_json": r"config\hidden_colors.json",
    "prepress_notes_json": r"work\prepress_notes.json",
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


@dataclass
class SingleColorCandidate:
    name: str
    entry: ET.Element
    source_file: Path
    mtime: float
    ignored_names: list[str] = field(default_factory=list)


class ColorTableManager:
    def __init__(self, config: dict, logger: HelperLogger):
        self.config = config
        self.logger = logger
        self.overview_lock = threading.RLock()
        self.import_corrections: dict[str, dict[str, str]] = {}
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

        master_entries = self._master_entries_by_name(master_path) if master_path.exists() else {}
        import_corrections: dict[str, dict[str, str]] = {}
        candidates_by_name: dict[str, list[SingleColorCandidate]] = {}
        display_names: dict[str, str] = {}
        extra_entry_files = 0

        for color_file in color_files:
            candidate, read_errors, read_warnings = self._single_color_candidate_from_file(color_file)
            for error in read_errors:
                errors.append(error)
                self.logger.log(error, "ERROR")
            for warning in read_warnings:
                warnings.append(warning)
                self.logger.log(warning, "WARNING")
            if candidate is None:
                continue
            if candidate.ignored_names:
                extra_entry_files += 1
                self.logger.log(
                    f"{color_file.name}: verwendet {candidate.name}; ignoriert: {', '.join(candidate.ignored_names)}"
                )
            key = self._normalized_color_key(candidate.name)
            candidates_by_name.setdefault(key, []).append(candidate)
            display_names.setdefault(key, candidate.name)

        if not candidates_by_name:
            error = "Keine gültigen Einzel-Farbexports gefunden. Der Master wurde nicht verändert."
            errors.append(error)
            self.logger.log(error, "ERROR")

        unique_entries: list[ET.Element] = []
        color_names: list[str] = []
        automatic_conflicts = 0
        updated_colors: list[str] = []
        for key in sorted(candidates_by_name, key=lambda item: display_names[item].casefold()):
            candidates = sorted(
                candidates_by_name[key],
                key=lambda candidate: (candidate.mtime, candidate.source_file.name.casefold()),
                reverse=True,
            )
            winner = candidates[0]
            if len(candidates) > 1:
                automatic_conflicts += 1
                self.logger.log(
                    "Mehrere Quellen für "
                    f"{winner.name} erkannt. Verwendet wurde die zuletzt geänderte Datei: "
                    f"{winner.source_file.name} ({self._mtime_text(winner.mtime)})",
                    "WARNING",
                )
            entry = copy.deepcopy(winner.entry)
            original_name = self._color_entry_name(entry)
            name = winner.name
            correction = self._detect_import_correction(
                name=name,
                original_name=original_name,
                incoming_entry=entry,
                master_entries=master_entries,
            )
            if correction:
                master_entry = master_entries.get(self._normalized_color_key(name))
                if master_entry is not None:
                    entry = copy.deepcopy(master_entry)
                    warning = self._import_correction_warning_text()
                    if warning not in warnings:
                        warnings.append(warning)
                    import_corrections[self._normalized_color_key(name)] = correction
                    self.logger.log(
                        f"Farbimport-Schutz: {name} aus {winner.source_file.name} korrigiert. "
                        "Bestehende MPRINT-Zuordnung beibehalten.",
                        "WARNING",
                    )
            master_entry = master_entries.get(self._normalized_color_key(name))
            if master_entry is not None and self._entry_signature(master_entry) != self._entry_signature(entry):
                updated_colors.append(name)
                self.logger.log(f"{name} wurde aus {winner.source_file.name} aktualisiert.")
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
            self.import_corrections = dict(import_corrections)
            master_names = color_names if write_master else self._master_color_names(master_path)
            overview_warning = self._write_color_overview(color_names, master_names)
            if overview_warning:
                warnings.append(overview_warning)
        except Exception as exc:
            warning = f"Farbübersicht konnte nicht geschrieben werden: {exc}"
            warnings.append(warning)
            self.logger.log(warning, "WARNING")
        finally:
            self.import_corrections = {}

        self.logger.log(f"Übernommene Farben: {len(unique_entries)}")
        if extra_entry_files:
            self.logger.log(
                f"{extra_entry_files} Mehrfarben-Exportdatei(en) automatisch auf Dateiname-Farbe reduziert"
            )
        if automatic_conflicts:
            self.logger.log(f"{automatic_conflicts} mehrdeutige Quellen automatisch nach Änderungsdatum aufgelöst")
        if updated_colors:
            self.logger.log("Aktualisierte Farben: " + ", ".join(updated_colors[:20]))

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
            if import_corrections:
                return SyncResult(
                    "yellow",
                    "Farbänderung erkannt und automatisch korrigiert",
                    color_names,
                    profiles,
                    warnings,
                    errors,
                    source_files,
                )
            return SyncResult(
                "yellow",
                f"{operation_done}, aber Warnungen vorhanden",
                color_names,
                profiles,
                warnings,
                errors,
                source_files,
            )
        success_message = "Master erfolgreich gebaut" if write_master else "Master-Prüfung erfolgreich"
        success_notes: list[str] = []
        if extra_entry_files:
            success_notes.append(
                "Mehrfarben-Exports wurden automatisch auf die passende Dateiname-Farbe reduziert."
            )
        if automatic_conflicts:
            success_notes.append("Mehrere Quellen wurden nach Änderungsdatum eindeutig aufgelöst.")
        if updated_colors:
            color_list = ", ".join(updated_colors[:10])
            if len(updated_colors) > 10:
                color_list += f" und {len(updated_colors) - 10} weitere"
            success_notes.append(f"Aktualisierte Farben: {color_list}.")
        if success_notes:
            success_message = "Farbabgleich erfolgreich. " + " ".join(success_notes)
        return SyncResult(
            "green",
            success_message,
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
        master_entries = self._master_entries_by_name(master_path)
        import_corrections: dict[str, dict[str, str]] = {}
        candidates_by_name: dict[str, list[SingleColorCandidate]] = {}
        display_names: dict[str, str] = {}
        for color_file in color_files:
            candidate, read_errors, read_warnings = self._single_color_candidate_from_file(color_file)
            errors.extend(read_errors)
            warnings.extend(read_warnings)
            if candidate is None:
                continue
            key = self._normalized_color_key(candidate.name)
            candidates_by_name.setdefault(key, []).append(candidate)
            display_names.setdefault(key, candidate.name)

        if not candidates_by_name:
            error = "Keine gültigen Einzel-Farbexports gefunden"
            errors.append(error)

        for key in sorted(candidates_by_name, key=lambda item: display_names[item].casefold()):
            candidates = sorted(
                candidates_by_name[key],
                key=lambda candidate: (candidate.mtime, candidate.source_file.name.casefold()),
                reverse=True,
            )
            winner = candidates[0]
            normalized_entry = copy.deepcopy(winner.entry)
            original_name = self._color_entry_name(normalized_entry)
            name = winner.name
            if len(candidates) > 1:
                self.logger.log(
                    "Mehrere Quellen für "
                    f"{name} erkannt. Verwendet wurde die zuletzt geänderte Datei: "
                    f"{winner.source_file.name} ({self._mtime_text(winner.mtime)})",
                    "WARNING",
                )
            correction = self._detect_import_correction(
                name=name,
                original_name=original_name,
                incoming_entry=normalized_entry,
                master_entries=master_entries,
            )
            if correction:
                master_entry = master_entries.get(self._normalized_color_key(name))
                if master_entry is not None:
                    normalized_entry = copy.deepcopy(master_entry)
                    warning = self._import_correction_warning_text()
                    if warning not in warnings:
                        warnings.append(warning)
                    import_corrections[self._normalized_color_key(name)] = correction
                    self.logger.log(
                        f"Farbimport-Schutz: {name} aus {winner.source_file.name} erkannt. "
                        "Bestehende MPRINT-Zuordnung bleibt maßgeblich.",
                        "WARNING",
                    )
            single_signatures[name] = self._entry_signature(normalized_entry)
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
        master_signature_lookup = {
            self._normalized_color_key(name): signature
            for name, signature in master_signatures.items()
        }
        missing_or_changed = [
            name
            for name, signature in single_signatures.items()
            if master_signature_lookup.get(self._normalized_color_key(name)) != signature
        ]

        try:
            self.import_corrections = dict(import_corrections)
            overview_warning = self._write_color_overview(color_names, list(master_signatures.keys()))
            if overview_warning:
                warnings.append(overview_warning)
        except Exception as exc:
            warning = f"Farbübersicht konnte nicht geschrieben werden: {exc}"
            warnings.append(warning)
            self.logger.log(warning, "WARNING")
        finally:
            self.import_corrections = {}

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

    def _single_color_candidate_from_file(
        self,
        color_file: Path,
    ) -> tuple[SingleColorCandidate | None, list[str], list[str]]:
        file_mtime = self._safe_mtime(color_file)
        target_name = self._target_color_name_from_file(color_file)
        errors: list[str] = []
        warnings: list[str] = []
        try:
            tree = ET.parse(color_file)
        except ET.ParseError as exc:
            return None, [f"XML fehlerhaft in {color_file.name}: {exc}"], []
        except Exception as exc:
            return None, [f"Datei konnte nicht gelesen werden: {color_file.name}: {exc}"], []

        entries = [
            copy.deepcopy(elem)
            for elem in tree.getroot().iter()
            if local_name(elem.tag) == "ColorEntry"
        ]
        self.logger.log(f"{color_file.name}: {len(entries)} ColorEntry-Einträge")
        matching: list[ET.Element] = []
        ignored_names: list[str] = []
        target_key = self._normalized_color_key(target_name)
        for entry in entries:
            entry_name = self._clean_color_name(self._color_entry_name(entry))
            if self._normalized_color_key(entry_name) == target_key:
                entry.set("Name", target_name)
                matching.append(entry)
            elif entry_name:
                ignored_names.append(entry_name)

        if not matching:
            warnings.append(
                f"{color_file.name} enthält keinen passenden Farbeintrag '{target_name}'. "
                "Die Datei wurde nicht übernommen."
            )
            return None, errors, warnings

        if len(matching) > 1:
            warnings.append(
                f"{color_file.name} enthält mehrere passende Farbeinträge '{target_name}'. "
                "Der erste passende Eintrag wurde verwendet."
            )

        return (
            SingleColorCandidate(
                name=target_name,
                entry=matching[0],
                source_file=color_file,
                mtime=file_mtime,
                ignored_names=ignored_names,
            ),
            errors,
            warnings,
        )

    def _target_color_name_from_file(self, color_file: Path) -> str:
        return self._clean_color_name(unicodedata.normalize("NFC", color_file.stem))

    def _normalized_color_key(self, value: str) -> str:
        normalized = unicodedata.normalize("NFC", self._clean_color_name(value))
        return normalized.casefold()

    def _mtime_text(self, value: float) -> str:
        if not value:
            return "Datum nicht lesbar"
        try:
            return dt.datetime.fromtimestamp(value).strftime("%d.%m.%Y %H:%M")
        except Exception:
            return "Datum nicht lesbar"

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

    def _master_entries_by_name(self, master_path: Path) -> dict[str, ET.Element]:
        if not master_path.exists():
            return {}
        try:
            tree = ET.parse(master_path)
        except Exception as exc:
            self.logger.log(f"Master konnte für Import-Schutz nicht gelesen werden: {master_path} ({exc})", "WARNING")
            return {}
        entries: dict[str, ET.Element] = {}
        for entry in tree.getroot().iter():
            if local_name(entry.tag) == "ColorEntry":
                name = self._clean_color_name(self._color_entry_name(entry))
                if name:
                    entries[self._normalized_color_key(name)] = copy.deepcopy(entry)
        return entries

    def _detect_import_correction(
        self,
        name: str,
        original_name: str,
        incoming_entry: ET.Element,
        master_entries: dict[str, ET.Element],
    ) -> dict[str, str] | None:
        cleaned_name = self._clean_color_name(name)
        cleaned_original = self._clean_color_name(original_name)
        if not cleaned_name:
            return None
        master_entry = master_entries.get(self._normalized_color_key(cleaned_name))
        if master_entry is None:
            return None
        if not self._is_technical_color_name(cleaned_original):
            return None
        if cleaned_original.casefold() == cleaned_name.casefold():
            return None
        incoming_values = self._entry_cmyk_values(incoming_entry)
        master_values = self._entry_cmyk_values(master_entry)
        if incoming_values is None or master_values is None:
            return None
        if incoming_values == master_values:
            return None
        return {
            "event": "import_correction",
            "timestamp": self._event_timestamp(now_stamp()),
            "user": "MJET Helper",
            "details": (
                "Importabweichung erkannt. Eine technische Farbe wurde versehentlich als "
                "Produktionsfarbe verwendet. Die ursprüngliche MPRINT-Zuordnung wurde beibehalten."
            ),
            "original_name": cleaned_original,
            "target_name": cleaned_name,
            "old_cmyk": self._cmyk_values_text(master_values),
            "incoming_cmyk": self._cmyk_values_text(incoming_values),
        }

    def _is_technical_color_name(self, name: str) -> bool:
        normalized = re.sub(r"[^a-z0-9äöüß]+", "", str(name).casefold())
        return normalized in {
            "eindruckfarbe",
            "eindruckfarbe2",
            "passer",
            "cut",
            "crop",
            "custom",
            "sonderfarbe",
            "technical",
            "hilfsfarbe",
        }

    def _entry_cmyk_values(self, entry: ET.Element) -> tuple[int, int, int, int] | None:
        text = self._color_entry_cmyk(entry)
        values = self._parse_cmyk_values(text)
        if values is None:
            return None
        return (values["c"], values["m"], values["y"], values["k"])

    def _cmyk_values_text(self, values: tuple[int, int, int, int]) -> str:
        return f"C {values[0]} / M {values[1]} / Y {values[2]} / K {values[3]}"

    def _import_correction_warning_text(self) -> str:
        return (
            "⚠️ Farbänderung erkannt\n\n"
            "Eine unplausible Änderung in der Farbtabelle wurde erkannt.\n\n"
            "Der MJET Helper hat die Änderung automatisch korrigiert.\n\n"
            "Die bestätigten Produktionsfarben wurden nicht verändert."
        )

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
            "color_id",
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
            "sk_assignments",
            "printed",
            "printed_at",
            "approved",
            "approved_at",
            "transfer",
            "not_printable",
            "not_printable_at",
            "not_printable_by",
            "not_printable_reason",
            "approval_notification_json",
            "approval_mail_preview",
            "source",
            "machine_values",
            "history_events",
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

        id_lookup = self._existing_color_ids(existing_rows, name_column)
        next_color_number = self._next_color_id_number_from_values(id_lookup.values())
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
            if in_single or in_master:
                technical_source = "MPRINT"
            else:
                technical_source = self._technical_color_source(existing.get("source", "") or source)

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
            correction_event = self.import_corrections.get(key)
            cmyk = str(info.get("cmyk", "") or existing.get("CMYK", "")).strip()
            if correction_event and correction_event.get("old_cmyk"):
                cmyk = str(correction_event.get("old_cmyk") or cmyk).strip()
            sk_assignments = self._parse_sk_assignments(existing)
            printed, printed_at, approved, approved_at, transfer = self._color_workflow_from_row(existing, sk_assignments)
            not_printable = self._truthy(existing.get("not_printable", ""))
            not_printable_at = existing.get("not_printable_at", "").strip()
            not_printable_by = existing.get("not_printable_by", "").strip()
            not_printable_reason = existing.get("not_printable_reason", "").strip()
            color_id = existing.get("color_id", "").strip() or id_lookup.get(key, "")
            if not color_id:
                color_id = self._format_color_id(next_color_number)
                next_color_number += 1
            history_events = self._merge_history_events(
                existing.get("history_events", ""),
                printed=printed,
                printed_at=printed_at,
                approved=approved,
                approved_at=approved_at,
                transfer=transfer,
                assignments=sk_assignments,
                not_printable=not_printable,
                not_printable_at=not_printable_at,
                not_printable_by=not_printable_by,
                not_printable_reason=not_printable_reason,
            )
            if correction_event:
                history_events.append(correction_event)
                history_events = self._dedupe_history_events(history_events)
            machine_values = self._machine_values_for_row(
                cmyk,
                technical_source,
                printed=printed,
                approved=approved,
                transfer=transfer,
            )

            output_row = {field: existing.get(field, "") for field in extra_fields}
            output_row.update(
                {
                    "color_id": color_id,
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
                    "sk_assignments": self._dump_sk_assignments(sk_assignments),
                    "printed": "ja" if printed else "nein",
                    "printed_at": printed_at,
                    "approved": "ja" if approved else "nein",
                    "approved_at": approved_at,
                    "transfer": self._dump_transfer(transfer),
                    "not_printable": "ja" if not_printable else "nein",
                    "not_printable_at": not_printable_at,
                    "not_printable_by": not_printable_by,
                    "not_printable_reason": not_printable_reason,
                    "approval_notification_json": existing.get("approval_notification_json", ""),
                    "approval_mail_preview": existing.get("approval_mail_preview", ""),
                    "source": technical_source,
                    "machine_values": self._dump_machine_values(machine_values),
                    "history_events": self._dump_history_events(history_events),
                }
            )
            rows.append(output_row)

        with self.overview_lock:
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            self._backup_color_overview_before_timestamp_migration(csv_path, existing_fields)
            self._backup_color_overview_before_sk_migration(csv_path, existing_fields)
            self._backup_color_overview_before_transfer_migration(csv_path, existing_fields)
            self._backup_color_overview_before_router_migration(csv_path, existing_fields)
            temp_csv = csv_path.with_suffix(csv_path.suffix + ".tmp")
            with temp_csv.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=";")
                writer.writeheader()
                writer.writerows(rows)
            os.replace(temp_csv, csv_path)
            self.logger.log(f"Interne Farbdaten geschrieben: {csv_path}")

            self._write_color_overview_html(html_path, self._visible_overview_rows(rows))
            self._write_color_export(rows)
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
            original_fields = list(fields)
            name_column = self._find_name_column(fields) or "Farbbezeichnung"
            if "Farbbezeichnung" not in fields:
                fields = ["Farbbezeichnung"] + [field for field in fields if field != name_column]
                name_column = "Farbbezeichnung"
            if "Quelle" not in fields:
                fields.append("Quelle")
            for field in (
                "color_id",
                "created_at",
                "last_printed_at",
                "last_synced_at",
                "sk_assignments",
                "printed",
                "printed_at",
                "approved",
                "approved_at",
                "transfer",
                "not_printable",
                "not_printable_at",
                "not_printable_by",
                "not_printable_reason",
                "approval_notification_json",
                "approval_mail_preview",
                "source",
                "machine_values",
                "history_events",
            ):
                if field not in fields:
                    fields.append(field)

            existing_keys = {
                (row.get(name_column) or row.get("Farbbezeichnung") or "").strip().casefold()
                for row in rows
            }
            if cleaned.casefold() not in existing_keys:
                created_at = now_stamp()
                color_id = self._format_color_id(self._next_color_id_number(rows))
                rows.append(
                    {
                        "color_id": color_id,
                        "Farbbezeichnung": cleaned,
                        "Quelle": "Vorstufe",
                        "created_at": created_at,
                        "last_printed_at": "",
                        "last_synced_at": created_at,
                        "sk_assignments": "[]",
                        "printed": "nein",
                        "printed_at": "",
                        "approved": "nein",
                        "approved_at": "",
                        "transfer": self._dump_transfer(self._empty_transfer()),
                        "not_printable": "nein",
                        "not_printable_at": "",
                        "not_printable_by": "",
                        "not_printable_reason": "",
                        "approval_notification_json": "",
                        "approval_mail_preview": "",
                        "source": "PREPRESS",
                        "machine_values": "[]",
                        "history_events": "[]",
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

    def add_sk_assignment(self, color_name: str, sk_number: str) -> dict:
        cleaned_color = self._clean_color_name(color_name)
        cleaned_sk = self._clean_sk_number(sk_number)
        if not cleaned_color:
            return self._api_result(False, "Keine Kundenfarbe übergeben.", 400)
        if not cleaned_sk:
            return self._api_result(False, "Bitte eine SK-Nr. eintragen.", 400)

        def update(row: dict[str, str], assignments: list[dict[str, object]]) -> tuple[bool, str]:
            if any(str(item.get("sk_number", "")).casefold() == cleaned_sk.casefold() for item in assignments):
                return False, f"Diese SK-Nr. ist bei {cleaned_color} bereits eingetragen."
            assignments.append(
                {
                    "sk_number": cleaned_sk,
                    "printed": False,
                    "printed_at": "",
                    "approved": False,
                    "approved_at": "",
                    "template_updated": False,
                    "template_updated_at": "",
                    "portal_informed": False,
                    "transfer_completed": False,
                    "transfer_completed_at": "",
                    "transfer_completed_by": "",
                    "transfer_note": "",
                }
            )
            row["sk_assignments"] = self._dump_sk_assignments(assignments)
            return True, f"{self._sk_label(cleaned_sk)} wurde bei {cleaned_color} hinzugefügt."

        return self._update_sk_assignment(cleaned_color, cleaned_sk, update)

    def mark_sk_printed(self, color_name: str, sk_number: str) -> dict:
        cleaned_color = self._clean_color_name(color_name)
        if not cleaned_color:
            return self._api_result(False, "Keine Kundenfarbe übergeben.", 400)
        return self._update_color_workflow(
            cleaned_color,
            lambda row, assignments: self._set_color_printed(row, assignments),
        )

    def approve_sk_assignment(self, color_name: str, sk_number: str) -> dict:
        cleaned_color = self._clean_color_name(color_name)
        if not cleaned_color:
            return self._api_result(False, "Keine Kundenfarbe übergeben.", 400)
        return self._update_color_workflow(
            cleaned_color,
            lambda row, assignments: self._set_color_approved(row, assignments),
        )

    def mark_template_updated(
        self,
        color_name: str,
        sk_number: str,
        template_updated: bool = False,
        portal_informed: bool = False,
        completed_by: str = "",
        note: str = "",
    ) -> dict:
        cleaned_color = self._clean_color_name(color_name)
        if not cleaned_color:
            return self._api_result(False, "Keine Kundenfarbe übergeben.", 400)
        if not template_updated and not portal_informed:
            return self._api_result(False, "Bitte mindestens eine Übernahmeart auswählen.", 400)
        cleaned_sk = self._clean_sk_number(sk_number)
        if not cleaned_sk:
            return self._api_result(False, "Bitte eine SK-Nr. auswählen.", 400)
        return self._update_sk_assignment(
            cleaned_color,
            cleaned_sk,
            lambda row, assignments: self._set_sk_transfer(
                row,
                assignments,
                sk_number=cleaned_sk,
                template_updated=template_updated,
                portal_informed=portal_informed,
                completed_by=self._clean_color_name(completed_by),
                note=str(note).strip(),
            ),
        )

    def set_color_not_printable(
        self,
        color_name: str,
        reason: str,
        completed_by: str = "",
    ) -> dict:
        cleaned_color = self._clean_color_name(color_name)
        cleaned_reason = str(reason or "").strip()
        if not cleaned_color:
            return self._api_result(False, "Keine Kundenfarbe übergeben.", 400)
        if not cleaned_reason:
            return self._api_result(False, "Bitte einen Grund eintragen.", 400)
        return self._update_color_workflow(
            cleaned_color,
            lambda row, assignments: self._set_not_printable(row, assignments, cleaned_reason, self._clean_color_name(completed_by)),
        )

    def clear_color_not_printable(self, color_name: str, completed_by: str = "") -> dict:
        cleaned_color = self._clean_color_name(color_name)
        if not cleaned_color:
            return self._api_result(False, "Keine Kundenfarbe übergeben.", 400)
        return self._update_color_workflow(
            cleaned_color,
            lambda row, assignments: self._clear_not_printable(row, assignments, self._clean_color_name(completed_by)),
        )

    def add_prepress_note(
        self,
        title: str,
        text: str,
        customer: str = "",
        color_name: str = "",
        sk_number: str = "",
        created_by: str = "",
    ) -> dict:
        cleaned_title = self._clean_color_name(title)
        cleaned_text = str(text or "").strip()
        if not cleaned_title:
            return self._api_result(False, "Bitte einen Titel eintragen.", 400)
        if not cleaned_text:
            return self._api_result(False, "Bitte eine Information eintragen.", 400)
        notes = self._read_prepress_notes()
        now_text = now_stamp()
        note = {
            "id": self._next_prepress_note_id(notes),
            "title": cleaned_title,
            "text": cleaned_text,
            "customer": self._clean_color_name(customer),
            "color": self._clean_color_name(color_name),
            "sk_number": self._clean_sk_number(sk_number),
            "created_at": now_text,
            "created_by": self._clean_color_name(created_by),
            "status": "offen",
            "completed_at": "",
            "completed_by": "",
            "history": [
                {
                    "event": "prepress_note_created",
                    "timestamp": self._event_timestamp(now_text),
                    "user": self._clean_color_name(created_by),
                }
            ],
        }
        notes.append(note)
        self._write_prepress_notes(notes)
        return self._api_result(True, "Vorstufen-Hinweis wurde gespeichert.", 200)

    def complete_prepress_note(self, note_id: str, completed_by: str = "") -> dict:
        cleaned_id = str(note_id or "").strip()
        if not cleaned_id:
            return self._api_result(False, "Kein Hinweis ausgewählt.", 400)
        notes = self._read_prepress_notes()
        for note in notes:
            if str(note.get("id") or "") != cleaned_id:
                continue
            if str(note.get("status") or "") == "erledigt":
                return self._api_result(True, "Vorstufen-Hinweis war bereits übernommen.", 200)
            note["status"] = "erledigt"
            completed_at = now_stamp()
            note["completed_at"] = completed_at
            note["completed_by"] = self._clean_color_name(completed_by)
            history = note.get("history") if isinstance(note.get("history"), list) else []
            history.append(
                {
                    "event": "prepress_note_completed",
                    "timestamp": self._event_timestamp(completed_at),
                    "user": self._clean_color_name(completed_by),
                }
            )
            note["history"] = history
            self._write_prepress_notes(notes)
            return self._api_result(True, "Vorstufen-Hinweis wurde als übernommen markiert.", 200)
        return self._api_result(False, "Vorstufen-Hinweis nicht gefunden.", 404)

    def hide_overview_color(self, color_name: str) -> str:
        cleaned = re.sub(r"\s+", " ", color_name).strip()
        if not cleaned:
            return "Keine Farbbezeichnung übergeben."

        hidden_path = self._hidden_colors_path()
        with self.overview_lock:
            hidden = self._read_hidden_colors()
            if any(item.casefold() == cleaned.casefold() for item in hidden):
                return f"Farbe ist bereits ausgeblendet: {cleaned}"
            self._backup_hidden_colors_before_change(hidden_path, hidden)
            hidden.append(cleaned)
            self._write_hidden_colors(hidden)
            self.logger.log(f"Farbe aus Übersicht ausgeblendet: {cleaned}")

        self.refresh_color_overview()
        return f"Farbe ausgeblendet: {cleaned}"

    def _update_sk_assignment(self, color_name: str, sk_number: str | None, update: callable) -> dict:
        csv_path = self._overview_csv_path()
        changed = False
        result_message = ""
        result_status = 200
        with self.overview_lock:
            rows, fields = self._read_color_overview_with_legacy(csv_path)
            original_fields = list(fields)
            name_column = self._find_name_column(fields) or "Farbbezeichnung"
            if "Farbbezeichnung" not in fields:
                fields = ["Farbbezeichnung"] + [field for field in fields if field != name_column]
                name_column = "Farbbezeichnung"
            if "sk_assignments" not in fields:
                fields.append("sk_assignments")

            target_row = None
            for row in rows:
                raw_name = self._clean_color_name(row.get(name_column) or row.get("Farbbezeichnung") or "")
                if raw_name.casefold() == color_name.casefold():
                    target_row = row
                    break
            if target_row is None:
                return self._api_result(False, f"Kundenfarbe nicht gefunden: {color_name}", 404)

            assignments = self._parse_sk_assignments(target_row)
            target_row["Farbbezeichnung"] = target_row.get(name_column) or target_row.get("Farbbezeichnung") or color_name
            changed, result_message = update(target_row, assignments)
            if not changed:
                result_status = 409 if sk_number else 400
                return self._api_result(False, result_message, result_status)

            self._backup_color_overview_before_sk_migration(csv_path, original_fields)
            target_row["sk_assignments"] = self._dump_sk_assignments(assignments)
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

        self.refresh_color_overview()
        return self._api_result(True, result_message, 200)

    def _update_color_workflow(self, color_name: str, update: callable) -> dict:
        csv_path = self._overview_csv_path()
        with self.overview_lock:
            rows, fields = self._read_color_overview_with_legacy(csv_path)
            original_fields = list(fields)
            name_column = self._find_name_column(fields) or "Farbbezeichnung"
            if "Farbbezeichnung" not in fields:
                fields = ["Farbbezeichnung"] + [field for field in fields if field != name_column]
                name_column = "Farbbezeichnung"
            for field in (
                "printed",
                "printed_at",
                "approved",
                "approved_at",
                "transfer",
                "not_printable",
                "not_printable_at",
                "not_printable_by",
                "not_printable_reason",
                "approval_notification_json",
                "approval_mail_preview",
                "history_events",
                "machine_values",
            ):
                if field not in fields:
                    fields.append(field)

            target_row = None
            assignments: list[dict[str, object]] = []
            for row in rows:
                raw_name = self._clean_color_name(row.get(name_column) or row.get("Farbbezeichnung") or "")
                if raw_name.casefold() == color_name.casefold():
                    target_row = row
                    assignments = self._parse_sk_assignments(row)
                    break
            if target_row is None:
                return self._api_result(False, f"Kundenfarbe nicht gefunden: {color_name}", 404)

            target_row["Farbbezeichnung"] = target_row.get(name_column) or target_row.get("Farbbezeichnung") or color_name
            changed, message = update(target_row, assignments)
            if not changed:
                return self._api_result(False, message, 409)

            self._backup_color_overview_before_transfer_migration(csv_path, original_fields)
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

        self.refresh_color_overview()
        return self._api_result(True, message, 200)

    def _set_color_printed(
        self,
        row: dict[str, str],
        assignments: list[dict[str, object]],
    ) -> tuple[bool, str]:
        printed, printed_at, approved, approved_at, transfer = self._color_workflow_from_row(row, assignments)
        if printed:
            return True, "Farbe ist bereits als gedruckt markiert."
        printed_at = now_stamp()
        row["printed"] = "ja"
        row["printed_at"] = printed_at
        row["last_printed_at"] = printed_at
        row["Gedruckt am"] = printed_at
        row["approved"] = "ja" if approved else "nein"
        row["approved_at"] = approved_at
        row["transfer"] = self._dump_transfer(transfer)
        return True, "Farbe wurde als gedruckt markiert."

    def _set_color_approved(
        self,
        row: dict[str, str],
        assignments: list[dict[str, object]],
    ) -> tuple[bool, str]:
        printed, printed_at, approved, approved_at, transfer = self._color_workflow_from_row(row, assignments)
        if not printed:
            return False, "Die Farbe muss zuerst als gedruckt markiert werden."
        if approved:
            return True, "Farbe ist bereits freigegeben."
        row["printed"] = "ja"
        row["printed_at"] = printed_at or now_stamp()
        row["approved"] = "ja"
        row["approved_at"] = now_stamp()
        row["transfer"] = self._dump_transfer(transfer)
        notification = self._approval_notification_payload(row, assignments)
        row["approval_notification_json"] = json.dumps(notification, ensure_ascii=False, separators=(",", ":"))
        row["approval_mail_preview"] = self._approval_mail_preview(notification)
        events = self._parse_history_events(row.get("history_events", ""))
        events.append(
            {
                "event": "approval",
                "timestamp": self._event_timestamp(str(row.get("approved_at") or "")),
                "user": "Andreas",
                "details": "Benachrichtigung vorbereitet",
            }
        )
        row["history_events"] = self._dump_history_events(events)
        return True, "Farbe wurde freigegeben."

    def _set_sk_transfer(
        self,
        row: dict[str, str],
        assignments: list[dict[str, object]],
        sk_number: str,
        template_updated: bool,
        portal_informed: bool,
        completed_by: str,
        note: str,
    ) -> tuple[bool, str]:
        printed, printed_at, approved, approved_at, transfer = self._color_workflow_from_row(row, assignments)
        if not approved:
            return False, "Die Farbe muss zuerst freigegeben werden."
        assignment = self._find_sk_assignment(assignments, sk_number)
        if assignment is None:
            return False, f"SK nicht gefunden: {sk_number}"
        completed_at = now_stamp()
        assignment["transfer_completed"] = True
        assignment["template_updated"] = bool(template_updated)
        assignment["portal_informed"] = bool(portal_informed)
        assignment["transfer_completed_at"] = completed_at
        assignment["template_updated_at"] = completed_at if template_updated else ""
        assignment["transfer_completed_by"] = completed_by
        assignment["transfer_note"] = note
        row["printed"] = "ja" if printed else "nein"
        row["printed_at"] = printed_at
        row["approved"] = "ja"
        row["approved_at"] = approved_at or now_stamp()
        row["sk_assignments"] = self._dump_sk_assignments(assignments)
        row["transfer"] = self._dump_transfer(self._aggregate_assignment_transfer(assignments, transfer))
        return True, f"Übernahme für SK {sk_number} wurde gespeichert."

    def _set_not_printable(
        self,
        row: dict[str, str],
        assignments: list[dict[str, object]],
        reason: str,
        completed_by: str,
    ) -> tuple[bool, str]:
        timestamp = now_stamp()
        row["not_printable"] = "ja"
        row["not_printable_at"] = timestamp
        row["not_printable_by"] = completed_by
        row["not_printable_reason"] = reason
        events = self._parse_history_events(row.get("history_events", ""))
        events.append(
            {
                "event": "not_printable_set",
                "timestamp": self._event_timestamp(timestamp),
                "user": completed_by,
                "details": reason,
            }
        )
        row["history_events"] = self._dump_history_events(events)
        return True, "Farbe wurde als auf MJET nicht druckbar markiert."

    def _clear_not_printable(
        self,
        row: dict[str, str],
        assignments: list[dict[str, object]],
        completed_by: str,
    ) -> tuple[bool, str]:
        if not self._truthy(row.get("not_printable", "")):
            return True, "Farbe war nicht als nicht druckbar markiert."
        timestamp = now_stamp()
        old_reason = row.get("not_printable_reason", "")
        row["not_printable"] = "nein"
        row["not_printable_at"] = ""
        row["not_printable_by"] = ""
        row["not_printable_reason"] = ""
        events = self._parse_history_events(row.get("history_events", ""))
        events.append(
            {
                "event": "not_printable_cleared",
                "timestamp": self._event_timestamp(timestamp),
                "user": completed_by,
                "details": old_reason,
            }
        )
        row["history_events"] = self._dump_history_events(events)
        return True, "Nicht-druckbar-Markierung wurde aufgehoben."

    def _color_workflow_from_row(
        self,
        row: dict[str, str],
        assignments: list[dict[str, object]],
    ) -> tuple[bool, str, bool, str, dict[str, object]]:
        legacy_printed = any(bool(item.get("printed")) for item in assignments)
        legacy_approved = any(bool(item.get("approved")) for item in assignments)
        legacy_transfer = any(bool(item.get("template_updated")) for item in assignments)
        printed = self._truthy(row.get("printed", "")) or legacy_printed
        approved = self._truthy(row.get("approved", "")) or legacy_approved
        printed_at = str(row.get("printed_at", "") or "")
        approved_at = str(row.get("approved_at", "") or "")
        if not printed_at:
            printed_at = self._first_assignment_time(assignments, "printed_at")
        if not approved_at:
            approved_at = self._first_assignment_time(assignments, "approved_at")
        transfer = self._parse_transfer(row.get("transfer", ""))
        has_assignment_transfer_state = any(bool(item.get("_transfer_state_present")) for item in assignments)
        has_completed_assignment = any(bool(self._assignment_transfer(item).get("completed")) for item in assignments)
        if transfer.get("completed") and assignments and not has_assignment_transfer_state and not has_completed_assignment:
            self._apply_legacy_color_transfer_to_assignments(assignments, transfer)
        elif legacy_transfer and not has_assignment_transfer_state:
            legacy = self._empty_transfer()
            legacy["completed"] = True
            legacy["template_updated"] = True
            legacy["portal_informed"] = False
            legacy["completed_at"] = self._first_assignment_time(assignments, "template_updated_at")
            self._apply_legacy_color_transfer_to_assignments(assignments, legacy)
            transfer = legacy
        transfer = self._aggregate_assignment_transfer(assignments, transfer)
        return printed, printed_at, approved, approved_at, transfer

    def _first_assignment_time(self, assignments: list[dict[str, object]], field: str) -> str:
        for item in assignments:
            value = str(item.get(field) or "").strip()
            if value:
                return value
        return ""

    def _empty_transfer(self) -> dict[str, object]:
        return {
            "completed": False,
            "template_updated": False,
            "portal_informed": False,
            "completed_at": "",
            "completed_by": "",
            "note": "",
        }

    def _parse_transfer(self, raw: object) -> dict[str, object]:
        transfer = self._empty_transfer()
        if isinstance(raw, dict):
            data = raw
        else:
            text = str(raw or "").strip()
            if not text:
                return transfer
            try:
                data = json.loads(text)
            except Exception:
                return transfer
        if not isinstance(data, dict):
            return transfer
        transfer["completed"] = bool(data.get("completed"))
        transfer["template_updated"] = bool(data.get("template_updated"))
        transfer["portal_informed"] = bool(data.get("portal_informed"))
        transfer["completed_at"] = str(data.get("completed_at") or "")
        transfer["completed_by"] = str(data.get("completed_by") or "")
        transfer["note"] = str(data.get("note") or "")
        return transfer

    def _dump_transfer(self, transfer: dict[str, object]) -> str:
        normalized = self._parse_transfer(transfer)
        return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))

    def _truthy(self, value: object) -> bool:
        return str(value).strip().casefold() in {"1", "true", "ja", "yes", "y", "x"}

    def _transfer_method_text(self, transfer: dict[str, object]) -> str:
        template = bool(transfer.get("template_updated"))
        portal = bool(transfer.get("portal_informed"))
        if template and portal:
            return "Vorlage + Portal"
        if template:
            return "Vorlage angepasst"
        if portal:
            return "Portal informiert"
        if transfer.get("completed"):
            return "nicht erfasst"
        return "offen"

    def _apply_legacy_color_transfer_to_assignments(
        self,
        assignments: list[dict[str, object]],
        transfer: dict[str, object],
    ) -> None:
        if not assignments or not transfer.get("completed"):
            return
        for assignment in assignments:
            if assignment.get("transfer_completed"):
                continue
            assignment["transfer_completed"] = True
            assignment["template_updated"] = bool(transfer.get("template_updated"))
            assignment["portal_informed"] = bool(transfer.get("portal_informed"))
            assignment["transfer_completed_at"] = str(transfer.get("completed_at") or "")
            assignment["template_updated_at"] = str(transfer.get("completed_at") or "")
            assignment["transfer_completed_by"] = str(transfer.get("completed_by") or "")
            assignment["transfer_note"] = str(transfer.get("note") or "")

    def _assignment_transfer(self, assignment: dict[str, object]) -> dict[str, object]:
        transfer = self._empty_transfer()
        transfer["completed"] = bool(assignment.get("transfer_completed") or assignment.get("template_updated"))
        transfer["template_updated"] = bool(assignment.get("template_updated"))
        transfer["portal_informed"] = bool(assignment.get("portal_informed"))
        transfer["completed_at"] = str(
            assignment.get("transfer_completed_at") or assignment.get("template_updated_at") or ""
        )
        transfer["completed_by"] = str(assignment.get("transfer_completed_by") or "")
        transfer["note"] = str(assignment.get("transfer_note") or "")
        return transfer

    def _aggregate_assignment_transfer(
        self,
        assignments: list[dict[str, object]],
        fallback: dict[str, object] | None = None,
    ) -> dict[str, object]:
        transfer = self._empty_transfer()
        if not assignments:
            return self._parse_transfer(fallback or transfer)
        completed = [self._assignment_transfer(item) for item in assignments if self._assignment_transfer(item).get("completed")]
        if not completed:
            return transfer
        transfer["completed"] = len(completed) == len(assignments)
        transfer["template_updated"] = any(bool(item.get("template_updated")) for item in completed)
        transfer["portal_informed"] = any(bool(item.get("portal_informed")) for item in completed)
        transfer["completed_at"] = str(completed[-1].get("completed_at") or "")
        transfer["completed_by"] = str(completed[-1].get("completed_by") or "")
        transfer["note"] = str(completed[-1].get("note") or "")
        return transfer

    def _transfer_counts(self, assignments: list[dict[str, object]]) -> tuple[int, int]:
        total = len(assignments)
        completed = sum(1 for item in assignments if self._assignment_transfer(item).get("completed"))
        return completed, total

    def _approval_notification_payload(
        self,
        row: dict[str, str],
        assignments: list[dict[str, object]],
    ) -> dict[str, object]:
        done_count, total_count = self._transfer_counts(assignments)
        return {
            "color_id": str(row.get("color_id") or "").strip(),
            "color_name": str(row.get("Farbbezeichnung") or "").strip(),
            "cmyk": str(row.get("CMYK") or "").strip(),
            "sk_numbers": [
                str(item.get("sk_number") or "")
                for item in assignments
                if str(item.get("sk_number") or "").strip()
            ],
            "approved_at": str(row.get("approved_at") or "").strip(),
            "approved_by": "Andreas",
            "open_templates": max(0, total_count - done_count),
            "prepress_status": "offen" if total_count != done_count else "übernommen",
            "mail_subject": f"MJET Farbfreigabe - {str(row.get('Farbbezeichnung') or '').strip()}",
        }

    def _approval_mail_preview(self, payload: dict[str, object]) -> str:
        sk_numbers = payload.get("sk_numbers") if isinstance(payload.get("sk_numbers"), list) else []
        sk_text = "\n".join(f"- {item}" for item in sk_numbers) if sk_numbers else "- keine SK hinterlegt"
        return (
            f"Betreff: {payload.get('mail_subject', '')}\n\n"
            f"Kundenfarbe:\n{payload.get('color_name', '')}\n\n"
            f"CMYK:\n{payload.get('cmyk', '') or 'nicht erfasst'}\n\n"
            f"Betroffene Eindruckvorlagen:\n{sk_text}\n\n"
            f"Freigegeben:\n{payload.get('approved_at', '') or 'nicht erfasst'}\n\n"
            f"Freigabe:\n{payload.get('approved_by', 'Andreas')}\n\n"
            "Hinweis:\n"
            "Die Farbe wurde an der MJET freigegeben.\n"
            "Bitte betroffene Eindruckvorlagen beziehungsweise Portal-Daten prüfen und aktualisieren."
        )

    def _workflow_history(
        self,
        printed: bool,
        printed_at: str,
        approved: bool,
        approved_at: str,
        assignments: list[dict[str, object]] | None = None,
    ) -> list[str]:
        entries: list[str] = []
        if printed:
            entries.append(f"{printed_at or 'Datum nicht erfasst'} - Gedruckt")
        if approved:
            entries.append(f"{approved_at or 'Datum nicht erfasst'} - Andreas freigegeben")
        for assignment in assignments or []:
            transfer = self._assignment_transfer(assignment)
            if not transfer.get("completed"):
                continue
            method = self._transfer_method_text(transfer)
            at = str(transfer.get("completed_at") or "Datum nicht erfasst")
            sk_number = str(assignment.get("sk_number") or "").strip()
            entries.append(f"{at} - {self._sk_label(sk_number)}: {method}")
        return entries

    def _history_event_lines(self, raw: object) -> list[str]:
        labels = {
            "not_printable_set": "Auf MJET nicht druckbar markiert",
            "not_printable_cleared": "Nicht-druckbar-Status aufgehoben",
            "prepress_note_created": "Vorstufen-Hinweis angelegt",
            "prepress_note_completed": "Vorstufen-Hinweis übernommen",
            "approval": "Andreas freigegeben",
        }
        lines: list[str] = []
        for event in self._parse_history_events(raw):
            label = labels.get(event.get("event", ""), "")
            if not label:
                continue
            timestamp = event.get("timestamp") or "Datum nicht erfasst"
            user = event.get("user") or ""
            details = event.get("details") or ""
            line = f"{timestamp} - {label}"
            if user:
                line += f" ({user})"
            if details:
                line += f": {details}"
            lines.append(line)
        return lines

    def _format_color_id(self, number: int) -> str:
        return f"CLR-{max(1, int(number)):06d}"

    def _next_color_id_number(self, rows: list[dict[str, str]]) -> int:
        highest = 0
        for row in rows:
            match = re.match(r"^CLR-(\d+)$", str(row.get("color_id", "")).strip(), re.IGNORECASE)
            if match:
                highest = max(highest, int(match.group(1)))
        return highest + 1

    def _next_color_id_number_from_values(self, values: object) -> int:
        highest = 0
        for value in values:
            match = re.match(r"^CLR-(\d+)$", str(value).strip(), re.IGNORECASE)
            if match:
                highest = max(highest, int(match.group(1)))
        return highest + 1

    def _existing_color_ids(self, rows: list[dict[str, str]], name_column: str) -> dict[str, str]:
        ids: dict[str, str] = {}
        used: set[str] = set()
        next_number = self._next_color_id_number(rows)
        for row in rows:
            name = self._clean_color_name(row.get(name_column) or row.get("Farbbezeichnung") or "")
            if not name:
                continue
            color_id = str(row.get("color_id", "")).strip()
            if not re.match(r"^CLR-\d+$", color_id, re.IGNORECASE) or color_id in used:
                color_id = self._format_color_id(next_number)
                next_number += 1
            used.add(color_id)
            ids[name.casefold()] = color_id
        return ids

    def _technical_color_source(self, source_text: str) -> str:
        text = str(source_text or "").strip().upper()
        if text in {"MPRINT", "PANTONE_REFERENCE", "HKS_REFERENCE", "PREPRESS"}:
            return text
        if "PANTONE" in text:
            return "PANTONE_REFERENCE"
        if "HKS" in text:
            return "HKS_REFERENCE"
        if "MPRINT" in text:
            return "MPRINT"
        return "PREPRESS"

    def _parse_cmyk_values(self, cmyk: str) -> dict[str, int] | None:
        parts = re.findall(r"-?\d+(?:[.,]\d+)?", str(cmyk or ""))
        if len(parts) < 4:
            return None
        values = [max(0, min(100, int(round(float(part.replace(",", ".")))))) for part in parts[:4]]
        return {"c": values[0], "m": values[1], "y": values[2], "k": values[3]}

    def _machine_values_for_row(
        self,
        cmyk: str,
        source: str,
        printed: bool,
        approved: bool,
        transfer: dict[str, object],
    ) -> list[dict[str, object]]:
        values = self._parse_cmyk_values(cmyk)
        if source != "MPRINT" or values is None:
            return []
        if approved:
            status = "approved"
        elif printed:
            status = "printed"
        elif transfer.get("completed"):
            status = "transfer_completed"
        else:
            status = "pending"
        return [
            {
                "machine": "MJET_X",
                **values,
                "status": status,
            }
        ]

    def _parse_machine_values(self, raw: object) -> list[dict[str, object]]:
        if isinstance(raw, list):
            data = raw
        else:
            text = str(raw or "").strip()
            if not text:
                return []
            try:
                data = json.loads(text)
            except Exception:
                return []
        values: list[dict[str, object]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            cmyk = {
                "c": self._clamp_percent_value(item.get("c", 0)),
                "m": self._clamp_percent_value(item.get("m", 0)),
                "y": self._clamp_percent_value(item.get("y", 0)),
                "k": self._clamp_percent_value(item.get("k", 0)),
            }
            values.append(
                {
                    "machine": str(item.get("machine") or "MJET_X"),
                    **cmyk,
                    "status": str(item.get("status") or "pending"),
                }
            )
        return values

    def _dump_machine_values(self, values: list[dict[str, object]]) -> str:
        return json.dumps(self._parse_machine_values(values), ensure_ascii=False, separators=(",", ":"))

    def _merge_history_events(
        self,
        raw: object,
        printed: bool,
        printed_at: str,
        approved: bool,
        approved_at: str,
        transfer: dict[str, object],
        assignments: list[dict[str, object]] | None = None,
        not_printable: bool = False,
        not_printable_at: str = "",
        not_printable_by: str = "",
        not_printable_reason: str = "",
    ) -> list[dict[str, str]]:
        events = self._parse_history_events(raw)
        if printed:
            events.append({"event": "printed", "timestamp": self._event_timestamp(printed_at), "user": ""})
        if approved:
            events.append({"event": "approved", "timestamp": self._event_timestamp(approved_at), "user": "Andreas"})
        if not_printable:
            events.append(
                {
                    "event": "not_printable_set",
                    "timestamp": self._event_timestamp(not_printable_at),
                    "user": not_printable_by,
                    "details": not_printable_reason,
                }
            )
        for assignment in assignments or []:
            assignment_transfer = self._assignment_transfer(assignment)
            if not assignment_transfer.get("completed"):
                continue
            completed_at = self._event_timestamp(str(assignment_transfer.get("completed_at") or ""))
            user = str(assignment_transfer.get("completed_by") or "")
            sk_number = str(assignment.get("sk_number") or "")
            details = f"SK {sk_number}".strip()
            if assignment_transfer.get("template_updated"):
                events.append({"event": "template_updated", "timestamp": completed_at, "user": user, "details": details})
            if assignment_transfer.get("portal_informed"):
                events.append({"event": "portal_informed", "timestamp": completed_at, "user": user, "details": details})
        if transfer.get("completed") and not assignments:
            completed_at = self._event_timestamp(str(transfer.get("completed_at") or ""))
            user = str(transfer.get("completed_by") or "")
            if transfer.get("template_updated"):
                events.append({"event": "template_updated", "timestamp": completed_at, "user": user})
            if transfer.get("portal_informed"):
                events.append({"event": "portal_informed", "timestamp": completed_at, "user": user})
        return self._dedupe_history_events(events)

    def _parse_history_events(self, raw: object) -> list[dict[str, str]]:
        if isinstance(raw, list):
            data = raw
        else:
            text = str(raw or "").strip()
            if not text:
                return []
            try:
                data = json.loads(text)
            except Exception:
                return []
        events: list[dict[str, str]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            event = str(item.get("event") or "").strip()
            timestamp = self._event_timestamp(str(item.get("timestamp") or ""))
            if not event:
                continue
            events.append(
                {
                    "event": event,
                    "timestamp": timestamp,
                    "user": str(item.get("user") or ""),
                    "details": str(item.get("details") or ""),
                }
            )
        return events

    def _dedupe_history_events(self, events: list[dict[str, str]]) -> list[dict[str, str]]:
        unique: list[dict[str, str]] = []
        seen: set[tuple[str, str, str, str]] = set()
        for event in events:
            key = (
                event.get("event", ""),
                event.get("timestamp", ""),
                event.get("user", ""),
                event.get("details", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(event)
        return unique

    def _dump_history_events(self, events: list[dict[str, str]]) -> str:
        return json.dumps(self._dedupe_history_events(events), ensure_ascii=False, separators=(",", ":"))

    def _event_timestamp(self, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        return text.replace(" ", "T", 1)

    def _clamp_percent_value(self, value: object) -> int:
        try:
            number = int(round(float(str(value).replace(",", "."))))
        except Exception:
            number = 0
        return max(0, min(100, number))

    def _parse_sk_assignments(self, row: dict[str, str]) -> list[dict[str, object]]:
        raw = str(row.get("sk_assignments", "") or row.get("SK-Zuordnungen", "")).strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        assignments: list[dict[str, object]] = []
        seen: set[str] = set()
        for item in data:
            if not isinstance(item, dict):
                continue
            sk_number = self._clean_sk_number(str(item.get("sk_number", "")))
            if not sk_number:
                continue
            transfer_state_present = any(
                key in item
                for key in (
                    "transfer_completed",
                    "transfer_completed_at",
                    "transfer_completed_by",
                    "transfer_note",
                    "portal_informed",
                )
            )
            key = sk_number.casefold()
            if key in seen:
                continue
            seen.add(key)
            assignments.append(
                {
                    "sk_number": sk_number,
                    "printed": bool(item.get("printed")),
                    "printed_at": str(item.get("printed_at") or ""),
                    "approved": bool(item.get("approved")),
                    "approved_at": str(item.get("approved_at") or ""),
                    "template_updated": bool(item.get("template_updated")),
                    "template_updated_at": str(item.get("template_updated_at") or ""),
                    "portal_informed": bool(item.get("portal_informed")),
                    "transfer_completed": bool(item.get("transfer_completed") or item.get("template_updated")),
                    "transfer_completed_at": str(
                        item.get("transfer_completed_at") or item.get("template_updated_at") or ""
                    ),
                    "transfer_completed_by": str(item.get("transfer_completed_by") or ""),
                    "transfer_note": str(item.get("transfer_note") or ""),
                    "_transfer_state_present": transfer_state_present,
                }
            )
        return assignments

    def _dump_sk_assignments(self, assignments: list[dict[str, object]]) -> str:
        cleaned: list[dict[str, object]] = []
        for assignment in assignments:
            cleaned.append({key: value for key, value in assignment.items() if not str(key).startswith("_")})
        return json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"))

    def _find_sk_assignment(
        self,
        assignments: list[dict[str, object]],
        sk_number: str,
    ) -> dict[str, object] | None:
        for assignment in assignments:
            if str(assignment.get("sk_number", "")).casefold() == sk_number.casefold():
                return assignment
        return None

    def _clean_color_name(self, value: str) -> str:
        return re.sub(r"\s+", " ", str(value)).strip()

    def _clean_sk_number(self, value: str) -> str:
        return re.sub(r"\s+", " ", str(value)).strip()

    def _sk_label(self, value: str) -> str:
        cleaned = self._clean_sk_number(value)
        if not cleaned:
            return "SK"
        if cleaned.casefold().startswith("sk"):
            return cleaned
        return f"SK {cleaned}"

    def _short_text(self, value: str, limit: int = 160) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 5)].rstrip() + " ..."

    def _api_result(self, ok: bool, message: str, status: int = 200) -> dict:
        return {"ok": ok, "message": message, "status": status}

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

    def _backup_color_overview_before_sk_migration(
        self,
        csv_path: Path,
        existing_fields: list[str],
    ) -> None:
        if not csv_path.exists():
            return
        if "sk_assignments" in set(existing_fields):
            return
        backup_path = csv_path.with_name(
            f"{csv_path.stem}_backup_vor_sk_workflow_migration_{filename_stamp()}{csv_path.suffix}"
        )
        try:
            shutil.copy2(csv_path, backup_path)
            self.logger.log(f"Backup vor SK-Workflow-Migration geschrieben: {backup_path}")
        except Exception as exc:
            self.logger.log(f"Backup vor SK-Workflow-Migration fehlgeschlagen: {exc}", "WARN")

    def _backup_color_overview_before_transfer_migration(
        self,
        csv_path: Path,
        existing_fields: list[str],
    ) -> None:
        if not csv_path.exists():
            return
        required = {"printed", "approved", "transfer"}
        if required.issubset(set(existing_fields)):
            return
        backup_path = csv_path.with_name(
            f"{csv_path.stem}_backup_vor_transfer_workflow_migration_{filename_stamp()}{csv_path.suffix}"
        )
        try:
            shutil.copy2(csv_path, backup_path)
            self.logger.log(f"Backup vor Übernahme-Workflow-Migration geschrieben: {backup_path}")
        except Exception as exc:
            self.logger.log(f"Backup vor Übernahme-Workflow-Migration fehlgeschlagen: {exc}", "WARN")

    def _backup_color_overview_before_router_migration(
        self,
        csv_path: Path,
        existing_fields: list[str],
    ) -> None:
        if not csv_path.exists():
            return
        required = {"color_id", "source", "machine_values", "history_events"}
        if required.issubset(set(existing_fields)):
            return
        backup_path = csv_path.with_name(
            f"{csv_path.stem}_backup_vor_router_export_migration_{filename_stamp()}{csv_path.suffix}"
        )
        try:
            shutil.copy2(csv_path, backup_path)
            self.logger.log(f"Backup vor Router-Export-Migration geschrieben: {backup_path}")
        except Exception as exc:
            self.logger.log(f"Backup vor Router-Export-Migration fehlgeschlagen: {exc}", "WARN")

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
            candidate, _errors, _warnings = self._single_color_candidate_from_file(color_file)
            if candidate is None:
                continue
            key = self._normalized_color_key(candidate.name)
            existing = info_by_key.get(key)
            if existing and float(existing.get("mtime", "0") or 0) > candidate.mtime:
                continue
            info_by_key[key] = {
                "name": candidate.name,
                "cmyk": self._color_entry_cmyk(candidate.entry),
                "mtime": str(candidate.mtime),
                "source_file": candidate.source_file.name,
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

    def export_color_records(self) -> list[dict[str, object]]:
        rows, _fields = self._read_color_overview_with_legacy(self._overview_csv_path())
        return self._color_export_records(rows)

    def _color_export_path(self) -> Path:
        configured = str(self.config.get("color_export_json", "")).strip()
        if not configured:
            return APP_DIR / "export" / "mprint_colors.json"
        path = Path(configured)
        if path.is_absolute() or re.match(r"^[A-Za-z]:[\\/]", configured):
            return path
        return APP_DIR / path

    def _write_color_export(self, rows: list[dict[str, str]]) -> None:
        export_path = self._color_export_path()
        try:
            export_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = export_path.with_suffix(export_path.suffix + ".tmp")
            temp_path.write_text(
                json.dumps(self._color_export_records(rows), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(temp_path, export_path)
            self.logger.log(f"Farb-Export geschrieben: {export_path}")
        except Exception as exc:
            self.logger.log(f"Farb-Export konnte nicht geschrieben werden: {exc}", "WARN")

    def _color_export_records(self, rows: list[dict[str, str]]) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for row in rows:
            assignments = self._parse_sk_assignments(row)
            printed, printed_at, approved, approved_at, transfer = self._color_workflow_from_row(row, assignments)
            cmyk = self._parse_cmyk_values(str(row.get("CMYK", "")))
            source = self._technical_color_source(row.get("source") or row.get("Quelle", ""))
            machine_values = self._parse_machine_values(row.get("machine_values", ""))
            if not machine_values:
                machine_values = self._machine_values_for_row(
                    str(row.get("CMYK", "")),
                    source,
                    printed=printed,
                    approved=approved,
                    transfer=transfer,
                )
            history = self._merge_history_events(
                row.get("history_events", ""),
                printed=printed,
                printed_at=printed_at,
                approved=approved,
                approved_at=approved_at,
                transfer=transfer,
                assignments=assignments,
            )
            records.append(
                {
                    "color_id": str(row.get("color_id", "")).strip(),
                    "name": str(row.get("Farbbezeichnung", "")).strip(),
                    "source": source,
                    "cmyk": cmyk or {"c": None, "m": None, "y": None, "k": None},
                    "status": {
                        "printed": bool(printed),
                        "approved": bool(approved),
                        "transfer_completed": bool(transfer.get("completed")),
                        "not_printable": self._truthy(row.get("not_printable", "")),
                    },
                    "not_printable": {
                        "active": self._truthy(row.get("not_printable", "")),
                        "reason": str(row.get("not_printable_reason", "")).strip(),
                        "at": str(row.get("not_printable_at", "")).strip(),
                        "by": str(row.get("not_printable_by", "")).strip(),
                    },
                    "affected_templates": [
                        str(item.get("sk_number", ""))
                        for item in assignments
                        if str(item.get("sk_number", "")).strip()
                    ],
                    "machine_values": machine_values,
                    "history": history,
                    "approval_notification": self._parse_json_object(row.get("approval_notification_json", "")),
                    "approval_mail_preview": str(row.get("approval_mail_preview", "")),
                }
            )
        return records

    def _parse_json_object(self, raw: object) -> dict[str, object]:
        text = str(raw or "").strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _hidden_colors_path(self) -> Path:
        configured = str(self.config.get("hidden_colors_json", "")).strip()
        if not configured:
            return APP_DIR / "config" / "hidden_colors.json"
        path = Path(configured)
        if path.is_absolute() or re.match(r"^[A-Za-z]:[\\/]", configured):
            return path
        return APP_DIR / path

    def _prepress_notes_path(self) -> Path:
        configured = str(self.config.get("prepress_notes_json", "")).strip()
        if not configured:
            return APP_DIR / "work" / "prepress_notes.json"
        path = Path(configured)
        if path.is_absolute() or re.match(r"^[A-Za-z]:[\\/]", configured):
            return path
        return APP_DIR / path

    def _read_prepress_notes(self) -> list[dict[str, str]]:
        path = self._prepress_notes_path()
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        notes: list[dict[str, str]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            note = {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or ""),
                "text": str(item.get("text") or ""),
                "customer": str(item.get("customer") or ""),
                "color": str(item.get("color") or ""),
                "sk_number": str(item.get("sk_number") or ""),
                "created_at": str(item.get("created_at") or ""),
                "created_by": str(item.get("created_by") or ""),
                "status": str(item.get("status") or "offen"),
                "completed_at": str(item.get("completed_at") or ""),
                "completed_by": str(item.get("completed_by") or ""),
                "history": item.get("history") if isinstance(item.get("history"), list) else [],
            }
            if note["id"] and note["title"]:
                notes.append(note)
        return notes

    def _write_prepress_notes(self, notes: list[dict[str, str]]) -> None:
        path = self._prepress_notes_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, path)

    def _next_prepress_note_id(self, notes: list[dict[str, str]]) -> str:
        highest = 0
        for note in notes:
            match = re.match(r"^NOTE-(\d+)$", str(note.get("id") or ""), re.IGNORECASE)
            if match:
                highest = max(highest, int(match.group(1)))
        return f"NOTE-{highest + 1:06d}"

    def _read_hidden_colors(self) -> list[str]:
        path = self._hidden_colors_path()
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.logger.log(f"Ausblend-Liste konnte nicht gelesen werden: {exc}", "WARN")
            return []
        raw_items = payload.get("hidden_colors", []) if isinstance(payload, dict) else []
        if not isinstance(raw_items, list):
            return []
        hidden: list[str] = []
        seen: set[str] = set()
        for item in raw_items:
            value = self._clean_color_name(str(item))
            key = value.casefold()
            if not value or key in seen:
                continue
            seen.add(key)
            hidden.append(value)
        return hidden

    def _write_hidden_colors(self, hidden: list[str]) -> None:
        path = self._hidden_colors_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in hidden:
            value = self._clean_color_name(str(item))
            key = value.casefold()
            if not value or key in seen:
                continue
            seen.add(key)
            cleaned.append(value)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps({"hidden_colors": cleaned}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temp_path, path)

    def _backup_hidden_colors_before_change(self, hidden_path: Path, hidden: list[str]) -> None:
        hidden_path.parent.mkdir(parents=True, exist_ok=True)
        backup_path = hidden_path.with_name(
            f"{hidden_path.stem}_backup_vor_aenderung_{filename_stamp()}{hidden_path.suffix}"
        )
        try:
            if hidden_path.exists():
                shutil.copy2(hidden_path, backup_path)
            else:
                backup_path.write_text(
                    json.dumps({"hidden_colors": hidden}, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            self.logger.log(f"Backup vor Ausblend-Änderung geschrieben: {backup_path}")
        except Exception as exc:
            self.logger.log(f"Backup vor Ausblend-Änderung fehlgeschlagen: {exc}", "WARN")

    def _visible_overview_rows(self, rows: list[dict[str, str]]) -> list[dict[str, str]]:
        hidden = self._read_hidden_colors()
        if not hidden:
            return rows
        return [
            row
            for row in rows
            if not self._is_hidden_color(str(row.get("Farbbezeichnung", "")), hidden)
        ]

    def _is_hidden_color(self, color_name: str, hidden: list[str]) -> bool:
        normalized = self._clean_color_name(color_name).casefold()
        if not normalized:
            return False
        for rule in hidden:
            pattern = self._clean_color_name(rule).casefold()
            if not pattern:
                continue
            if "*" in pattern and fnmatch.fnmatchcase(normalized, pattern):
                return True
            if normalized == pattern:
                return True
        return False

    def _prepress_notes_html(self, notes: list[dict[str, str]]) -> str:
        if not notes:
            return "<p class=\"muted\">Noch keine Vorstufen-Hinweise.</p>"
        items: list[str] = []
        for note in notes:
            note_id = html.escape(str(note.get("id") or ""), quote=True)
            title = html.escape(str(note.get("title") or "Ohne Titel"))
            text = html.escape(str(note.get("text") or ""))
            customer = html.escape(str(note.get("customer") or ""))
            color = html.escape(str(note.get("color") or ""))
            sk_number = html.escape(str(note.get("sk_number") or ""))
            created_at = html.escape(str(note.get("created_at") or "nicht erfasst"))
            created_by = html.escape(str(note.get("created_by") or ""))
            completed_at = html.escape(str(note.get("completed_at") or ""))
            completed_by = html.escape(str(note.get("completed_by") or ""))
            done = str(note.get("status") or "").casefold() == "erledigt"
            meta_parts = []
            if customer:
                meta_parts.append(f"Kunde: {customer}")
            if color:
                meta_parts.append(f"Farbe: {color}")
            if sk_number:
                meta_parts.append(f"SK: {sk_number}")
            meta = " · ".join(meta_parts)
            done_text = f"✓ übernommen {completed_at}" if done else "offen"
            if done and completed_by:
                done_text += f" · {completed_by}"
            action = "" if done else f"<button type=\"button\" class=\"completePrepressNote\" data-note-id=\"{note_id}\">Als übernommen markieren</button>"
            items.append(
                f"<div class=\"prepressNote {'done' if done else 'open'}\" data-note-id=\"{note_id}\">"
                f"<strong>{title}</strong>"
                f"<p>{text}</p>"
                f"<div class=\"skMeta\">{meta if meta else 'kein direkter Farb-/SK-Bezug'}</div>"
                f"<div class=\"skMeta\">Erstellt: {created_at}{' · ' + created_by if created_by else ''}</div>"
                f"<div class=\"prepressNoteStatus\">{html.escape(done_text)}</div>"
                f"{action}"
                "</div>"
            )
        return "".join(items)

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
        hide_url = submit_url.rsplit("/", 1)[0] + "/farbe-ausblenden"
        status_url = submit_url.rsplit("/", 1)[0] + "/status"
        sk_add_url = submit_url.rsplit("/", 1)[0] + "/sk-hinzufuegen"
        sk_printed_url = submit_url.rsplit("/", 1)[0] + "/sk-gedruckt"
        sk_approved_url = submit_url.rsplit("/", 1)[0] + "/sk-freigeben"
        sk_template_url = submit_url.rsplit("/", 1)[0] + "/sk-uebernommen"
        not_printable_url = submit_url.rsplit("/", 1)[0] + "/farbe-nicht-druckbar"
        prepress_note_url = submit_url.rsplit("/", 1)[0] + "/vorstufen-hinweis"
        prepress_note_done_url = submit_url.rsplit("/", 1)[0] + "/vorstufen-hinweis-erledigt"
        submit_url_json = json.dumps(submit_url)
        hide_url_json = json.dumps(hide_url)
        status_url_json = json.dumps(status_url)
        sk_add_url_json = json.dumps(sk_add_url)
        sk_printed_url_json = json.dumps(sk_printed_url)
        sk_approved_url_json = json.dumps(sk_approved_url)
        sk_template_url_json = json.dumps(sk_template_url)
        not_printable_url_json = json.dumps(not_printable_url)
        prepress_note_url_json = json.dumps(prepress_note_url)
        prepress_note_done_url_json = json.dumps(prepress_note_done_url)
        body_rows = []
        open_print_tests = 0
        open_approvals = 0
        open_template_updates = 0
        prepress_notes = self._read_prepress_notes()
        prepress_note_html = self._prepress_notes_html(prepress_notes)
        preview_mode = bool(self.config.get("ui_preview_mode"))
        preview_banner = (
            "<div class=\"previewBanner\">UI PREVIEW - keine Produktionsdaten</div>"
            if preview_mode
            else ""
        )
        machine_sort: dict[int, int] = {}
        sort_items: list[tuple[int, str, int]] = []
        for index, row in enumerate(rows):
            name = str(row.get("Farbbezeichnung", ""))
            assignments = self._parse_sk_assignments(row)
            printed, _printed_at, approved, _approved_at, _transfer = self._color_workflow_from_row(row, assignments)
            not_printable = self._truthy(row.get("not_printable", ""))
            transfer_done_count, transfer_total_count = self._transfer_counts(assignments)
            transfer_done = transfer_total_count > 0 and transfer_done_count == transfer_total_count
            if not_printable:
                group = 4
            elif not printed:
                group = 1
            elif transfer_done:
                group = 3
            else:
                group = 2
            sort_items.append((group, name.casefold(), index))
        for order_index, (_group, _name, original_index) in enumerate(sorted(sort_items), start=1):
            machine_sort[original_index] = order_index
        for row_index, row in enumerate(rows):
            name = str(row.get("Farbbezeichnung", ""))
            status = row.get("Status", "")
            angelegt_am = str(row.get("Angelegt am", ""))
            gedruckt_am = str(row.get("Gedruckt am", ""))
            abgeglichen_am = str(row.get("Abgeglichen am", "") or row.get("Letzter Abgleich", ""))
            cmyk = str(row.get("CMYK", ""))
            assignments = self._parse_sk_assignments(row)
            printed, printed_at, approved, approved_at, transfer = self._color_workflow_from_row(row, assignments)
            not_printable = self._truthy(row.get("not_printable", ""))
            not_printable_reason = str(row.get("not_printable_reason", "") or "").strip()
            not_printable_at = str(row.get("not_printable_at", "") or "").strip()
            not_printable_by = str(row.get("not_printable_by", "") or "").strip()
            transfer_done_count, transfer_total_count = self._transfer_counts(assignments)
            transfer_done = transfer_total_count > 0 and transfer_done_count == transfer_total_count
            if not printed and not not_printable:
                open_print_tests += 1
            if printed and not approved and not not_printable:
                open_approvals += 1
            if approved and not not_printable:
                open_template_updates += max(0, transfer_total_count - transfer_done_count)
            if not_printable:
                css = "blocked"
            elif "druckbar" in status:
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
            escaped_cmyk = html.escape(cmyk or "nicht erfasst")
            escaped_not_printable_reason = html.escape(not_printable_reason or "kein Grund erfasst")
            escaped_not_printable_reason_short = html.escape(self._short_text(not_printable_reason or "kein Grund erfasst", 170))
            escaped_not_printable_at = html.escape(not_printable_at or "nicht erfasst")
            escaped_not_printable_by = html.escape(not_printable_by or "nicht erfasst")
            button_name = html.escape(name, quote=True)
            button_cmyk = html.escape(cmyk, quote=True)
            button_not_printable_reason = html.escape(not_printable_reason, quote=True)
            search_parts = [name, cmyk]
            sk_state = []
            for assignment in assignments:
                search_parts.append(str(assignment.get("sk_number") or ""))
                assignment_transfer = self._assignment_transfer(assignment)
                sk_state.append(
                    {
                        "sk": str(assignment.get("sk_number") or ""),
                        "completed": bool(assignment_transfer.get("completed")),
                        "method": self._transfer_method_text(assignment_transfer),
                        "at": str(assignment_transfer.get("completed_at") or ""),
                        "by": str(assignment_transfer.get("completed_by") or ""),
                        "note": str(assignment_transfer.get("note") or ""),
                    }
                )
            sk_state_attr = html.escape(json.dumps(sk_state, ensure_ascii=False), quote=True)
            search_attr = html.escape(" ".join(search_parts), quote=True)
            if not_printable:
                print_summary = "<span class=\"statusLine idle\">○ zurückgestellt</span>"
            elif printed:
                print_summary = (
                    "<div class=\"printDecision\">"
                    "<span class=\"printChoice printable active\">✓ Druckbar</span>"
                    f"<button type=\"button\" class=\"printChoice notPrintable workflow\" data-action=\"notPrintable\" "
                    f"data-color=\"{button_name}\" data-cmyk=\"{button_cmyk}\" "
                    f"data-sk-state=\"{sk_state_attr}\">Nicht druckbar</button>"
                    "</div>"
                )
            else:
                print_summary = (
                    "<div class=\"printDecision\">"
                    f"<button type=\"button\" class=\"printChoice printable workflow\" data-action=\"printed\" "
                    f"data-color=\"{button_name}\" data-cmyk=\"{button_cmyk}\">Druckbar</button>"
                    f"<button type=\"button\" class=\"printChoice notPrintable workflow\" data-action=\"notPrintable\" "
                    f"data-color=\"{button_name}\" data-cmyk=\"{button_cmyk}\" "
                    f"data-sk-state=\"{sk_state_attr}\">Nicht druckbar</button>"
                    "</div>"
                )
            if not_printable:
                approval_summary = "<span class=\"statusLine idle\">○ zurückgestellt</span>"
            elif approved:
                approval_summary = (
                    "<span class=\"statusLine done\" title=\"Prüfung abgeschlossen\">"
                    "<span class=\"machineApproval\">✓</span>"
                    "<span class=\"detailApproval\">✓ Andreas</span>"
                    "</span>"
                )
            elif printed:
                approval_summary = (
                    f"<button type=\"button\" class=\"workflow warn\" data-action=\"approve\" "
                    f"data-color=\"{button_name}\" data-cmyk=\"{button_cmyk}\">Andreas freigeben</button>"
                )
            else:
                approval_summary = "<span class=\"statusLine idle\" title=\"Prüfung offen\"><span class=\"machineApproval\">○</span><span class=\"detailApproval\">○ offen</span></span>"
            if not_printable:
                template_summary = "<div class=\"machineTransferSummary idle\">○ zurückgestellt</div><div class=\"transferSummary idle\">Workflow zurückgestellt</div>"
            elif approved:
                transfer_class = "done" if transfer_done else "open"
                open_transfer_count = max(0, transfer_total_count - transfer_done_count)
                transfer_text = f"{transfer_done_count} / {transfer_total_count} Vorlagen übernommen"
                machine_transfer_text = (
                    "✓"
                    if transfer_done
                    else ("○" if transfer_total_count == 0 else f"○ {open_transfer_count}")
                )
                machine_transfer_title = (
                    "Alle Vorlagen übernommen"
                    if transfer_done
                    else ("Vorlagen offen" if transfer_total_count == 0 else f"{open_transfer_count} Vorlagen offen")
                )
                template_summary = (
                    f"<div class=\"transferSummary {transfer_class}\">{html.escape(transfer_text)}</div>"
                    f"<div class=\"machineTransferSummary {transfer_class}\" title=\"{html.escape(machine_transfer_title, quote=True)}\">{html.escape(machine_transfer_text)}</div>"
                    f"<button type=\"button\" class=\"workflow danger\" data-action=\"template\" "
                    f"data-color=\"{button_name}\" data-cmyk=\"{button_cmyk}\" "
                    f"data-sk-state=\"{sk_state_attr}\" data-open-count=\"{open_transfer_count}\">"
                    "Übernahmen verwalten</button>"
                )
            else:
                template_summary = (
                    f"<div class=\"transferSummary idle\">0 / {transfer_total_count} Vorlagen übernommen</div>"
                    "<div class=\"machineTransferSummary idle\" title=\"Vorlagen offen\">○</div>"
                )
            history_entries = self._workflow_history(printed, printed_at, approved, approved_at, assignments)
            history_entries.extend(self._history_event_lines(row.get("history_events", "")))
            history_html = "<br>".join(html.escape(item) for item in history_entries)
            if not history_html:
                history_html = "noch keine Workflow-Historie"
            if assignments:
                detail_items = []
                for assignment in assignments:
                    raw_sk_number = str(assignment.get("sk_number", ""))
                    sk_number = html.escape(raw_sk_number)
                    sk_label = html.escape(self._sk_label(raw_sk_number))
                    assignment_transfer = self._assignment_transfer(assignment)
                    if assignment_transfer.get("completed"):
                        sk_status = (
                            f"<span class=\"statusLine done\">✓ übernommen</span>"
                            f"<div class=\"skMeta\">{html.escape(self._transfer_method_text(assignment_transfer))}"
                            f" · {html.escape(str(assignment_transfer.get('completed_at') or 'Datum nicht erfasst'))}</div>"
                        )
                    else:
                        sk_status = "<span class=\"statusLine open\">○ Übernahme offen</span>"
                    detail_items.append(
                        "<div class=\"skItem\">"
                        f"<strong>{sk_label}</strong>"
                        f"{sk_status}"
                        "</div>"
                    )
                sk_html = (
                    f"<details class=\"skDetails\"><summary><span class=\"machineSkSummary\">Vorlagen {len(assignments)}</span><span class=\"detailSkSummary\">{len(assignments)} Eindruckvorlage(n)</span></summary>"
                    f"{''.join(detail_items)}</details>"
                )
            else:
                sk_html = "<span class=\"muted skEmpty\">Vorlagen 0</span>"
            sk_button_html = (
                "<span class=\"templateButtonLabel\">Vorlagen</span>"
                f"<span class=\"templateButtonCount\">{len(assignments)}</span>"
                + ("<span class=\"templateButtonPlus\">+</span>" if not assignments else "")
            )
            sk_button = (
                f"<button type=\"button\" class=\"addSk skPanelButton\" data-color=\"{button_name}\" "
                f"data-cmyk=\"{button_cmyk}\" data-sk-state=\"{sk_state_attr}\">{sk_button_html}</button>"
            )
            not_printable_banner = ""
            clear_not_printable_button = ""
            if not_printable:
                not_printable_banner = (
                    "<div class=\"notPrintableBanner\">✕ NICHT DRUCKBAR</div>"
                    f"<div class=\"notPrintableCardReason\">{escaped_not_printable_reason_short}</div>"
                )
                reason_detail_button = (
                    f"<br><button type=\"button\" class=\"reasonButton\" data-reason=\"{button_not_printable_reason}\">Grund anzeigen</button>"
                )
                clear_not_printable_button = (
                    f"<br><button type=\"button\" class=\"workflow clearNotPrintable\" data-action=\"clearNotPrintable\" "
                    f"data-color=\"{button_name}\" data-cmyk=\"{button_cmyk}\">Nicht-druckbar-Status aufheben</button>"
                )
            else:
                reason_detail_button = ""
            body_rows.append(
                f"<tr class=\"{css}\" style=\"--machine-order:{machine_sort.get(row_index, row_index + 1)}\" data-color-search=\"{search_attr}\">"
                f"<td><span class=\"dot\" aria-hidden=\"true\"></span></td>"
                f"<td class=\"name\"><span class=\"customerGlow\" data-cmyk=\"{button_cmyk}\" title=\"{button_name} · {button_cmyk}\" aria-hidden=\"true\"></span><span class=\"colorNameText\" title=\"{button_name}\">{escaped_name}</span><span class=\"machineCmyk\" title=\"{button_cmyk}\">{escaped_cmyk}</span>{not_printable_banner}</td>"
                f"<td><button type=\"button\" class=\"copy\" data-name=\"{button_name}\">Kopieren</button></td>"
                f"<td class=\"cmykCell\">{escaped_cmyk}</td>"
                f"<td class=\"printCell\">{print_summary}</td>"
                f"<td class=\"skCell\">{sk_html}{sk_button}</td>"
                f"<td class=\"approvalCell\">{approval_summary}</td>"
                f"<td class=\"transferCell\">{template_summary}</td>"
                f"<td class=\"history\"><strong>Historie</strong><br>{history_html}<br><span title=\"Angelegt am\">Angelegt: {escaped_angelegt_am}</span><br><span title=\"Abgeglichen am\">Abgleich: {escaped_abgeglichen_am}</span><br><span class=\"notPrintableReason\"><strong>Nicht druckbar:</strong> {escaped_not_printable_reason}<br>Markiert: {escaped_not_printable_at}<br>Von: {escaped_not_printable_by}</span>{reason_detail_button}{clear_not_printable_button}</td>"
                f"<td class=\"adminOnly\"><button type=\"button\" class=\"hideColor\" data-name=\"{button_name}\">Ausblenden</button></td>"
                f"</tr>"
            )

        summary_html = (
            f"<button type=\"button\" class=\"summaryPill\" data-filter=\"print\"><strong>{open_print_tests}</strong><span>Drucke offen</span></button>"
            f"<button type=\"button\" class=\"summaryPill\" data-filter=\"approval\"><strong>{open_approvals}</strong><span>Prüfungen offen</span></button>"
            f"<button type=\"button\" class=\"summaryPill\" data-filter=\"template\"><strong>{open_template_updates}</strong><span>Vorlagen offen</span></button>"
        )

        document = f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <title>MPRINT Farbübersicht</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; color: #20242a; background: #f4f5f6; }}
    h1 {{ margin: 0 0 6px; font-size: 25px; }}
    .meta {{ margin: 0 0 12px; color: #626b75; font-size: 13px; }}
    .previewBanner {{ display: inline-flex; margin: 0 0 14px; padding: 7px 10px; background: #fff4cc; color: #6b4d00; border: 1px solid #e5ca72; font-weight: 800; font-size: 13px; }}
    .topBar {{ display: grid; grid-template-columns: minmax(280px, 760px); gap: 14px; align-items: end; margin: 0 0 14px; }}
    .searchBar {{ display: flex; flex-direction: column; gap: 6px; }}
    .searchBar label {{ color: #1d3348; font-weight: 800; font-size: 14px; }}
    .searchBar input {{ font-size: 20px; padding: 14px 16px; }}
    .viewControls {{ margin: 0 0 16px; }}
    .viewToggle {{ min-width: 155px; }}
    .summary {{ display: grid; grid-template-columns: repeat(3, minmax(150px, 1fr)); gap: 10px; margin: 0 0 14px; max-width: 760px; }}
    .summaryPill {{ display: flex; align-items: baseline; gap: 8px; padding: 12px 14px; background: #fff; border-color: #d1d6dc; text-align: left; }}
    .summaryPill strong {{ font-size: 22px; color: #20242a; }}
    .summaryPill span {{ color: #626b75; }}
    .entry {{ display: flex; gap: 8px; margin: 0 0 10px; max-width: 720px; }}
    input {{ flex: 1; padding: 10px 12px; border: 1px solid #c8cdd3; font-size: 15px; }}
    button {{ border: 1px solid #b7c0ca; background: #d8e1ec; color: #1d3348; padding: 9px 12px; cursor: pointer; font-weight: 600; }}
    button:hover {{ background: #c7d5e5; }}
    .connection {{ display: inline-flex; align-items: center; gap: 8px; margin: 0 0 16px; color: #626b75; font-size: 13px; }}
    .connection::before {{ content: ""; width: 10px; height: 10px; border-radius: 50%; background: #8c939b; }}
    .connection.ok::before {{ background: #2f8f4e; }}
    .connection.down::before {{ background: #bd3f3f; }}
    .connection.checking::before {{ background: #c9901a; }}
    #entryStatus {{ margin: -8px 0 16px; color: #626b75; min-height: 20px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; box-shadow: 0 0 0 1px #c8cdd3; }}
    .noResults {{ display: none; margin: 12px 0 0; color: #626b75; font-weight: 700; }}
    .noResults.visible {{ display: block; }}
    th, td {{ padding: 9px 10px; border-bottom: 1px solid #dfe3e7; text-align: left; font-size: 14px; vertical-align: top; }}
    th {{ background: #e7e9ec; }}
    tr[hidden] {{ display: none !important; }}
    th.indicator, td:first-child {{ width: 34px; text-align: center; }}
    .name {{ font-weight: 600; }}
    .copy, .addSk, .workflow {{ padding: 6px 9px; font-size: 12px; }}
    .addSk {{ margin-top: 7px; margin-right: 6px; }}
    td:nth-child(4), td:nth-child(5), td:nth-child(7), td:nth-child(8), .history {{ color: #626b75; white-space: nowrap; }}
    details summary {{ cursor: pointer; color: #1d3348; font-weight: 700; }}
    .skItem {{ padding: 7px 0; border-top: 1px solid #eef1f4; }}
    .skItem strong {{ display: block; margin-bottom: 4px; }}
    .skMeta {{ color: #626b75; font-size: 12px; margin-top: 3px; }}
    .transferSummary {{ font-weight: 800; margin-bottom: 7px; }}
    .transferSummary.done {{ color: #2f8f4e; }}
    .transferSummary.open {{ color: #c9901a; }}
    .printDecision {{ display: inline-flex; flex-wrap: wrap; gap: 7px; }}
    .printChoice {{ border-radius: 999px; padding: 7px 10px; border: 1px solid #cfd5dc; background: rgba(255,255,255,0.62); color: #4b5560; font-weight: 800; }}
    .printChoice.printable.active {{ border-color: #a7bfae; background: #ffffff; color: #23382a; }}
    .printChoice.notPrintable {{ border-color: #d8d0d0; background: rgba(255,255,255,0.52); color: #5f4646; }}
    .printChoice.notPrintable.active {{ border-color: #c8a6a6; background: #fffafa; color: #6b3030; }}
    .printChoice.active {{ box-shadow: 0 1px 3px rgba(32,36,42,0.08); }}
    .notPrintableBanner {{ display: inline-flex; align-items: center; margin-top: 10px; padding: 0; background: transparent; color: #6d5555; border: 0; font-size: 14px; font-weight: 900; }}
    .notPrintableCardReason {{ margin-top: 7px; color: #776b6b; font-size: 13px; line-height: 1.35; font-weight: 600; }}
    .reasonButton {{ margin-left: 8px; padding: 5px 8px; font-size: 12px; background: #f8eeee; color: #7a1f1f; }}
    .notPrintableReason {{ display: none; margin-top: 8px; color: #7a1f1f; white-space: normal; }}
    tr.blocked .notPrintableReason {{ display: inline-block; }}
    .customerGlow {{ display: none; }}
    .cornerCmyk {{ display: none; }}
    .machineCmyk, .machineApproval {{ display: none; }}
    .badge {{ display: inline-block; padding: 5px 8px; border: 1px solid #c8cdd3; background: #eef1f4; font-size: 12px; font-weight: 700; }}
    .badge.done {{ border-color: #2f8f4e; background: #e3f0e7; color: #1f5c35; }}
    .badge.idle {{ color: #626b75; }}
    .workflow.warn {{ background: #f0dfbc; color: #4a3510; }}
    .workflow.danger {{ background: #e5c0c0; color: #3e1f1f; }}
    .muted {{ color: #8c939b; }}
    .history {{ font-size: 12px; }}
    .hideColor {{ padding: 6px 9px; font-size: 12px; background: #f0dfbc; color: #4a3510; }}
    .adminOnly {{ display: none; }}
    body.admin .adminOnly {{ display: table-cell; }}
    .prepressNotes {{ display: none; margin: 18px 0; padding: 16px; background: #fff; border: 1px solid #dfe3e7; }}
    body.detailMode .prepressNotes {{ display: block; }}
    .prepressNotes h2 {{ margin: 0 0 10px; font-size: 19px; }}
    .prepressEntry {{ display: grid; grid-template-columns: repeat(5, minmax(120px, 1fr)) auto; gap: 8px; margin-bottom: 12px; }}
    .prepressEntry input {{ min-width: 0; font-size: 13px; }}
    .prepressEntry textarea {{ grid-column: 1 / -2; min-height: 62px; padding: 10px 12px; border: 1px solid #c8cdd3; font: inherit; }}
    .prepressNoteList {{ display: grid; gap: 8px; }}
    .prepressNote {{ border-left: 5px solid #c9901a; background: #f6f7f8; padding: 10px; }}
    .prepressNote.done {{ border-left-color: #2f8f4e; }}
    .prepressNote p {{ margin: 6px 0; }}
    .prepressNoteStatus {{ margin: 6px 0; font-weight: 800; color: #c9901a; }}
    .prepressNote.done .prepressNoteStatus {{ color: #2f8f4e; }}
    body:not(.detailMode) thead {{ display: none; }}
    body:not(.detailMode) table {{ display: block; background: transparent; box-shadow: none; }}
    body:not(.detailMode) tbody {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; align-items: start; }}
    body:not(.detailMode) tr {{ order: var(--machine-order, 0); position: relative; overflow: hidden; display: grid; grid-template-columns: 112px minmax(0, 1fr) 72px 72px; grid-template-rows: 76px 42px 44px; gap: 8px 12px; height: 208px; padding: 18px; background: #f4f6f7; border: 1px solid #dfe4e8; border-left: 3px solid #c9d1d8; box-shadow: 0 1px 2px rgba(32,36,42,0.03); box-sizing: border-box; color: #49525c; }}
    body:not(.detailMode) tr.ok {{ background: #ffffff; border-color: #e0e7e1; border-left-color: #6f9b78; color: #20242a; }}
    body:not(.detailMode) tr.wait,
    body:not(.detailMode) tr.new,
    body:not(.detailMode) tr.warn {{ background: #f3f5f6; border-color: #dfe4e8; border-left-color: #c9d1d8; color: #4d5660; }}
    body:not(.detailMode) tr.blocked {{ background: #f7f6f5; border-color: #e5dfdd; border-left-color: #c9b4b0; color: #756c6c; }}
    body:not(.detailMode) td {{ display: block; border: 0; padding: 0; white-space: normal; }}
    body:not(.detailMode) td:first-child,
    body:not(.detailMode) td:nth-child(3),
    body:not(.detailMode) td:nth-child(9),
    body:not(.detailMode) td:nth-child(10) {{ display: none; }}
    body:not(.detailMode) td.name {{ grid-column: 1 / -1; grid-row: 1; min-height: 0; padding-right: 24%; font-size: 21px; line-height: 1.08; color: inherit; font-weight: 850; z-index: 1; }}
    body:not(.detailMode) .colorNameText {{ display: -webkit-box; max-width: 100%; overflow: hidden; overflow-wrap: anywhere; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }}
    body:not(.detailMode) .machineCmyk {{ display: block; max-width: calc(100% - 4px); margin-top: 5px; color: #626b75; font-size: 12px; line-height: 1.1; font-weight: 800; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    body:not(.detailMode) .customerGlow {{ display: block; position: absolute; inset: 0; z-index: 0; pointer-events: none; background: radial-gradient(circle at 92% 8%, rgba(var(--customer-rgb, 210,216,222), 0.28) 0, rgba(var(--customer-rgb, 210,216,222), 0.18) 12%, rgba(var(--customer-rgb, 210,216,222), 0.08) 24%, rgba(var(--customer-rgb, 210,216,222), 0) 38%); }}
    body:not(.detailMode) tr.blocked .customerGlow {{ opacity: 0.34; }}
    body:not(.detailMode) .cornerCmyk {{ display: none; }}
    body:not(.detailMode) .cmykCell {{ display: none; }}
    body:not(.detailMode) .printCell {{ grid-column: 1 / -1; grid-row: 2; align-self: start; padding-top: 0; z-index: 1; }}
    body:not(.detailMode) .printCell::before {{ content: none; }}
    body:not(.detailMode) td:nth-child(6) {{ grid-column: 1 / 3; grid-row: 3; padding: 0; z-index: 1; }}
    body:not(.detailMode) .approvalCell {{ grid-column: 3; grid-row: 3; }}
    body:not(.detailMode) .transferCell {{ grid-column: 4; grid-row: 3; }}
    body:not(.detailMode) .approvalCell,
    body:not(.detailMode) .transferCell {{ display: grid; align-content: center; justify-items: center; gap: 3px; min-width: 0; padding: 0; background: transparent; border: 0; box-sizing: border-box; z-index: 1; }}
    body:not(.detailMode) .approvalCell::before {{ content: "Prüfung"; color: #777f88; font-size: 11px; font-weight: 800; }}
    body:not(.detailMode) .transferCell::before {{ content: "Vorlagen"; color: #777f88; font-size: 11px; font-weight: 800; }}
    body:not(.detailMode) tr.ok .approvalCell,
    body:not(.detailMode) tr.ok .transferCell {{ background: transparent; border-color: transparent; }}
    body:not(.detailMode) .addSk {{ display: grid; width: 100%; height: 100%; margin: 0; padding: 0; align-content: center; justify-items: start; gap: 3px; background: transparent; border: 0; color: inherit; text-align: left; }}
    body:not(.detailMode) tr.ok .addSk {{ background: transparent; border-color: transparent; }}
    body:not(.detailMode) .templateButtonLabel {{ color: #626b75; font-size: 12px; font-weight: 900; }}
    body:not(.detailMode) .templateButtonCount {{ color: #20242a; font-size: 26px; line-height: 1; font-weight: 900; }}
    body:not(.detailMode) .templateButtonPlus {{ color: #626b75; font-size: 16px; line-height: 1; }}
    body:not(.detailMode) .workflow.danger {{ display: none; }}
    body:not(.detailMode) .transferSummary {{ display: none; }}
    body:not(.detailMode) .machineTransferSummary {{ display: block; min-width: 0; font-size: 23px; line-height: 1; font-weight: 900; white-space: nowrap; overflow: visible; }}
    body:not(.detailMode) .machineTransferSummary.done {{ color: #3f6248; }}
    body:not(.detailMode) .machineTransferSummary.open {{ color: #6d6f72; }}
    body:not(.detailMode) .machineTransferSummary.idle {{ color: #8c939b; }}
    body:not(.detailMode) .statusLine {{ min-width: 0; font-size: 23px; line-height: 1; font-weight: 900; white-space: nowrap; overflow: visible; }}
    body:not(.detailMode) .statusLine.done {{ color: #3f6248; }}
    body:not(.detailMode) .statusLine.idle {{ color: #8c939b; }}
    body:not(.detailMode) .machineApproval {{ display: inline; }}
    body:not(.detailMode) .detailApproval {{ display: none; }}
    body:not(.detailMode) .skMeta {{ display: none; }}
    body:not(.detailMode) tr.blocked .printCell,
    body:not(.detailMode) tr.blocked .approvalCell,
    body:not(.detailMode) tr.blocked .transferCell {{ display: none; }}
    body:not(.detailMode) tr.blocked td.name {{ grid-row: 1 / 3; min-height: 0; padding-right: 12%; }}
    body:not(.detailMode) tr.blocked .notPrintableBanner {{ display: flex; width: fit-content; margin-top: 12px; padding: 0; font-size: 14px; }}
    body:not(.detailMode) tr.blocked .notPrintableCardReason {{ display: -webkit-box; max-height: none; overflow: hidden; padding-right: 5px; font-size: 13px; -webkit-line-clamp: 3; -webkit-box-orient: vertical; }}
    body:not(.detailMode) tr.blocked .skCell {{ grid-column: 1 / -1; grid-row: 3; }}
    body:not(.detailMode) tr.blocked .addSk {{ display: flex; align-items: center; justify-content: flex-start; gap: 8px; padding: 0; background: transparent; border-color: transparent; }}
    body:not(.detailMode) tr.blocked .templateButtonCount {{ font-size: 20px; }}
    body:not(.detailMode) details {{ display: none; }}
    body:not(.detailMode) .skEmpty {{ display: none; }}
    body:not(.detailMode) details summary {{ display: inline-block; padding: 8px 10px; border: 1px solid #d1d6dc; background: #f6f7f8; }}
    body:not(.detailMode) details[open] summary {{ margin-bottom: 6px; }}
    body:not(.detailMode) .detailSkSummary {{ display: none; }}
    body.detailMode .machineSkSummary {{ display: none; }}
    body.detailMode .skPanelButton {{ display: none; }}
    body.detailMode .machineCmyk {{ display: none; }}
    body.detailMode .detailApproval {{ display: inline; }}
    body.detailMode .machineTransferSummary {{ display: none; }}
    body.detailMode .adminOnly {{ display: table-cell; }}
    @media (max-width: 760px) {{
      body {{ margin: 16px; }}
      .topBar, .summary {{ grid-template-columns: 1fr; }}
      .prepressEntry {{ grid-template-columns: 1fr; }}
      .prepressEntry textarea {{ grid-column: auto; }}
      .viewToggle {{ width: 100%; }}
      body:not(.detailMode) tr {{ grid-template-columns: 96px minmax(0, 1fr) 56px 56px; }}
    }}
    .dot {{ display: inline-block; width: 14px; height: 14px; border-radius: 50%; background: #8c939b; }}
    tr.ok .dot {{ background: #2f8f4e; }}
    tr.wait .dot {{ background: #c9901a; }}
    tr.new .dot, tr.warn .dot {{ background: #bd3f3f; }}
    .dialogBackdrop {{ position: fixed; inset: 0; background: rgba(32, 36, 42, 0.28); display: none; align-items: center; justify-content: center; z-index: 10; }}
    .dialogBackdrop.open {{ display: flex; }}
    .dialogBox {{ width: min(420px, calc(100vw - 32px)); background: #fff; border: 1px solid #b7c0ca; box-shadow: 0 18px 45px rgba(0, 0, 0, 0.22); padding: 16px; }}
    .dialogBox h2 {{ margin: 0 0 12px; font-size: 20px; }}
    .dialogBody {{ color: #20242a; line-height: 1.45; }}
    .statusLine {{ font-weight: 700; }}
    .statusLine.done {{ color: #2f8f4e; }}
    .statusLine.idle {{ color: #8c939b; }}
    .statusLine.open {{ color: #c9901a; }}
    .transferList {{ display: grid; gap: 10px; margin: 10px 0; }}
    .transferItem {{ border: 1px solid #dfe3e7; padding: 10px; background: #f6f7f8; }}
    .transferItem.done {{ border-left: 5px solid #2f8f4e; }}
    .transferItem.open {{ border-left: 5px solid #c9901a; }}
    .skPopupList {{ display: grid; gap: 7px; margin: 10px 0 14px; }}
    .skPopupItem {{ display: flex; justify-content: space-between; gap: 10px; padding: 8px 10px; background: #f6f7f8; border: 1px solid #e0e4e8; }}
    .skPopupItem span {{ color: #626b75; font-weight: 700; }}
    .dialogBody input[type="text"], .dialogBody input:not([type]), .dialogBody textarea {{ width: 100%; box-sizing: border-box; margin-top: 6px; }}
    .dialogBody input[type="checkbox"] {{ width: auto; margin: 0 6px 0 0; }}
    .dialogActions {{ display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }}
  </style>
</head>
<body>
  <h1 id="title">MPRINT Farbübersicht</h1>
  <p class="meta">Automatisch aktualisiert: {html.escape(now_stamp())}</p>
  {preview_banner}
  <div class="topBar">
    <div class="searchBar">
      <label for="colorSearch">Farbsuche</label>
      <input type="search" id="colorSearch" autocomplete="off" placeholder="Farbname suchen...">
    </div>
  </div>
  <div class="summary">{summary_html}</div>
  <form class="entry" method="post" action="{html.escape(submit_url, quote=True)}" target="submitFrame">
    <input name="farbe" id="farbe" autocomplete="off" placeholder="Kundenfarbe eintragen">
    <button type="submit">Eintragen</button>
  </form>
  <div id="connectionStatus" class="connection checking">Verbindung wird geprüft</div>
  <div class="viewControls"><button type="button" id="detailToggle" class="viewToggle">Details anzeigen</button></div>
  <div id="entryStatus"></div>
  <iframe name="submitFrame" style="display:none"></iframe>
  <section class="prepressNotes" aria-label="Vorstufen-Hinweise">
    <h2>Vorstufen-Hinweise</h2>
    <form id="prepressNoteForm" class="prepressEntry">
      <input name="title" autocomplete="off" placeholder="Titel">
      <input name="customer" autocomplete="off" placeholder="Kunde optional">
      <input name="color" autocomplete="off" placeholder="Farbe optional">
      <input name="sk" autocomplete="off" placeholder="SK optional">
      <input name="created_by" autocomplete="off" placeholder="Erstellt von optional">
      <button type="submit">Hinweis speichern</button>
      <textarea name="text" placeholder="Information"></textarea>
    </form>
    <div id="prepressNoteList" class="prepressNoteList">{prepress_note_html}</div>
  </section>
  <table>
    <thead><tr><th class="indicator"></th><th>Kundenfarbe</th><th></th><th>CMYK</th><th>Druck</th><th>Betroffene Eindruckvorlagen</th><th>Prüfung</th><th>Übernahme</th><th>Historie</th><th class="adminOnly"></th></tr></thead>
    <tbody>{''.join(body_rows)}</tbody>
  </table>
  <div id="noSearchResults" class="noResults">Keine passenden Farben gefunden</div>
  <div id="dialogBackdrop" class="dialogBackdrop" role="dialog" aria-modal="true">
    <div class="dialogBox">
      <h2 id="dialogTitle"></h2>
      <div id="dialogBody" class="dialogBody"></div>
      <div class="dialogActions">
        <button type="button" id="dialogCancel">Abbrechen</button>
        <button type="button" id="dialogOk"></button>
      </div>
    </div>
  </div>
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
        var payload = null;
        try {{
          payload = text ? JSON.parse(text) : null;
        }} catch (_error) {{
          payload = null;
        }}
        var message = payload && payload.message ? payload.message : text;
        if (!response.ok) {{
          var error = new Error(message || ('Servermeldung ' + response.status));
          error.status = response.status;
          error.payload = payload;
          throw error;
        }}
        return payload || {{ ok: true, message: message }};
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
    function postHelper(url, data) {{
      return fetchWithTimeout(url, {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' }},
        body: new URLSearchParams(data).toString()
      }}, 8000).then(responseTextOrError);
    }}
    function payloadMessage(payload, fallback) {{
      return payload && payload.message ? payload.message : fallback;
    }}
    function escapeHtml(value) {{
      return String(value || '').replace(/[&<>"']/g, function(char) {{
        return {{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }}[char];
      }});
    }}
    function cmykToCssColor(raw) {{
      var parts = String(raw || '').match(/-?\\d+(?:[\\.,]\\d+)?/g);
      if (!parts || parts.length < 4) {{
        return 'rgb(238, 241, 244)';
      }}
      var values = parts.slice(0, 4).map(function(part) {{
        var value = Math.round(parseFloat(String(part).replace(',', '.')));
        return isFinite(value) ? Math.max(0, Math.min(100, value)) : null;
      }});
      if (values.some(function(value) {{ return value === null; }})) {{
        return 'rgb(238, 241, 244)';
      }}
      var c = values[0] / 100;
      var m = values[1] / 100;
      var y = values[2] / 100;
      var k = values[3] / 100;
      var r = Math.round(255 * (1 - c) * (1 - k));
      var g = Math.round(255 * (1 - m) * (1 - k));
      var b = Math.round(255 * (1 - y) * (1 - k));
      if (values[0] === 0 && values[1] === 0 && values[2] === 0 && values[3] === 0) {{
        return 'rgb(247, 248, 249)';
      }}
      return 'rgb(' + r + ', ' + g + ', ' + b + ')';
    }}
    function cmykContrast(raw) {{
      var color = cmykToCssColor(raw);
      var match = color.match(/\\d+/g);
      if (!match || match.length < 3) {{
        return {{ text: '#20242a', shadow: '0 1px 1px rgba(255,255,255,0.55)' }};
      }}
      var r = parseInt(match[0], 10);
      var g = parseInt(match[1], 10);
      var b = parseInt(match[2], 10);
      var lightness = (r * 299 + g * 587 + b * 114) / 1000;
      if (lightness < 118) {{
        return {{ text: '#ffffff', shadow: '0 1px 2px rgba(0,0,0,0.55)' }};
      }}
      return {{ text: '#20242a', shadow: '0 1px 1px rgba(255,255,255,0.55)' }};
    }}
    document.querySelectorAll('.customerGlow').forEach(function(swatch) {{
      var cmyk = swatch.getAttribute('data-cmyk') || '';
      var color = cmykToCssColor(cmyk);
      var match = color.match(/\\d+/g);
      var rgb = match && match.length >= 3 ? match.slice(0, 3).join(', ') : '210, 216, 222';
      swatch.style.setProperty('--customer-rgb', rgb);
    }});
    function normalizeSearchText(value) {{
      return String(value || '').replace(/\\s+/g, ' ').trim().toLocaleLowerCase('de-DE');
    }}
    function refreshRowSearchText(row) {{
      if (!row) return;
      var stableSearch = row.getAttribute('data-color-search') || '';
      row.dataset.searchText = normalizeSearchText(stableSearch + ' ' + (row.textContent || ''));
    }}
    function applyColorSearch() {{
      var input = document.getElementById('colorSearch');
      var message = document.getElementById('noSearchResults');
      var query = normalizeSearchText(input ? input.value.trim() : '');
      var visible = 0;
      document.querySelectorAll('tbody tr').forEach(function(row) {{
        if (!row.dataset.searchText) {{
          refreshRowSearchText(row);
        }}
        var matches = !query || row.dataset.searchText.indexOf(query) !== -1;
        row.hidden = !matches;
        if (matches) {{
          visible += 1;
        }}
      }});
      if (message) {{
        message.classList.toggle('visible', visible === 0);
      }}
    }}
    document.querySelectorAll('tbody tr').forEach(refreshRowSearchText);
    var colorSearch = document.getElementById('colorSearch');
    if (colorSearch) {{
      colorSearch.addEventListener('input', applyColorSearch);
    }}
    var detailToggle = document.getElementById('detailToggle');
    if (detailToggle) {{
      detailToggle.addEventListener('click', function() {{
        document.body.classList.toggle('detailMode');
        detailToggle.textContent = document.body.classList.contains('detailMode')
          ? 'Maschinenansicht'
          : 'Details anzeigen';
      }});
    }}
    function showDialog(options) {{
      return new Promise(function(resolve) {{
        var backdrop = document.getElementById('dialogBackdrop');
        var title = document.getElementById('dialogTitle');
        var body = document.getElementById('dialogBody');
        var cancel = document.getElementById('dialogCancel');
        var ok = document.getElementById('dialogOk');
        title.textContent = options.title || '';
        body.innerHTML = options.body || '';
        ok.textContent = options.okText || 'OK';
        cancel.style.display = options.hideCancel ? 'none' : '';
        backdrop.classList.add('open');
        var input = options.returnInput ? body.querySelector('input') : null;
        function cleanup(value) {{
          backdrop.classList.remove('open');
          cancel.style.display = '';
          cancel.onclick = null;
          ok.onclick = null;
          document.removeEventListener('keydown', onKey);
          resolve(value);
        }}
        function onKey(event) {{
          if (event.key === 'Escape') {{
            event.preventDefault();
            cleanup(null);
          }} else if (event.key === 'Enter' && options.returnInput) {{
            event.preventDefault();
	            cleanup(input ? input.value : true);
          }}
        }}
        cancel.onclick = function() {{ cleanup(null); }};
        ok.onclick = function() {{ cleanup(input ? input.value : true); }};
        document.addEventListener('keydown', onKey);
        window.setTimeout(function() {{ (input || ok).focus(); }}, 0);
      }});
    }}
    function findColorRow(color) {{
      var buttons = document.querySelectorAll('.addSk[data-color]');
      for (var i = 0; i < buttons.length; i += 1) {{
        if ((buttons[i].getAttribute('data-color') || '') === color) {{
          return buttons[i].closest('tr');
        }}
      }}
      return null;
    }}
    function updateSummaries() {{
      var printOpen = document.querySelectorAll('.workflow[data-action="printed"]').length;
      var approvalOpen = document.querySelectorAll('.workflow[data-action="approve"]').length;
      var templateOpen = 0;
      document.querySelectorAll('.workflow[data-action="template"]').forEach(function(button) {{
        templateOpen += parseInt(button.getAttribute('data-open-count') || '0', 10) || 0;
      }});
      var pills = document.querySelectorAll('.summaryPill');
      function setPill(pill, count, label) {{
        if (pill) pill.innerHTML = '<strong>' + String(count) + '</strong><span>' + escapeHtml(label) + '</span>';
      }}
      setPill(pills[0], printOpen, 'Drucke offen');
      setPill(pills[1], approvalOpen, 'Prüfungen offen');
      setPill(pills[2], templateOpen, 'Vorlagen offen');
    }}
    function updateSkSummary(row) {{
      if (!row) return;
      var items = row.querySelectorAll('.skItem').length;
      var summary = row.querySelector('details summary');
      if (summary) summary.innerHTML = '<span class="machineSkSummary">Vorlagen ' + items + '</span><span class="detailSkSummary">' + items + ' Eindruckvorlage(n)</span>';
    }}
    function templateButtonHtml(count) {{
      var html = '<span class="templateButtonLabel">Vorlagen</span><span class="templateButtonCount">' + String(count) + '</span>';
      if (!count) {{
        html += '<span class="templateButtonPlus">+</span>';
      }}
      return html;
    }}
    function bindWorkflowButton(button) {{
      button.addEventListener('click', handleWorkflowClick);
    }}
    function createWorkflowButton(action, color, sk, cmyk, text, className) {{
      var button = document.createElement('button');
      button.type = 'button';
      button.className = className || 'workflow';
      button.dataset.action = action;
      button.dataset.color = color;
      if (sk) button.dataset.sk = sk;
      button.dataset.cmyk = cmyk || '';
      button.textContent = text;
      bindWorkflowButton(button);
      return button;
    }}
    function makeBadge(text, className) {{
      var badge = document.createElement('span');
      badge.className = className || 'badge done';
      badge.textContent = text;
      return badge;
    }}
    function parseSkState(button) {{
      try {{
        var parsed = JSON.parse(button.getAttribute('data-sk-state') || '[]');
        return Array.isArray(parsed) ? parsed : [];
      }} catch (_error) {{
        return [];
      }}
    }}
    function transferDialogBody(color, cmyk, skState) {{
      function skLabel(value) {{
        var cleaned = String(value || '').replace(/\\s+/g, ' ').trim();
        if (!cleaned) return 'SK';
        return /^sk/i.test(cleaned) ? cleaned : 'SK ' + cleaned;
      }}
      var items = skState.map(function(item, index) {{
        var sk = item.sk || '';
        var method = item.method || 'offen';
        var at = item.at || 'Datum nicht erfasst';
        var by = item.by || 'nicht erfasst';
        var note = item.note || '';
        if (item.completed) {{
          return '<div class="transferItem done"><strong>' + escapeHtml(skLabel(sk)) + '</strong><div><span class="statusLine done">● erledigt</span></div><div class="skMeta">Methode: ' + escapeHtml(method) + '</div><div class="skMeta">Datum: ' + escapeHtml(at) + '</div><div class="skMeta">Bearbeiter: ' + escapeHtml(by) + '</div>' + (note ? '<div class="skMeta">Notiz: ' + escapeHtml(note) + '</div>' : '') + '</div>';
        }}
        return '<label class="transferItem open"><input type="checkbox" class="transferSk" value="' + escapeHtml(sk) + '"><strong>' + escapeHtml(skLabel(sk)) + '</strong><div><span class="statusLine open">● offen</span></div></label>';
      }}).join('');
      if (!items) {{
        items = '<p>Keine Eindruckvorlage hinterlegt.</p>';
      }}
      return '<p><strong>Kundenfarbe:</strong><br>' + escapeHtml(color) + '</p><p><strong>CMYK:</strong><br>' + escapeHtml(cmyk) + '</p><div class="transferList">' + items + '</div><p>Ausgewählte offene SKs als übernommen speichern:</p><label><input type="checkbox" id="transferTemplate"> Eindruckvorlage angepasst</label><br><label><input type="checkbox" id="transferPortal"> Portal informiert</label><p><label>Bearbeitet durch:<input id="transferBy" autocomplete="off"></label></p><p><label>Notiz:<textarea id="transferNote" rows="3"></textarea></label></p>';
    }}
    function skDialogBody(color, skState) {{
      function skLabel(value) {{
        var cleaned = String(value || '').replace(/\\s+/g, ' ').trim();
        if (!cleaned) return 'SK';
        return /^sk/i.test(cleaned) ? cleaned : 'SK ' + cleaned;
      }}
      var items = skState.map(function(item) {{
        var sk = item.sk || '';
        var status = item.completed ? '✓ übernommen' : '○ Übernahme offen';
        return '<div class="skPopupItem"><strong>' + escapeHtml(skLabel(sk)) + '</strong><span>' + escapeHtml(status) + '</span></div>';
      }}).join('');
      if (!items) {{
        items = '<p class="muted">Noch keine SK hinterlegt.</p>';
      }}
      return '<p><strong>Kundenfarbe:</strong><br>' + escapeHtml(color) + '</p><div class="skPopupList">' + items + '</div><label>SK-Nummer hinzufügen<input id="skInput" autocomplete="off"></label>';
    }}
    function ensureDetails(row) {{
      var cell = row.cells[5];
      var details = cell.querySelector('details');
      if (details) return details;
      cell.querySelector('.muted')?.remove();
      details = document.createElement('details');
      details.open = true;
      var summary = document.createElement('summary');
      summary.textContent = '0 Eindruckvorlage(n)';
      summary.innerHTML = '<span class="machineSkSummary">Vorlagen 0</span><span class="detailSkSummary">0 Eindruckvorlage(n)</span>';
      details.appendChild(summary);
      cell.insertBefore(details, cell.firstChild);
      return details;
    }}
    function appendSkRow(color, sk, cmyk) {{
      var row = findColorRow(color);
      if (!row) return;
      var details = ensureDetails(row);
      var item = document.createElement('div');
      item.className = 'skItem';
      item.innerHTML = '<strong>' + escapeHtml(/^sk/i.test(sk) ? sk : 'SK ' + sk) + '</strong><span class="statusLine open">○ Übernahme offen</span>';
      details.appendChild(item);
      details.open = true;
      row.setAttribute('data-color-search', ((row.getAttribute('data-color-search') || '') + ' ' + sk).trim());
      updateSkSummary(row);
      var skButtons = row.querySelectorAll('.skPanelButton');
      skButtons.forEach(function(button) {{
        var currentState = parseSkState(button);
        currentState.push({{ sk: sk, completed: false, method: 'offen', at: '', by: '', note: '' }});
        button.setAttribute('data-sk-state', JSON.stringify(currentState));
        button.innerHTML = templateButtonHtml(currentState.length);
      }});
      refreshRowSearchText(row);
      applyColorSearch();
    }}
    document.querySelectorAll('.summaryPill').forEach(function(button) {{
      button.addEventListener('click', function() {{
        document.querySelectorAll('details').forEach(function(details) {{ details.open = true; }});
        document.getElementById('entryStatus').textContent = 'SK-Details geöffnet.';
      }});
    }});
    document.querySelectorAll('.hideColor').forEach(function(button) {{
      button.addEventListener('click', function() {{
        var name = button.getAttribute('data-name') || '';
        var status = document.getElementById('entryStatus');
        var row = button.closest('tr');
        if (!window.fetch) {{
          status.textContent = 'Ausblenden braucht einen aktuellen Browser.';
          return;
        }}
        showDialog({{
          title: 'Farbe ausblenden?',
          body: '<p><strong>Farbname:</strong><br>' + escapeHtml(name) + '</p><p>Die Farbe wird nur aus der MPRINT Farbübersicht ausgeblendet.<br>Die ursprünglichen Farbdaten werden nicht gelöscht.</p>',
          okText: 'Ausblenden'
        }}).then(function(confirmed) {{
          if (!confirmed) {{
            return;
          }}
          status.textContent = 'Farbe wird ausgeblendet...';
          postHelper({hide_url_json}, {{ farbe: name }})
          .then(function(payload) {{
            status.textContent = payloadMessage(payload, 'Farbe ausgeblendet.');
            if (row) {{
              row.remove();
            }}
            applyColorSearch();
            updateSummaries();
          }})
          .catch(function(error) {{
            status.textContent = 'Farbe nicht ausgeblendet: ' + friendlyFetchError(error);
          }});
        }});
      }});
    }});
    document.querySelectorAll('.addSk').forEach(function(button) {{
      button.addEventListener('click', function() {{
        var color = button.getAttribute('data-color') || '';
        var cmyk = button.getAttribute('data-cmyk') || 'nicht erfasst';
        var skState = parseSkState(button);
        var status = document.getElementById('entryStatus');
        showDialog({{
	          title: 'Betroffene Eindruckvorlagen',
	          body: skDialogBody(color, skState),
	          okText: 'Hinzufügen',
	          returnInput: true
	        }}).then(function(sk) {{
          if (sk === null) {{
            return;
          }}
          sk = String(sk).trim();
          if (!sk) {{
            status.textContent = 'Bitte eine SK-Nr. eintragen.';
            return;
          }}
          status.textContent = 'SK wird hinzugefügt...';
          postHelper({sk_add_url_json}, {{ farbe: color, sk: sk }})
            .then(function(payload) {{
              status.textContent = payloadMessage(payload, 'SK hinzugefügt.');
              appendSkRow(color, sk, cmyk);
            }})
            .catch(function(error) {{
              status.textContent = 'SK nicht gespeichert: ' + friendlyFetchError(error);
              checkConnection();
            }});
        }});
      }});
    }});
    document.querySelectorAll('.reasonButton').forEach(function(button) {{
      button.addEventListener('click', function() {{
        showDialog({{
          title: 'Grund',
          body: '<p>' + escapeHtml(button.getAttribute('data-reason') || 'Kein Grund erfasst.') + '</p>',
          okText: 'Schließen',
          hideCancel: true
        }});
      }});
    }});
    function handleWorkflowClick() {{
        var button = this;
        var action = button.getAttribute('data-action') || '';
        var color = button.getAttribute('data-color') || '';
        var cmyk = button.getAttribute('data-cmyk') || 'nicht erfasst';
        var status = document.getElementById('entryStatus');
        var url = '';
        var dialog = null;
        if (action === 'printed') {{
          url = {sk_printed_url_json};
          dialog = {{
            title: 'Druck erfolgreich?',
            body: '<p><strong>Farbe:</strong><br>' + escapeHtml(color) + '</p><p><strong>CMYK:</strong><br>' + escapeHtml(cmyk) + '</p><p>Wurde diese Farbe erfolgreich auf der MJET gedruckt?</p>',
            okText: 'Ja, gedruckt'
          }};
        }} else if (action === 'approve') {{
          url = {sk_approved_url_json};
          dialog = {{
            title: 'Druck freigeben?',
            body: '<p><strong>Farbe:</strong><br>' + escapeHtml(color) + '</p><p><strong>CMYK:</strong><br>' + escapeHtml(cmyk) + '</p><p>Andreas hat das Druckergebnis geprüft und die Farbrezeptur freigegeben?</p>',
            okText: 'Ja, freigeben'
          }};
        }} else if (action === 'template') {{
          url = {sk_template_url_json};
          var skState = parseSkState(button);
          dialog = {{
            title: 'Übernahmen verwalten',
            body: transferDialogBody(color, cmyk, skState),
            okText: 'Speichern'
          }};
        }} else if (action === 'notPrintable') {{
          url = {not_printable_url_json};
          var skStateForBlock = parseSkState(button).map(function(item) {{ return item.sk; }}).filter(Boolean).join('<br>');
          dialog = {{
            title: 'Auf MJET nicht druckbar',
            body: '<p><strong>Farbe:</strong><br>' + escapeHtml(color) + '</p><p><strong>CMYK:</strong><br>' + escapeHtml(cmyk) + '</p>' + (skStateForBlock ? '<p><strong>Betroffene SK:</strong><br>' + skStateForBlock + '</p>' : '') + '<label>Grund<textarea id="notPrintableReason" rows="4" required></textarea></label>',
            okText: 'Als nicht druckbar markieren'
          }};
        }} else if (action === 'clearNotPrintable') {{
          url = {not_printable_url_json};
          dialog = {{
            title: 'Nicht-druckbar-Status aufheben',
            body: '<p><strong>Farbe:</strong><br>' + escapeHtml(color) + '</p><p>Der bisherige Grund bleibt in der Historie erhalten.</p><label>Bearbeitet durch:<input id="clearNotPrintableBy" autocomplete="off"></label>',
            okText: 'Status aufheben'
          }};
        }} else {{
          return;
        }}
        showDialog(dialog).then(function(confirmed) {{
          if (!confirmed) {{
            return;
          }}
          status.textContent = 'Status wird gespeichert...';
          var data = {{ farbe: color }};
          if (action === 'template') {{
            var selectedSk = Array.from(document.querySelectorAll('.transferSk:checked')).map(function(input) {{ return input.value; }});
            if (!selectedSk.length) {{
              status.textContent = 'Keine offene SK ausgewählt.';
              return;
            }}
            var templateChecked = document.getElementById('transferTemplate') && document.getElementById('transferTemplate').checked;
            var portalChecked = document.getElementById('transferPortal') && document.getElementById('transferPortal').checked;
            if (!templateChecked && !portalChecked) {{
              status.textContent = 'Bitte mindestens eine Übernahmeart auswählen.';
              return;
            }}
            data.template_updated = templateChecked ? '1' : '';
            data.portal_informed = portalChecked ? '1' : '';
            data.completed_by = document.getElementById('transferBy') ? document.getElementById('transferBy').value : '';
            data.note = document.getElementById('transferNote') ? document.getElementById('transferNote').value : '';
            Promise.all(selectedSk.map(function(sk) {{
              var skData = Object.assign({{}}, data, {{ sk: sk }});
              return postHelper(url, skData);
            }}))
            .then(function(payloads) {{
              status.textContent = payloads.length + ' Übernahme(n) gespeichert.';
              window.setTimeout(function() {{ window.location.reload(); }}, 700);
            }})
            .catch(function(error) {{
              status.textContent = 'Status nicht gespeichert: ' + friendlyFetchError(error);
              checkConnection();
            }});
            return;
          }}
          if (action === 'notPrintable') {{
            var reasonInput = document.getElementById('notPrintableReason');
            var reason = reasonInput ? reasonInput.value.trim() : '';
            if (!reason) {{
              status.textContent = 'Bitte einen Grund eintragen.';
              return;
            }}
            data.reason = reason;
          }} else if (action === 'clearNotPrintable') {{
            data.clear = '1';
            data.completed_by = document.getElementById('clearNotPrintableBy') ? document.getElementById('clearNotPrintableBy').value : '';
          }}
          postHelper(url, data)
            .then(function(payload) {{
              var row = button.closest('tr');
              status.textContent = payloadMessage(payload, 'Status gespeichert.');
              if (action === 'printed') {{
                row.cells[4].innerHTML = '<div class="printDecision"><span class="printChoice printable active">✓ Druckbar</span></div>';
                var notPrintableButton = createWorkflowButton('notPrintable', color, '', cmyk, 'Nicht druckbar', 'printChoice notPrintable workflow');
                var skButtonForBlock = row.querySelector('.skPanelButton');
                if (skButtonForBlock) {{
                  notPrintableButton.setAttribute('data-sk-state', skButtonForBlock.getAttribute('data-sk-state') || '[]');
                }}
                row.cells[4].querySelector('.printDecision').appendChild(notPrintableButton);
                row.cells[6].innerHTML = '';
                row.cells[6].appendChild(createWorkflowButton('approve', color, '', cmyk, 'Andreas freigeben', 'workflow warn'));
              }} else if (action === 'approve') {{
                row.cells[6].innerHTML = '<span class="statusLine done" title="Prüfung abgeschlossen"><span class="machineApproval">✓</span><span class="detailApproval">✓ Andreas</span></span>';
                row.cells[7].innerHTML = '';
                row.cells[7].innerHTML = '<div class="transferSummary open">0 / 0 Vorlagen übernommen</div><div class="machineTransferSummary idle" title="Vorlagen offen">○</div>';
                var templateButton = createWorkflowButton('template', color, '', cmyk, 'Übernahmen verwalten', 'workflow danger');
                templateButton.setAttribute('data-open-count', '0');
                row.cells[7].appendChild(templateButton);
                window.setTimeout(function() {{ window.location.reload(); }}, 700);
              }} else if (action === 'notPrintable' || action === 'clearNotPrintable') {{
                window.setTimeout(function() {{ window.location.reload(); }}, 500);
              }}
              refreshRowSearchText(row);
              applyColorSearch();
              updateSummaries();
            }})
            .catch(function(error) {{
              status.textContent = 'Status nicht gespeichert: ' + friendlyFetchError(error);
              checkConnection();
            }});
        }});
    }}
    document.querySelectorAll('.workflow').forEach(bindWorkflowButton);
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
            ? 'Adminmodus aktiv: Einträge können ausgeblendet werden.'
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
      postHelper({submit_url_json}, {{ farbe: value }})
      .then(function(payload) {{
        status.textContent = payloadMessage(payload, 'Kundenfarbe eingetragen.');
        input.value = '';
        checkConnection();
        window.setTimeout(function() {{ window.location.reload(); }}, 900);
      }})
      .catch(function(error) {{
        status.textContent = 'Eintrag nicht gespeichert: ' + friendlyFetchError(error);
        checkConnection();
      }});
    }});
    var prepressForm = document.getElementById('prepressNoteForm');
    if (prepressForm) {{
      prepressForm.addEventListener('submit', function(event) {{
        event.preventDefault();
        var status = document.getElementById('entryStatus');
        var formData = new FormData(prepressForm);
        var title = String(formData.get('title') || '').trim();
        var text = String(formData.get('text') || '').trim();
        if (!title || !text) {{
          status.textContent = 'Bitte Titel und Information für den Hinweis eintragen.';
          return;
        }}
        status.textContent = 'Vorstufen-Hinweis wird gespeichert...';
        postHelper({prepress_note_url_json}, {{
          title: title,
          text: text,
          customer: formData.get('customer') || '',
          color: formData.get('color') || '',
          sk: formData.get('sk') || '',
          created_by: formData.get('created_by') || ''
        }})
          .then(function(payload) {{
            status.textContent = payloadMessage(payload, 'Vorstufen-Hinweis gespeichert.');
            window.setTimeout(function() {{ window.location.reload(); }}, 500);
          }})
          .catch(function(error) {{
            status.textContent = 'Hinweis nicht gespeichert: ' + friendlyFetchError(error);
          }});
      }});
    }}
    document.querySelectorAll('.completePrepressNote').forEach(function(button) {{
      button.addEventListener('click', function() {{
        var status = document.getElementById('entryStatus');
        showDialog({{
          title: 'Hinweis übernehmen?',
          body: '<p>Vorstufen-Hinweis als übernommen markieren.</p><label>Übernommen von:<input id="prepressDoneBy" autocomplete="off"></label>',
          okText: 'Als übernommen markieren'
        }}).then(function(confirmed) {{
          if (!confirmed) return;
          status.textContent = 'Vorstufen-Hinweis wird aktualisiert...';
          postHelper({prepress_note_done_url_json}, {{
            note_id: button.getAttribute('data-note-id') || '',
            completed_by: document.getElementById('prepressDoneBy') ? document.getElementById('prepressDoneBy').value : ''
          }})
            .then(function(payload) {{
              status.textContent = payloadMessage(payload, 'Vorstufen-Hinweis übernommen.');
              window.setTimeout(function() {{ window.location.reload(); }}, 500);
            }})
            .catch(function(error) {{
              status.textContent = 'Hinweis nicht aktualisiert: ' + friendlyFetchError(error);
            }});
        }});
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
                self._send_common_headers(0, "text/plain; charset=utf-8")
                self.end_headers()

            def do_POST(self) -> None:
                path = self.path.split("?", 1)[0]
                if path not in {
                    "/farbe",
                    "/farbe-loeschen",
                    "/farbe-ausblenden",
                    "/sk-hinzufuegen",
                    "/sk-gedruckt",
                    "/sk-freigeben",
                    "/sk-uebernommen",
                    "/farbe-nicht-druckbar",
                    "/vorstufen-hinweis",
                    "/vorstufen-hinweis-erledigt",
                }:
                    self.send_error(404)
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    body = self.rfile.read(min(length, 8192)).decode("utf-8", errors="replace")
                    values = parse_qs(body)
                    color_name = values.get("farbe", [""])[0]
                    sk_number = values.get("sk", [""])[0]
                    template_updated = bool(values.get("template_updated", [""])[0].strip())
                    portal_informed = bool(values.get("portal_informed", [""])[0].strip())
                    completed_by = values.get("completed_by", [""])[0]
                    note = values.get("note", [""])[0]
                    reason = values.get("reason", [""])[0]
                    clear_flag = bool(values.get("clear", [""])[0].strip())
                    if path in {"/farbe-loeschen", "/farbe-ausblenden"}:
                        if not color_name.strip():
                            self._send_json({"ok": False, "message": "Keine Farbbezeichnung übergeben."}, status=400)
                            return
                        message = color_manager.hide_overview_color(color_name)
                        self._send_json({"ok": True, "message": message})
                        return
                    if path == "/farbe":
                        if not color_name.strip():
                            self._send_json({"ok": False, "message": "Bitte eine Farbbezeichnung eintragen."}, status=400)
                            return
                        if len(re.sub(r"\s+", " ", color_name).strip()) > 160:
                            self._send_json({"ok": False, "message": "Die Farbbezeichnung ist zu lang."}, status=400)
                            return
                        message = color_manager.add_requested_color(color_name)
                        if message.startswith("Kundenfarbe ist bereits"):
                            self._send_json({"ok": False, "message": message}, status=409)
                            return
                        self._send_json({"ok": True, "message": message})
                        return
                    if path == "/farbe-nicht-druckbar":
                        if clear_flag:
                            result = color_manager.clear_color_not_printable(color_name, completed_by=completed_by)
                        else:
                            result = color_manager.set_color_not_printable(color_name, reason=reason, completed_by=completed_by)
                        self._send_json(result, status=int(result.get("status", 200)))
                        return
                    if path == "/vorstufen-hinweis":
                        result = color_manager.add_prepress_note(
                            values.get("title", [""])[0],
                            values.get("text", [""])[0],
                            customer=values.get("customer", [""])[0],
                            color_name=values.get("color", [""])[0],
                            sk_number=values.get("sk", [""])[0],
                            created_by=values.get("created_by", [""])[0],
                        )
                        self._send_json(result, status=int(result.get("status", 200)))
                        return
                    if path == "/vorstufen-hinweis-erledigt":
                        result = color_manager.complete_prepress_note(
                            values.get("note_id", [""])[0],
                            completed_by=completed_by,
                        )
                        self._send_json(result, status=int(result.get("status", 200)))
                        return
                    if path == "/sk-hinzufuegen":
                        result = color_manager.add_sk_assignment(color_name, sk_number)
                    elif path == "/sk-gedruckt":
                        result = color_manager.mark_sk_printed(color_name, sk_number)
                    elif path == "/sk-freigeben":
                        result = color_manager.approve_sk_assignment(color_name, sk_number)
                    else:
                        result = color_manager.mark_template_updated(
                            color_name,
                            sk_number,
                            template_updated=template_updated,
                            portal_informed=portal_informed,
                            completed_by=completed_by,
                            note=note,
                        )
                    self._send_json(result, status=int(result.get("status", 200)))
                except Exception as exc:
                    logger.log(f"Kundenfarbe konnte nicht übernommen werden: {exc}", "ERROR")
                    self._send_json({"ok": False, "message": f"Fehler: {exc}"}, status=500)

            def do_GET(self) -> None:
                path = self.path.split("?", 1)[0]
                if color_manager.config.get("ui_preview_mode") and path in {"/", "/preview"}:
                    preview_path = as_path(color_manager.config.get("color_overview_html", ""))
                    try:
                        self._send_text(preview_path.read_text(encoding="utf-8"), content_type="text/html; charset=utf-8")
                    except Exception as exc:
                        self._send_text(f"Preview konnte nicht geladen werden: {exc}", status=500)
                    return
                if path == "/status":
                    self._send_text(f"{APP_NAME} bereit")
                    return
                if path == "/api/colors":
                    try:
                        self._send_json(color_manager.export_color_records())
                    except Exception as exc:
                        logger.log(f"Farb-API konnte nicht gelesen werden: {exc}", "ERROR")
                        self._send_json({"ok": False, "message": f"Fehler: {exc}"}, status=500)
                    return
                self.send_error(404)

            def log_message(self, _format: str, *_args: object) -> None:
                return

            def _send_text(
                self,
                text: str,
                status: int = 200,
                content_type: str = "text/plain; charset=utf-8",
            ) -> None:
                data = text.encode("utf-8")
                self.send_response(status)
                self._send_common_headers(len(data), content_type)
                self.end_headers()
                self.wfile.write(data)

            def _send_json(self, payload: object, status: int = 200) -> None:
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self._send_common_headers(len(data), "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(data)

            def _send_common_headers(self, length: int, content_type: str) -> None:
                self.send_header("Content-Type", content_type)
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


class PreviewColorTableManager(ColorTableManager):
    def refresh_color_overview(self) -> None:
        csv_path = self._overview_csv_path()
        html_path = as_path(self.config.get("color_overview_html", ""))
        rows, _fields = self._read_color_overview_with_legacy(csv_path)
        self._write_color_overview_html(html_path, self._visible_overview_rows(rows))
        self._write_color_export(rows)


def _preview_sk(
    manager: ColorTableManager,
    sk_number: str,
    transfer_completed: bool = False,
    completed_by: str = "",
) -> dict[str, object]:
    return {
        "sk_number": sk_number,
        "printed": False,
        "printed_at": "",
        "approved": False,
        "approved_at": "",
        "template_updated": bool(transfer_completed),
        "template_updated_at": "2026-09-11 10:30:00" if transfer_completed else "",
        "portal_informed": bool(transfer_completed),
        "transfer_completed": bool(transfer_completed),
        "transfer_completed_at": "2026-09-11 10:30:00" if transfer_completed else "",
        "transfer_completed_by": completed_by,
        "transfer_note": "",
    }


def _preview_row(
    manager: ColorTableManager,
    color_id: str,
    name: str,
    cmyk: str,
    status: str,
    printed: bool = False,
    approved: bool = False,
    sks: list[dict[str, object]] | None = None,
    not_printable: bool = False,
    reason: str = "",
) -> dict[str, str]:
    assignments = sks or []
    printed_at = "2026-09-11 09:15:00" if printed else ""
    approved_at = "2026-09-11 09:45:00" if approved else ""
    done_count, total_count = manager._transfer_counts(assignments)
    transfer = manager._aggregate_assignment_transfer(assignments, manager._empty_transfer())
    events = manager._merge_history_events(
        "[]",
        printed=printed,
        printed_at=printed_at,
        approved=approved,
        approved_at=approved_at,
        transfer=transfer,
        assignments=assignments,
        not_printable=not_printable,
        not_printable_at="2026-09-11 11:10:00" if not_printable else "",
        not_printable_by="Marvin" if not_printable else "",
        not_printable_reason=reason,
    )
    return {
        "color_id": color_id,
        "Farbbezeichnung": name,
        "Status": status,
        "Angelegt am": "2026-09-11 08:00:00",
        "Gedruckt am": printed_at,
        "Abgeglichen am": now_stamp(),
        "CMYK": cmyk,
        "Einzelfarbe vorhanden": "ja",
        "In Masterdatei": "ja" if printed else "nein",
        "Letzter Abgleich": now_stamp(),
        "Quelle": "MPRINT",
        "created_at": "2026-09-11 08:00:00",
        "last_printed_at": printed_at,
        "last_synced_at": now_stamp(),
        "legacy_created_at": "",
        "legacy_printed_at": "",
        "sk_assignments": manager._dump_sk_assignments(assignments),
        "printed": "ja" if printed else "nein",
        "printed_at": printed_at,
        "approved": "ja" if approved else "nein",
        "approved_at": approved_at,
        "transfer": manager._dump_transfer(transfer),
        "not_printable": "ja" if not_printable else "nein",
        "not_printable_at": "2026-09-11 11:10:00" if not_printable else "",
        "not_printable_by": "Marvin" if not_printable else "",
        "not_printable_reason": reason,
        "approval_notification_json": "",
        "approval_mail_preview": "",
        "source": "MPRINT",
        "machine_values": "[]",
        "history_events": manager._dump_history_events(events),
        "_preview_done_count": str(done_count),
        "_preview_total_count": str(total_count),
    }


def _write_preview_data(config: dict, manager: ColorTableManager) -> None:
    csv_path = manager._overview_csv_path()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        _preview_row(manager, "CLR-900001", "MUSTERMANN ROT", "C 0 / M 90 / Y 80 / K 5", "Einzelfarbe vorhanden - Farbabgleich offen", sks=[_preview_sk(manager, "SK 100001")]),
        _preview_row(manager, "CLR-900002", "VOGT BLAU", "C 100 / M 60 / Y 10 / K 10", "MPRINT angepasst / druckbar", printed=True, sks=[_preview_sk(manager, "FOG_BAD_003")]),
        _preview_row(manager, "CLR-900006", "ADAM ROT", "C 5 / M 90 / Y 80 / K 5", "MPRINT angepasst / druckbar", printed=True, approved=True, sks=[_preview_sk(manager, "SK 400001"), _preview_sk(manager, "SK 400002")], not_printable=True, reason="Feine und fette schwarze Schriften im selben Eindruck - keine stabile gemeinsame Maschineneinstellung möglich."),
        _preview_row(manager, "CLR-900003", "ANDREAS GRUEN", "C 70 / M 0 / Y 90 / K 10", "MPRINT angepasst / druckbar", printed=True, approved=True, sks=[_preview_sk(manager, "SK 200010")]),
        _preview_row(manager, "CLR-900004", "FOGT BLAU MIT LANGER BEZEICHNUNG FUER MASCHINENTEST", "C 100 / M 60 / Y 10 / K 10", "MPRINT angepasst / druckbar", printed=True, approved=True, sks=[_preview_sk(manager, "FOG_BAD_003", True, "Marvin"), _preview_sk(manager, "FOG_BAD_011"), _preview_sk(manager, "FOG_BAD_020")]),
        _preview_row(manager, "CLR-900005", "ALLES ABGESCHLOSSEN", "C 30 / M 20 / Y 10 / K 0", "MPRINT angepasst / druckbar", printed=True, approved=True, sks=[_preview_sk(manager, "SK 300001", True, "Marvin"), _preview_sk(manager, "SK 300002", True, "Marvin")]),
        _preview_row(manager, "CLR-900007", "ADAM SCHWARZ LANGER GRUND", "C 80 / M 70 / Y 60 / K 100", "MPRINT angepasst / druckbar", printed=True, approved=True, sks=[_preview_sk(manager, "SK-SEHR-LANGE-123456789")], not_printable=True, reason="Sehr feine Negativschrift und massive Volltonflächen liegen in einer Anwendung zusammen. Die Maschine kann für diesen Eindruck nicht gleichzeitig scharf genug und flächig stabil genug eingestellt werden, ohne sichtbare Qualitätsverluste zu erzeugen."),
        _preview_row(manager, "CLR-900008", "SEHR HELLE FARBE", "C 0 / M 0 / Y 0 / K 0", "Noch nicht an MPRINT gedruckt"),
        _preview_row(manager, "CLR-900009", "TIEFSCHWARZ TEST", "C 80 / M 70 / Y 60 / K 100", "MPRINT angepasst / druckbar", printed=True, approved=True),
        _preview_row(manager, "CLR-900010", "OHNE CMYK WERT", "", "Noch nicht an MPRINT gedruckt"),
    ]
    fieldnames = [field for field in rows[0] if not field.startswith("_preview_")]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    manager._write_prepress_notes(
        [
            {
                "id": "NOTE-900001",
                "title": "Weinbiet Feldgrau",
                "text": "44 % Schwarz",
                "customer": "Weinbiet",
                "color": "Feldgrau",
                "sk_number": "SK 123456",
                "created_at": "2026-09-11 08:30:00",
                "created_by": "Marvin",
                "status": "offen",
                "completed_at": "",
                "completed_by": "",
                "history": [],
            }
        ]
    )


def _free_preview_port(start_port: int) -> int:
    for port in range(start_port, start_port + 40):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    return start_port


def run_color_overview_preview(port: int = 8766) -> None:
    preview_root = Path(tempfile.mkdtemp(prefix="mjet-helper-preview-"))
    preview_port = _free_preview_port(port)
    config = dict(DEFAULT_CONFIG)
    config.update(
        {
            "ui_preview_mode": True,
            "color_request_server_host": "127.0.0.1",
            "color_request_server_port": preview_port,
            "color_request_submit_url": f"http://127.0.0.1:{preview_port}/farbe",
            "color_overview_csv": str(preview_root / "work" / "preview_colors.csv"),
            "legacy_color_overview_csv": "",
            "color_overview_html": str(preview_root / "preview.html"),
            "color_export_json": str(preview_root / "export" / "preview_colors.json"),
            "hidden_colors_json": str(preview_root / "config" / "hidden_colors.json"),
            "prepress_notes_json": str(preview_root / "work" / "prepress_notes.json"),
            "backup_dir": str(preview_root / "backup"),
            "single_color_dir": str(preview_root / "unused_single_colors"),
            "color_root": str(preview_root / "unused_color_root"),
            "master_cct": str(preview_root / "unused_color_root" / "mprint4c-master.cct"),
        }
    )
    logger = HelperLogger(config)
    manager = PreviewColorTableManager(config, logger)
    _write_preview_data(config, manager)
    manager.refresh_color_overview()
    server = ColorRequestServer(config, logger, manager)
    server.start()
    url = f"http://127.0.0.1:{preview_port}/preview"
    print("UI PREVIEW - keine Produktionsdaten", flush=True)
    print(f"Preview-URL: {url}", flush=True)
    print(f"Temporärer Preview-Ordner: {preview_root}", flush=True)
    print("Beenden mit Ctrl+C", flush=True)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
        shutil.rmtree(preview_root, ignore_errors=True)


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
        self.color_mixer_window: ColorMixerWindow | None = None

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
        self.status_color_overview = StatusRow(status_box, "Farbstatus", emphasis=True)
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

        self._button(self.normal_frame, "🎨 Farbabgleich starten", self.start_color_sync)
        self._button(self.normal_frame, "📋 Farbübersicht", self.open_color_overview)
        self._button(self.normal_frame, "🎚 Farbmischer", self.open_color_mixer)
        self._button(self.normal_frame, "🧹 Druckdaten-Ordner leeren", self.clean_output_manual)
        self._build_pdf_controls(self.normal_frame)
        self.cancel_output_button = self._button(
            self.normal_frame,
            "⏹ Aufräumen stoppen",
            self.cancel_output_cleaning,
            style="secondary",
            pack_now=False,
        )
        self.rechner_button = self._button(self.normal_frame, "🧮 Rechner", self.toggle_calculator)

        self.calc_frame = self._build_calculator(self.normal_frame)
        self.calc_frame.pack_forget()

        spacer = tk.Frame(self.normal_frame, height=12, bg=THEME["window"])
        spacer.pack(fill="x")
        self._button(
            self.normal_frame,
            "⏻ Feierabend / Herunterfahren",
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
        self._update_color_overview_status()

        output_color, output_text = self.cleaner.output_status()
        job_color, job_text = self.cleaner.jobdir_status()
        self.status_output.set(output_color, output_text)
        if hasattr(self, "expert_jobdir_label"):
            self.expert_jobdir_label.configure(text=f"JobDir: {job_text}")
        self._maybe_auto_clean_output()

    def _update_color_overview_status(self) -> None:
        if not hasattr(self, "status_color_overview"):
            return
        if self.last_sync_result and self._result_has_color_overview_error(self.last_sync_result):
            self.status_color_overview.set("red", "Fehler")
            return
        if self.last_sync_result and self.last_sync_result.severity in {"green", "yellow"}:
            self.status_color_overview.set("green", "aktuell")
            return
        overview_csv = as_path(self.config.get("color_overview_csv", ""))
        overview_html = as_path(self.config.get("color_overview_html", ""))
        if overview_csv.exists() and overview_html.exists():
            self.status_color_overview.set("yellow", "prüfen")
        else:
            self.status_color_overview.set("red", "Fehler")

    def _result_has_color_overview_error(self, result: SyncResult) -> bool:
        messages = result.errors + result.warnings
        return any("Farbübersicht konnte nicht geschrieben werden" in message for message in messages)

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
        self._update_color_overview_status()
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
        if details and details[0] == result.message:
            details = details[1:]
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
        self._update_color_overview_status()
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

    def open_color_overview(self) -> None:
        configured = str(self.config.get("color_overview_html", "")).strip()
        if not configured:
            messagebox.showinfo(APP_NAME, "Die Farbübersicht wurde noch nicht erstellt.")
            return
        path = Path(configured)
        try:
            if not path.exists():
                parent = path.parent
                if str(parent) and not parent.exists():
                    messagebox.showwarning(APP_NAME, "Die Farbübersicht ist derzeit nicht erreichbar.")
                else:
                    messagebox.showinfo(APP_NAME, "Die Farbübersicht wurde noch nicht erstellt.")
                return
            if path.is_absolute():
                webbrowser.open(path.resolve().as_uri())
            else:
                webbrowser.open(str(path.resolve()))
            self.main_status_label.configure(text="Farbübersicht geöffnet")
        except Exception as exc:
            self.logger.log(f"Farbübersicht konnte nicht geöffnet werden: {exc}", "ERROR")
            messagebox.showwarning(APP_NAME, "Die Farbübersicht ist derzeit nicht erreichbar.")

    def open_color_mixer(self) -> None:
        try:
            if self.color_mixer_window and self.color_mixer_window.exists():
                self.color_mixer_window.show()
                return
            self.color_mixer_window = ColorMixerWindow(self.root, self.config)
            self.main_status_label.configure(text="Farbmischer geöffnet")
        except Exception as exc:
            self.logger.log(f"Farbmischer konnte nicht geöffnet werden: {exc}", "ERROR")
            messagebox.showerror(APP_NAME, f"Farbmischer konnte nicht geöffnet werden:\n{exc}")

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
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--preview", action="store_true", help="lokalen UI-Preview mit Demo-Daten starten")
    parser.add_argument("--preview-port", type=int, default=8766, help="Start-Port für den lokalen UI-Preview")
    args = parser.parse_args()
    if args.preview:
        run_color_overview_preview(args.preview_port)
        return

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
