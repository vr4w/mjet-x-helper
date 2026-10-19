# MJET-X Helper 1.1.2: Windows-Praxistest

Stand: 2026-08-19

Diese Checkliste ist fuer den Test an der MJET gedacht, bevor Version 1.1.2
produktiv genutzt oder weitergegeben wird.

## Vor dem Update

1. Bestehende MJET-Installation sichern.
2. Bestehende Farbdaten und interne Farbdaten-CSV sichern.
3. Bestehende `MPRINT_Farbuebersicht.html` sichern.
4. Helper beenden.

## Installation

1. Version 1.1.2 installieren.
2. Helper starten.
3. Pruefen, ob die vorhandene Konfiguration erhalten geblieben ist.
4. Pruefen, ob der Farbabgleich-Status wie gewohnt angezeigt wird.

## Farbluebersicht

1. Im Helper auf `Farbuebersicht` klicken.
2. Pruefen, ob die richtige HTML-Datei im Standardbrowser oeffnet.
3. Pruefen, ob oben `MJET erreichbar` angezeigt wird.
4. Eine vorhandene Kundenfarbe suchen.
5. Eine Test-SK hinzufuegen.
6. Dieselbe SK erneut eintragen und die Doppelungs-Meldung pruefen.
7. Eine zweite SK zur gleichen Farbe hinzufuegen.

## Farbmischer

1. Im Helper auf `Farbmischer` klicken.
2. Pruefen, ob ein separates Fenster oeffnet und der Helper weiter bedienbar
   bleibt.
3. Noch einmal auf `Farbmischer` klicken und pruefen, dass kein Stapel
   identischer Fenster entsteht.
4. C, M, Y und K-Regler bewegen.
5. Pruefen, ob Prozentwerte und Farbfeld sofort reagieren.
6. Zahlenfelder testen und pruefen, ob nur Werte von 0 bis 100 bleiben.
7. `Zuruecksetzen` klicken und pruefen, ob alle Werte wieder 0 sind.
8. Nach einer lokalen Referenzfarbe suchen, zum Beispiel nach einer vorhandenen
   Kundenfarbe aus den MJET-Farbtabellen.
9. Treffer anklicken und pruefen, ob die CMYK-Werte in die Regler uebernommen
   werden.
10. Danach Regler manuell veraendern und pruefen, ob die Vorschau weiter
    reagiert.
11. Fenster schliessen und erneut oeffnen.

## Druck, Freigabe, Uebernahme

1. Eine SK als gedruckt markieren.
2. Pruefen, dass noch keine Freigabe automatisch gesetzt wurde.
3. Freigabe durch Andreas bestaetigen.
4. Pruefen, dass die Uebernahme weiterhin offen bleibt.
5. Uebernahme offen lassen und pruefen, ob sie oben in der Zusammenfassung
   sichtbar bleibt.
6. Uebernahme bestaetigen.
7. Pruefen, dass nur diese SK als uebernommen markiert wurde.

## Neustart und Farbabgleich

1. Browser schliessen.
2. Helper neu starten.
3. Farbluebersicht erneut oeffnen.
4. Pruefen, ob SK-Zuordnungen und Status erhalten geblieben sind.
5. Farbabgleich ausfuehren.
6. Pruefen, ob SK-Zuordnungen und Status weiterhin erhalten sind.
7. Pruefen, ob alte Zeitstempel nicht als neue Druckzeitpunkte erfunden werden.

## Verbindungsfall

1. Helper beenden.
2. HTML im Browser offen lassen oder neu oeffnen.
3. Pruefen, ob `MJET nicht erreichbar` angezeigt wird.
4. Eine Farbe oder SK-Aktion versuchen.
5. Pruefen, ob eine verstaendliche deutsche Meldung erscheint und nicht nur
   `Failed to fetch`.

Erst wenn diese Punkte an der MJET erfolgreich sind, ist der Workflow fuer den
produktiven Einsatz freigegeben.
