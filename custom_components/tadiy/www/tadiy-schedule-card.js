/**
 * TaDIY Schedule Card
 * Modernized Lovelace card for viewing and editing all TaDIY heating schedules per room.
 * Features:
 * - All room modes overview (Normal - Wochentag, Normal - Wochenende, Homeoffice, etc.)
 * - In-line accordion expand/collapse per mode with edit/save/discard
 * - Unsaved changes dirty tracking & warning prompt
 * - Interactive timeline drag handles between blocks (00:00 and 24:00 pinned)
 * - JSON Import & Export for room schedules
 */

class TaDiyScheduleCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = null;
    this._hass = null;

    // Schedules state: map of modeKey -> Array of blocks
    this._modeSchedules = {};
    this._availableModes = [];
    this._loadErrors = {};
    
    // Active editing state
    this._expandedModeKey = null; // null if none expanded
    this._editingBlocks = [];
    this._originalBlocks = [];
    this._isDirty = false;
    this._selectedBlockIndex = null;
    
    this._hasOpenDropdown = false;
    this._isDraggingOrResizing = false;
    this._initialized = false;
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Please define an entity (climate entity)');
    }
    this._config = config;
    this._initialized = false;
  }

  set hass(hass) {
    const wasNull = !this._hass;
    const oldEntity = (this._hass && this._config) ? this._hass.states[this._config.entity] : null;
    const newEntity = (hass && this._config) ? hass.states[this._config.entity] : null;
    this._hass = hass;

    // Initialize on first hass set
    if (wasNull && !this._initialized) {
      this._initialized = true;
      this.loadAvailableModes().then(() => this.loadAllSchedules());
      return;
    }

    if (!this._availableModes.length) {
      this.loadAvailableModes();
      return;
    }

    // NEVER re-render while user is actively editing, has open dropdown, or dragging
    if (this._isDirty || this._hasOpenDropdown || this._isDraggingOrResizing) {
      return;
    }

    // Avoid DOM destruction if climate entity state did not change
    if (oldEntity && newEntity) {
      if (
        oldEntity.state === newEntity.state &&
        oldEntity.last_updated === newEntity.last_updated &&
        oldEntity.attributes.temperature === newEntity.attributes.temperature &&
        oldEntity.attributes.current_temperature === newEntity.attributes.current_temperature
      ) {
        return;
      }
    }

    this.render();
  }

  getModeDefinitions() {
    const defs = [
      { key: 'normal_weekday', mode: 'normal', scheduleType: 'weekday', label: 'Normal - Wochentag', icon: 'mdi:calendar-week' },
      { key: 'normal_weekend', mode: 'normal', scheduleType: 'weekend', label: 'Normal - Wochenende', icon: 'mdi:calendar-weekend' },
      { key: 'homeoffice', mode: 'homeoffice', scheduleType: 'daily', label: 'Homeoffice', icon: 'mdi:desk' }
    ];

    for (const m of this._availableModes) {
      if (['normal', 'homeoffice', 'manual', 'off'].includes(m.toLowerCase())) continue;
      const label = m.charAt(0).toUpperCase() + m.slice(1);
      defs.push({ key: m, mode: m, scheduleType: 'daily', label, icon: 'mdi:calendar-star' });
    }

    return defs;
  }

  async loadAvailableModes() {
    if (!this._hass) return;
    const hubEntity = Object.values(this._hass.states).find(
      entity => entity.entity_id === 'select.tadiy_hub_mode' ||
        (entity.entity_id.startsWith('select.') && entity.entity_id.includes('hub_mode'))
    );

    if (hubEntity && hubEntity.attributes && hubEntity.attributes.options) {
      this._availableModes = hubEntity.attributes.options;
    } else {
      this._availableModes = ['normal', 'homeoffice', 'away', 'manual', 'off'];
    }
  }

  async loadAllSchedules() {
    if (!this._hass || !this._config) return;

    const defs = this.getModeDefinitions();
    for (const def of defs) {
      try {
        const result = await this._hass.callWS({
          type: 'call_service',
          domain: 'tadiy',
          service: 'get_schedule',
          service_data: {
            entity_id: this._config.entity,
            mode: def.mode,
            schedule_type: def.scheduleType,
          },
          return_response: true,
        });

        if (result && result.response && result.response.blocks && result.response.blocks.length > 0) {
          this._modeSchedules[def.key] = JSON.parse(JSON.stringify(result.response.blocks));
          delete this._loadErrors[def.key];
        } else if (!this._modeSchedules[def.key]) {
          this._modeSchedules[def.key] = this.getDefaultSchedule(def.scheduleType);
          delete this._loadErrors[def.key];
        }
      } catch (err) {
        // Fehleranalyse: Bei einem Abruffehler darf ein vorhandener Plan im Cache nicht überschrieben werden,
        // muss aber zwingend in _loadErrors markiert werden, damit kein veralteter Stand gespeichert werden kann.
        console.warn(`Fehler beim Laden des Zeitplans für ${def.key}:`, err);
        this._loadErrors[def.key] = true;
      }
    }

    this.render();
  }

  getDefaultSchedule(scheduleType) {
    if (scheduleType === 'weekday') {
      return [
        { start_time: '00:00', end_time: '06:00', temperature: 18.0 },
        { start_time: '06:00', end_time: '08:00', temperature: 21.0 },
        { start_time: '08:00', end_time: '16:00', temperature: 18.0 },
        { start_time: '16:00', end_time: '22:00', temperature: 21.0 },
        { start_time: '22:00', end_time: '24:00', temperature: 18.0 },
      ];
    } else if (scheduleType === 'weekend') {
      return [
        { start_time: '00:00', end_time: '08:00', temperature: 18.0 },
        { start_time: '08:00', end_time: '23:00', temperature: 21.0 },
        { start_time: '23:00', end_time: '24:00', temperature: 18.0 },
      ];
    } else {
      return [
        { start_time: '00:00', end_time: '08:00', temperature: 18.0 },
        { start_time: '08:00', end_time: '18:00', temperature: 21.0 },
        { start_time: '18:00', end_time: '24:00', temperature: 18.0 },
      ];
    }
  }

  getTemperatureColor(temperature) {
    if (typeof temperature === 'string' || temperature === 0) return '#64748b';
    const t = parseFloat(temperature);
    if (t <= 15.0) return '#4dabf7';
    if (t <= 17.0) return '#22b8cf';
    if (t <= 18.5) return '#20c997';
    if (t <= 20.0) return '#40c057';
    if (t <= 21.5) return '#fab005';
    if (t <= 23.0) return '#fd7e14';
    return '#fa5252';
  }

  formatTemperature(temperature) {
    if (typeof temperature === 'string') return temperature.toUpperCase();
    if (temperature === 0) return 'FROST';
    return `${parseFloat(temperature).toFixed(1)}°`;
  }

  formatTime(time) {
    if (time === '24:00' || time === '23:59') return '24:00';
    return time;
  }

  timeToMinutes(time) {
    if (!time) return 0;
    const [h, m] = time.split(':').map(Number);
    return (h || 0) * 60 + (m || 0);
  }

  minutesToTime(minutes) {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  }

  renderTimeline(blocks, isInteractive = false, modeKey = '') {
    const totalMinutes = 24 * 60;
    let blocksHtml = '';

    blocks.forEach((block, index) => {
      const startM = this.timeToMinutes(block.start_time);
      let endM = this.timeToMinutes(block.end_time);
      if (block.end_time === '24:00' || block.end_time === '23:59' || endM === 0) {
        endM = 24 * 60;
      }

      const duration = Math.max(15, endM - startM);
      const leftPercent = (startM / totalMinutes) * 100;
      const widthPercent = (duration / totalMinutes) * 100;
      const color = this.getTemperatureColor(block.temperature);
      const tempDisplay = this.formatTemperature(block.temperature);
      const isSelected = isInteractive && this._selectedBlockIndex === index;

      blocksHtml += `
        <div class="timeline-block ${isSelected ? 'selected' : ''}"
             style="position: absolute; left: ${leftPercent.toFixed(2)}%; width: ${widthPercent.toFixed(2)}%; background: ${color};"
             data-block-index="${index}"
             title="${tempDisplay} (${this.formatTime(block.start_time)} - ${this.formatTime(block.end_time)})">
          <div class="timeline-content">
            <div class="timeline-temp">${tempDisplay}</div>
            <div class="timeline-time">${this.formatTime(block.start_time)}-${this.formatTime(block.end_time)}</div>
          </div>
        </div>
      `;

      // Render draggable splitter handle between block and next block (NOT after last block)
      if (isInteractive && index < blocks.length - 1) {
        const handleLeftPercent = (endM / totalMinutes) * 100;
        blocksHtml += `
          <div class="boundary-splitter"
               style="left: ${handleLeftPercent.toFixed(2)}%;"
               data-splitter-index="${index}"
               title="Uhrzeitgrenze verschieben (${this.formatTime(block.end_time)})">
            <div class="splitter-grip"></div>
          </div>
        `;
      }
    });

    return `
      <div class="timeline-wrapper">
        <div class="timeline ${isInteractive ? 'interactive' : ''}" data-timeline="${modeKey}">
          ${blocksHtml}
        </div>
        <div class="timeline-labels">
          <span>00:00</span>
          <span>06:00</span>
          <span>12:00</span>
          <span>18:00</span>
          <span>24:00</span>
        </div>
      </div>
    `;
  }

  renderBlockEditor(block, index, totalBlocks) {
    const isSelected = this._selectedBlockIndex === index;
    const startM = this.timeToMinutes(block.start_time);
    const endM = this.timeToMinutes(block.end_time === '24:00' ? '24:00' : block.end_time);
    const durationM = (block.end_time === '24:00' ? 1440 : endM) - startM;
    const durHours = Math.floor(durationM / 60);
    const durMins = durationM % 60;
    const durationText = durMins > 0 ? `${durHours}h ${durMins}m` : `${durHours}h`;
    const color = this.getTemperatureColor(block.temperature);

    const isFirstBlock = index === 0;
    const isLastBlock = index === totalBlocks - 1;

    return `
      <div class="block-editor ${isSelected ? 'selected' : ''}" data-index="${index}">
        <div class="block-header-info">
          <span class="block-color-dot" style="background: ${color};"></span>
          <span class="block-label">#${index + 1}</span>
        </div>

        <div class="block-time-group">
          <!-- Start Time -->
          <div class="input-group">
            <span class="input-label">Start</span>
            <div class="time-badge ${isFirstBlock ? 'fixed' : ''}">
              ${this.formatTime(block.start_time)}
              ${isFirstBlock ? '<span class="lock-icon" title="Fest verankert um 00:00 Uhr">🔒</span>' : ''}
            </div>
          </div>

          <span class="time-separator-arrow">➔</span>

          <!-- End Time -->
          <div class="input-group">
            <span class="input-label">Ende</span>
            ${isLastBlock ? `
              <div class="time-badge fixed">
                24:00
                <span class="lock-icon" title="Fest verankert um 24:00 Uhr">🔒</span>
              </div>
            ` : `
              <div class="time-adjuster">
                <button type="button" class="btn-time-step" data-action="step-end-time" data-index="${index}" data-step="-15" title="-15 Minuten">−15m</button>
                <div class="time-input-select-wrapper">
                  <select class="time-select" data-index="${index}" data-action="change-end-time">
                    ${this.generateEndTimeOptions(index)}
                  </select>
                </div>
                <button type="button" class="btn-time-step" data-action="step-end-time" data-index="${index}" data-step="+15" title="+15 Minuten">+15m</button>
              </div>
            `}
          </div>

          <span class="duration-badge">${durationText}</span>
        </div>

        <!-- Temperature -->
        <div class="input-group temp-input-group">
          <span class="input-label">Temperatur</span>
          <div class="temp-adjuster">
            <button type="button" class="btn-time-step" data-action="step-temp" data-index="${index}" data-step="-0.5" title="-0.5°C">−0.5°</button>
            <select class="temp-select" data-index="${index}" data-action="change-temp">
              ${this.renderTemperatureOptions(block.temperature)}
            </select>
            <button type="button" class="btn-time-step" data-action="step-temp" data-index="${index}" data-step="+0.5" title="+0.5°C">+0.5°</button>
          </div>
        </div>

        <!-- Delete block -->
        <div class="block-actions">
          ${totalBlocks > 1 ? `
            <button type="button" class="btn-delete-block" data-action="delete-block" data-index="${index}" title="Diesen Block löschen">
              ✕
            </button>
          ` : ''}
        </div>
      </div>
    `;
  }

  generateEndTimeOptions(index) {
    const blocks = this._editingBlocks;
    const startM = this.timeToMinutes(blocks[index].start_time);
    const nextEndM = index < blocks.length - 1 ? this.timeToMinutes(blocks[index + 1].end_time) : 1440;
    const currentEndM = this.timeToMinutes(blocks[index].end_time);

    let html = '';
    for (let m = startM + 15; m <= nextEndM - 15; m += 15) {
      const timeStr = this.minutesToTime(m);
      const selected = m === currentEndM ? 'selected' : '';
      html += `<option value="${timeStr}" ${selected}>${timeStr}</option>`;
    }
    return html;
  }

  renderTemperatureOptions(currentTemp) {
    const isOff = typeof currentTemp === 'string' && currentTemp.toLowerCase() === 'off';
    let html = `<option value="off" ${isOff ? 'selected' : ''}>AUS</option>`;
    for (let t = 5.0; t <= 30.0; t += 0.5) {
      const val = t.toFixed(1);
      const selected = !isOff && Math.abs(parseFloat(currentTemp) - t) < 0.01 ? 'selected' : '';
      html += `<option value="${val}" ${selected}>${val}°C</option>`;
    }
    return html;
  }

  render() {
    if (!this._hass || !this._config) return;

    const entity = this._hass.states[this._config.entity];
    if (!entity) {
      this.shadowRoot.innerHTML = '<ha-card style="padding: 16px;">Raum-Klima-Entität nicht gefunden</ha-card>';
      return;
    }

    const roomName = entity.attributes.friendly_name || 'Raum';
    const defs = this.getModeDefinitions();

    // Check active mode for room
    const currentMode = entity.attributes.mode || entity.state;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          --tadiy-card-bg: var(--card-background-color, #ffffff);
          --tadiy-text-primary: var(--primary-text-color, #1e293b);
          --tadiy-text-secondary: var(--secondary-text-color, #64748b);
          --tadiy-divider: var(--divider-color, #e2e8f0);
          --tadiy-primary: var(--primary-color, #0284c7);
        }
        ha-card {
          padding: 24px;
          border-radius: 16px;
          background: var(--tadiy-card-bg);
          box-shadow: var(--ha-card-box-shadow, 0 2px 10px rgba(0,0,0,0.06));
          color: var(--tadiy-text-primary);
          box-sizing: border-box;
        }
        .card-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 12px;
          margin-bottom: 20px;
          padding-bottom: 14px;
          border-bottom: 1px solid var(--tadiy-divider);
        }
        .header-title-group {
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .header-title {
          font-size: 20px;
          font-weight: 700;
        }
        .modes-count-badge {
          font-size: 12px;
          font-weight: 600;
          padding: 4px 10px;
          background: rgba(2, 132, 199, 0.1);
          color: var(--tadiy-primary);
          border-radius: 12px;
        }
        .header-actions {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        /* Mode Cards Accordion */
        .modes-accordion {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .mode-card {
          background: var(--card-background-color, #ffffff);
          border: 1px solid var(--tadiy-divider);
          border-radius: 12px;
          padding: 16px;
          transition: all 0.2s ease-in-out;
          box-shadow: 0 1px 3px rgba(0,0,0,0.03);
        }
        .mode-card.expanded {
          border-color: var(--tadiy-primary);
          box-shadow: 0 4px 14px rgba(2, 132, 199, 0.12);
        }
        .mode-card-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 12px;
          user-select: none;
        }
        .mode-title-info {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .mode-name {
          font-size: 16px;
          font-weight: 600;
        }
        .active-badge {
          font-size: 11px;
          font-weight: 700;
          padding: 2px 8px;
          border-radius: 10px;
          background: #dcfce7;
          color: #15803d;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        /* Timeline Styles */
        .timeline-wrapper {
          position: relative;
          margin-bottom: 8px;
        }
        .timeline {
          position: relative;
          width: 100%;
          height: 52px;
          border-radius: 8px;
          overflow: hidden;
          background: #f1f5f9;
          box-shadow: inset 0 1px 3px rgba(0,0,0,0.12);
          box-sizing: border-box;
        }
        .timeline.interactive {
          height: 64px;
        }
        .timeline-block {
          display: flex;
          align-items: center;
          justify-content: center;
          color: #ffffff;
          font-weight: 600;
          position: absolute;
          top: 0;
          bottom: 0;
          box-sizing: border-box;
          user-select: none;
          cursor: pointer;
          transition: filter 0.15s;
          border-right: 1px solid rgba(255,255,255,0.25);
        }
        .timeline-block:hover {
          filter: brightness(1.08);
        }
        .timeline-block.selected {
          box-shadow: inset 0 0 0 3px #ffffff, 0 0 0 2px var(--tadiy-primary);
          z-index: 5;
        }
        .timeline-content {
          text-align: center;
          padding: 2px 4px;
          pointer-events: none;
          text-shadow: 0 1px 2px rgba(0,0,0,0.5);
          overflow: hidden;
          white-space: nowrap;
          text-overflow: ellipsis;
        }
        .timeline-temp {
          font-size: 13px;
          font-weight: 700;
        }
        .timeline-time {
          font-size: 9px;
          opacity: 0.95;
        }
        .timeline-labels {
          display: flex;
          justify-content: space-between;
          font-size: 11px;
          color: var(--tadiy-text-secondary);
          padding: 4px 2px 0 2px;
        }

        /* Boundary Splitters (Drag handles) */
        .boundary-splitter {
          position: absolute;
          top: 0;
          bottom: 0;
          width: 20px;
          margin-left: -10px;
          cursor: ew-resize;
          z-index: 10;
          display: flex;
          align-items: center;
          justify-content: center;
          touch-action: none;
        }
        .splitter-grip {
          width: 4px;
          height: 28px;
          background: #ffffff;
          border-radius: 2px;
          box-shadow: 0 1px 4px rgba(0,0,0,0.4);
          transition: transform 0.15s, background 0.15s;
        }
        .boundary-splitter:hover .splitter-grip,
        .boundary-splitter.active .splitter-grip {
          background: var(--tadiy-primary);
          transform: scaleY(1.2);
          box-shadow: 0 0 8px rgba(2, 132, 199, 0.6);
        }

        /* Block Editor List */
        .editor-container {
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px dashed var(--tadiy-divider);
          display: flex;
          flex-direction: column;
          gap: 10px;
        }
        .block-editor {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 12px;
          padding: 10px 14px;
          background: var(--card-background-color, rgba(255, 255, 255, 0.04));
          border: 1px solid var(--tadiy-divider);
          border-radius: 8px;
          transition: all 0.15s ease-in-out;
        }
        .block-editor:hover {
          background: rgba(255, 255, 255, 0.08);
        }
        .block-editor.selected {
          border-color: var(--tadiy-primary);
          background: rgba(2, 132, 199, 0.12);
          box-shadow: 0 2px 8px rgba(2, 132, 199, 0.15);
        }
        .block-header-info {
          display: flex;
          align-items: center;
          gap: 8px;
          font-weight: 700;
          font-size: 14px;
          min-width: 45px;
        }
        .block-color-dot {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          border: 1px solid rgba(0,0,0,0.15);
        }
        .block-time-group {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-wrap: wrap;
        }
        .input-group {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }
        .input-label {
          font-size: 10px;
          font-weight: 600;
          text-transform: uppercase;
          color: var(--tadiy-text-secondary);
        }
        .time-badge {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 5px 10px;
          background: rgba(255, 255, 255, 0.08);
          border: 1px solid var(--tadiy-divider);
          border-radius: 6px;
          font-size: 13px;
          font-weight: 600;
          font-family: monospace;
          color: var(--tadiy-text-primary);
        }
        .time-badge.fixed {
          background: #cbd5e1;
          color: #334155;
        }
        .lock-icon {
          font-size: 11px;
          opacity: 0.8;
        }
        .time-separator-arrow {
          font-size: 14px;
          color: var(--tadiy-text-secondary);
          margin-top: 14px;
        }
        .duration-badge {
          display: inline-flex;
          align-items: center;
          padding: 5px 8px;
          border-radius: 6px;
          background: #e2e8f0;
          color: #475569;
          font-size: 11px;
          font-weight: 600;
          margin-top: 14px;
        }
        .time-adjuster, .temp-adjuster {
          display: flex;
          align-items: center;
          gap: 4px;
        }
        .btn-time-step {
          padding: 4px 6px;
          border: 1px solid var(--tadiy-divider);
          background: #ffffff;
          border-radius: 4px;
          font-size: 11px;
          font-weight: 700;
          cursor: pointer;
          color: var(--tadiy-text-primary);
        }
        .btn-time-step:hover {
          background: var(--tadiy-primary);
          color: #ffffff;
          border-color: var(--tadiy-primary);
        }
        .time-select, .temp-select {
          padding: 5px 8px;
          border: 1px solid var(--tadiy-divider);
          border-radius: 6px;
          background: #ffffff;
          font-size: 13px;
          font-weight: 600;
          color: var(--tadiy-text-primary);
          cursor: pointer;
        }
        .btn-delete-block {
          background: transparent;
          border: none;
          color: #ef4444;
          font-size: 16px;
          cursor: pointer;
          padding: 4px 8px;
          border-radius: 4px;
        }
        .btn-delete-block:hover {
          background: #fee2e2;
        }

        /* Buttons & Actions */
        .editor-actions {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-wrap: wrap;
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid var(--tadiy-divider);
        }
        .btn {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 8px 14px;
          border-radius: 8px;
          font-size: 13px;
          font-weight: 600;
          cursor: pointer;
          border: 1px solid transparent;
          transition: all 0.15s ease-in-out;
        }
        .btn-sm {
          padding: 5px 10px;
          font-size: 12px;
          border-radius: 6px;
        }
        .btn-primary {
          background: var(--tadiy-primary);
          color: #ffffff;
        }
        .btn-primary:hover {
          background: #0369a1;
        }
        .btn-secondary {
          background: #f1f5f9;
          color: var(--tadiy-text-primary);
          border-color: var(--tadiy-divider);
        }
        .btn-secondary:hover {
          background: #e2e8f0;
        }
        .btn-success {
          background: #10b981;
          color: #ffffff;
        }
        .btn-success:hover {
          background: #059669;
        }
        .btn-warning {
          background: #f59e0b;
          color: #ffffff;
        }
        .btn-warning:hover {
          background: #d97706;
        }
        .btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .notification-banner {
          margin-top: 12px;
          padding: 10px 14px;
          border-radius: 8px;
          font-size: 13px;
          font-weight: 600;
          display: none;
        }
        .notification-banner.show { display: block; }
        .notification-banner.success { background: #dcfce7; color: #15803d; }
        .notification-banner.error { background: #fee2e2; color: #b91c1c; }
      </style>

      <ha-card>
        <div class="card-header">
          <div class="header-title-group">
            <span class="header-title">📅 ${roomName} - Zeitpläne</span>
            <span class="modes-count-badge">${defs.length} Profile</span>
          </div>
          <div class="header-actions">
            <button class="btn btn-sm btn-secondary" data-action="export-schedules" title="Alle Zeitpläne dieses Raumes als JSON herunterladen">
              📤 Exportieren
            </button>
            <label class="btn btn-sm btn-secondary" title="Zeitpläne aus JSON-Datei importieren" style="cursor: pointer; margin: 0;">
              📥 Importieren
              <input type="file" id="schedule-import-file" accept=".json" style="display: none;">
            </label>
          </div>
        </div>

        <div id="card-notification" class="notification-banner"></div>

        <div class="modes-accordion">
          ${defs.map(def => {
            const isExpanded = this._expandedModeKey === def.key;
            const blocks = isExpanded ? this._editingBlocks : (this._modeSchedules[def.key] || this.getDefaultSchedule(def.scheduleType));
            const isActive = currentMode && currentMode.toLowerCase().includes(def.mode.toLowerCase());

            return `
              <div class="mode-card ${isExpanded ? 'expanded' : ''}" data-mode-key="${def.key}">
                <div class="mode-card-header">
                  <div class="mode-title-info">
                    <span class="mode-name">${def.label}</span>
                    ${isActive ? '<span class="active-badge">AKTIV</span>' : ''}
                    ${isExpanded && this._isDirty ? '<span style="font-size: 11px; color: #f59e0b; font-weight: 700;">(ungespeichert)</span>' : ''}
                  </div>
                  <div>
                    ${isExpanded ? `
                      <button class="btn btn-sm btn-warning" data-action="collapse-mode" data-mode-key="${def.key}">
                        ▲ Einklappen
                      </button>
                    ` : `
                      <button class="btn btn-sm btn-primary" data-action="edit-mode" data-mode-key="${def.key}">
                        ✏️ Bearbeiten
                      </button>
                    `}
                  </div>
                </div>

                <div class="mode-card-body">
                  ${this.renderTimeline(blocks, isExpanded, def.key)}

                  ${isExpanded ? `
                    <div class="editor-container">
                      ${blocks.map((block, idx) => this.renderBlockEditor(block, idx, blocks.length)).join('')}

                      <div class="editor-actions">
                        <button class="btn btn-primary" data-action="save-schedule" data-mode-key="${def.key}">
                          💾 Zeitplan speichern
                        </button>
                        <button class="btn btn-secondary" data-action="discard-changes" data-mode-key="${def.key}">
                          ✕ Verwerfen
                        </button>
                        <button class="btn btn-success" data-action="add-block" data-mode-key="${def.key}">
                          ➕ Block hinzufügen
                        </button>
                        <button class="btn btn-secondary" data-action="reset-defaults" data-mode-key="${def.key}">
                          ↺ Standard wiederherstellen
                        </button>
                        <button class="btn btn-secondary" data-action="revert-original" data-mode-key="${def.key}" title="Verwirft ungespeicherte Änderungen und stellt den Stand vor Bearbeitung wieder her">
                          ↺ Entwurf zurücksetzen
                        </button>
                      </div>
                    </div>
                  ` : ''}
                </div>
              </div>
            `;
          }).join('')}
        </div>
      </ha-card>
    `;

    this.attachEventListeners();
  }

  attachEventListeners() {
    const root = this.shadowRoot;

    // Export button
    const exportBtn = root.querySelector('[data-action="export-schedules"]');
    if (exportBtn) {
      exportBtn.addEventListener('click', () => this.exportSchedules());
    }

    // Import file input
    const importInput = root.getElementById('schedule-import-file');
    if (importInput) {
      importInput.addEventListener('change', (e) => this.importSchedules(e));
    }

    // Edit mode buttons
    root.querySelectorAll('[data-action="edit-mode"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const modeKey = btn.dataset.modeKey;
        this.openModeEditor(modeKey);
      });
    });

    // Collapse mode button
    root.querySelectorAll('[data-action="collapse-mode"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const modeKey = btn.dataset.modeKey;
        this.closeModeEditor(modeKey);
      });
    });

    // Save schedule button
    root.querySelectorAll('[data-action="save-schedule"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const modeKey = btn.dataset.modeKey;
        this.saveCurrentSchedule(modeKey);
      });
    });

    // Discard changes button
    root.querySelectorAll('[data-action="discard-changes"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const modeKey = btn.dataset.modeKey;
        this.discardChanges(modeKey);
      });
    });

    // Add block button
    root.querySelectorAll('[data-action="add-block"]').forEach(btn => {
      btn.addEventListener('click', () => this.addBlock());
    });

    // Reset defaults button
    root.querySelectorAll('[data-action="reset-defaults"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const modeKey = btn.dataset.modeKey;
        this.resetToDefaults(modeKey);
      });
    });

    // Revert to original state button (Feature 2)
    root.querySelectorAll('[data-action="revert-original"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const modeKey = btn.dataset.modeKey;
        this.revertOriginal(modeKey);
      });
    });

    // Step end time buttons
    root.querySelectorAll('[data-action="step-end-time"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const index = parseInt(btn.dataset.index);
        const step = parseInt(btn.dataset.step);
        this.stepBlockEndTime(index, step);
      });
    });

    // Change end time select
    root.querySelectorAll('[data-action="change-end-time"]').forEach(sel => {
      sel.addEventListener('change', (e) => {
        const index = parseInt(sel.dataset.index);
        const newEndTime = sel.value;
        this.updateBlockEndTime(index, newEndTime);
      });
    });

    // Change temperature select
    root.querySelectorAll('[data-action="change-temp"]').forEach(sel => {
      sel.addEventListener('change', (e) => {
        const index = parseInt(sel.dataset.index);
        const val = sel.value === 'off' ? 'off' : parseFloat(sel.value);
        this._editingBlocks[index].temperature = val;
        this._isDirty = true;
        this.render();
      });
    });

    // Step temperature buttons
    root.querySelectorAll('[data-action="step-temp"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const index = parseInt(btn.dataset.index);
        const step = parseFloat(btn.dataset.step);
        this.stepBlockTemperature(index, step);
      });
    });

    // Delete block buttons
    root.querySelectorAll('[data-action="delete-block"]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const index = parseInt(btn.dataset.index);
        this.deleteBlock(index);
      });
    });

    // Attach boundary splitter dragging
    this.attachSplitterDragHandlers();
  }

  attachSplitterDragHandlers() {
    const root = this.shadowRoot;
    const splitters = root.querySelectorAll('.boundary-splitter');
    const timeline = root.querySelector('.timeline.interactive');
    if (!timeline || !splitters.length) return;

    splitters.forEach(splitter => {
      const onStart = (e) => {
        e.preventDefault();
        e.stopPropagation();
        this._isDraggingOrResizing = true;
        splitter.classList.add('active');

        const index = parseInt(splitter.dataset.splitterIndex);
        const timelineRect = timeline.getBoundingClientRect();
        const startBlock = this._editingBlocks[index];
        const nextBlock = this._editingBlocks[index + 1];

        const minBound = this.timeToMinutes(startBlock.start_time) + 15;
        const maxBound = this.timeToMinutes(nextBlock.end_time) - 15;

        const onMove = (moveEvt) => {
          const clientX = moveEvt.touches ? moveEvt.touches[0].clientX : moveEvt.clientX;
          const relativeX = clientX - timelineRect.left;
          const percent = Math.max(0, Math.min(1, relativeX / timelineRect.width));
          let targetMinutes = Math.round((percent * 1440) / 15) * 15;
          targetMinutes = Math.max(minBound, Math.min(maxBound, targetMinutes));

          const newTime = this.minutesToTime(targetMinutes);
          if (startBlock.end_time !== newTime) {
            startBlock.end_time = newTime;
            nextBlock.start_time = newTime;
            this._isDirty = true;

            // Live visual update without tearing down DOM
            const startM = this.timeToMinutes(startBlock.start_time);
            const midM = targetMinutes;
            const endM = this.timeToMinutes(nextBlock.end_time === '24:00' ? '24:00' : nextBlock.end_time);

            const block0El = timeline.querySelector(`.timeline-block[data-block-index="${index}"]`);
            const block1El = timeline.querySelector(`.timeline-block[data-block-index="${index + 1}"]`);
            if (block0El && block1El) {
              const dur0 = midM - startM;
              const dur1 = (nextBlock.end_time === '24:00' ? 1440 : endM) - midM;
              block0El.style.width = `${((dur0 / 1440) * 100).toFixed(2)}%`;
              block1El.style.left = `${((midM / 1440) * 100).toFixed(2)}%`;
              block1El.style.width = `${((dur1 / 1440) * 100).toFixed(2)}%`;
              splitter.style.left = `${((midM / 1440) * 100).toFixed(2)}%`;
            }
          }
        };

        const onEnd = () => {
          this._isDraggingOrResizing = false;
          splitter.classList.remove('active');
          window.removeEventListener('mousemove', onMove);
          window.removeEventListener('mouseup', onEnd);
          window.removeEventListener('touchmove', onMove);
          window.removeEventListener('touchend', onEnd);
          window.removeEventListener('touchcancel', onEnd);
          this.render();
        };

        window.addEventListener('mousemove', onMove);
        window.addEventListener('mouseup', onEnd);
        window.addEventListener('touchmove', onMove);
        window.addEventListener('touchend', onEnd);
        window.addEventListener('touchcancel', onEnd);
      };

      splitter.addEventListener('mousedown', onStart);
      splitter.addEventListener('touchstart', onStart, { passive: false });
    });
  }

  openModeEditor(modeKey) {
    if (this._expandedModeKey && this._isDirty) {
      if (!confirm('Du hast ungespeicherte Änderungen am Zeitplan. Möchtest du diese wirklich verwerfen?')) {
        return;
      }
    }

    if (this._loadErrors && this._loadErrors[modeKey]) {
      this.showNotification('Achtung: Zeitplan konnte nicht vom Server geladen werden. Speichern ist gesperrt.', true);
    }

    const defs = this.getModeDefinitions();
    const def = defs.find(d => d.key === modeKey);
    if (!def) return;

    this._expandedModeKey = modeKey;
    const blocks = this._modeSchedules[modeKey] || this.getDefaultSchedule(def.scheduleType);
    this._editingBlocks = JSON.parse(JSON.stringify(blocks));
    this._originalBlocks = JSON.parse(JSON.stringify(blocks));
    this._isDirty = false;
    this.render();
  }

  closeModeEditor(modeKey) {
    if (this._isDirty) {
      if (!confirm('Du hast ungespeicherte Änderungen am Zeitplan. Möchtest du diese wirklich verwerfen?')) {
        return;
      }
    }
    this._expandedModeKey = null;
    this._editingBlocks = [];
    this._originalBlocks = [];
    this._isDirty = false;
    this.render();
  }

  discardChanges(modeKey) {
    if (this._isDirty) {
      if (!confirm('Möchtest du alle Änderungen an diesem Zeitplan wirklich verwerfen?')) {
        return;
      }
    }
    this._expandedModeKey = null;
    this._editingBlocks = [];
    this._originalBlocks = [];
    this._isDirty = false;
    this.render();
  }

  revertOriginal(modeKey) {
    if (this._originalBlocks && this._originalBlocks.length > 0) {
      this._editingBlocks = JSON.parse(JSON.stringify(this._originalBlocks));
      this._isDirty = false;
      this.render();
      this.showNotification('Entwurf zurückgesetzt. Stand vor Bearbeitung wiederhergestellt.');
    }
  }

  stepBlockEndTime(index, stepMinutes) {
    const blocks = this._editingBlocks;
    const currentM = this.timeToMinutes(blocks[index].end_time);
    const startM = this.timeToMinutes(blocks[index].start_time);
    const nextEndM = index < blocks.length - 1 ? this.timeToMinutes(blocks[index + 1].end_time) : 1440;

    let targetM = currentM + stepMinutes;
    targetM = Math.max(startM + 15, Math.min(nextEndM - 15, targetM));

    if (targetM === currentM) return;

    const newTime = this.minutesToTime(targetM);
    blocks[index].end_time = newTime;
    if (index < blocks.length - 1) {
      blocks[index + 1].start_time = newTime;
    }
    this._isDirty = true;
    this.render();
  }

  stepBlockTemperature(index, step) {
    const blocks = this._editingBlocks;
    const current = blocks[index].temperature;
    let newTemp;

    if (current === 'off' || typeof current === 'string') {
      newTemp = step > 0 ? 5.0 : 'off';
    } else {
      let t = Math.round((parseFloat(current) + step) * 10) / 10;
      if (t < 5.0) {
        newTemp = 'off';
      } else if (t > 30.0) {
        newTemp = 30.0;
      } else {
        newTemp = t;
      }
    }

    blocks[index].temperature = newTemp;
    this._isDirty = true;
    this.render();
  }

  updateBlockEndTime(index, newTime) {
    const blocks = this._editingBlocks;
    blocks[index].end_time = newTime;
    if (index < blocks.length - 1) {
      blocks[index + 1].start_time = newTime;
    }
    this._isDirty = true;
    this.render();
  }

  addBlock() {
    const blocks = this._editingBlocks;
    // Find longest block with at least 30 minutes duration
    let longestIdx = 0;
    let maxDur = 0;
    blocks.forEach((b, i) => {
      const dur = this.timeToMinutes(b.end_time === '24:00' ? '24:00' : b.end_time) - this.timeToMinutes(b.start_time);
      if (dur > maxDur) {
        maxDur = dur;
        longestIdx = i;
      }
    });

    if (maxDur < 30) {
      this.showNotification('Kein Block mit mindestens 30 Minuten verfügbar zum Aufteilen.', true);
      return;
    }

    const target = blocks[longestIdx];
    const startM = this.timeToMinutes(target.start_time);
    const endM = this.timeToMinutes(target.end_time === '24:00' ? '24:00' : target.end_time);
    const midM = Math.round((startM + (endM - startM) / 2) / 15) * 15;
    const splitTime = this.minutesToTime(midM);

    const oldEndTime = target.end_time;
    target.end_time = splitTime;

    const newBlock = {
      start_time: splitTime,
      end_time: oldEndTime,
      temperature: target.temperature,
    };

    blocks.splice(longestIdx + 1, 0, newBlock);
    this._isDirty = true;
    this.render();
  }

  deleteBlock(index) {
    const blocks = this._editingBlocks;
    if (blocks.length <= 1) return;

    if (index === 0) {
      // Deleting first block: second block absorbs it and starts at 00:00
      blocks[1].start_time = '00:00';
      blocks.splice(0, 1);
    } else {
      // Previous block expands to this block's end_time
      blocks[index - 1].end_time = blocks[index].end_time;
      blocks.splice(index, 1);
    }

    this._isDirty = true;
    this.render();
  }

  resetToDefaults(modeKey) {
    const defs = this.getModeDefinitions();
    const def = defs.find(d => d.key === modeKey);
    if (!def) return;
    this._editingBlocks = this.getDefaultSchedule(def.scheduleType);
    this._isDirty = true;
    this.render();
  }

  _parseMinutes(timeStr, isEnd = false) {
    if (typeof timeStr !== 'string') return null;
    const match = timeStr.trim().match(/^(\d{1,2}):(\d{2})$/);
    if (!match) return null;
    const h = parseInt(match[1], 10);
    const m = parseInt(match[2], 10);
    if (m < 0 || m > 59) return null;
    if (isEnd && h === 24 && m === 0) return 1440;
    if (h < 0 || h > 23) return null;
    return h * 60 + m;
  }

  _isValidTemp(val) {
    if (val === null || val === undefined || typeof val === 'boolean' || val === '') {
      return false;
    }
    if (typeof val === 'number') {
      return Number.isFinite(val) && val >= 5.0 && val <= 30.0;
    }
    if (typeof val === 'string') {
      const s = val.trim().toLowerCase();
      if (s === 'off') return true;
      // Fehleranalyse: Number("0x14") akzeptiert Hex-Strings; Number([20]) akzeptiert Arrays.
      // Lösung: Strikte Dezimalprüfung per Regex (/^\d+(\.\d+)?$/) und Ausschluss von Nicht-Primitiven.
      if (/^\d+(\.\d+)?$/.test(s)) {
        const num = parseFloat(s);
        return Number.isFinite(num) && num >= 5.0 && num <= 30.0;
      }
      return false;
    }
    return false;
  }

  validateScheduleBlocks(blocks) {
    // Fehleranalyse: Vorherige Prüfung warf bei blocks[0] === null einen TypeError vor der Block-Schleife.
    // Lösung: Vorab alle Elemente auf valides Objekt prüfen vor dem Zugriff auf .start_time / .end_time.
    if (!Array.isArray(blocks) || blocks.length === 0) {
      return 'Mindestens ein Block ist erforderlich';
    }

    for (let i = 0; i < blocks.length; i++) {
      if (!blocks[i] || typeof blocks[i] !== 'object' || Array.isArray(blocks[i])) {
        return `Block #${i + 1} ist ungültig (kein Objekt)`;
      }
    }

    const firstStart = this._parseMinutes(blocks[0].start_time, false);
    if (firstStart !== 0) {
      return 'Erster Block muss um 00:00 beginnen';
    }

    const lastEnd = this._parseMinutes(blocks[blocks.length - 1].end_time, true);
    if (lastEnd !== 1440 && lastEnd !== 1439) {
      return 'Letzter Block muss um 24:00 enden';
    }

    let prevEnd = 0;
    for (let i = 0; i < blocks.length; i++) {
      const b = blocks[i];

      const startMin = this._parseMinutes(b.start_time, false);
      const endMin = this._parseMinutes(b.end_time, true);

      if (startMin === null) {
        return `Block #${i + 1}: Ungültige Startzeit "${b.start_time}"`;
      }
      if (endMin === null) {
        return `Block #${i + 1}: Ungültige Endzeit "${b.end_time}"`;
      }
      if (startMin >= endMin) {
        return `Block #${i + 1}: Startzeit (${b.start_time}) muss vor Endzeit (${b.end_time}) liegen`;
      }
      if (i > 0 && startMin !== prevEnd) {
        return `Block #${i + 1}: Zeitlücke oder Überlappung bei ${b.start_time} (vorheriger Block endete bei ${blocks[i - 1].end_time})`;
      }
      if (!this._isValidTemp(b.temperature)) {
        return `Block #${i + 1}: Ungültige Temperatur "${b.temperature}" (zulässig: 5.0°C–30.0°C oder "AUS")`;
      }
      prevEnd = endMin;
    }
    return null;
  }

  async saveCurrentSchedule(modeKey) {
    const defs = this.getModeDefinitions();
    const def = defs.find(d => d.key === modeKey);
    if (!def || !this._hass) return;

    if (this._loadErrors && this._loadErrors[modeKey]) {
      this.showNotification('Fehler: Zeitplan konnte zuvor nicht geladen werden (veralteter Stand). Speichern zum Schutz vor Überschreiben gesperrt.', true);
      return;
    }

    const blocks = this._editingBlocks;
    const valError = this.validateScheduleBlocks(blocks);
    if (valError) {
      this.showNotification(`Fehler: ${valError}.`, true);
      return;
    }

    try {
      await this._hass.callService('tadiy', 'set_schedule', {
        entity_id: this._config.entity,
        mode: def.mode,
        schedule_type: def.scheduleType,
        blocks: blocks,
      });

      this._modeSchedules[modeKey] = JSON.parse(JSON.stringify(blocks));
      this._originalBlocks = JSON.parse(JSON.stringify(blocks));
      this._isDirty = false;
      this.showNotification('✅ Zeitplan erfolgreich gespeichert!', false);

      setTimeout(() => {
        this._expandedModeKey = null;
        this.render();
      }, 1200);
    } catch (err) {
      console.error('Failed to save schedule:', err);
      this.showNotification('Fehler beim Speichern: ' + (err.message || err), true);
    }
  }

  exportSchedules() {
    const entity = this._hass?.states[this._config?.entity];
    const roomName = entity?.attributes?.friendly_name || 'raum';

    const loadErrorKeys = Object.keys(this._loadErrors || {});
    if (loadErrorKeys.length > 0) {
      this.showNotification(`⚠️ Warnung: Nicht geladene Pläne (${loadErrorKeys.join(', ')}) wurden vom Export ausgenommen.`, true);
    }

    const exportSchedules = {};
    for (const [k, v] of Object.entries(this._modeSchedules)) {
      if (!this._loadErrors || !this._loadErrors[k]) {
        exportSchedules[k] = v;
      }
    }

    const exportData = {
      version: '3.1.2',
      exported_at: new Date().toISOString(),
      room_entity: this._config.entity,
      room_name: roomName,
      schedules: exportSchedules,
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tadiy_zeitplaene_${roomName.toLowerCase().replace(/[^a-z0-9]/g, '_')}.json`;
    a.click();
    URL.revokeObjectURL(url);
    this.showNotification('📤 Zeitpläne erfolgreich exportiert!', false);
  }

  async importSchedules(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    // PLAN-04: Ungespeicherte Änderungen beim Import schützen
    if (this._isDirty) {
      if (!confirm('Du hast ungespeicherte Änderungen im Editor. Wenn du fortfährst, werden diese verworfen. Möchtest du wirklich importieren?')) {
        event.target.value = '';
        return;
      }
    }

    try {
      const text = await file.text();
      let data;
      try {
        data = JSON.parse(text);
      } catch (jsonErr) {
        throw new Error('Datei enthält kein valides JSON: ' + jsonErr.message);
      }

      if (!data.schedules || typeof data.schedules !== 'object') {
        throw new Error('Ungültiges Format: "schedules" Objekt fehlt.');
      }

      const defs = this.getModeDefinitions();
      const validModesToImport = [];

      // Fehleranalyse: if (data.schedules[def.key]) übersprang falsy Werte wie null oder [] stillschweigend.
      // Lösung: Prüfe jeden im schedules-Objekt übergebenen Schlüssel. Ist ein bekannter Modus vorhanden,
      // MUSS er ein gültiges Block-Array sein, andernfalls bricht der gesamte Import vorab ab (null Schreibaufrufe).
      const scheduleKeys = Object.keys(data.schedules);
      if (scheduleKeys.length === 0) {
        throw new Error('Datei enthält ein leeres "schedules"-Objekt.');
      }

      for (const key of scheduleKeys) {
        const def = defs.find(d => d.key === key);
        if (!def) {
          throw new Error(`Unbekannter Modus "${key}" in Importdatei.`);
        }
        const blocks = data.schedules[key];
        const valError = this.validateScheduleBlocks(blocks);
        if (valError) {
          throw new Error(`Modus "${def.label}": ${valError} (keine Pläne übernommen)`);
        }
        validModesToImport.push({ def, blocks });
      }

      if (validModesToImport.length === 0) {
        throw new Error('Keine passenden Zeitpläne für diesen Raum in der Datei gefunden.');
      }

      const appliedModes = [];
      try {
        for (const item of validModesToImport) {
          await this._hass.callService('tadiy', 'set_schedule', {
            entity_id: this._config.entity,
            mode: item.def.mode,
            schedule_type: item.def.scheduleType,
            blocks: item.blocks,
          });
          this._modeSchedules[item.def.key] = item.blocks;
          if (this._loadErrors) {
            delete this._loadErrors[item.def.key];
          }
          appliedModes.push(item.def.label);
        }

        this._expandedModeKey = null;
        this._isDirty = false;
        this.render();
        this.showNotification(`✅ ${appliedModes.length} Zeitpläne erfolgreich importiert: ${appliedModes.join(', ')}`, false);
      } catch (writeErr) {
        // Fehleranalyse: Wenn ein Service-Aufruf während des Imports scheitert, muss dem Benutzer exakt mitgeteilt
        // werden, welche Modi bereits wirksam gespeichert wurden und welcher Modus gescheitert ist.
        this.render();
        const appliedInfo = appliedModes.length > 0 
          ? ` Bereits erfolgreich übernommen: ${appliedModes.join(', ')}.` 
          : ' Es wurden noch keine Modi übernommen.';
        throw new Error(`Schreibfehler bei Modus "${validModesToImport[appliedModes.length]?.def?.label || 'unbekannt'}": ${writeErr.message || writeErr}.${appliedInfo}`);
      }
    } catch (err) {
      console.error('Import failed:', err);
      this.showNotification('Import fehlgeschlagen: ' + (err.message || err), true);
    } finally {
      event.target.value = '';
    }
  }

  showNotification(msg, isError = false) {
    const banner = this.shadowRoot.getElementById('card-notification');
    if (banner) {
      banner.textContent = msg;
      banner.className = `notification-banner show ${isError ? 'error' : 'success'}`;
      setTimeout(() => {
        banner.className = 'notification-banner';
      }, 4000);
    }
  }
}

if (!customElements.get('tadiy-schedule-card')) {
  customElements.define('tadiy-schedule-card', TaDiyScheduleCard);
}
