# 🚀 v1.0.2 – Team-Statistiken Robuster

**Veröffentlicht:** 2025-01-27

## 🎯 Team-Statistiken Analyse verbessert

### ✨ **Neue Features**
- **Referenznamen-System:** Team-Zusammensetzung wird zuerst analysiert und dient als Referenz für Stats-Analyse
- **Konsistente Namensschreibweisen:** Spielernamen aus dem Composition-Bild werden als Standard verwendet
- **Intelligente Namenszuordnung:** KI gleicht Stats-Namen mit Referenznamen ab für höchste Genauigkeit
- **Manuelle Namenszuordnung:** Bearbeiten-Button für manuelle Korrektur von Spielernamen
- **Auto-Solve Feature:** KI-basierte automatische Zuordnung von misspelled Namen zu Referenznamen
- **Re-Analyse für fehlende Spieler:** "Neu analysieren" Button wenn Composition-Spieler in Stats fehlen

### 🔧 **Technische Verbesserungen**
- **Reihenfolge optimiert:** Composition-Bild wird vor Stats-Bild analysiert für bessere Qualität
- **Robuste KI-Prompts:** Erweiterte Anweisungen für Pfeffi KI mit Referenznamen-Validierung
- **Duplikat-Vermeidung:** Automatische Entfernung doppelter Namen und alphabetische Sortierung
- **Enemy-Stats Persistierung:** Enemy-Stats gehen nicht mehr verloren bei Namens-Korrekturen
- **Modal-Label-Optimierung:** Kürzere Labels für bessere Discord-Kompatibilität

### 🐛 **Bugfixes**
- **Namens-Inkonsistenzen:** Keine unterschiedlichen Schreibweisen für denselben Spieler mehr
- **Fehlende Spieler:** Spieler die nur in Stats aber nicht in Composition stehen werden übersprungen
- **Analyse-Robustheit:** Verbesserte Fehlerbehandlung bei unvollständigen oder fehlerhaften Bildern
- **Spieler-Check:** Warnung wenn nicht alle Composition-Spieler in Stats gefunden wurden
- **Enemy-Stats Verlust:** Enemy-Stats werden korrekt erhalten und weitergegeben

---

# 🚀 v1.0.1 – Rollen-Auswahl Verbesserungen

**Veröffentlicht:** 2025-01-27

## 🎯 Rollen-Auswahl in Bildanalyse verbessert

### ✨ **Neue Features**
- **Zweite optionale Rolle:** Wenn eine erste Rolle ausgewählt wird, erscheint ein zweites Rollen-Feld für zusätzliche Berechtigungen
- **Konsistente Benutzeroberfläche:** Rollen-Auswahl funktioniert jetzt wie die Kanal-Auswahl - als einfaches Dropdown ohne Choices.js
- **Verbesserte Rollen-ID-Behandlung:** Robuste Konvertierung zwischen String- und Integer-Rollen-IDs für bessere Kompatibilität

### 🔧 **Technische Verbesserungen**
- **Frontend:** Rollen-Auswahl von Choices.js auf einfaches Select-Feld umgestellt
- **Backend:** Rollen-IDs werden konsistent als Strings gespeichert und übertragen
- **Fehlerbehandlung:** Verbesserte Fehlerbehandlung beim Laden und Speichern von Rollen-Konfigurationen

### 🐛 **Bugfixes**
- **Rollen-Persistierung:** Rollen werden beim Laden der Seite korrekt ausgewählt angezeigt
- **Berechtigungsprüfung:** Rollen-basierte Berechtigungen funktionieren weiterhin korrekt
- **UI-Konsistenz:** Rollen-Auswahl verhält sich jetzt identisch zur Kanal-Auswahl

---

# 🚀 v1.0.0 – Das große Release!

**Veröffentlicht:** 2025-07-26

## 🎉 Highlights

- **Web-UI für alle!**
  - Endlich kannst du deine Server im Browser verwalten. Keine Ausreden mehr! 🖥️✨
- **Rollen-Icons:**
  - Verpasse deinen Membern automatisch schicke Emojis im Nickname – ganz nach Rolle! 😎👑
- **Google-Sheet-Sync:**
  - Synchronisiere Mitgliederlisten direkt ins Google Sheet. Tabellen-Fans jubeln! 📊📝
- **Voice-Channel-User-Creation:**
  - Automatisch eigene Voice-Channels für Nutzer, die Generator-Channels betreten. Nie wieder Channel-Chaos! 🎤🔊
- **Review & VOD Befehle:**
  - `/review` und `/vod` schicken schicke Nachrichten und Links. Feedback und VODs? Kein Problem! 📝📹
- **Super dunkles Design:**
  - Die Web-UI blendet dich nicht mehr – jetzt mit Dark Mode! 🌑🦇

## 📊 Google Sheet Integration – Vollständig überarbeitet!

### 🎯 **Usermapping & Mitglieder-Sync**
- **Intelligentes Mapping:** Rechtsklick auf Zellen für Usermapping (vertikal/horizontal)
- **Mitglieder-Filter:** Nur bestimmte Rollen oder alle Mitglieder synchronisieren
- **Visuelles Feedback:** Rote Highlights zeigen gemappte Bereiche im Sheet-Preview
- **Automatische Updates:** Bei Rollen-Änderungen wird das Sheet automatisch aktualisiert

### 🔧 **Regelspalten-System (NEU!)**
- **Mehrere Regeln pro Spalte:** Erstelle beliebig viele Regeln für eine Spalte
- **Flexible Verhaltensweisen:**
  - **"Erste Regel verwenden"** (Standard): Nur die erste zutreffende Regel wird angewendet
  - **"Alle kombinieren"** (NEU!): Mehrere zutreffende Werte werden mit Komma getrennt
- **Zwei Modi pro Regel:**
  - **String-Modus:** Beliebigen Text eintragen (z.B. "VIP", "Admin")
  - **True/False-Modus:** Automatisch "true" oder "false" eintragen
- **Visuelles Feedback:** Grüne Highlights zeigen Regelspalten im Sheet-Preview
- **Spalten-Index-Support:** Direkte Spaltenauswahl (A, B, C, etc.) oder Spaltennamen

### 🎨 **Verbesserte Web-UI**
- **Kontextmenüs:** Rechtsklick auf Spalten für Regel-Einstellungen
- **Regel-Management:** Einfaches Hinzufügen/Entfernen von Regeln
- **Live-Preview:** Sofortige Vorschau der Regelspalten-Highlights
- **Migration:** Bestehende Konfigurationen werden automatisch ins neue Format konvertiert

### 🔄 **Automatisierung & Sync**
- **Intelligente Updates:** Nur geänderte Bereiche werden aktualisiert
- **Rollen-basierte Logik:** Automatische Werte basierend auf Discord-Rollen
- **Duplikat-Vermeidung:** Bei "Kombinieren"-Modus werden doppelte Werte entfernt
- **Robuste Fehlerbehandlung:** Graceful Fallbacks bei fehlenden Spalten

## 🛠️ Weitere Features & Verbesserungen

- **Slash-Commands** für alle wichtigen Aktionen
- **Per-Guild Einstellungen** (alles bleibt schön getrennt!)
- **Sheet-Mapping per Rechtsklick** – Tabellen-Nerds, ihr seid gemeint!
- **Viele kleine Bugfixes**, damit alles rund läuft 🐛🔨
- **Toast-Benachrichtigungen**, damit du weißt, was abgeht 🍞
- **Verbesserte Rollen-Auswahl** mit Choices.js für bessere UX
- **Robuste Spaltenindex-Berechnung** für präzise Sheet-Updates

## 🧙‍♂️ Hinweise

- **Service-Account** für Google Sheets muss im Backend liegen (Umweltvariable `GOOGLE_CREDENTIALS_PATH`)
- Für die **Web-UI** brauchst du Discord-Login (OAuth2)
- Bot braucht die **richtigen Rechte** auf deinem Server, sonst wird er zickig!
- **Regelspalten** werden automatisch in die konfigurierten Spalten geschrieben (A, B, C, etc.)

## 🔄 Migration

- **Bestehende Usermappings** funktionieren weiterhin ohne Änderungen
- **Alte Regelspalten-Konfigurationen** werden automatisch ins neue Format konvertiert
- **Neue Features** sind optional und müssen nicht verwendet werden

**Danke an alle Tester, Bug-Melder und Meme-Lieferanten!**

Bleib stabil und viel Spaß mit Sentinel v1.0.0! 🚀 
