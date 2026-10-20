# MJET-X Helper

Kleines Windows-Desktop-Tool für den Maschinenrechner der MJET-X / MPRINT IP2000i 4c.

Der Helper soll den Alltag an der Maschine einfacher machen:

- neue Kundenfarben in die Master-Farbtabelle übernehmen
- beim Start direkt zeigen, ob der Farbabgleich sauber ist
- den Druckdaten-Übergabeordner aufräumen, damit LP2000i nicht mit alten Dateien voll läuft
- eine gut lesbare Farbübersicht für die Vorstufe schreiben
- PDFs mit negativer Überfüllung/Choke vorbereiten
- auf Wunsch prüfen, ob eine neue Helper-Version bereitliegt

## Start

1. Diesen Ordner auf den Maschinenrechner kopieren.
2. Beim ersten Start die vorgeschlagenen Orte prüfen und speichern.
3. Starten:

```powershell
python main.py
```

Beim ersten Start wird die lokale Einstellung `helper_config.json` automatisch erzeugt, falls sie fehlt. Wer die fertige EXE nutzt, muss Python nicht separat anfassen.

## Ersteinrichtung / Setup

Wenn beim ersten Start wichtige Pfade fehlen, öffnet der MJET-X Helper einen Setup-Assistenten.

Dort werden nur die Orte festgelegt, an denen die Maschine arbeitet. Wenn ein Vorschlag passt, einfach so lassen.

Im Setup können gewählt werden:

- **Hauptordner der Maschine**
  Der gemeinsame Ordner, in dem die MJET-X ihre Farbdaten und die Übersicht ablegt.

- **Ordner für Maschinenfarben**
  Hier liegen die Farbdaten der Maschine, inklusive Master-Farbtabelle und einzelne Kundenfarben.

- **Ordner für einzelne Kundenfarben**
  Dort landen einzelne Spotfarben mit Kundennamen, zum Beispiel `Weingut_Beispiel_Blau`.

- **Backup-Ordner**
  Vor Änderungen speichert der Helper hier Sicherungskopien, damit nichts endgültig verloren geht.

- **Master-Farbtabelle**
  Die Sammeldatei für alle Kundenfarben. Der Helper überträgt neue Farbnamen automatisch dorthin, damit ColorGate neue Jobs mit den bekannten Farben verarbeiten kann.

- **Druckdaten-Übergabeordner**
  Das ist der Ordner, den ColorGate mit fertigen Druckdaten befüllt und aus dem LP2000i die Daten öffnet. Der Helper kann ihn automatisch bereinigen, damit dort nicht ständig alte Jobs in der Liste stehen.

- **Farbübersicht für die Vorstufe**
  Eine gut lesbare HTML-Datei mit Farbbezeichnung, Status, Datum und CMYK-Werten. Die Vorstufe kann dort Kundenfarben nachschauen und neue Farbnamen eintragen.

Zusätzlich gibt es ColorGate-Felder. Diese sind im Setup bewusst weniger prominent dargestellt, weil sie meistens automatisch erkannt werden:

- **ColorGate-Programmordner**
  Der Installationsordner von ColorGate auf dem Maschinenrechner.

- **ColorGate-Einstellungsdatei / Profil- und Auftragsdatei / Jobordner**
  Interne ColorGate-Orte. Diese bitte nur ändern, wenn die automatische Erkennung falsch ist.

Der Button `Ordner automatisch suchen` sucht nach dem Unterordner `Maschinenfarben` direkt im Netzlaufwerk `Z:\`. Er erkennt außerdem noch den früheren Aufbau mit einem zusätzlichen Ordner `_MPRINT_4c`. Alle Vorschläge bleiben manuell änderbar.

Beispiele für typische Orte:

```text
Z:\
C:\ProgramData\ColorGATE Software\Productionserver25
C:\Users\user\Desktop\OUTPUT_PRINTDATA
```

Das Setup kann später im Expertmodus erneut geöffnet werden:

```text
... -> Setup
```

## Update-Check

Der Helper prüft beim Start und über `... -> Update` das letzte **veröffentlichte** GitHub-Release. Eine neue Version wird nur nach Bestätigung heruntergeladen und installiert. Während eines Druckauftrags bitte kein Update starten.

Der Release-Abruf funktioniert ohne Anmeldung, solange das Repository öffentlich ist. Veröffentlicht wird ein Update erst, wenn ein Release mit dem passenden Installer bereitsteht.

Die Einstellung liegt lokal in `helper_config.json`:

```json
"update_check_enabled": true,
"update_check_url": "https://api.github.com/repos/vr4w/mjet-x-helper/releases/latest"
```

Bereits gespeicherte Einstellungen mit der alten Adresse zu `update_info.json` funktionieren weiter und werden intern auf das letzte Release umgeleitet. Andere eigene Prüfquellen können weiterhin Versionshinweise liefern, aber aus Sicherheitsgründen keinen Installer per Klick starten.

Der Helper akzeptiert nur den Installer mit passendem Versionsnamen aus `vr4w/mjet-x-helper`. Vor dem Start vergleicht er die heruntergeladene Datei mit der SHA-256-Prüfsumme des GitHub-Release-Assets. Bei fehlendem Installer, fehlender Prüfsumme oder abweichender Datei wird nichts installiert. Die bestehende Version bleibt dann geöffnet.

**Einmaliger Übergang:** Version 1.1.2 kann Updates nur anzeigen und muss einmal manuell durch Version 1.1.3 oder neuer ersetzt werden. Danach kann der Helper veröffentlichte Updates nach Bestätigung direkt installieren.

Wichtig: `helper_config.json` enthält lokale Maschinenpfade und wird nicht ins Repository aufgenommen. Für Weitergabe und neue Installationen gibt es `helper_config.example.json`.

## Was der Helper macht

- Baut aus den `.cct`- und `.ct`-Dateien im Ordner `Einzelfarben` eine neue `mprint4c-master.cct`.
- Kopiert die alte Masterdatei vor dem Ersetzen in den Backup-Ordner.
- Schreibt die neue Masterdatei zuerst als temporäre Datei und ersetzt sie danach atomar.
- Prüft beim Start, ob die Einzelfarben bereits in der Masterdatei stehen.
- Prüft `mprint mlabel.cos` im normalen Farbabgleich nicht.
- Version 1.1.1 baut nur die Masterdatei neu; ColorGate übernimmt diese Datei beim Import neuer Jobs.
- Schreibt bei jedem Farbabgleich eine gut lesbare Farbübersicht für die Vorstufe.
- Überwacht `OUTPUT_PRINTDATA` optional und löscht nur stabile Dateien im Hintergrund.
- Zeigt den JobDir-Status im Expertmodus an; JobDir wird nie automatisch geleert.
- Bietet einen kleinen Tasten-Rechner mit `+ - * /`, Klammern, `pt → mm` und `mm → pt`.
- Kann PDFs bei 3600 dpi als Rasterprozess reduzieren; die Choke-Stärke wird pro Durchlauf ausgewählt.
- Die PDF-Reduktion liegt in der Normalansicht und kann mehrere PDFs in einem Lauf verarbeiten.
- Speichert Fensterposition und Fenstergröße.

## Expertmodus

Der kleine `...`-Button oben rechts öffnet den Expertmodus.

Dort sieht man Logs, erkannte Farbnamen, Pfade und Zusatzbuttons für Setup, Konfig, Backup, Farben, ColorGate-Profil, Druckdaten, Info, reine Prüfung und Master-Neubau. Die Profilprüfung ist in Version 1.1.1 nur als spätere Zusatzfunktion vorgesehen und blockiert den Farbabgleich nicht.

## Farbübersicht für die Vorstufe

Die Farbübersicht ist die einfache Nachschlageseite für die Vorstufe. Dort stehen Farbbezeichnung, Status, Datum und CMYK-Werte, ohne dass jemand direkt in Farbtabelle oder Maschinenordner schauen muss.

Beim Setup wird gewählt, wo diese HTML-Datei liegen soll. Sinnvoll ist ein Ort, den die Vorstufe gut erreichen kann.

Die interne Datendatei liegt im MJET-X-Helper-Programmordner:

```text
work\MPRINT_Farbuebersicht_daten.csv
```

Wenn die Vorstufe in der HTML bei `Kundenfarbe eintragen` eine Farbe einträgt, speichert der laufende Helper diese Farbe intern und aktualisiert die HTML. Solange noch keine passende Einzelfarbe existiert, bleibt sie in der Übersicht mit:

```text
Noch nicht an MPRINT gedruckt
```

Sobald eine passende Einzelfarbe vorhanden ist und die Farbe in der Masterdatei steht, schreibt das Tool:

```text
MPRINT angepasst / druckbar
```

Die HTML-Datei ist die gut lesbare Ansicht für schnelles Nachschauen.

Wichtig: Damit das Eingabefeld in der HTML funktioniert, muss der MJET-X Helper laufen. Der Helper startet dafür einen kleinen lokalen Empfang auf Port `8765`. Falls die Vorstufe von einem anderen Rechner aus einträgt, muss dieser Port auf dem MPRINT-Rechner erreichbar sein.

Versteckter Adminmodus in der HTML: fünfmal auf die Überschrift `MPRINT Farbübersicht` klicken. Dann erscheint eine Löschspalte für falsche Übersichtseinträge. Echte Farben aus `Einzelfarben` oder der Masterdatei erscheinen beim nächsten Abgleich wieder automatisch.

Die HTML zeigt zusätzlich `Angelegt am`, `Gedruckt am` und die aus der Einzelfarbe gelesenen CMYK-Werte. `Gedruckt am` wird gesetzt, sobald die Farbe erstmals als `MPRINT angepasst / druckbar` erkannt wird.

## PDF Reduktion

Buttons:

```text
PDF 0,05 pt
PDF 0,07 pt
PDF 0,10 pt
PDF 0,15 pt
```

Das Tool fragt nach Klick auf eine der Stärken eine oder mehrere PDFs ab und erstellt neben jeder Originaldatei einen Ordner:

```text
<PDF-Name>_reduziert
```

Darin wird nur die ausgewählte Variante erzeugt:

```text
*_reduce_010pt.pdf
```

Die PDF wird dafür mit 3600 dpi gerastert. Die reduzierte Hauptgrafik wird als Volltonfarbe aus der Quell-PDF ausgegeben. QR-/EAN-artige Bereiche werden vorher auf einer Suchauflösung erkannt und mit einer Schutzbox ausgespart.

Wichtig: Die Quell-PDF muss eine echte Volltonfarbe enthalten. Das Tool verwendet die erste gefundene Separation-Volltonfarbe, ignoriert dabei aber `All`/Registrierungsfarbe.

Die Erkennung nutzt zwei Wege:

- Rastermuster im gerenderten Bild
- viele kleine PDF-Pfade/Rechtecke, wie sie bei QR-/EAN-Codes vorkommen können

Wenn keine Codebereiche sicher erkannt werden, öffnet das Tool ein kleines Vorschaubild:

```text
QR/EAN markieren
```

Dort kann der Bediener einen oder mehrere Kästen um QR-/EAN-Codes ziehen und mit `Markierung übernehmen` fortfahren. Die markierten Bereiche werden wie automatisch erkannte Codes geschützt.

Mit `Trotzdem ohne Code reduzieren` kann eine PDF ohne Codes bewusst weiterverarbeitet werden. Mit `Abbrechen` wird gestoppt, damit Codes nicht versehentlich beschädigt werden.

Wichtige Config-Werte:

```json
"pdf_reduce_dpi": 3600,
"pdf_reduce_detect_dpi": 300,
"pdf_reduce_code_protect_margin_mm": 3.0,
"pdf_reduce_abort_if_no_codes_found": true,
"pdf_reduce_vector_detection": true
```

Für den PyInstaller-Build müssen PyMuPDF und Pillow mit eingepackt werden. Falls lokal installiert werden muss:

```powershell
python -m pip install PyMuPDF Pillow
```

## PyInstaller Build (lokaler Notfallweg)

Der normale Windows-Build läuft über GitHub Actions. Falls nötig, kann weiterhin auf einem Windows-Rechner lokal gebaut werden:

```powershell
build_exe.bat
```

Die Datei erstellt eine lokale Build-Umgebung, installiert `pyinstaller`, `PyMuPDF` und `Pillow`, baut die EXE und kopiert `helper_config.json` neben die fertige EXE.

PyInstaller und die PDF-Pakete installieren:

```powershell
python -m pip install pyinstaller PyMuPDF Pillow
```

EXE bauen:

```powershell
pyinstaller --onefile --noconsole --clean --name MJETXHelper --collect-all fitz --collect-all PIL --hidden-import fitz --hidden-import PIL --hidden-import PIL.Image --hidden-import PIL.ImageChops --hidden-import PIL.ImageFilter --hidden-import PIL.PngImagePlugin main.py
```

Die fertige EXE liegt danach unter `dist\MJETXHelper.exe`.

Wichtig: `helper_config.json` muss neben der EXE liegen. Wenn sie dort fehlt, erstellt die EXE beim ersten Start eine neue Default-Datei. Interne Farbübersichts-Daten liegen unter `%LOCALAPPDATA%\MJET-X Helper\Data` und bleiben dadurch auch erhalten, wenn der Programmordner beim Update wechselt. Vorhandene `work`-Dateien werden beim ersten Start kopiert, nicht verschoben.

## Installer Build

Der Installer ist für die Weitergabe gedacht. Damit bekommt ein anderer Maschinenrechner eine normale Windows-Installation mit Startmenü-Eintrag und optionalem Autostart.

Der Ablauf auf Windows:

1. `build_exe.bat` starten.
2. Prüfen, ob `dist\MJETXHelper.exe` vorhanden ist.
3. Einmalig Inno Setup 6 installieren, falls es auf dem Build-Rechner noch fehlt.
4. `build_installer.bat` starten.

Die fertige Installer-Datei liegt danach unter:

```text
installer_dist\MJETXHelper_Setup_v1.1.6.exe
```

Der Installer legt den Helper bewusst im Benutzerordner ab:

```text
%LOCALAPPDATA%\MJET-X Helper
```

Das ist wichtig, weil der Helper dort seine lokale Einstellung und Logs speichern kann, ohne dass Windows nach Adminrechten fragt. Interne Farbübersichts-Daten liegen getrennt davon unter `%LOCALAPPDATA%\MJET-X Helper\Data`.

## GitHub / Release

1. Änderungen nach `main` bringen. `APP_VERSION` in `main.py` und `MyAppVersion` in `installer.iss` müssen gleich sein.
2. Für einen Test-Build auf einem Arbeitsbranch einen Pull Request nach `main` öffnen. Der Workflow **Windows-Installer** läuft dann automatisch und bietet den Installer als herunterladbares Workflow-Artefakt an. Nach Aufnahme des Workflows auf `main` kann er auch im GitHub-Reiter **Actions** manuell gestartet werden. Dabei wird noch kein Release veröffentlicht.
3. Für einen fertigen Stand auf `main` einen passenden Tag setzen und pushen, zum Beispiel `v1.1.6`. Der Workflow prüft Tag und Version, führt Tests aus, baut EXE und Installer und legt einen **Release-Entwurf** mit Installer an.
4. Release-Entwurf und Installer prüfen und das Release bewusst veröffentlichen. Erst dann erscheint es bei der Update-Prüfung an der Maschine.

Der Installer enthält keine `helper_config.json` und keine Farbübersichts-Arbeitsdaten. CSV, Vorstufenhinweise, Ausblendliste und Farbexport bleiben im lokalen Datenordner erhalten. Vorhandene relative `work/`- und `config/`-Dateien werden beim ersten Start kopiert; den Installationsordner vor einem Update nicht manuell löschen.

## Maschinen-Test nach Build

Nach dem Build auf dem MPRINT-Rechner sollte zuerst die echte EXE getestet werden:

1. `build_exe.bat` starten.
2. `dist\MJETXHelper.exe` öffnen.
3. Expertmodus über den `...`-Button öffnen.
4. `PDF 0,10 pt` mit der Felsenberg-Testdatei starten.
5. Ergebnis-PDF aus dem erzeugten Ordner `<PDF-Name>_reduziert` in ColorGate importieren.

Bitte dabei prüfen:

- Wird die Volltonfarbe in ColorGate als `Crusius dgrau` erkannt?
- Wird der Name nicht sichtbar als `Crusius#20dgrau` angezeigt?
- Bleiben QR/EAN-Bereiche sauber und lesbar?
- Wirkt feine Schrift bei 3600 dpi sichtbar besser als vorher?
- Bleiben Laufzeit und Speicherverbrauch am Maschinenrechner akzeptabel?
- Stimmen Ausgabeordner und Dateiname, zum Beispiel `*_reduce_010pt.pdf`?

Hinweis: `#20` ist in der PDF-Rohsyntax die normale Codierung für ein Leerzeichen. Wenn ColorGate daraus trotzdem einen sichtbaren Farbnamen mit `#20` macht, muss die Spot-Ausgabestruktur im PDF noch einmal angepasst werden.

## Bekannte Grenzen

- Wenn eine PDF mehrere echte Volltonfarben enthält, nimmt das Tool aktuell die erste gefundene Nicht-Registrierungsfarbe.
- Die manuelle QR/EAN-Markierung ist eingebaut, muss aber am Maschinenrechner praktisch mit Ziehen der Kästen getestet werden.
- QR/EAN-Schutzbereiche werden als unveränderte Rasterausschnitte über die Spot-Hauptgrafik gelegt.
- 3600 dpi ist bewusst als Qualitätsstandard gesetzt, kann bei sehr großen PDFs aber Laufzeit und RAM deutlich erhöhen.
- 4800 dpi ist nicht als Standard gesetzt. Ein späterer Testmodus wäre sinnvoll, falls 3600 dpi noch zu grob wirkt.

## Autostart

1. `Win + R` drücken.
2. `shell:startup` eingeben.
3. Eine Verknuepfung zu `MJETXHelper.exe` in diesen Ordner legen.

Das Tool läuft normal im Benutzerkontext. Dadurch bleiben gemappte Laufwerke wie `Z:` sichtbar.

## Feierabend / Herunterfahren

Der Button startet ohne Countdown und ohne Ja/Nein-Abfragen:

1. Farbabgleich ausführen.
2. `OUTPUT_PRINTDATA` stabil leeren.
3. Bekannte Programme sauber schließen.
4. Windows-Shutdown starten.

Im normalen Ablauf erscheint keine Bestätigung, damit Bediener nicht vor einem offenen Dialog stehen bleiben.

## Sicherheitshinweise

- Die `.cos`-Datei wird in Version 1.1.1 im normalen Farbabgleich nicht geprüft.
- JobDir wird nicht automatisch geleert.
- Der JobDir-Löschbutton ist nur im Expertmodus sichtbar.
- Es werden keine beliebigen Dialogfenster automatisch bestätigt.
- Beim Herunterfahren werden nur bekannte Prozessnamen aus der Config angesprochen.
- `taskkill` wird zuerst ohne `/F` genutzt. Erzwingen gibt es nur im Expertmodus.
- OUTPUT_PRINTDATA und JobDir löschen nur Dateien, keine Ordner.
- Dateien werden erst gelöscht, wenn sie alt genug sind und ihre Größe nach 2 Sekunden unverändert ist.

## Logs

Logs liegen unter:

```text
Z:\Maschinenfarben\Backup\helper_logs
```

Falls dieser Ordner nicht erreichbar ist, nutzt das Tool einen lokalen `helper_logs`-Ordner neben `main.py` beziehungsweise neben der EXE.
