from __future__ import annotations

import re
import tkinter as tk
import xml.etree.ElementTree as ET
import json
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk


APP_DIR = Path(__file__).resolve().parent
DEFAULT_REFERENCE_JSON = APP_DIR / "data" / "reference_colors.json"


def cmyk_to_rgb(c: int | float, m: int | float, y: int | float, k: int | float) -> tuple[int, int, int]:
    c_value = _clamp_percent(c) / 100
    m_value = _clamp_percent(m) / 100
    y_value = _clamp_percent(y) / 100
    k_value = _clamp_percent(k) / 100
    r = round(255 * (1 - c_value) * (1 - k_value))
    g = round(255 * (1 - m_value) * (1 - k_value))
    b = round(255 * (1 - y_value) * (1 - k_value))
    return (_clamp_rgb(r), _clamp_rgb(g), _clamp_rgb(b))


def _clamp_percent(value: int | float | str) -> int:
    try:
        number = int(round(float(str(value).replace(",", "."))))
    except Exception:
        number = 0
    return max(0, min(100, number))


def _clamp_rgb(value: int | float) -> int:
    return max(0, min(255, int(round(value))))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def normalize_reference_query(value: str) -> tuple[str, str, str]:
    text = re.sub(r"\s+", " ", value.strip().upper())
    text = re.sub(r"\bPANTONE\b", "", text).strip()
    text = re.sub(r"\bHKS\b", "", text).strip()
    number_match = re.search(r"\d+", text)
    search_number = number_match.group(0) if number_match else ""
    remainder = text
    if number_match:
        remainder = (text[: number_match.start()] + " " + text[number_match.end() :]).strip()
    variant_match = re.search(r"\b([A-Z])\b", remainder)
    variant = variant_match.group(1) if variant_match else ""
    normalized = re.sub(r"[^A-Z0-9]+", " ", text).strip()
    return normalized, search_number, variant


@dataclass(frozen=True)
class ReferenceColor:
    system: str
    name: str
    search_number: str
    variant: str
    c: int
    m: int
    y: int
    k: int

    @property
    def cmyk_text(self) -> str:
        return f"C {self.c} % / M {self.m} % / Y {self.y} % / K {self.k} %"

    @property
    def origin_label(self) -> str:
        if self.system == "MPRINT":
            return "MPRINT"
        return f"{self.system} Referenz"

    @property
    def origin_note(self) -> str:
        if self.system == "MPRINT":
            return "Produktionswert – bereits verwendet"
        return "Referenzwert – nicht maschinell geprüft"


class LocalColorReferenceProvider:
    def __init__(self, config: dict):
        self.config = config
        self._colors: list[ReferenceColor] | None = None

    def colors(self) -> list[ReferenceColor]:
        if self._colors is None:
            self._colors = self._load_colors()
        return list(self._colors)

    def search(self, query: str, limit: int = 30) -> list[ReferenceColor]:
        normalized, search_number, variant = normalize_reference_query(query)
        if not normalized:
            return []
        system_filter = self._system_filter(query)
        matches: list[ReferenceColor] = []
        for color in self.colors():
            if system_filter and color.system != system_filter:
                continue
            name_normalized, color_number, color_variant = normalize_reference_query(color.name)
            if search_number:
                if color.search_number != search_number and color_number != search_number:
                    continue
                if variant and color.variant != variant and color_variant != variant:
                    continue
            elif normalized not in name_normalized:
                continue
            matches.append(color)
            if len(matches) >= limit:
                break
        return matches

    def _load_colors(self) -> list[ReferenceColor]:
        candidates = self._candidate_files()
        colors: list[ReferenceColor] = []
        seen: set[tuple[str, str]] = set()
        for path in candidates:
            for color in self._read_color_file(path):
                key = (color.system, color.name.casefold())
                if key in seen:
                    continue
                seen.add(key)
                colors.append(color)
        for color in self._read_offline_reference_file():
            key = (color.system, color.name.casefold())
            if key in seen:
                continue
            seen.add(key)
            colors.append(color)
        colors.sort(key=lambda item: (self._system_sort(item.system), item.name.casefold()))
        return colors

    def _candidate_files(self) -> list[Path]:
        paths: list[Path] = []
        single_dir = Path(str(self.config.get("single_color_dir", "")))
        if single_dir.exists():
            paths.extend(sorted(single_dir.glob("*.cct")))
        master_path = Path(str(self.config.get("master_cct", "")))
        if master_path.exists():
            paths.append(master_path)
        return paths

    def _read_color_file(self, path: Path) -> list[ReferenceColor]:
        try:
            tree = ET.parse(path)
        except Exception:
            return []
        colors: list[ReferenceColor] = []
        for entry in tree.getroot().iter():
            if _local_name(entry.tag) != "ColorEntry":
                continue
            name = str(entry.attrib.get("Name", "")).strip()
            values = _entry_cmyk(entry)
            if not name or values is None:
                continue
            name = _normalize_mprint_name(name, path)
            _, search_number, variant = normalize_reference_query(name)
            colors.append(ReferenceColor("MPRINT", name, search_number, variant, *values))
        return colors

    def _read_offline_reference_file(self) -> list[ReferenceColor]:
        path = Path(str(self.config.get("reference_colors_json", ""))).expanduser()
        if not str(path) or not path.exists():
            path = DEFAULT_REFERENCE_JSON
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        colors: list[ReferenceColor] = []
        for item in payload.get("colors", []):
            if not isinstance(item, dict):
                continue
            system = str(item.get("system", "")).upper().strip()
            if system not in {"PANTONE", "HKS"}:
                continue
            name = str(item.get("name", "")).strip()
            number = str(item.get("number", "")).strip()
            variant = str(item.get("variant", "")).upper().strip()
            if not name or not number:
                continue
            colors.append(
                ReferenceColor(
                    system,
                    name,
                    number,
                    variant,
                    _clamp_percent(item.get("c", 0)),
                    _clamp_percent(item.get("m", 0)),
                    _clamp_percent(item.get("y", 0)),
                    _clamp_percent(item.get("k", 0)),
                )
            )
        return colors

    def _system_filter(self, query: str) -> str:
        upper = query.upper()
        if re.search(r"\bPANTONE\b", upper):
            return "PANTONE"
        if re.search(r"\bHKS\b", upper):
            return "HKS"
        return ""

    def _system_sort(self, system: str) -> int:
        return {"MPRINT": 0, "PANTONE": 1, "HKS": 2}.get(system, 9)


def _entry_cmyk(entry: ET.Element) -> tuple[int, int, int, int] | None:
    color_out = None
    for elem in entry.iter():
        if _local_name(elem.tag) == "ColorOut":
            color_out = elem
            break
    if color_out is None:
        return None
    values_text = ""
    for elem in color_out.iter():
        if _local_name(elem.tag) == "ComponentValues" and elem.text:
            values_text = elem.text.strip()
            break
    parts = re.findall(r"-?\d+(?:[.,]\d+)?", values_text)
    if len(parts) < 4:
        return None
    return tuple(_clamp_percent(part) for part in parts[:4])  # type: ignore[return-value]


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _normalize_mprint_name(name: str, path: Path) -> str:
    generic_names = {"eindruckfarbe", "eindruckfarbe2", "test", "custom", "sonderfarbe"}
    file_name = path.stem.strip()
    if file_name and name.casefold() in generic_names and file_name.casefold() != name.casefold():
        return file_name
    return name


class ColorMixerWindow:
    def __init__(self, parent: tk.Tk, config: dict):
        self.parent = parent
        self.config = config
        self.provider = LocalColorReferenceProvider(config)
        self.reference_matches: list[ReferenceColor] = []
        self.selected_reference: ReferenceColor | None = None
        self.window = tk.Toplevel(parent)
        self.window.title("Farbmischer")
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.values = {
            "C": tk.IntVar(value=0),
            "M": tk.IntVar(value=0),
            "Y": tk.IntVar(value=0),
            "K": tk.IntVar(value=0),
        }
        self.value_labels: dict[str, tk.Label] = {}
        self._build()
        self.update_preview()
        self.window.focus_set()

    def show(self) -> None:
        self.window.deiconify()
        self.window.lift()
        self.window.focus_set()

    def exists(self) -> bool:
        try:
            return bool(self.window.winfo_exists())
        except Exception:
            return False

    def close(self) -> None:
        self.window.destroy()

    def _build(self) -> None:
        outer = ttk.Frame(self.window, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")
        preview_box = ttk.Frame(outer)
        preview_box.grid(row=0, column=0, sticky="n", padx=(0, 14))
        self.preview = tk.Frame(preview_box, width=220, height=220, relief="solid", bd=1)
        self.preview.grid(row=0, column=0)
        self.preview.grid_propagate(False)
        ttk.Label(
            preview_box,
            text="Bildschirmdarstellung dient nur zur Orientierung.",
            wraplength=220,
            justify="center",
        ).grid(row=1, column=0, pady=(8, 0))

        controls = ttk.Frame(outer)
        controls.grid(row=0, column=1, sticky="nsew")
        for index, channel in enumerate(("C", "M", "Y", "K")):
            self._build_slider_row(controls, channel, index)

        ttk.Button(controls, text="Zurücksetzen", command=self.reset).grid(row=4, column=0, columnspan=4, sticky="ew", pady=(8, 14))

        search_box = ttk.LabelFrame(controls, text="Referenzfarbe suchen", padding=8)
        search_box.grid(row=5, column=0, columnspan=4, sticky="ew")
        self.search_var = tk.StringVar(value="")
        search_entry = ttk.Entry(search_box, textvariable=self.search_var, width=28)
        search_entry.grid(row=0, column=0, sticky="ew")
        search_entry.bind("<KeyRelease>", lambda _event: self.search_references())
        search_entry.bind("<Return>", lambda _event: self.search_references())
        search_box.columnconfigure(0, weight=1)

        self.result_list = tk.Listbox(search_box, height=6, width=34, exportselection=False)
        self.result_list.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.result_list.bind("<<ListboxSelect>>", lambda _event: self.apply_selected_reference())
        self.reference_status = ttk.Label(search_box, text=f"{len(self.provider.colors())} lokale Referenzfarben verfügbar")
        self.reference_status.grid(row=2, column=0, sticky="w", pady=(6, 0))
        self.selected_label = ttk.Label(search_box, text="Ausgangspunkt: -")
        self.selected_label.grid(row=3, column=0, sticky="w", pady=(4, 0))
        self.selected_note = ttk.Label(search_box, text="")
        self.selected_note.grid(row=4, column=0, sticky="w", pady=(2, 0))

    def _build_slider_row(self, parent: ttk.Frame, channel: str, row: int) -> None:
        ttk.Label(parent, text=channel, width=2).grid(row=row, column=0, sticky="w", pady=4)
        scale = ttk.Scale(
            parent,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.values[channel],
            command=lambda _value, key=channel: self.on_value_changed(key),
            length=230,
        )
        scale.grid(row=row, column=1, sticky="ew", pady=4)
        spinbox = tk.Spinbox(
            parent,
            from_=0,
            to=100,
            width=4,
            textvariable=self.values[channel],
            command=lambda key=channel: self.on_value_changed(key),
        )
        spinbox.grid(row=row, column=2, padx=(8, 4), pady=4)
        spinbox.bind("<KeyRelease>", lambda _event, key=channel: self.on_value_changed(key))
        label = ttk.Label(parent, text=f"{channel} 0 %", width=8)
        label.grid(row=row, column=3, sticky="w", pady=4)
        self.value_labels[channel] = label

    def on_value_changed(self, channel: str) -> None:
        current = self._safe_var_value(channel)
        value = _clamp_percent(current)
        if current != value:
            self.values[channel].set(value)
        if self.selected_reference:
            self.selected_label.configure(
                text=f"Ausgangspunkt: {self.selected_reference.origin_label} · {self.selected_reference.name} · manuell angepasst"
            )
        self.update_preview()

    def update_preview(self) -> None:
        c, m, y, k = self.current_values()
        for channel, value in zip(("C", "M", "Y", "K"), (c, m, y, k)):
            self.value_labels[channel].configure(text=f"{channel} {value} %")
        self.preview.configure(bg=rgb_to_hex(cmyk_to_rgb(c, m, y, k)))

    def current_values(self) -> tuple[int, int, int, int]:
        return tuple(_clamp_percent(self._safe_var_value(channel)) for channel in ("C", "M", "Y", "K"))  # type: ignore[return-value]

    def _safe_var_value(self, channel: str) -> int:
        try:
            return int(self.values[channel].get())
        except Exception:
            return 0

    def search_references(self) -> None:
        query = self.search_var.get()
        self.reference_matches = self.provider.search(query)
        self.result_list.delete(0, "end")
        for color in self.reference_matches:
            marker = "MPRINT" if color.system == "MPRINT" else f"{color.system} Referenz"
            self.result_list.insert("end", f"{marker} · {color.name} · {color.cmyk_text}")
        if query.strip() and not self.reference_matches:
            self.reference_status.configure(text="Keine passende lokale Referenzfarbe gefunden")
        else:
            self.reference_status.configure(text=f"{len(self.reference_matches)} Treffer")

    def apply_selected_reference(self) -> None:
        selection = self.result_list.curselection()
        if not selection:
            return
        color = self.reference_matches[selection[0]]
        self.selected_reference = color
        for channel, value in zip(("C", "M", "Y", "K"), (color.c, color.m, color.y, color.k)):
            self.values[channel].set(value)
        self.selected_label.configure(text=f"Ausgangspunkt: {color.origin_label} · {color.name}")
        self.selected_note.configure(text=color.origin_note)
        self.update_preview()

    def reset(self) -> None:
        for value in self.values.values():
            value.set(0)
        self.search_var.set("")
        self.reference_matches = []
        self.selected_reference = None
        self.result_list.delete(0, "end")
        self.reference_status.configure(text=f"{len(self.provider.colors())} lokale Referenzfarben verfügbar")
        self.selected_label.configure(text="Ausgangspunkt: -")
        self.selected_note.configure(text="")
        self.update_preview()
