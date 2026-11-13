import csv
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

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
                "cmyk_orders_json": str(root / "work" / "cmyk_orders.json"),
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

    def write_overview_csv(self, path, row):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(row), delimiter=";")
            writer.writeheader()
            writer.writerow(row)

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

    def test_prepress_and_machine_rename_preserve_identity_and_track_alias(self):
        self.manager.add_requested_color("Farbteh ler")
        before = self.overview_rows()[0]
        result = self.manager.rename_overview_color("Farbteh ler", "Farbfehler")
        self.assertTrue(result["ok"])
        after = self.overview_rows()[0]
        self.assertEqual(after["color_id"], before["color_id"])
        self.assertEqual(after["Farbbezeichnung"], "Farbfehler")
        self.assertTrue(list((Path(self.config["color_overview_csv"]).parent / "Backup").glob("*.csv")))
        self.manager.add_requested_color("Anderer Name")
        merged = self.manager.rename_overview_color("Farbfehler", "Anderer Name")
        self.assertTrue(merged["ok"])
        self.assertEqual(merged["merged_duplicates"], 1)
        self.color_file("Normal Blau.cct", "Normal Blau", True)
        self.manager.rebuild_master(write_master=True)
        cct_bytes = (self.single_dir / "Normal Blau.cct").read_bytes()
        master_bytes = self.master_path.read_bytes()
        renamed = self.manager.rename_overview_color("Normal Blau", "Normal Blau Korrigiert")
        self.assertTrue(renamed["ok"])
        row = next(row for row in self.overview_rows() if row["Farbbezeichnung"] == "Normal Blau Korrigiert")
        self.assertEqual(row["machine_color_name"], "Normal Blau")
        self.assertIn("Normal Blau", json.loads(row["color_aliases"]))
        self.assertEqual((self.single_dir / "Normal Blau.cct").read_bytes(), cct_bytes)
        self.assertEqual(self.master_path.read_bytes(), master_bytes)
        self.manager.refresh_color_overview()
        rows = self.overview_rows()
        self.assertEqual(sum(row["Farbbezeichnung"] == "Normal Blau Korrigiert" for row in rows), 1)
        self.assertFalse(any(row["Farbbezeichnung"] == "Normal Blau" for row in rows))
        self.assertTrue(Path(self.config["color_overview_html"]).read_text(encoding="utf-8").count("data:image/svg+xml;base64,"))

    def test_machine_alias_merges_numbered_newer_cct_into_single_overview_row(self):
        self.color_file("Crusius grau.cct", "Crusius grau", True)
        self.manager.rebuild_master(write_master=True)
        renamed = self.manager.rename_overview_color("Crusius grau", "Crusius grau korrigiert")
        self.assertTrue(renamed["ok"])
        self.color_file("Crusius grau korrigiert 2.cct", "Crusius grau korrigiert 2", True)

        self.manager.refresh_color_overview()

        rows = self.overview_rows()
        matches = [row for row in rows if row["Farbbezeichnung"] == "Crusius grau korrigiert"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["machine_color_name"], "Crusius grau korrigiert 2")
        self.assertIn("Crusius grau", json.loads(matches[0]["color_aliases"]))
        self.assertTrue((self.single_dir / "Crusius grau.cct").is_file())
        self.assertTrue((self.single_dir / "Crusius grau korrigiert 2.cct").is_file())

    def test_edit_dialog_can_merge_duplicate_rows_without_losing_sk_or_history(self):
        self.manager.add_requested_color("Crusius grau")
        self.manager.add_sk_assignment("Crusius grau", "SK 123")
        self.manager.mark_sk_printed("Crusius grau", "")
        self.manager.add_requested_color("Crusius grau Korrigiert")
        result = self.manager.rename_overview_color(
            "Crusius grau", "Crusius grau Korrigiert", aliases="Crusius grau Korrigiert"
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["merged_duplicates"], 1)
        rows = self.overview_rows()
        self.assertEqual(len(rows), 1)
        merged = rows[0]
        self.assertEqual(merged["Farbbezeichnung"], "Crusius grau Korrigiert")
        self.assertTrue(self.manager._truthy(merged["printed"]))
        self.assertEqual([item["sk_number"] for item in json.loads(merged["sk_assignments"])], ["SK 123"])
        self.assertTrue(any(event["event"] == "color_alias_merged" for event in json.loads(merged["history_events"])))
        self.assertTrue(list((Path(self.config["color_overview_csv"]).parent / "Backup").glob("*.csv")))

    def test_customer_assignment_survives_refresh_and_is_rendered_in_prepress_view(self):
        self.manager.add_requested_color("Schneider Blau")
        before = self.overview_rows()[0]

        result = self.manager.rename_overview_color("Schneider Blau", "Schneider Blau", "Schneider Druck")
        self.assertTrue(result["ok"])
        self.assertEqual(self.overview_rows()[0]["Kunde"], "Schneider Druck")
        self.assertEqual(self.overview_rows()[0]["color_id"], before["color_id"])

        self.manager.refresh_color_overview()
        after = self.overview_rows()[0]
        self.assertEqual(after["Kunde"], "Schneider Druck")
        html = Path(self.config["color_overview_html"]).read_text(encoding="utf-8")
        self.assertIn("Kunde: Schneider Druck", html)
        self.assertIn("data-customer=\"Schneider Druck\"", html)

        cleared = self.manager.rename_overview_color("Schneider Blau", "Schneider Blau", "")
        self.assertTrue(cleared["ok"])
        self.assertEqual(self.overview_rows()[0]["Kunde"], "")

    def test_total_color_count_is_shown_in_shared_overview_header(self):
        self.manager.add_requested_color("Schneider Blau")
        self.manager.add_requested_color("Schneider Rot")

        html = Path(self.config["color_overview_html"]).read_text(encoding="utf-8")
        self.assertIn('<span class="colorCount">· Farben gesamt: 2</span>', html)
        self.assertIn('<span class="versionTag">Version 1.4</span>', html)
        self.assertIn("position: absolute; top: 0; right: 0", html)
        self.assertIn("Weitere Namen / Dubletten", html)

    def test_machine_cards_follow_production_state_and_completed_colors_sort_first(self):
        names = ["A Offen", "B Gedruckt", "C Übernommen", "D Nicht druckbar"]
        for name in names:
            self.manager.add_requested_color(name)

        self.manager.mark_sk_printed("B Gedruckt", "")
        self.manager.add_sk_assignment("C Übernommen", "SK 123")
        self.manager.mark_sk_printed("C Übernommen", "")
        self.manager.mark_template_updated("C Übernommen", "SK 123", template_updated=True)
        self.manager.set_color_not_printable("D Nicht druckbar", "Teststatus")

        html = Path(self.config["color_overview_html"]).read_text(encoding="utf-8")
        self.assertIn('class="colorRow new machine-transferred" style="--machine-order:1"', html)
        self.assertIn('class="colorRow new machine-printed" style="--machine-order:2"', html)
        self.assertIn('class="colorRow new machine-pending" style="--machine-order:3"', html)
        self.assertIn('class="colorRow blocked machine-blocked" style="--machine-order:4"', html)
        self.assertIn("tr.machine-pending { background: #e9ecef", html)
        self.assertIn("tr.machine-printed { background: #ffffff; border: 1px solid #91ad98", html)
        self.assertIn("tr.machine-transferred { background: #f1f8f2; border: 2px solid #438052", html)
        self.assertIn("tr.machine-blocked { background: #f0eeee", html)
        self.assertIn('<span class="colorCount">· Farben gesamt: 4</span>', html)

    def test_marking_printable_enables_template_transfer_without_review_status(self):
        self.manager.add_requested_color("Schneider Druckbar")
        self.manager.add_sk_assignment("Schneider Druckbar", "SK 456")
        result = self.manager.mark_sk_printed("Schneider Druckbar", "")

        self.assertTrue(result["ok"])
        transfer = self.manager.mark_template_updated(
            "Schneider Druckbar", "SK 456", template_updated=True
        )
        self.assertTrue(transfer["ok"])
        html = Path(self.config["color_overview_html"]).read_text(encoding="utf-8")
        self.assertNotIn('data-action="approve"', html)
        self.assertNotIn("Prüfungen offen", html)
        self.assertNotIn("Prüfung abschließen", html)
        self.assertIn("Übernahmen verwalten", html)

    def test_machine_color_allows_customer_assignment_and_renaming(self):
        self.color_file("Schneider Blau.cct", "Schneider Blau", True)
        self.manager.rebuild_master(write_master=True)

        assigned = self.manager.rename_overview_color("Schneider Blau", "Schneider Blau", "Schneider Kunde 2")
        self.assertTrue(assigned["ok"])
        row = self.overview_rows()[0]
        self.assertEqual(row["Farbbezeichnung"], "Schneider Blau")
        self.assertEqual(row["Kunde"], "Schneider Kunde 2")

        renamed = self.manager.rename_overview_color("Schneider Blau", "Schneider Blau Neu", "Schneider Kunde 2")
        self.assertTrue(renamed["ok"])
        row = next(row for row in self.overview_rows() if row["Farbbezeichnung"] == "Schneider Blau Neu")
        self.assertEqual(row["machine_color_name"], "Schneider Blau")

    def test_prepress_colors_survive_install_folder_change(self):
        old_install = Path(self.temp.name) / "old-install"
        new_install = Path(self.temp.name) / "new-install"
        stable_data = Path(self.temp.name) / "user-data"
        legacy_csv = old_install / "work" / "MPRINT_Farbuebersicht_daten.csv"
        legacy_csv.parent.mkdir(parents=True)
        legacy_csv.write_text(
            "Farbbezeichnung;Quelle;source\nWittmann mblau 7690;Vorstufe;PREPRESS\n",
            encoding="utf-8-sig",
        )
        config = dict(self.config)
        config["color_overview_csv"] = "work/MPRINT_Farbuebersicht_daten.csv"
        manager = ColorTableManager(config, HelperLogger(config))

        with mock.patch("main.APP_DIR", old_install), mock.patch(
            "main.user_data_dir", return_value=stable_data
        ):
            migrated_csv = manager._overview_csv_path()
            self.assertEqual(migrated_csv.read_bytes(), legacy_csv.read_bytes())
            manager.refresh_color_overview()

        with mock.patch("main.APP_DIR", new_install), mock.patch(
            "main.user_data_dir", return_value=stable_data
        ):
            updated_manager = ColorTableManager(config, HelperLogger(config))
            self.assertEqual(updated_manager._overview_csv_path(), migrated_csv)
            updated_manager.refresh_color_overview()

        self.assertTrue(legacy_csv.exists())
        with migrated_csv.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter=";"))
        self.assertEqual([row["Farbbezeichnung"] for row in rows], ["Wittmann mblau 7690"])

    def test_workflow_state_recovers_when_existing_current_csv_is_freshly_rebuilt(self):
        old_install = Path(self.temp.name) / "old-install"
        stable_data = Path(self.temp.name) / "stable-user-data"
        old_csv = old_install / "work" / "MPRINT_Farbuebersicht_daten.csv"
        current_csv = stable_data / "work" / "MPRINT_Farbuebersicht_daten.csv"
        assignment = {
            "sk_number": "WOL_DIT_008",
            "printed": True,
            "printed_at": "2026-10-20 09:00:00",
            "approved": True,
            "approved_at": "2026-10-20 09:05:00",
            "template_updated": True,
            "template_updated_at": "2026-10-20 09:10:00",
            "portal_informed": False,
            "transfer_completed": True,
            "transfer_completed_at": "2026-10-20 09:10:00",
            "transfer_completed_by": "MS",
            "transfer_note": "",
        }
        preserved = {
            "Farbbezeichnung": "Wolff-Roll Rot",
            "Quelle": "MPRINT",
            "source": "MPRINT",
            "color_id": "CLR-000042",
            "printed": "ja",
            "printed_at": "2026-10-20 09:00:00",
            "approved": "ja",
            "approved_at": "2026-10-20 09:05:00",
            "sk_assignments": json.dumps([assignment]),
            "transfer": '{"completed":true,"template_updated":true,"portal_informed":false,"completed_at":"2026-10-20 09:10:00","completed_by":"MS","note":""}',
            "not_printable": "nein",
            "not_printable_at": "",
            "not_printable_by": "",
            "not_printable_reason": "",
            "history_events": '[{"event":"printed","timestamp":"2026-10-20T09:00:00","user":""},{"event":"approved","timestamp":"2026-10-20T09:05:00","user":"Andreas"}]',
            "machine_values": "[]",
        }
        reset = dict(preserved)
        reset.update(
            {
                "color_id": "CLR-000001",
                "printed": "nein",
                "printed_at": "",
                "approved": "nein",
                "approved_at": "",
                "sk_assignments": "[]",
                "transfer": '{"completed":false,"template_updated":false,"portal_informed":false,"completed_at":"","completed_by":"","note":""}',
                "history_events": "[]",
            }
        )
        self.write_overview_csv(old_csv, preserved)
        self.write_overview_csv(current_csv, reset)
        config = dict(self.config)
        config["color_overview_csv"] = "work/MPRINT_Farbuebersicht_daten.csv"
        manager = ColorTableManager(config, HelperLogger(config))

        with mock.patch("main.APP_DIR", old_install), mock.patch(
            "main.user_data_dir", return_value=stable_data
        ):
            manager.refresh_color_overview()

        self.config["color_overview_csv"] = str(current_csv)
        recovered = next(row for row in self.overview_rows() if row["Farbbezeichnung"] == "Wolff-Roll Rot")
        self.assertEqual(recovered["color_id"], "CLR-000042")
        self.assertEqual(recovered["printed"], "ja")
        self.assertEqual(recovered["approved"], "ja")
        recovered_assignment = json.loads(recovered["sk_assignments"])[0]
        self.assertEqual(recovered_assignment["sk_number"], "WOL_DIT_008")
        self.assertTrue(recovered_assignment["transfer_completed"])
        recovered_events = json.loads(recovered["history_events"])
        self.assertTrue(any(event["event"] == "printed" for event in recovered_events))
        self.assertTrue(any(event["event"] == "approved" for event in recovered_events))
        self.assertTrue(list((current_csv.parent / "Backup").glob("*_vor_Aenderung_*.csv")))

    def test_intentionally_cleared_state_is_not_restored_from_stale_install_csv(self):
        old_install = Path(self.temp.name) / "old-install"
        stable_data = Path(self.temp.name) / "stable-user-data"
        old_csv = old_install / "work" / "MPRINT_Farbuebersicht_daten.csv"
        current_csv = stable_data / "work" / "MPRINT_Farbuebersicht_daten.csv"
        old_row = {
            "Farbbezeichnung": "Adam Rot",
            "Quelle": "MPRINT",
            "source": "MPRINT",
            "printed": "nein",
            "approved": "nein",
            "sk_assignments": "[]",
            "transfer": "{}",
            "not_printable": "ja",
            "not_printable_at": "2026-10-19 10:00:00",
            "not_printable_by": "MS",
            "not_printable_reason": "Nicht stabil",
            "history_events": "[]",
            "machine_values": "[]",
        }
        current_row = dict(old_row)
        current_row.update(
            {
                "not_printable": "nein",
                "not_printable_at": "",
                "not_printable_by": "",
                "not_printable_reason": "",
                "history_events": '[{"event":"not_printable_cleared","timestamp":"2026-10-20T10:00:00","user":"MS"}]',
            }
        )
        self.write_overview_csv(old_csv, old_row)
        self.write_overview_csv(current_csv, current_row)
        config = dict(self.config)
        config["color_overview_csv"] = "work/MPRINT_Farbuebersicht_daten.csv"
        manager = ColorTableManager(config, HelperLogger(config))

        with mock.patch("main.APP_DIR", old_install), mock.patch(
            "main.user_data_dir", return_value=stable_data
        ):
            manager.refresh_color_overview()

        self.config["color_overview_csv"] = str(current_csv)
        current = next(row for row in self.overview_rows() if row["Farbbezeichnung"] == "Adam Rot")
        self.assertEqual(current["not_printable"], "nein")
        self.assertEqual(current["not_printable_reason"], "")
        events = json.loads(current["history_events"])
        self.assertTrue(any(event["event"] == "not_printable_cleared" for event in events))

    def test_workflow_state_recovers_from_machine_backup_after_local_reset(self):
        archive_source = Path(self.temp.name) / "previous-overview.csv"
        current_csv = Path(self.config["color_overview_csv"])
        saved = {
            "Farbbezeichnung": "Wolff-Roll Blau",
            "Quelle": "MPRINT",
            "source": "MPRINT",
            "color_id": "CLR-000055",
            "printed": "ja",
            "printed_at": "2026-10-20 11:00:00",
            "approved": "ja",
            "approved_at": "2026-10-20 11:05:00",
            "sk_assignments": '[{"sk_number":"WOL_DIT_009","transfer_completed":true,"transfer_completed_at":"2026-10-20 11:10:00"}]',
            "transfer": '{"completed":true}',
            "history_events": '[{"event":"printed","timestamp":"2026-10-20T11:00:00","user":""}]',
            "machine_values": "[]",
        }
        self.write_overview_csv(archive_source, saved)
        archive_path = self.manager._archive_color_overview(archive_source)
        reset = dict(saved)
        reset.update(
            {
                "color_id": "CLR-000001",
                "printed": "nein",
                "printed_at": "",
                "approved": "nein",
                "approved_at": "",
                "sk_assignments": "[]",
                "transfer": "{}",
                "history_events": "[]",
            }
        )
        self.write_overview_csv(current_csv, reset)

        self.manager.refresh_color_overview()

        self.config["color_overview_csv"] = str(current_csv)
        recovered = next(row for row in self.overview_rows() if row["Farbbezeichnung"] == "Wolff-Roll Blau")
        self.assertEqual(recovered["color_id"], "CLR-000055")
        self.assertEqual(recovered["printed"], "ja")
        self.assertEqual(recovered["approved"], "ja")
        self.assertTrue(json.loads(recovered["sk_assignments"])[0]["transfer_completed"])
        self.assertTrue(archive_path.is_file())
        self.assertEqual(len(list(archive_path.parent.glob("Farbuebersicht_*.csv"))), 2)

    def test_overview_change_is_blocked_if_machine_backup_cannot_be_written(self):
        current_csv = Path(self.config["color_overview_csv"])
        row = {"Farbbezeichnung": "Bestehende Farbe", "printed": "ja"}
        self.write_overview_csv(current_csv, row)
        before = current_csv.read_bytes()
        temp_csv = current_csv.with_suffix(".csv.tmp")
        temp_csv.write_text("neue Daten", encoding="utf-8")

        with mock.patch.object(self.manager, "_archive_color_overview", side_effect=OSError("NAS nicht erreichbar")):
            with self.assertRaisesRegex(OSError, "nicht geändert"):
                self.manager._replace_color_overview(temp_csv, current_csv)

        self.assertEqual(current_csv.read_bytes(), before)
        self.assertFalse(temp_csv.exists())

    def test_cmyk_order_persists_and_joins_customer_color_table(self):
        self.manager.add_requested_color("VOGT Blau")
        added = self.manager.add_cmyk_order(
            "VOGT", "SK 123456", machine_info="Grau 44 % K, Tiefschwarz angepasst", created_by="Marvin"
        )
        self.assertTrue(added["ok"])
        order_id = added["order"]["id"]

        duplicate = self.manager.add_cmyk_order("vogt", "SK 123456")
        self.assertFalse(duplicate["ok"])
        self.assertEqual(duplicate["status"], 409)

        changed = self.manager.update_cmyk_order(order_id, status="druckbar", changed_by="Thao")
        self.assertTrue(changed["ok"])
        self.manager.refresh_color_overview()

        reloaded = ColorTableManager(self.config, HelperLogger(self.config))
        orders = reloaded._read_cmyk_orders()
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["status"], "druckbar")
        self.assertEqual(orders[0]["machine_info"], "Grau 44 % K, Tiefschwarz angepasst")
        self.assertEqual(orders[0]["created_by"], "Marvin")
        self.assertEqual(orders[0]["history"][-1]["user"], "Thao")

        rows = self.overview_rows()
        spot = next(row for row in rows if row["Farbbezeichnung"] == "VOGT Blau")
        self.assertEqual(spot["printed"], "nein")
        self.assertEqual(len(orders), 1)

        html = Path(self.config["color_overview_html"]).read_text(encoding="utf-8")
        self.assertIn('id="cmykOrderForm" class="cmykOrderForm"', html)
        self.assertNotIn('id="cmykOrderForm" class="cmykOrderForm" data-machine-only hidden', html)
        self.assertIn('id="overviewRows"', html)
        self.assertIn("function renderCmykOrders(orders)", html)
        self.assertIn("customerGroupHeader", html)
        self.assertIn("groupFor(customer, customer)", html)
        self.assertNotIn('id="cmykOrderList"', html)
        self.assertIn("VOGT Blau", html)
        self.assertIn("/api/cmyk-orders", html)

    def test_corrupt_cmyk_order_file_is_never_overwritten(self):
        path = Path(self.config["cmyk_orders_json"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ kaputt", encoding="utf-8")
        before = path.read_bytes()

        with self.assertRaisesRegex(ValueError, "beschädigt"):
            self.manager.add_cmyk_order("Eberle Runkel", "SK 999")

        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
