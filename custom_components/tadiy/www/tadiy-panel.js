/**
 * TaDIY Panel - Adaptive Climate Orchestrator
 * Modernized overview, quick controls, and integrated weekly schedule planner.
 */

class TaDiyPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass = null;
    this._config = null;
    this._rooms = [];
    this._hubMode = 'normal';
    this._hubModeOptions = [];
    this._hubModeEntityId = null;
    this._activeTab = 'overview'; // 'overview' | 'schedules' | 'system'
    this._selectedScheduleRoom = null;
    this._selectedSettingsRoom = null;
    this._hasOpenDropdown = false;
    this._openDetails = new Set();
  }

  set hass(hass) {
    const oldHass = this._hass;
    this._hass = hass;

    // Do not re-render if user has a dropdown open or is on schedules tab (schedule card manages its own state)
    if (this._hasOpenDropdown) {
      return;
    }

    if (!oldHass || this._shouldRerender(oldHass, hass)) {
      this.loadRooms();
      this.render();
    }
  }

  _shouldRerender(oldHass, newHass) {
    // If on schedules tab, pass hass to the embedded schedule card without rebuilding panel DOM
    if (this._activeTab === 'schedules') {
      const scheduleCard = this.shadowRoot.querySelector('tadiy-schedule-card');
      if (scheduleCard && scheduleCard.hass !== newHass) {
        scheduleCard.hass = newHass;
      }
      return false;
    }

    const relevantOld = Object.keys(oldHass.states).filter(id =>
      id.includes('tadiy') || id.includes('hub_mode') || id.startsWith('climate.')
    );
    const relevantNew = Object.keys(newHass.states).filter(id =>
      id.includes('tadiy') || id.includes('hub_mode') || id.startsWith('climate.')
    );

    if (relevantOld.length !== relevantNew.length) return true;

    for (const entityId of relevantOld) {
      const oldState = oldHass.states[entityId];
      const newState = newHass.states[entityId];

      if (!newState || oldState.state !== newState.state) {
        return true;
      }
      if (
        oldState.attributes.temperature !== newState.attributes.temperature ||
        oldState.attributes.current_temperature !== newState.attributes.current_temperature ||
        oldState.attributes.hvac_action !== newState.attributes.hvac_action
      ) {
        return true;
      }
    }

    return false;
  }

  set panel(panel) {
    this._config = panel.config;
  }

  loadRooms() {
    if (!this._hass) return;

    const normalize = (str) =>
      str.toLowerCase()
        .replace(/ä/g, 'ae')
        .replace(/ö/g, 'oe')
        .replace(/ü/g, 'ue')
        .replace(/ß/g, 'ss');

    this._rooms = Object.values(this._hass.states)
      .filter(entity => {
        if (!entity.entity_id.startsWith('climate.')) return false;
        if (entity.attributes.integration === 'tadiy') return true;
        if (entity.entity_id.includes('tadiy')) return true;
        const friendly = (entity.attributes.friendly_name || '').toLowerCase();
        return friendly.includes('tadiy');
      })
      .map(entity => {
        const roomSlug = entity.entity_id.replace('climate.', '').replace('tadiy_', '');
        const cleanSlug = normalize(roomSlug).replace(/[^a-z0-9]/g, '');

        // Resolve window binary sensor
        const windowSensor = Object.values(this._hass.states).find(s =>
          s.entity_id.startsWith('binary_sensor.') &&
          s.entity_id.endsWith('_window') &&
          normalize(s.entity_id).replace(/[^a-z0-9]/g, '').includes(cleanSlug)
        );

        // Resolve heating problem sensor
        const problemSensor = Object.values(this._hass.states).find(s =>
          s.entity_id.startsWith('binary_sensor.') &&
          s.entity_id.endsWith('_heating_problem') &&
          normalize(s.entity_id).replace(/[^a-z0-9]/g, '').includes(cleanSlug)
        );

        // Resolve comfort sensor
        const comfortSensor = Object.values(this._hass.states).find(s =>
          s.entity_id.startsWith('sensor.') &&
          s.entity_id.endsWith('_room_comfort') &&
          normalize(s.entity_id).replace(/[^a-z0-9]/g, '').includes(cleanSlug)
        );

        // Resolve humidity sensor
        const humiditySensor = Object.values(this._hass.states).find(s =>
          s.entity_id.startsWith('sensor.') &&
          s.entity_id.endsWith('_humidity') &&
          normalize(s.entity_id).replace(/[^a-z0-9]/g, '').includes(cleanSlug)
        );

        // Resolve clear override button
        const clearBtn = Object.values(this._hass.states).find(s =>
          s.entity_id.startsWith('button.') &&
          s.entity_id.endsWith('_clear_override') &&
          normalize(s.entity_id).replace(/[^a-z0-9]/g, '').includes(cleanSlug)
        );

        // Resolve battery status sensor (multi-device batteries & offline check)
        const batterySensor = Object.values(this._hass.states).find(s =>
          s.entity_id.startsWith('sensor.') &&
          s.entity_id.endsWith('_battery_status') &&
          normalize(s.entity_id).replace(/[^a-z0-9]/g, '').includes(cleanSlug)
        );
        const offlineDevices = batterySensor?.attributes?.offline_devices || [];
        const lowBatteryDevices = batterySensor?.attributes?.low_battery_devices || [];
        const deviceDetails = batterySensor?.attributes?.device_details || [];

        return {
          entity_id: entity.entity_id,
          name: entity.attributes.friendly_name || entity.entity_id,
          away_temperature: entity.attributes.away_temperature !== undefined ? entity.attributes.away_temperature : 15.0,
          tolerance: entity.attributes.tolerance !== undefined ? entity.attributes.tolerance : 0.5,
          early_start_max_minutes: entity.attributes.early_start_max_minutes !== undefined ? entity.attributes.early_start_max_minutes : 120,
          window_open_timeout: entity.attributes.window_open_timeout !== undefined ? entity.attributes.window_open_timeout : 30,
          window_close_timeout: entity.attributes.window_close_timeout !== undefined ? entity.attributes.window_close_timeout : 60,
          min_heating_rate: entity.attributes.min_heating_rate !== undefined ? entity.attributes.min_heating_rate : 0.5,
          max_heating_rate: entity.attributes.max_heating_rate !== undefined ? entity.attributes.max_heating_rate : 3.0,
          current_temp: entity.attributes.current_temperature,
          target_temp: entity.attributes.temperature,
          hvac_action: entity.attributes.hvac_action,
          hvac_mode: entity.state,
          current_humidity: entity.attributes.current_humidity || (humiditySensor ? humiditySensor.state : null),
          comfort_level: entity.attributes.comfort_level || (comfortSensor ? comfortSensor.state : null),
          comfort_color: entity.attributes.comfort_color || (comfortSensor?.attributes?.comfort_color) || '#059669',
          comfort_score: entity.attributes.comfort_score,
          window_open: windowSensor ? windowSensor.state === 'on' : false,
          has_problem: problemSensor ? problemSensor.state === 'on' : false,
          problem_desc: problemSensor?.attributes?.description || null,
          clear_override_btn: clearBtn ? clearBtn.entity_id : null,
          trv_target: entity.attributes.trv_target_temperature || entity.attributes.trv_target || null,
          target_source: entity.attributes.target_source || null,
          decision_reason: entity.attributes.decision_reason || null,
          decision_time: entity.attributes.decision_time || null,
          active_temp_sensor: entity.attributes.active_temp_sensor || null,
          sensor_fallback_active: !!entity.attributes.sensor_fallback_active,
          heating_rate: entity.attributes.heating_rate !== undefined ? entity.attributes.heating_rate : null,
          heating_rate_samples: entity.attributes.heating_rate_samples || 0,
          heating_rate_confidence: entity.attributes.heating_rate_confidence !== undefined ? entity.attributes.heating_rate_confidence : 0,
          heating_rate_last_updated: entity.attributes.heating_rate_last_updated || null,
          override_active: !!entity.attributes.override_active,
          battery_status: batterySensor ? batterySensor.state : null,
          offline_devices: offlineDevices,
          low_battery_devices: lowBatteryDevices,
          device_details: deviceDetails,
        };
      })
      .sort((a, b) => a.name.localeCompare(b.name));

    if (!this._selectedScheduleRoom && this._rooms.length > 0) {
      this._selectedScheduleRoom = this._rooms[0].entity_id;
    }
    if (!this._selectedSettingsRoom && this._rooms.length > 0) {
      this._selectedSettingsRoom = this._rooms[0].entity_id;
    }

    // Hub mode entity
    const hubModeEntity = Object.values(this._hass.states).find(
      entity => entity.entity_id.startsWith('select.') && entity.entity_id.includes('hub_mode')
    );
    if (hubModeEntity) {
      this._hubMode = hubModeEntity.state;
      this._hubModeOptions = hubModeEntity.attributes.options || [];
      this._hubModeEntityId = hubModeEntity.entity_id;
      this._hubAttributes = hubModeEntity.attributes || {};
    }

    // Resolve optional boiler temperature and active state
    const boilerTempEntity = Object.values(this._hass.states).find(
      s => s.entity_id.includes('boiler_temperature') || s.entity_id === 'sensor.boilertemperatur_temperature_probe'
    );
    if (boilerTempEntity) {
      const parsed = parseFloat(boilerTempEntity.state);
      this._boilerTemp = !isNaN(parsed) ? parsed : null;
      this._boilerTempEntityId = boilerTempEntity.entity_id;
    }
    const boilerActiveEntity = Object.values(this._hass.states).find(
      s => s.entity_id.includes('boiler_active')
    );
    if (boilerActiveEntity) {
      this._boilerActive = boilerActiveEntity.state === 'on';
    }
  }

  render() {
    if (!this._hass) return;

    // Calculate house-wide KPIs
    const roomCount = this._rooms.length;
    const heatingCount = this._rooms.filter(r => r.hvac_action === 'heating').length;
    const openWindowsCount = this._rooms.filter(r => r.window_open).length;
    const problemCount = this._rooms.filter(r => r.has_problem).length;

    let avgTemp = '---';
    const validTemps = this._rooms.map(r => r.current_temp).filter(t => typeof t === 'number');
    if (validTemps.length > 0) {
      avgTemp = (validTemps.reduce((a, b) => a + b, 0) / validTemps.length).toFixed(1) + ' °C';
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          padding: 20px 24px 40px;
          background: var(--primary-background-color, #f8fafc);
          color: var(--primary-text-color, #1e293b);
          font-family: var(--paper-font-body1_-_font-family, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif);
          box-sizing: border-box;
          min-height: 100vh;
        }

        /* Top Header */
        .header-bar {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
          flex-wrap: wrap;
          gap: 16px;
        }
        .header-title-box {
          display: flex;
          align-items: center;
          gap: 12px;
        }
        .header-title-box .logo-icon {
          font-size: 32px;
          line-height: 1;
        }
        .header-title-box h1 {
          margin: 0;
          font-size: 26px;
          font-weight: 700;
          letter-spacing: -0.5px;
        }
        .header-title-box .tagline {
          font-size: 13px;
          color: var(--secondary-text-color, #64748b);
          font-weight: 400;
        }

        /* Hub Mode Pill Selector */
        .quick-btn-homeoffice {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 8px 14px;
          border-radius: 20px;
          background: var(--card-background-color, #ffffff);
          border: 1px solid var(--divider-color, #e2e8f0);
          box-shadow: 0 1px 3px rgba(0,0,0,0.06);
          cursor: pointer;
          font-size: 13px;
          font-weight: 600;
          color: var(--primary-text-color, #1e293b);
          transition: all 0.15s ease-in-out;
        }
        .quick-btn-homeoffice:hover {
          border-color: #3b82f6;
          box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        }
        .quick-btn-homeoffice.active {
          background: #eff6ff;
          border-color: #3b82f6;
          color: #1d4ed8;
          font-weight: 700;
        }
        .hub-mode-container {
          position: relative;
        }
        .hub-mode-button {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 8px 16px;
          border-radius: 20px;
          background: var(--card-background-color, #ffffff);
          border: 1px solid var(--divider-color, #e2e8f0);
          box-shadow: 0 1px 3px rgba(0,0,0,0.06);
          cursor: pointer;
          font-size: 14px;
          font-weight: 600;
          color: var(--primary-text-color, #1e293b);
          transition: all 0.15s ease-in-out;
        }
        .hub-mode-button:hover {
          border-color: var(--primary-color, #0284c7);
          box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        }
        .hub-mode-dot {
          width: 10px;
          height: 10px;
          border-radius: 50%;
          background: #10b981;
        }
        .hub-mode-dot.homeoffice { background: #3b82f6; }
        .hub-mode-dot.away { background: #f59e0b; }
        .hub-mode-dot.off { background: #94a3b8; }
        .hub-mode-dropdown {
          position: absolute;
          top: calc(100% + 8px);
          right: 0;
          background: var(--card-background-color, #ffffff);
          border: 1px solid var(--divider-color, #e2e8f0);
          border-radius: 12px;
          box-shadow: 0 10px 25px rgba(0,0,0,0.15);
          min-width: 220px;
          z-index: 1000;
          overflow: hidden;
          display: none;
        }
        .hub-mode-dropdown.open { display: block; }
        .hub-mode-item {
          padding: 12px 16px;
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 10px;
          font-size: 13px;
          font-weight: 500;
          transition: background 0.15s;
        }
        .hub-mode-item:hover {
          background: var(--secondary-background-color, #f1f5f9);
        }
        .hub-mode-item.active {
          background: rgba(2, 132, 199, 0.1);
          color: var(--primary-color, #0284c7);
          font-weight: 700;
        }

        /* Navigation Bar */
        .navigation-tabs {
          display: flex;
          gap: 8px;
          border-bottom: 2px solid var(--divider-color, #e2e8f0);
          margin-bottom: 24px;
        }
        .nav-tab {
          padding: 10px 18px;
          border: none;
          background: transparent;
          cursor: pointer;
          font-size: 14px;
          font-weight: 600;
          color: var(--secondary-text-color, #64748b);
          border-bottom: 3px solid transparent;
          margin-bottom: -2px;
          display: inline-flex;
          align-items: center;
          gap: 8px;
          transition: all 0.15s ease-in-out;
        }
        .nav-tab:hover {
          color: var(--primary-color, #0284c7);
        }
        .nav-tab.active {
          color: var(--primary-color, #0284c7);
          border-bottom-color: var(--primary-color, #0284c7);
        }

        /* KPI Banner */
        .kpi-row {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 16px;
          margin-bottom: 24px;
        }
        .kpi-card {
          background: var(--card-background-color, #ffffff);
          border: 1px solid var(--divider-color, #e2e8f0);
          border-radius: 12px;
          padding: 16px;
          display: flex;
          align-items: center;
          gap: 14px;
          box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }
        .kpi-icon {
          font-size: 28px;
          line-height: 1;
        }
        .kpi-meta .kpi-value {
          font-size: 20px;
          font-weight: 700;
          line-height: 1.2;
        }
        .kpi-meta .kpi-label {
          font-size: 12px;
          color: var(--secondary-text-color, #64748b);
          font-weight: 500;
        }

        /* Room Grid */
        .rooms-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
          gap: 20px;
        }
        .room-card {
          background: var(--card-background-color, #ffffff);
          border: 1px solid var(--divider-color, #e2e8f0);
          border-radius: 16px;
          padding: 20px;
          box-shadow: 0 2px 6px rgba(0,0,0,0.05);
          display: flex;
          flex-direction: column;
          gap: 16px;
          transition: transform 0.15s, box-shadow 0.15s;
        }
        .room-card:hover {
          transform: translateY(-2px);
          box-shadow: 0 6px 14px rgba(0,0,0,0.08);
        }
        .room-card.has-problem {
          border-color: #ef4444;
          box-shadow: 0 0 0 1px #ef4444;
        }

        /* Room Card Header */
        .room-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
        }
        .room-name {
          font-size: 18px;
          font-weight: 700;
          color: var(--primary-text-color, #0f172a);
          line-height: 1.3;
        }
        .status-pill {
          padding: 4px 10px;
          border-radius: 12px;
          font-size: 11px;
          font-weight: 700;
          text-transform: uppercase;
          display: inline-flex;
          align-items: center;
          gap: 4px;
        }
        .status-pill.heating {
          background: #fee2e2;
          color: #dc2626;
          box-shadow: 0 0 8px rgba(220, 38, 38, 0.2);
          animation: pulse 2s infinite ease-in-out;
        }
        .status-pill.idle {
          background: #dcfce7;
          color: #16a34a;
        }
        .status-pill.off {
          background: #f1f5f9;
          color: #64748b;
        }
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }

        /* Room Temp Display & Quick Steppers */
        .room-temp-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px 14px;
          background: var(--secondary-background-color, #f8fafc);
          border-radius: 12px;
        }
        .temp-display {
          display: flex;
          flex-direction: column;
        }
        .current-temp {
          font-size: 28px;
          font-weight: 800;
          line-height: 1;
          color: var(--primary-text-color, #0f172a);
          transition: color 0.2s ease-in-out;
        }
        .current-temp.heating { color: #ef4444; }
        .current-temp.idle { color: #22c55e; }
        .current-temp.off { color: #94a3b8; }
        .target-temp-label {
          font-size: 12px;
          font-weight: 600;
          color: var(--secondary-text-color, #64748b);
          margin-top: 4px;
        }
        .stepper-controls {
          display: flex;
          gap: 6px;
        }
        .step-btn {
          width: 36px;
          height: 36px;
          border-radius: 8px;
          border: 1px solid var(--divider-color, #cbd5e1);
          background: var(--card-background-color, #ffffff);
          color: var(--primary-text-color, #0f172a);
          font-size: 16px;
          font-weight: 700;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.15s;
        }
        .step-btn:hover {
          background: var(--primary-color, #0284c7);
          color: #fff;
          border-color: var(--primary-color, #0284c7);
        }

        /* Room Badges Row */
        .room-badges {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }
        .badge {
          padding: 4px 10px;
          border-radius: 8px;
          font-size: 12px;
          font-weight: 600;
          display: inline-flex;
          align-items: center;
          gap: 6px;
          background: var(--secondary-background-color, #f1f5f9);
          color: var(--primary-text-color, #334155);
        }
        .badge.window-open {
          background: #fef2f2;
          color: #b91c1c;
          border: 1px solid #fecaca;
          font-weight: 700;
        }
        .badge.window-closed {
          background: #f8fafc;
          color: #64748b;
        }
        .badge.problem {
          background: #dc2626;
          color: #ffffff;
          font-weight: 700;
        }
        .badge.override {
          background: #fef3c7;
          color: #b45309;
          border: 1px solid #fde68a;
        }

        /* Room Footer Controls */
        .room-actions {
          display: flex;
          gap: 8px;
          margin-top: auto;
        }
        .btn-schedule {
          flex: 1;
          padding: 10px;
          border-radius: 8px;
          border: 1px solid var(--divider-color, #cbd5e1);
          background: var(--card-background-color, #ffffff);
          color: var(--primary-color, #0284c7);
          font-weight: 600;
          font-size: 13px;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          transition: all 0.15s;
        }
        .btn-schedule:hover {
          background: rgba(2, 132, 199, 0.08);
          border-color: var(--primary-color, #0284c7);
        }
        .btn-reset-override {
          padding: 8px 12px;
          border-radius: 8px;
          border: 1px solid #fcd34d;
          background: #fef3c7;
          color: #b45309;
          font-weight: 600;
          font-size: 12px;
          cursor: pointer;
          display: inline-flex;
          align-items: center;
          gap: 4px;
        }
        .btn-reset-override:hover {
          background: #fde68a;
        }

        /* Reglerdetails Accordion (DIAG-01, Feature 1, 5, 6) */
        .room-details-accordion {
          margin-top: 4px;
          border-top: 1px dashed var(--divider-color, #e2e8f0);
          padding-top: 10px;
        }
        .room-details-summary {
          font-size: 12px;
          font-weight: 600;
          color: var(--secondary-text-color, #64748b);
          cursor: pointer;
          user-select: none;
          display: flex;
          align-items: center;
          gap: 6px;
        }
        .room-details-summary:hover {
          color: var(--primary-color, #0284c7);
        }
        .room-details-content {
          margin-top: 8px;
          padding: 10px;
          background: var(--secondary-background-color, #f8fafc);
          border-radius: 8px;
          display: flex;
          flex-direction: column;
          gap: 6px;
          font-size: 11px;
        }
        .detail-row {
          display: flex;
          justify-content: space-between;
          align-items: baseline;
          gap: 8px;
        }
        .detail-label {
          color: var(--secondary-text-color, #64748b);
          font-weight: 500;
          white-space: nowrap;
        }
        .detail-value {
          color: var(--primary-text-color, #0f172a);
          font-weight: 600;
          text-align: right;
          word-break: break-word;
        }
        .detail-value.text-warning {
          color: #d97706;
          font-weight: 700;
        }
        .detail-btn-reset {
          margin-top: 6px;
          padding: 6px 10px;
          background: transparent;
          border: 1px solid var(--divider-color, #cbd5e1);
          border-radius: 6px;
          font-size: 11px;
          font-weight: 600;
          color: var(--secondary-text-color, #64748b);
          cursor: pointer;
          transition: background 0.15s, color 0.15s, border-color 0.15s;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 4px;
        }
        .detail-btn-reset:hover {
          background: #fee2e2;
          color: #dc2626;
          border-color: #fca5a5;
        }

        /* Schedules View */
        .schedules-container {
          background: var(--card-background-color, #ffffff);
          border-radius: 16px;
          padding: 24px;
          border: 1px solid var(--divider-color, #e2e8f0);
          box-shadow: 0 2px 6px rgba(0,0,0,0.04);
        }
        .schedules-header {
          margin-bottom: 20px;
        }
        .schedules-header h2 {
          margin: 0 0 12px 0;
          font-size: 20px;
          font-weight: 700;
        }
        .room-selector-pills {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-bottom: 20px;
        }
        .room-pill {
          padding: 8px 16px;
          border-radius: 20px;
          border: 1px solid var(--divider-color, #cbd5e1);
          background: var(--card-background-color, #ffffff);
          color: var(--primary-text-color, #334155);
          cursor: pointer;
          font-size: 13px;
          font-weight: 600;
          transition: all 0.15s;
        }
        .room-pill:hover {
          border-color: var(--primary-color, #0284c7);
        }
        .room-pill.active {
          background: var(--primary-color, #0284c7);
          color: #ffffff;
          border-color: var(--primary-color, #0284c7);
        }

        /* System View */
        .system-container {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
          gap: 20px;
        }
        .system-card {
          background: var(--card-background-color, #ffffff);
          border: 1px solid var(--divider-color, #e2e8f0);
          border-radius: 16px;
          padding: 20px;
          box-shadow: 0 2px 6px rgba(0,0,0,0.04);
          box-sizing: border-box;
          overflow: hidden;
          max-width: 100%;
        }
        .system-card h3 {
          margin: 0 0 16px 0;
          font-size: 18px;
          font-weight: 700;
        }
        .system-table {
          width: 100%;
          table-layout: fixed;
          border-collapse: collapse;
          font-size: 13px;
          box-sizing: border-box;
        }
        .system-table th, .system-table td {
          padding: 10px 12px;
          border-bottom: 1px solid var(--divider-color, #f1f5f9);
          text-align: left;
          vertical-align: middle;
          box-sizing: border-box;
          word-break: break-word;
          overflow-wrap: anywhere;
        }
        .system-table tr:last-child td {
          border-bottom: none;
        }
        .system-table th {
          font-weight: 600;
          color: var(--secondary-text-color, #64748b);
        }
        .settings-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
          gap: 12px;
          margin-top: 14px;
        }
        .setting-item {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .setting-label {
          font-size: 11px;
          font-weight: 600;
          color: var(--secondary-text-color, #64748b);
        }
        .setting-input {
          padding: 8px 10px;
          border: 1px solid var(--divider-color, #cbd5e1);
          border-radius: 6px;
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color, #0f172a);
          font-size: 13px;
          font-weight: 600;
          box-sizing: border-box;
          outline: none;
        }
        .setting-input:focus {
          border-color: var(--primary-color, #0284c7);
        }
        .btn-save-settings {
          margin-top: 16px;
          padding: 10px 18px;
          background: var(--primary-color, #0284c7);
          color: #fff;
          border: none;
          border-radius: 8px;
          font-weight: 600;
          font-size: 13px;
          cursor: pointer;
          transition: all 0.15s ease-in-out;
          display: inline-flex;
          align-items: center;
          gap: 6px;
        }
        .btn-save-settings:hover {
          background: #0369a1;
        }

        /* tado° Style Comfort Tab */
        .tado-container {
          display: flex;
          flex-direction: column;
          gap: 20px;
        }
        .tado-frischluft-card {
          background: #f0fdf4;
          border: 1px solid #bbf7d0;
          border-radius: 20px;
          padding: 22px 24px;
          box-shadow: 0 4px 12px rgba(16, 185, 129, 0.08);
          display: flex;
          flex-direction: column;
          align-items: center;
          text-align: center;
          box-sizing: border-box;
        }
        .frischluft-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          width: 100%;
          margin-bottom: 6px;
        }
        .frischluft-title {
          font-size: 19px;
          font-weight: 700;
          color: #14532d;
        }
        .frischluft-weather {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 17px;
          font-weight: 700;
          color: #15803d;
        }
        .frischluft-sub {
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.8px;
          color: #16a34a;
          margin-bottom: 18px;
          width: 100%;
          text-align: left;
        }
        .frischluft-house-box {
          background: #ffffff;
          border: 1px solid #dcfce7;
          border-radius: 16px;
          padding: 20px 24px;
          width: 100%;
          max-width: 520px;
          box-sizing: border-box;
          box-shadow: 0 2px 8px rgba(0,0,0,0.04);
          display: flex;
          flex-direction: column;
          align-items: center;
        }
        .house-status-text {
          font-size: 16px;
          font-weight: 800;
          letter-spacing: 0.6px;
          color: #166534;
          margin: 8px 0 4px 0;
        }
        .house-desc {
          font-size: 13px;
          color: #4b5563;
          line-height: 1.45;
        }

        .tado-rooms-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
          gap: 20px;
        }
        .tado-room-card {
          border-radius: 22px;
          padding: 22px;
          color: #ffffff;
          box-shadow: 0 6px 18px rgba(0,0,0,0.12);
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          position: relative;
          min-height: 390px;
          box-sizing: border-box;
          transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .tado-room-card:hover {
          transform: translateY(-2px);
          box-shadow: 0 10px 26px rgba(0,0,0,0.18);
        }
        .tado-card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 6px;
        }
        .tado-room-name {
          font-size: 21px;
          font-weight: 700;
          text-shadow: 0 1px 3px rgba(0,0,0,0.25);
        }
        .tado-status-badge {
          font-size: 12px;
          font-weight: 800;
          letter-spacing: 1px;
          padding: 4px 12px;
          background: rgba(255,255,255,0.22);
          border-radius: 12px;
          backdrop-filter: blur(4px);
          text-shadow: 0 1px 2px rgba(0,0,0,0.2);
        }
        .tado-stats-subbar {
          display: flex;
          justify-content: space-between;
          font-size: 11px;
          font-weight: 700;
          letter-spacing: 0.6px;
          opacity: 0.9;
          margin-bottom: 12px;
          border-bottom: 1px solid rgba(255,255,255,0.22);
          padding-bottom: 8px;
        }
        .tado-dial-container {
          display: flex;
          justify-content: center;
          align-items: center;
          margin: 10px 0 16px 0;
        }
        .tado-dial-svg {
          width: 175px;
          height: 175px;
          overflow: visible;
        }
        .tado-bottom-bar {
          display: flex;
          flex-direction: column;
          gap: 10px;
          margin-top: auto;
          border-top: 1px solid rgba(255,255,255,0.22);
          padding-top: 12px;
        }
        .tado-temp-control {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .tado-target-label {
          font-size: 14px;
          font-weight: 700;
          text-shadow: 0 1px 2px rgba(0,0,0,0.2);
        }
        .tado-steppers {
          display: flex;
          gap: 6px;
        }
        .tado-step-btn {
          width: 32px;
          height: 32px;
          border-radius: 8px;
          border: 1.5px solid rgba(255,255,255,0.65);
          background: rgba(255,255,255,0.18);
          color: #ffffff;
          font-size: 18px;
          font-weight: bold;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: background 0.15s;
        }
        .tado-step-btn:hover {
          background: rgba(255,255,255,0.38);
        }
        .tado-extra-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 12px;
        }
        .tado-badge {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 4px 10px;
          border-radius: 8px;
          background: rgba(255,255,255,0.22);
          font-weight: 600;
          backdrop-filter: blur(4px);
        }
        .tado-btn-plan {
          background: rgba(255,255,255,0.22);
          border: 1px solid rgba(255,255,255,0.5);
          color: #ffffff;
          border-radius: 8px;
          padding: 5px 12px;
          font-size: 12px;
          font-weight: 600;
          cursor: pointer;
          transition: background 0.15s;
        }
        .tado-btn-plan:hover {
          background: rgba(255,255,255,0.4);
        }
      </style>

      <!-- App Header -->
      <div class="header-bar">
        <div class="header-title-box">
          <div class="logo-icon">🔥</div>
          <div>
            <h1>TaDIY Klima-Manager</h1>
            <div class="tagline">Adaptive Climate Orchestrator v3.1.2</div>
          </div>
        </div>

        <div style="display: flex; align-items: center; gap: 10px;">
          <div class="hub-mode-container">
            <button class="hub-mode-button" data-action="toggle-hub-dropdown">
              <span class="hub-mode-dot ${this._hubMode}"></span>
              <span>Modus: <strong>${this._hubMode.toUpperCase()}</strong></span>
              <span>▼</span>
            </button>
            <div class="hub-mode-dropdown" data-dropdown>
              ${this._hubModeOptions.map(m => `
                <div class="hub-mode-item ${m === this._hubMode ? 'active' : ''}" data-hub-mode="${m}">
                  <span class="hub-mode-dot ${m}"></span>
                  <span>${m.toUpperCase()}</span>
                </div>
              `).join('')}
            </div>
          </div>
        </div>
      </div>

      <!-- Navigation Tabs -->
      <div class="navigation-tabs">
        <button class="nav-tab ${this._activeTab === 'overview' ? 'active' : ''}" data-tab="overview">
          🏠 Räume & Übersicht
        </button>
        <button class="nav-tab ${this._activeTab === 'comfort' ? 'active' : ''}" data-tab="comfort">
          🌿 Raumluft-Komfort
        </button>
        <button class="nav-tab ${this._activeTab === 'schedules' ? 'active' : ''}" data-tab="schedules">
          📅 Wochen- & Modus-Zeitpläne
        </button>
        <button class="nav-tab ${this._activeTab === 'system' ? 'active' : ''}" data-tab="system">
          ⚙️ Kessel & Systemstatus
        </button>
      </div>

      <!-- Tab Content -->
      ${this._activeTab === 'overview' ? this.renderOverviewTab(roomCount, heatingCount, openWindowsCount, problemCount, avgTemp) : ''}
      ${this._activeTab === 'comfort' ? this.renderComfortTab(openWindowsCount) : ''}
      ${this._activeTab === 'schedules' ? this.renderSchedulesTab() : ''}
      ${this._activeTab === 'system' ? this.renderSystemTab(heatingCount) : ''}
    `;

    this.attachEventListeners();

    if (this._activeTab === 'schedules') {
      this.embedScheduleCard();
    }
  }

  renderOverviewTab(roomCount, heatingCount, openWindowsCount, problemCount, avgTemp) {
    return `
      <!-- KPI Stats -->
      <div class="kpi-row">
        <div class="kpi-card">
          <div class="kpi-icon">🌡️</div>
          <div class="kpi-meta">
            <div class="kpi-value">${avgTemp}</div>
            <div class="kpi-label">Durchschnittstemperatur</div>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon">🔥</div>
          <div class="kpi-meta">
            <div class="kpi-value">${heatingCount} / ${roomCount}</div>
            <div class="kpi-label">Räume heizen aktiv</div>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon"><ha-icon icon="mdi:window-open-variant" style="--mdc-icon-size: 28px;"></ha-icon></div>
          <div class="kpi-meta">
            <div class="kpi-value">${openWindowsCount}</div>
            <div class="kpi-label">Fenster geöffnet</div>
          </div>
        </div>
        <div class="kpi-card">
          <div class="kpi-icon">⚠️</div>
          <div class="kpi-meta">
            <div class="kpi-value">${problemCount}</div>
            <div class="kpi-label">Heizstörungen / Kalk</div>
          </div>
        </div>
      </div>

      <!-- Action Bar: Rooms Header & Single-Day Homeoffice Toggle -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin: 20px 0 12px 0;">
        <h2 style="font-size: 18px; font-weight: 700; margin: 0; color: var(--primary-text-color, #1e293b);">Räume</h2>
        <button class="quick-btn-homeoffice ${this._hubMode === 'homeoffice' ? 'active' : ''}" data-action="toggle-homeoffice" title="Homeoffice für heute aktivieren (automatischer Rückfall auf Normal zum Feierabend)">
          💼 ${this._hubMode === 'homeoffice' ? 'Homeoffice aktiv (Heute bis Feierabend)' : 'Homeoffice Heute (1 Tag)'}
        </button>
      </div>

      <!-- Room Cards Grid -->
      <div class="rooms-grid">
        ${this._rooms.map(room => this.renderRoomCard(room)).join('')}
      </div>
    `;
  }

  renderRoomCard(room) {
    const isHeating = room.hvac_action === 'heating';
    const isOff = room.hvac_mode === 'off';
    const statusClass = isHeating ? 'heating' : (isOff ? 'off' : 'idle');
    const statusText = isHeating ? '🔥 Heizt' : (isOff ? '⚪ Aus' : '🟢 Bereit');

    const currentTemp = typeof room.current_temp === 'number' ? room.current_temp.toFixed(1) + ' °C' : '--.- °C';
    const targetTemp = typeof room.target_temp === 'number' ? room.target_temp.toFixed(1) + ' °C' : 'AUS';

    return `
      <div class="room-card ${room.has_problem ? 'has-problem' : ''}" data-room="${room.entity_id}">
        <div class="room-header">
          <div class="room-name">${room.name}</div>
          <div class="status-pill ${statusClass}">${statusText}</div>
        </div>

        <div class="room-temp-row">
          <div class="temp-display">
            <div class="current-temp ${statusClass}">${currentTemp}</div>
            <div class="target-temp-label">Sollwert: ${targetTemp}</div>
          </div>
          <div class="stepper-controls">
            <button class="step-btn" data-action="temp-step" data-step="-0.5" data-entity="${room.entity_id}" title="-0.5°C">−</button>
            <button class="step-btn" data-action="temp-step" data-step="+0.5" data-entity="${room.entity_id}" title="+0.5°C">+</button>
          </div>
        </div>

        <div class="room-badges">
          ${room.window_open ? `
            <div class="badge window-open"><ha-icon icon="mdi:window-open-variant" style="--mdc-icon-size: 14px; margin-right: 4px;"></ha-icon> Fenster offen (Heizstopp)</div>
          ` : `
            <div class="badge window-closed"><ha-icon icon="mdi:window-closed-variant" style="--mdc-icon-size: 14px; margin-right: 4px;"></ha-icon> Fenster zu</div>
          `}

          ${room.has_problem ? `
            <div class="badge problem" title="${room.problem_desc || 'Kein Temperaturanstieg / Kalkblockade'}">
              ⚠️ Heizstörung / Kalk
            </div>
          ` : ''}

          ${room.offline_devices && room.offline_devices.length > 0 ? `
            <div class="badge" style="background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3);" title="Offline: ${room.offline_devices.join(', ')}">
              ⚠️ ${room.offline_devices.length} Sensor${room.offline_devices.length > 1 ? 'en' : ''} offline
            </div>
          ` : ''}

          ${room.low_battery_devices && room.low_battery_devices.length > 0 ? `
            <div class="badge" style="background: rgba(245, 158, 11, 0.15); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3);" title="Batterie schwach: ${room.low_battery_devices.join(', ')}">
              🔋 Batterie schwach (${room.low_battery_devices.length})
            </div>
          ` : ''}

          ${room.current_humidity ? `
            <div class="badge">💧 ${room.current_humidity}%</div>
          ` : ''}

          ${room.comfort_level ? `
            <div class="badge" style="border-left: 3px solid ${room.comfort_color};">
              ⭐ ${room.comfort_level}
            </div>
          ` : ''}
        </div>

        <div class="room-actions">
          <button class="btn-schedule" data-action="open-schedule" data-entity="${room.entity_id}">
            📅 Zeitplan bearbeiten
          </button>
          <button class="btn-reset-override" data-action="clear-override" data-entity="${room.entity_id}" title="Manuellen Sollwert zurücksetzen">
            ↺ Plan
          </button>
        </div>

        <details class="room-details-accordion" data-details-id="${room.entity_id}" ${this._openDetails.has(room.entity_id) ? 'open' : ''}>
          <summary class="room-details-summary">ℹ️ Reglerdetails</summary>
          <div class="room-details-content">
            <div class="detail-row">
              <span class="detail-label">Effektiver Sollwert:</span>
              <span class="detail-value">${typeof room.target_temp === 'number' ? room.target_temp.toFixed(1) + ' °C' : 'AUS'}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">Sollwert-Quelle:</span>
              <span class="detail-value">${room.target_source || 'Standard'}</span>
            </div>
            <div class="detail-row">
              <span class="detail-label">Entscheidungsgrund:</span>
              <span class="detail-value">${room.decision_reason || (isHeating ? 'Heizbedarf aktiv' : 'Bereit / Leerlauf')}</span>
            </div>
            ${room.decision_time ? `
              <div class="detail-row">
                <span class="detail-label">Zeitpunkt:</span>
                <span class="detail-value">${new Date(room.decision_time).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', second:'2-digit'})}</span>
              </div>
            ` : ''}
            <div class="detail-row">
              <span class="detail-label">Aktiver Fühler:</span>
              <span class="detail-value ${room.sensor_fallback_active ? 'text-warning' : ''}">
                ${room.sensor_fallback_active ? '⚠️ TRV-Fallback: ' : '🟢 '}${room.active_temp_sensor || (room.current_temp ? 'Hauptsensor' : 'Nicht verfügbar')}
              </span>
            </div>
            <div class="detail-row">
              <span class="detail-label">Gelernte Heizrate:</span>
              <span class="detail-value">
                ${typeof room.heating_rate === 'number' ? room.heating_rate.toFixed(2) + ' °C/h' : '--.-'}
                ${room.heating_rate_samples ? `(${room.heating_rate_samples} Messung${room.heating_rate_samples === 1 ? '' : 'en'}, ${(room.heating_rate_confidence * 100).toFixed(0)}% Konfidenz)` : '(Initial)'}
              </span>
            </div>
            ${room.device_details && room.device_details.length > 0 ? `
              <div class="detail-row" style="margin-top: 8px; border-top: 1px dashed var(--divider-color, #334155); padding-top: 8px;">
                <span class="detail-label" style="font-weight: 700;">Geräte & Sensoren (${room.device_details.length}):</span>
              </div>
              ${room.device_details.map(d => `
                <div class="detail-row" style="padding-left: 8px; font-size: 11px;">
                  <span class="detail-label">${d.type === 'trv' ? '🌡️' : (d.type === 'window' ? '🪟' : '📡')} ${d.name}:</span>
                  <span class="detail-value ${d.is_offline ? 'text-danger' : (d.is_low ? 'text-warning' : '')}">
                    ${d.is_offline ? '⚠️ Offline' : (d.battery !== null && d.battery !== undefined ? d.battery + '%' : 'Online')}
                  </span>
                </div>
              `).join('')}
            ` : ''}
          </div>
        </details>
      </div>
    `;
  }

  renderComfortTab(openWindowsCount) {
    // Resolve outdoor temp and weather
    const weatherEntity = Object.values(this._hass.states).find(s => s.entity_id.startsWith('weather.'));
    const outdoorSensor = Object.values(this._hass.states).find(s =>
      (s.entity_id.includes('outdoor') || s.entity_id.includes('aussen')) && s.entity_id.includes('temp')
    );
    const outdoorTemp = outdoorSensor ? Number(outdoorSensor.state) : (weatherEntity?.attributes?.temperature ?? 15.0);

    const roomsWithHumidity = this._rooms.filter(r => r.current_humidity !== null && r.current_humidity !== undefined);
    const avgHumidity = roomsWithHumidity.length > 0
      ? Math.round(roomsWithHumidity.reduce((sum, r) => sum + Number(r.current_humidity), 0) / roomsWithHumidity.length)
      : 50;

    let airStatus = 'AUSGEWOGEN';
    let airAdvice = 'Während der letzten 24 Stunden optimaler Luftaustausch.';
    if (openWindowsCount > 0) {
      airStatus = 'LÜFTEN AKTIV';
      airAdvice = `${openWindowsCount} Raum/Räume werden aktuell gelüftet. Heizstopp aktiv.`;
    } else if (avgHumidity > 60) {
      airStatus = 'MÄSSIG';
      airAdvice = 'Erhöhte Luftfeuchte gemessen (> 60%). Stoßlüften für Frischluft empfohlen.';
    } else if (avgHumidity < 40) {
      airStatus = 'TROCKEN';
      airAdvice = 'Trockene Heizungsluft (< 40%). Kurzes Durchlüften empfohlen.';
    }

    return `
      <div class="tado-container">
        <!-- Frischluft-Indikator (tado-style) -->
        <div class="tado-frischluft-card">
          <div class="frischluft-header">
            <div class="frischluft-title">Frischluft-Indikator</div>
            <div class="frischluft-weather">
              <span>⛅</span>
              <span>${typeof outdoorTemp === 'number' && !isNaN(outdoorTemp) ? outdoorTemp.toFixed(0) : '15'}°</span>
            </div>
          </div>
          <div class="frischluft-sub">
            LUFTQUALITÄTSINDEX AUSSENLUFT 76 - GUT
          </div>
          <div class="frischluft-house-box">
            <ha-icon icon="mdi:home-heart" style="--mdc-icon-size: 52px; color: #10b981;"></ha-icon>
            <div class="house-status-text">RAUMLUFT ${airStatus}</div>
            <div class="house-desc">${airAdvice}</div>
          </div>
        </div>

        <!-- Room Air Comfort Cards Grid (tado-style) -->
        <div class="tado-rooms-grid">
          ${this._rooms.map(room => this.renderTadoRoomCard(room)).join('')}
        </div>
      </div>
    `;
  }

  renderTadoRoomCard(room) {
    const temp = typeof room.current_temp === 'number' ? room.current_temp : 20.0;
    const humidity = (room.current_humidity !== null && room.current_humidity !== undefined && !isNaN(room.current_humidity)) ? Number(room.current_humidity) : 50;
    const targetTemp = typeof room.target_temp === 'number' ? room.target_temp.toFixed(1) + '°C' : 'AUS';

    // Status evaluation & color
    let statusText = 'AUSGEWOGEN';
    let cardBg = 'linear-gradient(145deg, #10b981 0%, #059669 100%)';

    if (humidity >= 60 && temp < 20) {
      statusText = 'FEUCHT';
      cardBg = 'linear-gradient(145deg, #3b82f6 0%, #1d4ed8 100%)';
    } else if (humidity >= 60) {
      statusText = 'FEUCHT';
      cardBg = 'linear-gradient(145deg, #2563eb 0%, #1e40af 100%)';
    } else if (temp < 18.5) {
      statusText = 'KALT';
      cardBg = 'linear-gradient(145deg, #0284c7 0%, #0369a1 100%)';
    } else if (temp > 22.5) {
      statusText = 'ZU WARM';
      cardBg = 'linear-gradient(145deg, #f59e0b 0%, #d97706 100%)';
    } else if (humidity < 40) {
      statusText = 'TROCKEN';
      cardBg = 'linear-gradient(145deg, #0ea5e9 0%, #0369a1 100%)';
    }

    // Dot positioning calculation on circle (center 80, 80, radius 54)
    let dx = ((humidity - 50.0) / 25.0) * 36.0;
    let dy = -(((temp - 21.0) / 4.0) * 36.0);

    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist > 46) {
      dx = (dx / dist) * 46;
      dy = (dy / dist) * 46;
    }

    const dotX = (80 + dx).toFixed(1);
    const dotY = (80 + dy).toFixed(1);

    return `
      <div class="tado-room-card" style="background: ${cardBg};" data-room="${room.entity_id}">
        <div class="tado-card-header">
          <div class="tado-room-name">${room.name}</div>
          <div class="tado-status-badge">${statusText}</div>
        </div>

        <div class="tado-stats-subbar">
          <span>TEMPERATUR ${temp.toFixed(1)}°</span>
          <span>LUFTFEUCHTIGKEIT ${Math.round(humidity)}%</span>
        </div>

        <div class="tado-dial-container">
          <svg class="tado-dial-svg" viewBox="0 0 160 160">
            <!-- 4 Coordinate Labels -->
            <text x="80" y="15" text-anchor="middle" fill="rgba(255,255,255,0.92)" font-size="9" font-weight="700" letter-spacing="0.5">ZU WARM</text>
            <text x="80" y="153" text-anchor="middle" fill="rgba(255,255,255,0.92)" font-size="9" font-weight="700" letter-spacing="0.5">KALT</text>
            <text x="4" y="83" text-anchor="start" fill="rgba(255,255,255,0.92)" font-size="9" font-weight="700" letter-spacing="0.5">TROCKEN</text>
            <text x="156" y="83" text-anchor="end" fill="rgba(255,255,255,0.92)" font-size="9" font-weight="700" letter-spacing="0.5">FEUCHT</text>

            <!-- Outer Circle Boundary -->
            <circle cx="80" cy="80" r="54" fill="none" stroke="rgba(255,255,255,0.45)" stroke-width="1.5" />

            <!-- Inner Comfort Ring (Target Zone) -->
            <circle cx="80" cy="80" r="24" fill="rgba(255,255,255,0.22)" stroke="rgba(255,255,255,0.7)" stroke-width="1.5" />

            <!-- Moving Position Dot with Glow -->
            <circle cx="${dotX}" cy="${dotY}" r="9" fill="rgba(255,255,255,0.3)" />
            <circle cx="${dotX}" cy="${dotY}" r="6.5" fill="#ffffff" filter="drop-shadow(0 2px 4px rgba(0,0,0,0.35))" />
            <circle cx="${dotX}" cy="${dotY}" r="3" fill="rgba(255,255,255,0.95)" />
          </svg>
        </div>

        <div class="tado-bottom-bar">
          <div class="tado-temp-control">
            <span class="tado-target-label">Sollwert: ${targetTemp}</span>
            <div class="tado-steppers">
              <button class="tado-step-btn" data-action="temp-step" data-step="-0.5" data-entity="${room.entity_id}" title="-0.5°C">−</button>
              <button class="tado-step-btn" data-action="temp-step" data-step="+0.5" data-entity="${room.entity_id}" title="+0.5°C">+</button>
            </div>
          </div>
          <div class="tado-extra-row">
            ${room.window_open ? `
              <span class="tado-badge"><ha-icon icon="mdi:window-open-variant" style="--mdc-icon-size: 14px; margin-right: 3px;"></ha-icon> Offen</span>
            ` : `
              <span class="tado-badge"><ha-icon icon="mdi:window-closed-variant" style="--mdc-icon-size: 14px; margin-right: 3px;"></ha-icon> Zu</span>
            `}
            <button class="tado-btn-plan" data-action="open-schedule" data-entity="${room.entity_id}">
              📅 Zeitplan
            </button>
          </div>
        </div>
      </div>
    `;
  }

  renderSchedulesTab() {
    return `
      <div class="schedules-container">
        <div class="schedules-header">
          <h2>Wochen- & Modus-Zeitpläne</h2>
          <div class="room-selector-pills">
            ${this._rooms.map(room => `
              <button class="room-pill ${room.entity_id === this._selectedScheduleRoom ? 'active' : ''}"
                      data-action="select-schedule-room"
                      data-entity="${room.entity_id}">
                ${room.name}
              </button>
            `).join('')}
          </div>
        </div>

        <div id="schedule-card-mount">
          <!-- <tadiy-schedule-card> will be mounted here directly in full-width -->
        </div>
      </div>
    `;
  }

  renderSystemTab(heatingCount) {
    const hubAttrs = this._hubAttributes || {};
    const frostTemp = hubAttrs.frost_protection_temp !== undefined ? hubAttrs.frost_protection_temp : 7.0;
    const boostTemp = hubAttrs.boost_temperature !== undefined ? hubAttrs.boost_temperature : 24.0;
    const boostDur = hubAttrs.boost_duration !== undefined ? hubAttrs.boost_duration : 60;
    const winOpenTimeout = hubAttrs.window_open_timeout !== undefined ? hubAttrs.window_open_timeout : 30;
    const winCloseTimeout = hubAttrs.window_close_timeout !== undefined ? hubAttrs.window_close_timeout : 60;
    const dontHeatBelow = (hubAttrs.dont_heat_below_outdoor !== undefined && hubAttrs.dont_heat_below_outdoor !== null) ? hubAttrs.dont_heat_below_outdoor : '';

    const boilerTemp = this._boilerTemp !== undefined && this._boilerTemp !== null ? this._boilerTemp : hubAttrs.boiler_temperature;
    const boilerActive = this._boilerActive !== undefined ? this._boilerActive : hubAttrs.boiler_active;
    const boilerSensorAvailable = hubAttrs.boiler_sensor_available !== false;
    const boilerEntity = this._boilerTempEntityId || hubAttrs.boiler_temp_sensor || 'sensor.boilertemperatur_temperature_probe';

    return `
      <div class="system-container">
        <div class="system-card">
          <h3>🏠 TaDIY Hub Betriebsmodus</h3>
          <p style="font-size: 13px; color: var(--secondary-text-color);">
            Wähle den globalen Betriebsmodus für das gesamte Gebäude:
          </p>
          <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 12px;">
            ${this._hubModeOptions.map(m => `
              <button class="btn-schedule" style="justify-content: flex-start; padding: 12px; font-weight: 600; ${m === this._hubMode ? 'border-color: var(--primary-color); background: rgba(2, 132, 199, 0.08);' : ''}"
                      data-hub-mode="${m}">
                <span class="hub-mode-dot ${m}" style="display: inline-block; margin-right: 8px;"></span>
                <span>${m.toUpperCase()}</span>
              </button>
            `).join('')}
          </div>
        </div>

        <div class="system-card">
          <h3>⚙️ Hub-Einstellungen</h3>
          <p style="font-size: 13px; color: var(--secondary-text-color);">
            Zentrale Parameter für Frostschutz, Boost und Fensterüberwachung:
          </p>
          <div class="settings-grid">
            <div class="setting-item">
              <span class="setting-label">❄️ Frostschutz-Temp (°C)</span>
              <input type="number" class="setting-input" id="setting-frost-temp" value="${frostTemp}" step="0.5" min="3" max="15">
            </div>
            <div class="setting-item">
              <span class="setting-label">🚀 Boost-Temp (°C)</span>
              <input type="number" class="setting-input" id="setting-boost-temp" value="${boostTemp}" step="0.5" min="18" max="30">
            </div>
            <div class="setting-item">
              <span class="setting-label">⏱️ Boost-Dauer (Min.)</span>
              <input type="number" class="setting-input" id="setting-boost-duration" value="${boostDur}" step="5" min="10" max="360">
            </div>
            <div class="setting-item">
              <span class="setting-label"><ha-icon icon="mdi:window-open-variant" style="--mdc-icon-size: 16px; vertical-align: text-bottom; margin-right: 4px;"></ha-icon> Fenster-Offen Wartezeit (s)</span>
              <input type="number" class="setting-input" id="setting-win-open" value="${winOpenTimeout}" step="5" min="5" max="600">
            </div>
            <div class="setting-item">
              <span class="setting-label">🔄 Schließ-Abklingzeit (s)</span>
              <input type="number" class="setting-input" id="setting-win-close" value="${winCloseTimeout}" step="5" min="5" max="600">
            </div>
            <div class="setting-item">
              <span class="setting-label">☀️ Sommerabschaltung (°C)</span>
              <input type="number" class="setting-input" id="setting-dont-heat" value="${dontHeatBelow}" step="0.5" min="10" max="25" placeholder="Deaktiviert">
            </div>
            <div class="setting-item">
              <span class="setting-label">⏱️ Brenner-Mindestlaufzeit (s)</span>
              <input type="number" class="setting-input" id="setting-boiler-min-run" value="${hubAttrs.boiler_min_run_time || 300}" step="30" min="60" max="1800">
            </div>
            <div class="setting-item">
              <span class="setting-label">🔄 Zyklus-Sperre bei Absenkung</span>
              <select class="setting-input" id="setting-cycle-lock">
                <option value="true" ${hubAttrs.cycle_lock_on_setpoint_drop !== false ? 'selected' : ''}>Aktiv (Sofortige Freigabe)</option>
                <option value="false" ${hubAttrs.cycle_lock_on_setpoint_drop === false ? 'selected' : ''}>Inaktiv</option>
              </select>
            </div>
            <div class="setting-item" style="grid-column: 1 / -1;">
              <span class="setting-label">🔥 Kessel-Vorlauftemperaturfühler</span>
              <input type="text" class="setting-input" id="setting-boiler-sensor" value="${boilerEntity}" placeholder="sensor.kessel_vorlauf">
            </div>
            <div class="setting-item" style="grid-column: 1 / -1;">
              <span class="setting-label">🚰 Warmwasser-Zirkulationsfühler</span>
              <input type="text" class="setting-input" id="setting-dhw-sensor" value="${hubAttrs.dhw_temp_sensor || ''}" placeholder="sensor.warmwasser_vorlauf">
            </div>
          </div>
          <button type="button" class="btn-save-settings" data-action="save-hub-settings">
            💾 Hub-Einstellungen speichern
          </button>
        </div>

        <div class="system-card">
          <h3>🚪 Raum-Einstellungen</h3>
          <p style="font-size: 13px; color: var(--secondary-text-color);">
            Spezifische Regelungsparameter, Hysterese und Vorheizzeiten je Raum:
          </p>
          <div style="margin-bottom: 14px;">
            <label style="font-size: 12px; font-weight: 600; color: var(--secondary-text-color);">Raum auswählen:</label>
            <select class="setting-input" id="room-settings-selector" style="width: 100%; margin-top: 4px; padding: 8px;">
              ${this._rooms.map(r => `
                <option value="${r.entity_id}" ${r.entity_id === this._selectedSettingsRoom ? 'selected' : ''}>
                  ${r.name} (${r.entity_id})
                </option>
              `).join('')}
            </select>
          </div>

          ${(() => {
            const currentRoom = this._rooms.find(r => r.entity_id === this._selectedSettingsRoom) || this._rooms[0] || {};
            return `
              <div class="settings-grid">
                <div class="setting-item">
                  <span class="setting-label">🚶 Abwesenheits-Temp (°C)</span>
                  <input type="number" class="setting-input" id="room-setting-away" value="${currentRoom.away_temperature ?? 15.0}" step="0.5" min="10" max="22">
                </div>
                <div class="setting-item">
                  <span class="setting-label">🎯 Regelungstoleranz / Hysterese (°C)</span>
                  <input type="number" class="setting-input" id="room-setting-tolerance" value="${currentRoom.tolerance ?? 0.5}" step="0.1" min="0.2" max="1.5">
                </div>
                <div class="setting-item">
                  <span class="setting-label">⏳ Max. Vorheizzeit (Minuten)</span>
                  <input type="number" class="setting-input" id="room-setting-early-start" value="${currentRoom.early_start_max_minutes ?? 120}" step="15" min="0" max="240">
                </div>
                <div class="setting-item">
                  <span class="setting-label"><ha-icon icon="mdi:window-open-variant" style="--mdc-icon-size: 14px;"></ha-icon> Fenster-Offen Timeout (s)</span>
                  <input type="number" class="setting-input" id="room-setting-win-open" value="${currentRoom.window_open_timeout ?? 30}" step="5" min="5" max="300">
                </div>
                <div class="setting-item">
                  <span class="setting-label">📈 Min. Heizrate (°C/h)</span>
                  <input type="number" class="setting-input" id="room-setting-min-rate" value="${currentRoom.min_heating_rate ?? 0.5}" step="0.1" min="0.1" max="5.0">
                </div>
                <div class="setting-item">
                  <span class="setting-label">📉 Max. Heizrate (°C/h)</span>
                  <input type="number" class="setting-input" id="room-setting-max-rate" value="${currentRoom.max_heating_rate ?? 3.0}" step="0.1" min="0.5" max="10.0">
                </div>
              </div>
            `;
          })()}

          <button type="button" class="btn-save-settings" data-action="save-room-settings" style="margin-top: 14px;">
            💾 Raum-Einstellungen speichern
          </button>
        </div>

        <div class="system-card">
          <h3>🔥 Kessel- & Heißwasser-Vorlauf</h3>
          <table class="system-table">
            <colgroup>
              <col style="width: 44%;">
              <col style="width: 56%;">
            </colgroup>
            <tr>
              <td>Wärmeanforderung gesamt</td>
              <td><strong>${heatingCount} Räume</strong></td>
            </tr>
            <tr>
              <td>Kessel-Status</td>
              <td><strong>${heatingCount > 0 ? '🔥 EIN (Heizbedarf)' : '🟢 STANDBY (Kein Bedarf)'}</strong></td>
            </tr>
            <tr>
              <td>Vorlauftemperatur</td>
              <td><strong>${boilerTemp !== undefined && boilerTemp !== null ? Number(boilerTemp).toFixed(1) + ' °C' : 'Nicht konfiguriert'}</strong></td>
            </tr>
            <tr>
              <td>Heißwasser / Zirkulation</td>
              <td><strong>${boilerActive ? '🔥 Aktiv / Fließend (>= 45°C)' : (boilerTemp !== null && boilerTemp !== undefined ? '🟢 Standby / Kalt (< 45°C)' : '---')}</strong></td>
            </tr>
            <tr>
              <td>Fühler-Zustand</td>
              <td>
                ${boilerSensorAvailable ? '🟢 Online' : '⚠️ Offline / Fallback gepuffert'}
                <div style="font-size: 11px; color: var(--secondary-text-color, #64748b); word-break: break-all; margin-top: 3px;">
                  (${boilerEntity})
                </div>
              </td>
            </tr>
            <tr>
              <td>Brennerschutz-Mindestlaufzeit</td>
              <td>Aktiv (300 Sekunden Mindestlaufzeit)</td>
            </tr>
            <tr>
              <td>Zyklus-Sperre bei Absenkung</td>
              <td>Sofortige Freigabe bei Sollwertsenkung (K-01)</td>
            </tr>
          </table>
        </div>

        <div class="system-card" style="grid-column: 1 / -1;">
          <h3>📋 Raumübersicht & Diagnose</h3>
          <table class="system-table">
            <thead>
              <tr>
                <th>Raum</th>
                <th>Ist-Temp</th>
                <th>Sollwert</th>
                <th>TRV-Ziel</th>
                <th>Fenster</th>
                <th>Komfort</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${this._rooms.map(r => `
                <tr>
                  <td><strong>${r.name}</strong></td>
                  <td>${typeof r.current_temp === 'number' ? r.current_temp.toFixed(1) + ' °C' : '---'}</td>
                  <td>${typeof r.target_temp === 'number' ? r.target_temp.toFixed(1) + ' °C' : 'AUS'}</td>
                  <td>${r.trv_target ? r.trv_target + ' °C' : '---'}</td>
                  <td>${r.window_open ? '🔴 Offen' : '🟢 Zu'}</td>
                  <td>${r.comfort_level || '---'}</td>
                  <td>${r.has_problem ? '⚠️ Störung' : (r.hvac_action === 'heating' ? '🔥 Heizt' : '🟢 Idle')}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    `;
  }

  async embedScheduleCard() {
    const mount = this.shadowRoot.getElementById('schedule-card-mount');
    if (!mount || !this._selectedScheduleRoom) return;

    if (!customElements.get('tadiy-schedule-card')) {
      try {
        const script = document.createElement('script');
        script.type = 'module';
        script.src = '/tadiy/tadiy-schedule-card.js?v=3.1.2';
        document.head.appendChild(script);
        await customElements.whenDefined('tadiy-schedule-card');
      } catch (err) {
        mount.innerHTML = '<div style="color: red; padding: 20px;">Fehler beim Laden des Zeitplan-Editors.</div>';
        return;
      }
    }

    mount.innerHTML = '';
    const card = document.createElement('tadiy-schedule-card');
    card.setConfig({
      entity: this._selectedScheduleRoom,
      initialMode: this._hubMode || 'normal',
    });
    card.hass = this._hass;
    mount.appendChild(card);
  }

  attachEventListeners() {
    // Navigation Tabs
    this.shadowRoot.querySelectorAll('.nav-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const newTab = tab.dataset.tab;
        if (newTab !== this._activeTab) {
          this._activeTab = newTab;
          this.render();
        }
      });
    });

    // Details Accordion State Persistence
    this.shadowRoot.querySelectorAll('details[data-details-id]').forEach(el => {
      el.addEventListener('toggle', () => {
        const id = el.getAttribute('data-details-id');
        if (el.open) {
          this._openDetails.add(id);
        } else {
          this._openDetails.delete(id);
        }
      });
    });

    // Quick Homeoffice Toggle
    const homeofficeBtn = this.shadowRoot.querySelector('[data-action="toggle-homeoffice"]');
    if (homeofficeBtn && this._hubModeEntityId && this._hass) {
      homeofficeBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const targetMode = this._hubMode === 'homeoffice' ? 'normal' : 'homeoffice';
        try {
          await this._hass.callService('select', 'select_option', {
            entity_id: this._hubModeEntityId,
            option: targetMode
          });
          this._hubMode = targetMode;
          this.render();
        } catch (err) {
          console.error('Failed to toggle homeoffice mode:', err);
        }
      });
    }

    // Hub Mode Dropdown Toggle
    const hubBtn = this.shadowRoot.querySelector('[data-action="toggle-hub-dropdown"]');
    const hubDropdown = this.shadowRoot.querySelector('[data-dropdown]');
    if (hubBtn && hubDropdown) {
      hubBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = hubDropdown.classList.contains('open');
        hubDropdown.classList.toggle('open');
        this._hasOpenDropdown = !isOpen;
      });

      const closeDropdown = (e) => {
        if (!hubBtn.contains(e.target) && !hubDropdown.contains(e.target)) {
          hubDropdown.classList.remove('open');
          this._hasOpenDropdown = false;
        }
      };
      document.addEventListener('click', closeDropdown);
    }

    // Hub Mode Select
    this.shadowRoot.querySelectorAll('[data-hub-mode]').forEach(item => {
      item.addEventListener('click', async (e) => {
        e.stopPropagation();
        const mode = item.dataset.hubMode;
        if (mode && this._hubModeEntityId && this._hass) {
          try {
            await this._hass.callService('select', 'select_option', {
              entity_id: this._hubModeEntityId,
              option: mode
            });
            this._hubMode = mode;
            this._hasOpenDropdown = false;
            this.render();
          } catch (err) {
            console.error('Failed to change hub mode:', err);
          }
        }
      });
    });

    // Room Actions: Step Temp
    this.shadowRoot.querySelectorAll('[data-action="temp-step"]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const entityId = btn.dataset.entity;
        const step = parseFloat(btn.dataset.step);
        const room = this._rooms.find(r => r.entity_id === entityId);
        if (room && typeof room.target_temp === 'number' && this._hass) {
          const newTarget = Math.round((room.target_temp + step) * 2) / 2;
          const clamped = Math.min(30.0, Math.max(5.0, newTarget));
          try {
            await this._hass.callService('climate', 'set_temperature', {
              entity_id: entityId,
              temperature: clamped
            });
          } catch (err) {
            console.error('Failed to set temperature:', err);
          }
        }
      });
    });

    // Room Actions: Clear Override
    this.shadowRoot.querySelectorAll('[data-action="clear-override"]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const entityId = btn.dataset.entity;
        if (entityId && this._hass) {
          try {
            await this._hass.callService('tadiy', 'clear_override', {
              entity_id: entityId
            });
          } catch (err) {
            console.error('Failed to clear override:', err);
          }
        }
      });
    });

    // Room Actions: Reset Learning (Feature 6)
    this.shadowRoot.querySelectorAll('[data-action="reset-learning"]').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const roomName = btn.dataset.roomName;
        if (roomName && this._hass) {
          if (!confirm(`Möchtest du die gelernten Heizraten für "${roomName}" wirklich zurücksetzen?`)) {
            return;
          }
          try {
            await this._hass.callService('tadiy', 'reset_learning', {
              room: roomName
            });
          } catch (err) {
            console.error('Failed to reset learning:', err);
          }
        }
      });
    });

    // Room Actions: Open Schedule (Switches to Schedules Tab)
    this.shadowRoot.querySelectorAll('[data-action="open-schedule"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const entityId = btn.dataset.entity;
        this._selectedScheduleRoom = entityId;
        this._activeTab = 'schedules';
        this.render();
      });
    });

    // Schedules Tab: Select Room Pill with dirty changes protection
    this.shadowRoot.querySelectorAll('[data-action="select-schedule-room"]').forEach(pill => {
      pill.addEventListener('click', () => {
        const entityId = pill.dataset.entity;
        if (entityId !== this._selectedScheduleRoom) {
          const scheduleCard = this.shadowRoot.querySelector('tadiy-schedule-card');
          if (scheduleCard && scheduleCard._isDirty) {
            if (!confirm('Du hast ungespeicherte Änderungen am Zeitplan. Möchtest du diese wirklich verwerfen?')) {
              return;
            }
          }
          this._selectedScheduleRoom = entityId;
          this.render();
        }
      });
    });

    // Hub Settings Save Button
    const saveSettingsBtn = this.shadowRoot.querySelector('[data-action="save-hub-settings"]');
    if (saveSettingsBtn) {
      saveSettingsBtn.addEventListener('click', async () => {
        const frostEl = this.shadowRoot.getElementById('setting-frost-temp');
        const boostTempEl = this.shadowRoot.getElementById('setting-boost-temp');
        const boostDurEl = this.shadowRoot.getElementById('setting-boost-duration');
        const winOpenEl = this.shadowRoot.getElementById('setting-win-open');
        const winCloseEl = this.shadowRoot.getElementById('setting-win-close');
        const dontHeatEl = this.shadowRoot.getElementById('setting-dont-heat');

        const serviceData = {};
        if (frostEl && frostEl.value !== '') serviceData.frost_protection_temp = parseFloat(frostEl.value);
        if (boostTempEl && boostTempEl.value !== '') serviceData.boost_temperature = parseFloat(boostTempEl.value);
        if (boostDurEl && boostDurEl.value !== '') serviceData.boost_duration = parseInt(boostDurEl.value);
        if (winOpenEl && winOpenEl.value !== '') serviceData.window_open_timeout = parseInt(winOpenEl.value);
        if (winCloseEl && winCloseEl.value !== '') serviceData.window_close_timeout = parseInt(winCloseEl.value);
        if (dontHeatEl && dontHeatEl.value !== '') serviceData.dont_heat_below_outdoor = parseFloat(dontHeatEl.value);

        try {
          saveSettingsBtn.textContent = '⏳ Wird gespeichert...';
          await this._hass.callService('tadiy', 'set_hub_config', serviceData);
          saveSettingsBtn.textContent = '✅ Gespeichert!';
          setTimeout(() => {
            saveSettingsBtn.textContent = '💾 Einstellungen speichern';
          }, 2000);
        } catch (err) {
          saveSettingsBtn.textContent = '❌ Fehler!';
          console.error('Failed to save hub settings:', err);
          setTimeout(() => {
            saveSettingsBtn.textContent = '💾 Einstellungen speichern';
          }, 3000);
        }
      });
    }
  }
}

if (!customElements.get('tadiy-panel')) {
  customElements.define('tadiy-panel', TaDiyPanel);
}
