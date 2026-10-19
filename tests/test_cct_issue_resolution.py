import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from main import ColorTableManager, DEFAULT_CONFIG, HelperLogger


class CctIssueResolutionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.single = self.root / "Einzelfarben"
        self.single.mkdir()
        self.config = dict(DEFAULT_CONFIG)
        self.config.update({
            "color_root": str(self.root),
            "single_color_dir": str(self.single),
            "master_cct": str(self.root / "master.cct"),
            "backup_dir": str(self.root / "Backup"),
        })
        self.manager = ColorTableManager(self.config, HelperLogger(self.config))

    def make_file(self, filename, entry_name=None, model="Custom", enabled="true", values="10 20 30 40"):
        root = ET.Element("ColorTable", Name=Path(filename).stem)
        if entry_name is not None:
            entry = ET.SubElement(root, "ColorEntry", Name=entry_name, ReplacementEnabled=enabled)
            output = ET.SubElement(entry, "ColorOut", ColorModel=model)
            if values:
                ET.SubElement(output, "ComponentValues").text = values
        path = self.single / filename
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        return path

    def test_similar_names_offer_explicit_repairs(self):
        path = self.make_file("Carl-Koch rot 1807.cct", "Carl Koch 1807 rot")
        issue, = self.manager.inspect_single_color_issues()
        self.assertEqual(issue.kind, "mismatch")
        self.assertTrue(issue.can_rename)
        self.assertFalse(issue.can_accept_without_replacement)
        original = path.read_bytes()
        target = self.manager.resolve_single_color_issue(issue, "rename_file")
        self.assertEqual(target.name, "Carl Koch 1807 rot.cct")
        self.assertFalse(path.exists())
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(len(list((self.root / "Backup").glob("*.cct"))), 1)
        self.assertEqual(self.manager.inspect_single_color_issues(), [])

    def test_rename_entry_keeps_actual_replacement_values_and_creates_backup(self):
        path = self.make_file("Carl-Koch rot 1807.cct", "Carl Koch 1807 rot")
        issue, = self.manager.inspect_single_color_issues()
        original = path.read_bytes()
        self.manager.resolve_single_color_issue(issue, "rename_entry")
        entry = next(part for part in ET.parse(path).getroot() if part.tag.endswith("ColorEntry"))
        self.assertEqual(entry.get("Name"), "Carl-Koch rot 1807")
        self.assertEqual(entry.find("ColorOut/ComponentValues").text, "10 20 30 40")
        self.assertEqual(next((self.root / "Backup").glob("*.cct")).read_bytes(), original)
        self.assertFalse(self.manager.inspect_single_color_issues())

    def test_foreign_color_only_allows_manual_resolution(self):
        path = self.make_file("FOGT BLAU.cct", "Peters ROT 300")
        issue, = self.manager.inspect_single_color_issues()
        self.assertEqual(issue.kind, "foreign")
        self.assertIn("Peters ROT 300", issue.entries[0])
        self.assertFalse(issue.can_rename)
        self.assertFalse(issue.can_accept_without_replacement)
        with self.assertRaises(ValueError):
            self.manager.resolve_single_color_issue(issue, "rename_entry")
        self.assertTrue(path.exists())
        self.assertFalse(list((self.root / "Backup").glob("*.cct")))

    def test_foreign_name_without_replacement_values_is_accepted_as_original(self):
        path = self.make_file("FOGT BLAU.cct", "Peters ROT 300", model="None", values="")
        source_bytes = path.read_bytes()
        self.assertEqual(self.manager.inspect_single_color_issues(), [])
        candidate, errors, warnings = self.manager._single_color_candidate_from_file(path)
        self.assertFalse(errors)
        self.assertFalse(warnings)
        self.assertTrue(candidate.passthrough)
        self.assertEqual(path.read_bytes(), source_bytes)
        self.assertFalse(list((self.root / "Backup").glob("*.cct")))

    def test_enabled_without_replacement_values_is_accepted_without_rewriting_file(self):
        path = self.make_file("Eberbach Rot.cct", "Eberbach 7628 U", model="None", values="")
        original = path.read_bytes()
        self.assertEqual(self.manager.inspect_single_color_issues(), [])
        candidate, errors, warnings = self.manager._single_color_candidate_from_file(path)
        self.assertFalse(errors)
        self.assertFalse(warnings)
        self.assertTrue(candidate.passthrough)
        self.assertEqual(path.read_bytes(), original)
        self.assertFalse(list((self.root / "Backup").glob("*.cct")))

    def test_matching_name_with_no_replacement_values_is_accepted_automatically(self):
        path = self.make_file("Eberbach Rot.cct", "Eberbach Rot", model="None", values="")
        self.assertEqual(self.manager.inspect_single_color_issues(), [])
        candidate, errors, warnings = self.manager._single_color_candidate_from_file(path)
        self.assertIsNotNone(candidate)
        self.assertFalse(candidate.passthrough)
        self.assertFalse(errors)
        self.assertFalse(warnings)

    def test_missing_color_out_is_accepted_automatically(self):
        path = self.make_file("Eberbach Rot.cct", "Eberbach Rot")
        tree = ET.parse(path)
        tree.getroot().find("ColorEntry").remove(tree.getroot().find("ColorEntry/ColorOut"))
        tree.write(path, encoding="utf-8", xml_declaration=True)
        self.assertEqual(self.manager.inspect_single_color_issues(), [])
        candidate, errors, warnings = self.manager._single_color_candidate_from_file(path)
        self.assertIsNotNone(candidate)
        self.assertFalse(errors)
        self.assertFalse(warnings)
        entry = next(part for part in ET.parse(path).getroot() if part.tag.endswith("ColorEntry"))
        self.assertEqual(entry.get("ReplacementEnabled"), "true")
        self.assertIsNone(entry.find("ColorOut"))

    def test_real_replacement_and_filename_collision_are_not_overwritten(self):
        path = self.make_file("Carl-Koch rot 1807.cct", "Carl Koch 1807 rot")
        other = self.make_file("Carl Koch 1807 rot.cct", "Carl Koch 1807 rot")
        issue, = self.manager.inspect_single_color_issues()
        with self.assertRaises(FileExistsError):
            self.manager.resolve_single_color_issue(issue, "rename_file")
        with self.assertRaises(ValueError):
            self.manager.resolve_single_color_issue(issue, "without_replacement")
        self.assertTrue(path.exists())
        self.assertTrue(other.exists())
        self.assertFalse(list((self.root / "Backup").glob("*.cct")))

    def test_stale_issue_must_be_rechecked(self):
        path = self.make_file("Carl-Koch rot 1807.cct", "Carl Koch 1807 rot")
        issue, = self.manager.inspect_single_color_issues()
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaises(RuntimeError):
            self.manager.resolve_single_color_issue(issue, "rename_entry")
        self.assertFalse(list((self.root / "Backup").glob("*.cct")))


if __name__ == "__main__":
    unittest.main()
