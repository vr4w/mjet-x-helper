# MJET HTML-Farbuebersicht: Zeitstempel und Verbindungstest

Stand: 2026-08-05

## Produktive Basis

Die Korrektur basiert lokal auf Commit `d91f27e` / Version `1.1.1`.

Grund: In diesem Stand stehen `APP_VERSION = "1.1.1"`, `installer.iss` erzeugt
`MJETXHelper_Setup_v1.1.1.exe`, und `update_info.json` verweist ebenfalls auf
diesen Installer. Ein direkt im Installer eingebetteter Git-Commit wurde nicht
gefunden, deshalb ist `d91f27e` der wahrscheinlichste produktive Quellstand.

Die Arbeiten liegen auf der lokalen Branch:

`fix/mjet-html-timestamps-and-fetch`

## Ursache der falschen Datumswerte

Die HTML-Farbuebersicht wurde bei jedem Farbabgleich neu aus CSV, Einzelfarben
und Masterdatei aufgebaut. Wenn ein alter Eintrag kein Datum hatte, hat der
Helper bisher automatisch die aktuelle Uhrzeit eingetragen.

Dadurch konnten viele Farben denselben Wert bei `Angelegt am` bekommen. Wenn
eine Farbe gleichzeitig als Einzelfarbe und in der Masterdatei gefunden wurde,
wurde ausserdem `Gedruckt am` automatisch mit der aktuellen Uhrzeit gefuellt.
Das war keine echte Druckhistorie.

## Neues Zeitmodell

`created_at`

Erster sicherer Zeitpunkt, an dem eine Farbe durch den Helper neu angelegt oder
ueber die HTML-Seite eingetragen wurde.

`last_printed_at`

Nur fuer echte Druckereignisse gedacht. Der Helper erfindet diesen Wert nicht
mehr, nur weil eine Farbe in Einzelfarbe und Masterdatei vorhanden ist.

`last_synced_at`

Wird bei jedem Abgleich aktualisiert und bedeutet: Diese Farbe wurde zuletzt vom
Helper gesehen beziehungsweise synchronisiert.

`legacy_created_at` und `legacy_printed_at`

Alte Werte aus den bisherigen Spalten werden beim ersten neuen Schreiben
gesichert, aber nicht mehr als sichere Historie angezeigt. Vor der Migration
wird neben der CSV automatisch ein Backup mit
`backup_vor_timestamp_migration` im Dateinamen geschrieben.

## Verhalten in der HTML-Seite

- `Angelegt am` zeigt nur noch einen sicheren `created_at`-Wert.
- `Gedruckt am` bleibt leer beziehungsweise `nicht erfasst`, solange kein
  echter Druckzeitpunkt bekannt ist.
- `Abgeglichen am` zeigt den letzten technischen Abgleich des Helpers.
- Die HTML-Seite zeigt zusaetzlich den Verbindungsstatus:
  - `MJET erreichbar`
  - `MJET nicht erreichbar`
  - `Verbindung wird geprueft`
- Bei Verbindungsproblemen bleibt die eingetragene Farbbezeichnung im Feld.

## Windows-Test vor neuem Installer

1. Helper auf der MJET starten.
2. HTML-Farbuebersicht von der NAS oeffnen.
3. Pruefen, ob oben `MJET erreichbar` angezeigt wird.
4. Testfarbe in der HTML-Seite eintragen.
5. Pruefen, ob die Farbe in der Tabelle erscheint.
6. Dieselbe Farbe erneut eintragen und pruefen, ob eine verstaendliche
   Doppelungs-Meldung erscheint.
7. Helper auf der MJET beenden und die HTML-Seite neu laden.
8. Pruefen, ob `MJET nicht erreichbar` angezeigt wird.
9. Bei ausgeschaltetem Helper eine Farbe eintragen und pruefen, ob keine
   Browser-Meldung `Failed to fetch`, sondern die deutsche Helper-Meldung
   erscheint.
10. Farbabgleich am Helper ausfuehren.
11. Pruefen, ob alte pauschale Werte nicht mehr als sichere Druckzeitpunkte
    angezeigt werden.
12. Pruefen, ob neben der internen CSV einmalig ein Backup mit
    `backup_vor_timestamp_migration` erzeugt wurde.

Erst nach diesem Windows-Test sollte daraus wieder ein Installer gebaut werden.
