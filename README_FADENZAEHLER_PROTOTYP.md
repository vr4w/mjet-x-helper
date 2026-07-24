# Digitaler Fadenzähler - Prototyp

Eigenständiger Windows-Test für eine stark vergrößerte Kameravorschau.

Wichtig: Dieser Prototyp ist absichtlich nicht in den produktiven Little MPRINT Helper integriert.

## Zweck

Das iPhone 15 Pro wird über iVCam als virtuelle Windows-Webcam bereitgestellt. Der Prototyp öffnet diese Kameraquelle und zeigt ein vergrößertes Livebild beziehungsweise periodische Standbilder.

Es gibt keine Bildanalyse, keine Messung, keine Aufzeichnung und keine direkte iPhone-Steuerung.

## Vorbereitung

1. iVCam auf dem Windows-PC installieren.
2. iVCam-App auf dem iPhone 15 Pro installieren.
3. iPhone per USB anschließen.
4. Auf dem iPhone `Diesem Computer vertrauen` bestätigen.
5. iVCam auf iPhone und PC starten.
6. In iVCam die rückwärtige Kamera auswählen.
7. Fokus, Zoom, Belichtung und Licht zunächst direkt in iVCam einstellen.
8. Prototyp starten.
9. In der Kamera-Auswahl `iVCam` beziehungsweise die passende Kamera auswählen.
10. `Kamera starten` klicken.

## Start

Falls OpenCV und Pillow noch fehlen:

```powershell
python -m pip install opencv-python pillow
```

Start:

```powershell
python digitaler_fadenzaehler_prototyp.py
```

## Bedienung

- `Kameras neu suchen`: sucht Windows-Kameraquellen.
- `Kamera starten`: öffnet die ausgewählte Kamera.
- `Kamera stoppen`: gibt die Kamera wieder frei.
- `LIVE`: fortlaufendes Livebild.
- `AUTO-STANDBILD`: Kamerastream läuft weiter, Anzeige aktualisiert alle X Sekunden.
- `FREEZE`: Anzeige bleibt stehen, Kamera kann im Hintergrund weiterlaufen.
- `Intervall`: 0,5 / 1 / 2 / 3 / 5 Sekunden.
- `Zoom`: 100 bis 500 Prozent.
- Mit gedrückter Maustaste kann der gezoomte Ausschnitt verschoben werden.
- `Zoom zurücksetzen`: Zoom und Ausschnitt zurücksetzen.
- `Fadenkreuz`: Mittelpunkt ein-/ausblenden.
- `Bild speichern`: aktuelles Bild als PNG speichern.
- `Vollbild`: Vollbild auf aktuellem Monitor.
- `ESC`: beendet nur den Vollbildmodus.

## Morgen am MPRINT-PC testen

1. Startet das Programm ohne angeschlossenes iPhone?
2. Wird iVCam in der Kamera-Auswahl angezeigt?
3. Lässt sich iVCam starten und stoppen?
4. Bleibt die Oberfläche während Kamera-Suche und Livebild bedienbar?
5. Funktioniert `LIVE` stabil?
6. Funktioniert `AUTO-STANDBILD` mit 0,5 / 1 / 2 / 3 / 5 Sekunden?
7. Bleibt `FREEZE` stabil?
8. Bleibt der Zoom beim Standbildwechsel erhalten?
9. Lässt sich der Ausschnitt per Maus verschieben?
10. Wird ein PNG über `Bild speichern` erzeugt?
11. Funktionieren Vollbild und `ESC`?
12. Wird die Kamera beim Schließen wieder freigegeben?

## Bekannte Einschränkungen

- Kamera-Namen können mit OpenCV nicht immer eindeutig ausgelesen werden; Quellen erscheinen eventuell als `Kamera 0`, `Kamera 1` usw.
- iPhone-Linse, Fokus, Licht und Belichtung werden zunächst in iVCam eingestellt.
- Mehrmonitor-Auswahl ist vorbereitet über normales Fenster/Vollbild, aber noch nicht als feste Monitor-2-Auswahl umgesetzt.
- Ohne OpenCV/Pillow startet die Datei nicht sinnvoll als Kameratool.
- Ohne iPhone kann nur mit vorhandenen Webcams getestet werden.

