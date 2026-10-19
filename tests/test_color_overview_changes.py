import csv
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from main import ColorTableManager, DEFAULT_CONFIG, HelperLogger, local_name


class ColorOverviewChangesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.single_dir = root / "Einzelfarben"
        self.single_dir.mkdir()
        self.master_path = root / "Maschinenfarben" / "master.cct"
        self.config = dict(DEFAULT_CONFIG)
        self.config.update(
            {
                "color_root": str(self.master_path.parent),
                "single_color_dir": str(self.single_dir),
                "master_cct": str(self.master_path),
                "backup_dir": str(root / "Backup"),
                "color_overview_csv": str(root / "work" / "colors.csv"),
                "color_overview_html": str(root / "overview.html"),
                "color_export_json": str(root / "export" / "colors.json"),
                "hidden_colors_json": str(root / "config" / "hidden.json"),
                "prepress_notes_json": str(root / "work" / "notes.json"),
                "legacy_color_overview_csv": "",
            }
        )
        self.master_path.parent.mkdir()
        self.manager = ColorTableManager(self.config, HelperLogger(self.config))

    def color_file(self, filename, entry_name, replacement):
        root = ET.Element("ColorTable", Name=Path(filename).stem)
        entry = ET.SubElement(
            root,
            "ColorEntry",
            Name=entry_name,
            ReplacementEnabled="true" if replacement else "false",
        )
        output = ET.SubElement(entry, "ColorOut", ColorModel="Custom" if replacement else "None")
        if replacement:
            ET.SubElement(output, "ComponentValues").text = "10 20 30 40"
        path = self.single_dir / filename
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        return path

    def overview_rows(self):
        with Path(self.config["color_overview_csv"]).open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle, delimiter=";"))

    def test_no_replacement_needs_no_matching_entry_or_master_write(self):
        path = self.color_file("Martinushof Türkis.cct", "Acker Martinushof Blau", False)
        tree = ET.parse(path)
        entry = next(part for part in tree.getroot().iter() if local_name(part.tag) == "ColorEntry")
        entry.set("ReplacementEnabled", "false")
        color_out = next(part for part in entry.iter() if local_name(part.tag) == "ColorOut")
        color_out.set("ColorModel", "Custom")
        ET.SubElement(color_out, "ComponentValues").text = "10 20 30 40"
        tree.write(path, encoding="utf-8", xml_declaration=True)
        source_bytes = path.read_bytes()
        candidate, errors, warnings = self.manager._single_color_candidate_from_file(path)
        self.assertFalse(errors)
        self.assertFalse(warnings)
        self.assertTrue(candidate.passthrough)
        result = self.manager.rebuild_master(write_master=True)
        self.assertEqual(result.severity, "green")
        self.assertFalse(self.master_path.exists())
        row = next(row for row in self.overview_rows() if row["Farbbezeichnung"] == "Martinushof Türkis")
        self.assertEqual(row["Status"], "Originalfarbe ohne Ersatzfarbe")
        self.assertEqual(row["In Masterdatei"], "nein")
        self.assertEqual(path.read_bytes(), source_bytes)

    def test_active_mismatch_still_warns_and_valid_entry_builds_master(self):
        self.color_file("Martinushof Türkis.cct", "Acker Martinushof Blau", False)
        self.color_file("Normal Blau.cct", "Normal Blau", True)
        bad = self.color_file("Eberbach Rot.cct", "Eberbach 7628 U", True)
        candidate, errors, warnings = self.manager._single_color_candidate_from_file(bad)
        self.assertIsNone(candidate)
        self.assertFalse(errors)
        self.assertTrue(warnings)
        self.assertIn("Ersatzfarbe aktiv", warnings[0])
        result = self.manager.rebuild_master(write_master=True)
        self.assertEqual(result.severity, "yellow")
        master_names = [
            entry.get("Name") for entry in ET.parse(self.master_path).iter()
            if local_name(entry.tag) == "ColorEntry"
        ]
        self.assertEqual(master_names, ["Normal Blau"])

    def test_matching_entry_without_replacement_has_neutral_overview_status(self):
        self.color_file("Eberbach Hellblau.cct", "Eberbach Hellblau", False)
        result = self.manager.rebuild_master(write_master=True)
        self.assertEqual(result.severity, "green")
        self.assertEqual(self.overview_rows()[0]["Status"], "Originalfarbe ohne Ersatzfarbe")
        self.assertTrue(self.master_path.exists())

    def test_prepress_rename_preserves_id_and_blocks_machine_colors(self):
        self.manager.add_requested_color("Farbteh ler")
        before = self.overview_rows()[0]
        result = self.manager.rename_overview_color("Farbteh ler", "Farbfehler")
        self.assertTrue(result["ok"])
        after = self.overview_rows()[0]
        self.assertEqual(after["color_id"], before["color_id"])
        self.assertEqual(after["Farbbezeichnung"], "Farbfehler")
        self.assertTrue(list((Path(self.config["color_overview_csv"]).parent / "Backup").glob("*.csv")))
        self.manager.add_requested_color("Anderer Name")
        self.assertEqual(self.manager.rename_overview_color("Farbfehler", "Anderer Name")["status"], 409)
        self.color_file("Normal Blau.cct", "Normal Blau", True)
        self.manager.rebuild_master(write_master=True)
        self.assertEqual(self.manager.rename_overview_color("Normal Blau", "Neu Blau")["status"], 409)
        self.assertTrue(Path(self.config["color_overview_html"]).read_text(encoding="utf-8").count("data:image/svg+xml;base64,"))


if __name__ == "__main__":
    unittest.main()
