# Änderungsdokumentation Winter-Bugfixes (Stand 2026-11-11)

## Testumgebung
- HAOS-Testinstanz `http://10.1.99.30` mit Simulation (`/homeassistant/packages/tadiy_simulation.yaml`): virtuelle TRVs, Fenster-/Temperatursensoren, Außentemperatur, Wetter, Zeitraffer (1/10/60/300x).
- Live-Instanz wurde nicht angefasst. `.ignore/` (Live-Backup) steht in `.gitignore`.

## Behobene Probleme (Ursache → Fix)
| Problem | Ursache | Fix (Datei) |
|---|---|---|
| Zeitpläne greifen nicht / nach Neustart hängend | TRV-Rückmeldungen nach Planwechsel wurden als manuelle Überschreibung gewertet (`_last_commanded` zu spät gesetzt, kalibrierter vs. unkalibrierter Wert); `next_block`-Overrides liefen nie ab (Zeitzone) | `trv_manager.py`, `coordinator.py`, `core/override.py` (UTC-Expiry) |
| Plan speichern ohne Wirkung | Zielwert wurde nicht neu gesendet | `__init__.py` (`set_schedule` löscht Overrides, erzwingt Neusendung) |
| Early Start wirkte nie | `EarlyStartCalculator` wurde nicht aufgerufen | `coordinator.py` (`get_scheduled_target`) |
| Fenstererkennung | Timer wurde alle 5 s zurückgesetzt; `should_heat` ignorierte Fensterstatus; Temperaturabfall-Erkennung löste trotz Fenstersensor aus | `core/window.py`, `coordinator.py`, `core/sensor_manager.py` |
| Fenstersensor pro Raum fehlte | Kein Sensor-Entity | `sensor.py` (`window_state`) |
| Modi pro Raum / Hub-Modus-Wechsel | `get_hub_mode()` las veralteten Select-Zustand und machte Wechsel rückgängig | `coordinator.py` |
| Heizrate lernt nicht (1,0 / Count 0) | Referenztemperatur wurde alle 5 s überschrieben; Heat-Model nicht geladen/registriert; Reset-Services wirkten nicht auf Raum-Modelle | `coordinator.py`, `__init__.py`, `button.py` |
| Thermostat "heizt" bei 20,9 °C (Soll 20) | Kein `hvac_action`; TRV-Sollwert blieb bei `target + Offset` | `climate.py` (`hvac_action`), `trv_manager.py` |
| Debug-Logging wirkungslos | Ausgabe auf DEBUG bei Logger-Level WARNING | `core/logger.py` (INFO), `__init__.py` (Level INFO) |
| 403 auf `/tadiy` | Statischer Verzeichnispfad `/tadiy` kollidierte mit Panel-URL | `__init__.py` (Einzeldatei-Routen) |
| Doppelte `unique_id` bei schnellem Raumanlegen | Sekunden-Timestamp | `config_flow.py` (Millisekunden) |
| K-12: At Home / Away Override ohne Funktion | `_away_since` wurde bei manuellem Override nicht gesetzt (Dauer immer 0 s, Schonfrist permanent); Timer nicht persistiert; Raumkoordinator berechnete keine Absenkung | `core/location.py` (`_away_since`, `immediate`, `to_dict`/`restore`), `coordinator.py` (Storage, Anbindung in `get_scheduled_target`), `__init__.py` (Storage-Load & Hub-Reload Verknüpfung) |
| Feature: Homeoffice Feierabend-Rückfall | Homeoffice galt starr ganztägig; keine Umschaltung abends | `const.py` (`homeoffice_end_hour`, `homeoffice_single_day`), `options_flow.py`, `core/schedule_model.py`, `core/schedule.py`, `coordinator.py` (Auto-Reset um Mitternacht auf Normalmodus) |
| K-13: Störungsüberwachung (Kalk & Kesselausfall) | Kesselausfall wurde durch abs(delta) als funktionierend gewertet; klemmendes offenes Ventil (Kalk) über Solltemperatur unbemerkt; Alarme wurden nicht an HA übergeben | `core/safety.py` (Kalk-/Überhitzungserkennung, richtungsabhängige Heizungsausfallerkennung), `binary_sensor.py` (`heating_problem`), `coordinator.py` (Event `tadiy_alert` & Dashboard-Benachrichtigung), `strings.json`, `translations/de.json` |
| K-06: Climate HVAC-Modus und Action-Konsistenz | Bei Erreichen der Zieltemperatur schaltete `_commanded_hvac_mode` fälschlich auf `off` statt `heat` mit `hvac_action = idle`; manuelles Raum-Aus wurde vom Zyklus überschrieben | `climate.py` (`hvac_mode`, `hvac_action`, `async_turn_off`/`on`, `async_set_hvac_mode`), `coordinator.py` (`_manual_room_off`, Rückfall bei Planblockwechsel), `core/orchestrator.py` |
| K-01 & Overshoot-Lernen ("Anti-Hysterie") | Mindestzykluszeit (300 s) hielt Heizung trotz Planabsenkung aktiv; Overshoot-Learning brach Tracking sofort bei Sollwerterreichung ab und speicherte keine Proben | `core/control.py` (Zielwertabsenkung hebt Cycle-Guard auf und schaltet sofort ab), `core/overshoot.py` (Tracking über 10 min Settling-Window, Probenrückgabe), `coordinator.py` (kein vorzeitiger Abbruch, Speicherung via `async_save_overshoot`) |
| K-07: TRV-Target-Offset bei erreichter Zieltemperatur | Kalibrier-Offset hielt TRV-Zielwert bei 20,5 °C bei Raumsoll 18,5 °C; TRV heizte weiter | `core/trv_manager.py` (Kalibrierung bei `should_heat=False` strikt deaktiviert, `trv_target` pro TRV isoliert, TRV-Zielwert auf Frost/Min-Temp abgesenkt) |
| K-09: Service `set_heating_curve` API im `HeatUpModel` | Manuelles Setzen manipulierte interne Summanden direkt und gab bei hoher Stichprobenanzahl künstlich hohe Konfidenz vor | `core/early_start.py` (`set_manual_rate` mit 0.1-10.0 Validierung & Baseline sample_count=1, `reset`), `__init__.py` (Nutzung der API) |
| K-02: Raumsensoren/Panel-Entity-Suche & Umlaute | Fragiles String-Matching führte bei Umlauten oder abweichenden Entity-Präfixen zu N/A-Werten im Panel | `climate.py` (exponiert `current_humidity`, `comfort_score`, `comfort_level`, `comfort_color` direkt), `core/temperature.py` (`calculate_comfort` ausgelagert), `sensor.py`, `www/tadiy-panel.js` (Umlaut-Normalisierung ä/ae, ö/oe, ü/ue, ß/ss) |
| K-08: Audit & Härtung Kernmodule | Calibration ignorierte Modus `disabled`; Manual-Offset benötigte fälschlich Sensormessungen; WeatherPredictor stürzte bei naivem Datetime ab; RoomCoupling rechnete kalte unbeteiligte Räume als aktiv heizend und war nicht im Coordinator verdrahtet; Number-Plattform persistierte Boost-Werte nicht | `core/calibration.py`, `core/weather_predictor.py`, `core/room_coupling.py`, `coordinator.py`, `number.py` |
| Feature: Nativer Fenster-Binärsensor | Raum-Gerät hatte nur Textstatus-Sensor; Standard-Window-Badge und -Icon auf HA-Geräteseite fehlten | `binary_sensor.py` (`TaDIYRoomWindowBinarySensor`), `strings.json`, `translations/de.json`, `translations/en.json` |
| CI & Validierungs-Infrastruktur | Fehlende Testausführung in CI und keine automatisierten Git-Hooks bei Pushes/Commits | `.github/workflows/validate.yaml`, `.forgejo/workflows/test.yaml`, `.githooks/pre-commit` |
| Release 3.1.0 | Manifest und Dokumentation auf v3.1.0 aktualisiert | `manifest.json`, `README.md`, `docs/STATUS.md` |
| K-14: Hub-Modus NameError / Select-Loop | Select-Entity verursachte Revert des Hub-Modus | `coordinator.py`, `select.py` (v3.1.4, v3.1.5) |
| K-15: Safety Fehlalarme | Träge TRVs unterschieden von Kesselausfall | `core/safety.py` (v3.1.3) |
| K-16: Homeoffice Morgen | Einzeltag-Schalter und Morgen-Toggle | `coordinator.py`, `services.yaml`, `www/tadiy-panel.js` (v3.1.2, v3.1.6) |
| K-17: Quick Offset & Nachbar-Fenster | Schnell-Offset (±X°C) und Nachbar-Absenkung | `coordinator.py`, `www/tadiy-panel.js` (v3.1.6) |
| K-18: AttributeError person_entities | Leere Person-Config beim Hub-Start stürzte ab | `coordinator.py` (v3.1.7) |
| K-19: WindowDetector.is_open | Fehlende Property verhinderte Raumstart (setup_retry) | `core/window.py`, `coordinator.py` (v3.1.8) |
| K-20: RoomConfig.min_temp | Fehlende Property verursachte Raum-Unavailable | `core/room.py`, `coordinator.py` (v3.1.9) |
| K-21: mappingproxy in set_hub_config | Read-only mappingproxy verhinderte Hub-Optionen-Save | `coordinator.py`, `__init__.py` (v3.1.9) |
| K-22: DHW-Fühler & Filter & TRV-Tab | Warmwasserfühler synchronisiert, 5. Tab Einzel-TRVs, 🪟 durch ha-icon ersetzt | `coordinator.py`, `climate.py`, `www/tadiy-panel.js` (v3.1.9) |
| K-23: Schema validation error services.yaml | `options: []` in `select` selector fehlte; Service-Registrierung schlug fehl | `services.yaml` (v3.1.10) |
| K-24: Persistenz Hub- & Raum-Settings | `entry.options` ging bei Reload verloren, da Coordinators nur `entry.data` lasen | `__init__.py`, `select.py` (v3.1.10) |
| K-25: TRV-Diskrepanzwarnung im Standby (5°C) | TRVs im Leerlauf/Frostschutz wurden fälschlich mit Raum-Sollwert verglichen | `www/tadiy-panel.js` (v3.1.10) |
| K-26: Granulare TRV-Temperatursteuerung | TRVs mit `use_hvac_off_for_low_temp=false` fielen bei `should_heat=False` auf 5°C; echter Sollwert bleibt nun erhalten | `core/trv_manager.py`, `tests/test_audit_core.py` (v3.1.11) |

## Konfiguration / UI
- Wetter-Entität, Außensensor, Early Start, Wetterkompensation nur noch im Hub; Raumformular ohne diese Felder (`config_flow.py`, `options_flow.py`); Raumwerte erben Hub-Einstellungen.
- "Panel Settings" → "Hub Configuration" (`strings.json`, `translations/de.json`).
- Schedule-Karte: kompakter Zeitpicker, gleiche Höhe (32 px) für Zeit/Temperatur, schmaler zentrierter Temperaturpicker mit `OFF`, gleiche Abstände bis zum Löschen-Button, Dropdown nicht mehr abgeschnitten, Endzeit `24:00` (`www/tadiy-schedule-card.js`).
- Panel: Entity-Suche für Komfort/Feuchte/Override-Button robuster; Override-Reset über Service (`www/tadiy-panel.js`).

## Tests
- `tests/test_window.py` (6 Tests) wurde über den orchestrator-core erzeugt: Job `07bf26ab…`, Route `opencode-go/glm-5.3-flash`, Status `needs_review`, unabhängige Prüfung bestanden.
- `tests/test_location_and_schedule.py` (8 Tests) für Away Override & Homeoffice-Feierabend-Rückfall hinzugefügt.
- `tests/test_safety.py` (4 Tests) für Störungsüberwachung (Kalkblockade / Kesselausfall).
- `tests/test_climate_mode.py` (8 Tests für Climate-Modus, Action-Konsistenz K-06, Feuchte & Komfort-Attribute K-02).
- `tests/test_control.py` (13 Tests inkl. Planabsenkungs-Zyklussperren-Aufhebung K-01).
- `tests/test_overshoot.py` (2 Tests für Overshoot-Tracking & Settling-Window).
- `tests/test_early_start.py` (4 Tests für HeatUpModel API, Validierung, Baseline-Konfidenz und EarlyStartCalculator).
- `tests/test_audit_core.py` (11 Tests für Calibration, Weather, Coupling, Valve-Protection und Window-Binary-Sensor).
- `tests/test_config_flow.py` (5 Tests für ConfigFlow Hub-Erstellung, Raum-Formular und Duplikatvalidierung K-11).
- `python -m unittest discover -s tests`: 61 Tests OK.

## Live-Verifikation auf der Testinstanz
- `/tadiy` HTTP 200 (vorher 403), JS-Assets 200.
- Heizrate lernt: `sample_count` Wohnzimmer 14, Büro 9.
- Fensterstatus korrekt `closed` bei geschlossenen Sensoren (vorher fälschlich `open_heating_stopped`).

## Offen / ungeprüft
- Hub-Konfiguration: Änderungen von Early Start/Heizkurve live prüfen.
- UI-Layout im Browser visuell abnehmen.
- Orchestrator-Profil `projects/tadiy/profile.json` wurde für den Testjob geändert (Backup `profile.json.bak-control`).

