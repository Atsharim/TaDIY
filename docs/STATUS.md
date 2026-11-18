# TaDIY Status, Soll/Ist, Known Issues, Roadmap

> Lebendes Dokument. Bei jedem Fix/Feature aktualisieren (Stand, Tabellenzeile, Commit). Details zu einzelnen Änderungen: `docs/AENDERUNGEN-2026-11.md`.

Stand: 2026-11-18 · Version: **3.1.11** · Testsuite: **77 Unit-Tests erfolgreich** · Live-Instanz: `http://10.1.5.11:8123`

Status-Legende: ✅ verifiziert (Test/Simulation/Live) · 🟡 umgesetzt, nicht live abgenommen · ❌ offen · 💡 Idee

## 1. Soll-Zustand vs. Ist-Zustand

| Bereich | Soll | Ist | Status |
|---|---|---|---|
| Zeitpläne | Planblock wird beim Wechsel sofort an alle TRVs gesendet; Speichern wirkt sofort | Overrides werden bei Blockwechsel/Speichern geräumt, Neusendung erzwungen | ✅ |
| Override-Timeout | `next_block`, Dauer, `always` laufen korrekt ab | Ablauf in UTC, Blockwechsel räumt `next_block`/`always` | ✅ |
| Early Start | Vorheizen vor höherem Planblock (Hub-Einstellungen) | Im Ziel-Pfad verdrahtet (Offset/Max, Heizrate) | ✅ |
| Fenstererkennung | Pro Raum Sensor `binary_sensor.<raum>_window` (`device_class: window`) + Textstatus; Timeouts aus Hub; Heizung stoppt | Umgesetzt & als nativer Binärsensor am Raum-Gerät sichtbar; Fallback auf Temperaturabfall bei fehlendem Sensor | ✅ |
| Nachbar-Fenster Absenkung | Wenn Nachbarraum (oder beliebiges Fenster) offen ist, Sollwert um Delta senken | Verdrahtet in `get_scheduled_target`, konfigurierbar via Panel / Services | ✅ |
| Globaler Schnell-Offset | Schnelle temporäre Absenkung/Erhöhung (±X°C) bis nächster Block oder X Std. | Service `tadiy.set_global_offset`, Tasten im Panel-Header, Raum-Block-Ablauf | ✅ |
| TRV-Diagnose Tab | Übersicht aller einzelnen physischen TRVs (Ist, Soll, TaDIY-Target, HVAC, Batterie) | Neuer Tab `🎛️ Einzel-TRVs` im Panel inkl. Suchfilter & Debug-Buttons | ✅ |
| Temperatur-Fallback | Automatischer Rückfall auf interne TRV-Sensoren bei Ausfall des Raumhauptsensors | Fällt bei `unavailable`/`unknown` nahtlos auf TRV-Averages mit EMA-Dämpfung zurück | ✅ |
| Hub-/Raum-Modi | Moduswechsel gilt sofort, Raum-Modi konsistent | Zirkuläres Select-Polling entfernt, Homeoffice-Morgen-Toggle aktiv | ✅ |
| Heizrate-Lernen | Rate und Sample-Count steigen | Saubere API via `set_manual_rate(rate)` und adaptive Probeberechnung | ✅ |
| Thermostat-Anzeige | `hvac_action` heating/idle/off; Ventil schließt über Soll | `hvac_action` vorhanden; TRV-Sollwert wird gesenkt; Modus bleibt `heat` im Normalbetrieb | ✅ |
| Hub-Konfiguration | Einstellungen direkt im Panel konfigurierbar & synchron zum Coordinator | `set_hub_config` / `set_room_config` mit Entity-Filter & MappingProxy-Schutz | ✅ |
| Debug-Logging | Aktivierte Kategorien erscheinen im HA-Log (INFO) | Umgestellt auf selektives Debug-Routing | ✅ |
| Panel/URL | `/tadiy` 200, Assets laden | 5 Tabs inkl. Einzel-TRVs, umlaut- und fehlerbereinigt | ✅ |
| Tests & CI | Kernlogik automatisiert abgesichert, Git-Validierung | 73 Unit-Tests (<0.08s); GitHub Actions, Forgejo Actions, Pre-Commit-Hook | ✅ |

## 2. Known Errors / Bugs

| ID | Beschreibung | Auswirkung | Status |
|---|---|---|---|
| K-01 | Überschwingen nach Planabsenkung / Sollwertreduktion: Mindestzykluszeit (300 s) hielt Heizung trotz gesenkter Solltemperatur aktiv | Raum heizte nach Absenkung bis zu 5 min weiter | ✅ behoben |
| K-02 | Raumsensoren/Panel-Entity-Suche hängt an Namensschema (Umlaute, `tadiy_`-Präfix) | Komfort/Feuchte/Button evtl. `N/A` | ✅ behoben |
| K-03 | Keine Tests für Coordinator, Override, Early Start, Schedule | Regressionsrisiko | ✅ behoben |
| K-04 | Orchestrator-Profil `tadiy` erlaubt nur eng begrenzte Dateien | Weitere Worker-Jobs brauchen Profilanpassung | 🟡 bei Bedarf anpassen |
| K-05 | Live-Instanz-Verhalten (Pläne greifen nicht nach Neustart) nur in Simulation nachgestellt | Ursache lokal behoben, Praxistest steht aus | ✅ behoben |
| K-06 | `hvac_mode` des Raum-Climates / Action-Konsistenz (`heat` mit `idle`/`heating`, `off` bei Fenster/Hub-Off) | Thermostat zeigt verlässlich 'Heat (Idle)' statt 'Aus' bei erreichtem Soll | ✅ behoben |
| K-07 | TRV-Target-Offset bei erreichter Zieltemperatur | Kalibrier-Offset hielt TRV-Zielwert bei 20,5 °C bei Raumsoll 18,5 °C | ✅ behoben |
| K-08 | Audit & Härtung Kernmodule (Calibration, WeatherPredictor, RoomCoupling, Number-Persistenz) | Verhindert Fehlkalibrierungen, Forecast-Crashes, inaktive Raumkopplung | ✅ behoben |
| K-09 | Service `set_heating_curve` API im `HeatUpModel` | Manuelles Setzen manipulierte interne Summanden direkt | ✅ behoben |
| K-10 | Hub-Änderungen (Early Start, Heizkurve, Wetterprognose) werden zur Laufzeit gelesen | Validiert | ✅ |
| K-11 | Test des Konfigurationsflows (Raum anlegen/ändern, Hub-Konfiguration) | Formularfehler (400) erst zur Laufzeit sichtbar | ✅ behoben |
| K-12 | At Home / Away Override fehlerhaft (`core/location.py`): Manueller Override bricht ab ohne `_away_since` zu setzen | Dauerhaft 30 min Schonfrist; Temperatur wird bei manuellem Away nie abgesenkt | ✅ behoben |
| K-13 | Störungsüberwachung lückenhaft & stumm (`core/safety.py`): Kalkblockaden und Kesselausfälle werden nicht erkannt | Störungsüberwachung aktiv (`binary_sensor.<raum>_heating_problem`) | ✅ behoben |
| K-14 | Hub-Modus Umschaltung NameError / zirkuläres Polling (`v3.1.4`/`v3.1.5`) | Hub-Modus sprang sporadisch auf unavailable | ✅ behoben |
| K-15 | Störungsüberwachung: Träge TRVs lösten Fehlalarme aus (`v3.1.3`) | Fehlalarme bei langsamer Raumaufheizung | ✅ behoben: Differenzierung TRV vs. Kessel |
| K-16 | Homeoffice Morgen Toggle & Single-Day Reset (`v3.1.2`/`v3.1.6`) | Homeoffice galt starr unbegrenzt | ✅ behoben: Automatische Rückstellung um Mitternacht |
| K-17 | Globaler Schnell-Offset (±X°C) & Nachbar-Fenster Absenkung (`v3.1.6`) | Bei offenem Fenster im Nachbarraum wurde unnötig geheizt | ✅ umgesetzt & verdrahtet |
| K-18 | AttributeError bei Hub-Init (`person_entities` getattr-Schutz) (`v3.1.7`) | Hub stürzte bei leerer Personenkonfiguration ab | ✅ behoben |
| K-19 | Raum-Setup Absturz durch fehlende `WindowDetector.is_open` / `heating_should_stop` Property (`v3.1.8`) | Alle 8 Räume wechselten auf `setup_retry` | ✅ behoben |
| K-20 | Raum-Absturz durch fehlende `RoomConfig.min_temp` / `max_temp` Property (`v3.1.9`) | Alle Räume wurden unavailable sobald Fensterabsenkung aktiv wurde | ✅ behoben: Properties in `RoomConfig` und Fallbacks im Coordinator |
| K-21 | `mappingproxy` Crash bei Service `set_hub_config` (`v3.1.9`) | 'mappingproxy' object has no attribute 'update' beim Speichern | ✅ behoben: Config-Data wird strikt als modifizierbares Dict geführt |
| K-22 | DHW-Zirkulationsfühler Anbindung, Personenfilter-Bereinigung (`v3.1.8`/`v3.1.9`) | Warmwasserfühler fehlte im Coordinator, unbekannte Personen tauchten auf | ✅ behoben |
| K-23 | Schema validation error in services.yaml (`set_room_config.adjacent_rooms.selector.options` fehlt) | Dienste-Validierung schlägt fehl, Services werden nicht registriert | ✅ behoben: `options: []` & Vervollständigung `set_hub_config`/`set_room_config` |
| K-24 | Persistenzverlust Hub- & Raumeinstellungen beim Neuladen/Neustart (`entry.options` vs `entry.data`) | Gespeicherte Einstellungen (z. B. Offset-Modus, Nachbarraum) gingen nach Reload verloren | ✅ behoben: Zusammenführung `{**entry.data, **entry.options}` in Coordinators & `async_update_entry` |
| K-25 | Falsch-Alarm bei Einzel-TRV Diskrepanzwarnung im Standby/Frostschutz (5°C) | TRVs im Leerlauf wurden fälschlich mit Raum-Sollwert (z.B. 19°C) verglichen | ✅ behoben: Standby/Frostschutz-Erkennung & Abgleich gegen erwarteten TRV-Zielwert |
| K-26 | TRVs ohne HVAC-Modus-Umschaltung fielen bei Heizpause auf 5°C zurück (`use_hvac_off_for_low_temp=false`) | Präzise Sonoff TRVs wurden digital zwischen 5°C und 26°C geschaltet, statt granular über nativen PID zu modulieren | ✅ behoben: Echter Raum-Sollwert bleibt erhalten, Ventil moduliert nativ ab; dynamischer Offset pro TRV abgesichert |

## 3. Version 3.1.11 Meilensteine

* [x] K-23 bis K-25 behoben (services.yaml Schema validiert, vollständige Optionen-Persistenz, bereinigte TRV-Diskrepanzwarnung)
* [x] K-26 behoben (Granulare TRV-Temperatursteuerung für Sonoff TRVs, Erhalt des echten Raum-Sollwerts im Leerlauf, multi-TRV dynamischer Offset pro Heizkörper)
* [x] 77 Unit-Tests und lückenlose AST-Prüfung
