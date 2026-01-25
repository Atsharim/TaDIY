/**
 * TaDIY Schedule Card
 * Custom Lovelace card for editing TaDIY heating schedules
 */

class TaDiyScheduleCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = null;
    this._hass = null;
    this._editingBlocks = [];
    this._selectedMode = null; // Start with no mode selected
    this._selectedScheduleType = 'weekday';
    this._isEditing = false;
    this._availableModes = [];
    this._selectedBlockIndex = null; // Track selected block for keyboard operations
    this._renderDebounce = null; // Debounce timer for rendering
    this._modeExpanded = false; // Track if mode is expanded to show timeline
    this._hasOpenDropdown = false; // Track if any dropdown is open
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Please define an entity (climate entity)');
    }
    this._config = config;
    // Don't set defaults here - wait for hass to initialize
    this._initialized = false;

    // Support opening with a specific mode pre-selected (from panel)
    if (config.initialMode) {
      this._selectedMode = config.initialMode;
      this._modeExpanded = true;
    }
    if (config.initialScheduleType) {
      this._selectedScheduleType = config.initialScheduleType;
    }
  }

  set hass(hass) {
    const wasNull = !this._hass;
    this._hass = hass;

    // Initialize on first hass set
    if (wasNull && !this._initialized) {
      this._initialized = true;
      this.initializeDefaults();
      this.loadAvailableModes();
      this.loadSchedule();
    }

    if (!this._availableModes.length) {
      this.loadAvailableModes();
    }
    this.render();
  }

  initializeDefaults() {
    // Don't auto-select mode - wait for user to click
    this._selectedMode = null;
    this._modeExpanded = false;

    // Auto-detect schedule type based on current day (for when mode is selected)
    const today = new Date().getDay(); // 0 = Sunday, 6 = Saturday
    if (today === 0 || today === 6) {
      this._selectedScheduleType = 'weekend';
    } else {
      this._selectedScheduleType = 'weekday';
    }
    console.log('TaDIY: Auto-detected schedule type:', this._selectedScheduleType, '(day:', today, ')');
  }

  async loadAvailableModes() {
    if (!this._hass) return;

    // Get hub entity to find custom modes - check all select entities
    const hubEntity = Object.values(this._hass.states).find(
      entity => entity.entity_id.startsWith('select.') &&
        entity.entity_id.includes('hub_mode')
    );

    console.log('TaDIY: Found hub entity:', hubEntity);

    if (hubEntity && hubEntity.attributes.options) {
      this._availableModes = hubEntity.attributes.options;
      console.log('TaDIY: Loaded modes:', this._availableModes);
    } else {
      // Fallback to default modes
      this._availableModes = ['normal', 'homeoffice', 'manual', 'off'];
      console.warn('TaDIY: Using default modes, hub entity not found');
    }

    this.render();
  }

  async loadSchedule() {
    if (!this._hass || !this._config) return;

    try {
      // FIXED: Use callWS for services with return_response
      const result = await this._hass.callWS({
        type: 'call_service',
        domain: 'tadiy',
        service: 'get_schedule',
        service_data: {
          entity_id: this._config.entity,
          mode: this._selectedMode,
          schedule_type: this._selectedScheduleType,
        },
        return_response: true,
      });

      if (result && result.response && result.response.blocks) {
        this._editingBlocks = result.response.blocks;
      } else {
        this._editingBlocks = this.getDefaultSchedule();
      }
    } catch (error) {
      console.warn('Could not load schedule, using defaults:', error);
      this._editingBlocks = this.getDefaultSchedule();
    }

    this.render();
  }

  getDefaultSchedule() {
    if (this._selectedScheduleType === 'weekday') {
      return [
        { start_time: '00:00', end_time: '06:00', temperature: 18.0 },
        { start_time: '06:00', end_time: '08:00', temperature: 21.0 },
        { start_time: '08:00', end_time: '16:00', temperature: 18.0 },
        { start_time: '16:00', end_time: '22:00', temperature: 21.0 },
        { start_time: '22:00', end_time: '23:59', temperature: 18.0 },
      ];
    } else if (this._selectedScheduleType === 'weekend') {
      return [
        { start_time: '00:00', end_time: '08:00', temperature: 18.0 },
        { start_time: '08:00', end_time: '23:00', temperature: 21.0 },
        { start_time: '23:00', end_time: '23:59', temperature: 18.0 },
      ];
    } else {
      return [
        { start_time: '00:00', end_time: '06:00', temperature: 18.0 },
        { start_time: '06:00', end_time: '22:00', temperature: 21.0 },
        { start_time: '22:00', end_time: '23:59', temperature: 18.0 },
      ];
    }
  }

  getTemperatureColor(temperature) {
    if (typeof temperature === 'string') {
      return '#6c757d';
    }
    if (temperature <= 15) return '#0d6efd';
    if (temperature <= 18) return '#0dcaf0';
    if (temperature <= 20) return '#20c997';
    if (temperature <= 22) return '#fd7e14';
    return '#dc3545';
  }

  formatTemperature(temperature) {
    if (typeof temperature === 'string') {
      return temperature.toUpperCase();
    }
    if (temperature === 0) {
      return 'FROST';
    }
    return `${temperature.toFixed(1)}°C`;
  }

  // FIXED: Ensure minutes are always two digits
  formatTime(time) {
    // Keep 24:00 as-is for display in timeline
    const [hours, minutes] = time.split(':');
    return `${hours.padStart(2, '0')}:${minutes.padStart(2, '0')}`;
  }

  parseEndTime(time) {
    // Convert 00:00 end time to 24:00 (end of day)
    if (time === '00:00') return '24:00';
    return time;
  }

  timeToMinutes(time) {
    const [h, m] = time.split(':').map(Number);
    return h * 60 + m;
  }

  minutesToTime(minutes) {
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  }

  renderTimeInput(value, className, index, isEndTime = false) {
    // Check if this is a fixed time (first start or last end)
    const isFirstStart = index === 0 && !isEndTime;
    const isLastEnd = index === this._editingBlocks.length - 1 && isEndTime;
    const isFixed = isFirstStart || isLastEnd;

    const [hours, minutes] = value.split(':');

    return `
      <div class="time-input-wrapper ${isFixed ? 'fixed' : ''}">
        <div class="time-input-inline" data-index="${index}" data-is-end="${isEndTime}">
          <div class="time-part hours-part ${isFixed ? 'disabled' : ''}" data-part="hours">
            <span class="time-value">${hours}</span>
            ${!isFixed ? '<span class="dropdown-arrow">▼</span>' : ''}
            ${!isFixed ? this.renderHoursDropdown(parseInt(hours), index, isEndTime) : ''}
          </div>
          <span class="time-separator">:</span>
          <div class="time-part minutes-part ${isFixed ? 'disabled' : ''}" data-part="minutes">
            <span class="time-value">${minutes}</span>
            ${!isFixed ? '<span class="dropdown-arrow">▼</span>' : ''}
            ${!isFixed ? this.renderMinutesDropdown(parseInt(minutes), parseInt(hours), index, isEndTime) : ''}
          </div>
        </div>
      </div>
    `;
  }

  renderHoursDropdown(currentHour, index, isEndTime) {
    // Get constraints based on neighboring blocks
    const constraints = this.getTimeConstraints(index, isEndTime);
    const maxHour = isEndTime ? 24 : 23;

    let options = '';
    for (let h = 0; h <= maxHour; h++) {
      const selected = h === currentHour ? 'selected' : '';
      const disabled = !this.isHourAllowed(h, 0, constraints);
      const disabledClass = disabled ? 'disabled' : '';
      const disabledAttr = disabled ? 'disabled' : '';
      options += `<div class="time-option ${selected} ${disabledClass}" data-value="${h}" ${disabledAttr}>${String(h).padStart(2, '0')}</div>`;
    }
    return `<div class="time-dropdown hours-dropdown">${options}</div>`;
  }

  renderMinutesDropdown(currentMinute, currentHour, index, isEndTime) {
    const minuteOptions = [0, 15, 30, 45];
    const constraints = this.getTimeConstraints(index, isEndTime);

    let options = '';
    for (const m of minuteOptions) {
      const selected = m === currentMinute ? 'selected' : '';
      const disabled = !this.isMinuteAllowed(currentHour, m, constraints);
      const disabledClass = disabled ? 'disabled' : '';
      const disabledAttr = disabled ? 'disabled' : '';
      options += `<div class="time-option ${selected} ${disabledClass}" data-value="${m}" ${disabledAttr}>${String(m).padStart(2, '0')}</div>`;
    }
    return `<div class="time-dropdown minutes-dropdown">${options}</div>`;
  }

  getTimeConstraints(index, isEndTime) {
    // Get min/max time based on neighboring blocks
    let minTime = "00:00";
    let maxTime = "24:00";

    if (isEndTime) {
      // End time: minimum is start time + 15min, maximum is next block's end time - 15min
      const startTime = this._editingBlocks[index].start_time;
      const [sh, sm] = startTime.split(':').map(Number);
      minTime = this.minutesToTime(sh * 60 + sm + 15); // At least 15min after start

      // Find next block
      if (index < this._editingBlocks.length - 1) {
        maxTime = this._editingBlocks[index + 1].end_time;
        const [mh, mm] = maxTime.split(':').map(Number);
        maxTime = this.minutesToTime(Math.max(0, mh * 60 + mm - 15)); // At most 15min before next block's end
      } else {
        maxTime = "24:00"; // Last block must end at 24:00
      }
    } else {
      // Start time: minimum is previous block's start time + 15min, maximum is end time - 15min
      if (index > 0) {
        const prevStart = this._editingBlocks[index - 1].start_time;
        const [ph, pm] = prevStart.split(':').map(Number);
        minTime = this.minutesToTime(ph * 60 + pm + 15); // At least 15min after previous start
      } else {
        minTime = "00:00"; // First block must start at 00:00
      }

      const endTime = this._editingBlocks[index].end_time;
      const [eh, em] = endTime.split(':').map(Number);
      maxTime = this.minutesToTime(Math.max(0, eh * 60 + em - 15)); // At most 15min before end
    }

    return { minTime, maxTime };
  }

  isHourAllowed(hour, minute, constraints) {
    const timeMinutes = hour * 60 + minute;
    const minMinutes = this.timeToMinutes(constraints.minTime);
    const maxMinutes = this.timeToMinutes(constraints.maxTime);
    return timeMinutes >= minMinutes && timeMinutes <= maxMinutes;
  }

  isMinuteAllowed(hour, minute, constraints) {
    const timeMinutes = hour * 60 + minute;
    const minMinutes = this.timeToMinutes(constraints.minTime);
    const maxMinutes = this.timeToMinutes(constraints.maxTime);
    return timeMinutes >= minMinutes && timeMinutes <= maxMinutes;
  }

  snapToGrid(minutes) {
    // Snap to 15-minute intervals (0, 15, 30, 45)
    // Always round to nearest 15-minute mark
    return Math.round(minutes / 15) * 15;
  }

  snapTimeToQuarter(timeStr) {
    // Snap a HH:MM time string to nearest quarter hour (0, 15, 30, 45)
    const [h, m] = timeStr.split(':').map(Number);
    const totalMinutes = h * 60 + m;
    const snappedMinutes = Math.round(totalMinutes / 15) * 15;
    return this.minutesToTime(snappedMinutes);
  }

  generateTimeline() {
    const totalMinutes = 24 * 60;
    const isEditing = this._isEditing;

    // Use absolute positioning for interactive timeline
    if (isEditing) {
      let html = `<div class="timeline interactive" data-timeline>`;

      this._editingBlocks.forEach((block, index) => {
        const [startH, startM] = block.start_time.split(':').map(Number);
        const [endH, endM] = block.end_time.split(':').map(Number);

        const startTotal = startH * 60 + startM;
        let endTotal = endH * 60 + endM;

        if (endH === 23 && endM === 59) {
          endTotal = 24 * 60;
        }
        if (endTotal === 0) {
          endTotal = 24 * 60;
        }

        const duration = endTotal > startTotal
          ? endTotal - startTotal
          : (24 * 60) - startTotal + endTotal;

        const leftPercent = (startTotal / totalMinutes) * 100;
        const widthPercent = (duration / totalMinutes) * 100;
        const color = this.getTemperatureColor(block.temperature);
        const tempDisplay = this.formatTemperature(block.temperature);

        html += `
          <div class="timeline-block draggable"
               style="position: absolute; left: ${leftPercent.toFixed(2)}%; width: ${widthPercent.toFixed(2)}%; background: ${color};"
               data-block-index="${index}"
               data-start-minutes="${startTotal}"
               data-end-minutes="${endTotal}"
               draggable="true">
            <div class="resize-handle resize-left" data-handle="left"></div>
            <div class="timeline-content">
              <div class="timeline-temp">${tempDisplay}</div>
              <div class="timeline-time">${this.formatTime(block.start_time)}-${this.formatTime(block.end_time)}</div>
            </div>
            <div class="resize-handle resize-right" data-handle="right"></div>
          </div>
        `;
      });

      html += '</div>';
      html += `
        <div class="timeline-labels">
          <span>00:00</span>
          <span>06:00</span>
          <span>12:00</span>
          <span>18:00</span>
          <span>24:00</span>
        </div>
      `;
      return html;
    }

    // Original flex-based timeline for non-editing mode
    let html = `<div class="timeline" data-timeline>`;

    this._editingBlocks.forEach((block) => {
      const [startH, startM] = block.start_time.split(':').map(Number);
      const [endH, endM] = block.end_time.split(':').map(Number);

      const startTotal = startH * 60 + startM;
      let endTotal = endH * 60 + endM;

      if (endH === 23 && endM === 59) {
        endTotal = 24 * 60;
      }

      if (endTotal === 0) {
        endTotal = 24 * 60;
      }

      const duration = endTotal > startTotal
        ? endTotal - startTotal
        : (24 * 60) - startTotal + endTotal;

      const percentage = (duration / totalMinutes) * 100;
      const color = this.getTemperatureColor(block.temperature);
      const tempDisplay = this.formatTemperature(block.temperature);

      html += `
        <div class="timeline-block"
             style="flex: 0 0 ${percentage.toFixed(2)}%; background: ${color};">
          <div class="timeline-content">
            <div class="timeline-temp">${tempDisplay}</div>
            <div class="timeline-time">${this.formatTime(block.start_time)}-${this.formatTime(block.end_time)}</div>
          </div>
        </div>
      `;
    });

    html += '</div>';
    html += `
      <div class="timeline-labels">
        <span>00:00</span>
        <span>06:00</span>
        <span>12:00</span>
        <span>18:00</span>
        <span>24:00</span>
      </div>
    `;

    return html;
  }

  debouncedRender() {
    // Clear existing timeout
    if (this._renderDebounce) {
      clearTimeout(this._renderDebounce);
    }

    // Set new timeout - wait 300ms after last change
    this._renderDebounce = setTimeout(() => {
      this.render();
    }, 300);
  }

  render() {
    if (!this._hass || !this._config) return;

    // NEVER re-render while dropdown is open to prevent closure
    if (this._hasOpenDropdown) {
      return;
    }

    const entity = this._hass.states[this._config.entity];
    if (!entity) {
      this.shadowRoot.innerHTML = '<ha-card>Entity not found</ha-card>';
      return;
    }

    const roomName = entity.attributes.friendly_name || 'Room';

    // Generate mode buttons dynamically
    const modeButtons = this.generateModeButtons();

    this.shadowRoot.innerHTML = `
      <style>
        ha-card {
          padding: 16px;
        }
        .card-header {
          font-size: 20px;
          font-weight: bold;
          margin-bottom: 16px;
        }
        .mode-selector {
          display: flex;
          gap: 8px;
          margin-bottom: 16px;
          flex-wrap: wrap;
        }
        .mode-btn {
          padding: 8px 16px;
          border: 1px solid var(--primary-color);
          border-radius: 4px;
          background: transparent;
          color: var(--primary-color);
          cursor: pointer;
          font-size: 14px;
        }
        .mode-btn.active {
          background: var(--primary-color);
          color: white;
        }
        .timeline {
          display: flex;
          height: 60px;
          border-radius: 8px;
          overflow: hidden;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
          margin-bottom: 8px;
          position: relative;
        }
        .timeline.interactive {
          height: 80px;
          display: block;
        }
        .timeline-block {
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-weight: bold;
          border-right: 1px solid rgba(255,255,255,0.3);
          position: relative;
          height: 100%;
        }
        .timeline-block.draggable {
          cursor: move;
          transition: opacity 0.2s;
          position: absolute;
          top: 0;
          bottom: 0;
          border-right: 2px solid rgba(0,0,0,0.3);
        }
        .timeline-block.draggable:hover {
          opacity: 0.9;
          box-shadow: inset 0 0 0 2px rgba(255,255,255,0.5);
        }
        .timeline-block.dragging {
          opacity: 0.5;
        }
        .resize-handle {
          position: absolute;
          top: 0;
          bottom: 0;
          width: 10px;
          cursor: ew-resize;
          z-index: 10;
          background: rgba(255,255,255,0.2);
          opacity: 0;
          transition: opacity 0.2s;
        }
        .timeline-block:hover .resize-handle {
          opacity: 1;
        }
        .resize-handle:hover {
          background: rgba(255,255,255,0.4);
        }
        .resize-left {
          left: 0;
        }
        .resize-right {
          right: 0;
        }
        .timeline-content {
          text-align: center;
          padding: 5px;
          pointer-events: none;
        }
        .timeline-temp {
          font-size: 14px;
        }
        .timeline-time {
          font-size: 10px;
          opacity: 0.9;
        }
        .timeline-labels {
          display: flex;
          justify-content: space-between;
          font-size: 11px;
          color: #666;
          margin-bottom: 16px;
        }
        .blocks-container {
          margin-top: 16px;
          max-height: ${this._isEditing ? '1000px' : '0'};
          overflow: hidden;
          transition: max-height 0.3s ease-in-out;
        }
        .block-editor {
          display: grid;
          grid-template-columns: 95px 95px 100px 60px;
          gap: 8px;
          align-items: center;
          margin-bottom: 12px;
          padding: 12px;
          background: var(--secondary-background-color);
          border-radius: 4px;
          border: 2px solid transparent;
          cursor: pointer;
          transition: all 0.2s;
        }
        .block-editor:hover {
          background: var(--table-row-background-color);
        }
        .block-editor.selected {
          border-color: var(--primary-color);
          background: var(--table-row-alternative-background-color);
        }
        .block-label {
          grid-column: 1 / -1;
          font-weight: bold;
          font-size: 14px;
          margin-bottom: 4px;
        }
        .input-group {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .input-label {
          font-size: 12px;
          color: #666;
        }
        .time-input-wrapper {
          position: relative;
          display: flex;
          align-items: center;
        }
        .time-input-wrapper.fixed {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .time-input-inline {
          display: flex;
          align-items: center;
          gap: 2px;
          padding: 8px;
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          background: var(--card-background-color);
          color: var(--primary-text-color);
          font-size: 14px;
          font-family: monospace;
          min-width: 80px;
          justify-content: center;
        }
        .time-separator {
          font-weight: bold;
          padding: 0 1px;
          font-size: 12px;
        }
        .time-part {
          position: relative;
          display: inline-flex;
          align-items: center;
          padding: 2px 4px;
          cursor: pointer;
          border-radius: 3px;
          transition: background 0.2s;
          user-select: none;
        }
        .time-part:hover:not(.disabled) {
          background: var(--secondary-background-color);
        }
        .time-part.disabled {
          cursor: not-allowed;
          opacity: 0.6;
        }
        .time-value {
          font-weight: bold;
          min-width: 22px;
          text-align: center;
        }
        .dropdown-arrow {
          font-size: 8px;
          margin-left: 2px;
          opacity: 0.6;
        }
        .time-dropdown {
          display: none;
          position: absolute;
          top: 100%;
          left: 0;
          margin-top: 2px;
          background: var(--card-background-color);
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          max-height: 200px;
          overflow-y: auto;
          box-shadow: 0 4px 8px rgba(0,0,0,0.2);
          z-index: 10000;
          min-width: 60px;
        }
        .time-dropdown.open {
          display: block;
        }
        .time-option {
          padding: 8px 12px;
          text-align: center;
          cursor: pointer;
          transition: background 0.1s;
          font-weight: bold;
        }
        .time-option:hover:not(.disabled) {
          background: var(--secondary-background-color);
        }
        .time-option.selected {
          background: var(--primary-color);
          color: white;
        }
        .time-option.disabled {
          opacity: 0.3;
          cursor: not-allowed;
          text-decoration: line-through;
        }
        input[type="number"] {
          padding: 8px;
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          background: var(--card-background-color);
          color: var(--primary-text-color);
          font-size: 14px;
          width: 100%;
        }
        .delete-btn {
          padding: 8px;
          background: #dc3545;
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 20px;
          height: 40px;
          margin-top: 20px;
        }
        .delete-btn:hover {
          background: #c82333;
        }
        .actions {
          display: flex;
          gap: 8px;
          margin-top: 16px;
          flex-wrap: wrap;
        }
        .btn {
          padding: 10px 20px;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 14px;
          font-weight: bold;
        }
        .btn-primary {
          background: var(--primary-color);
          color: white;
        }
        .btn-secondary {
          background: var(--secondary-text-color);
          color: white;
        }
        .btn-success {
          background: #28a745;
          color: white;
        }
        .btn-warning {
          background: #ffc107;
          color: black;
        }
        .btn:hover {
          opacity: 0.9;
        }
        .validation-error {
          color: #dc3545;
          font-size: 12px;
          margin-top: 8px;
        }
      </style>

      <ha-card>
        <div class="card-header">
          ${roomName} - Schedule Editor
        </div>

        <div class="mode-selector">
          ${modeButtons}
        </div>

        ${this._modeExpanded ? `
          ${this.generateTimeline()}

          ${this._isEditing ? `
            <div class="blocks-container">
              ${this._editingBlocks.map((block, index) => this.renderBlockEditor(block, index)).join('')}
            </div>

            <div class="actions">
              <button class="btn btn-warning" data-action="back">
                ◀ Back
              </button>
              <button class="btn btn-secondary" data-action="reset">
                🔄 Reset
              </button>
              <button class="btn btn-primary" data-action="save">
                💾 Save
              </button>
              <button class="btn btn-success" data-action="add">
                ➕ Add Block
              </button>
            </div>

            <div id="validation-error" class="validation-error"></div>
          ` : `
            <div class="actions">
              <button class="btn btn-primary" data-action="edit">
                ✏️ Edit Schedule
              </button>
            </div>
          `}
        ` : ''}
      </ha-card>
    `;

    this.attachEventListeners();
  }

  generateModeButtons() {
    let html = '';

    // Normal mode has weekday/weekend split
    const isNormalWeekday = this._selectedMode === 'normal' && this._selectedScheduleType === 'weekday';
    const isNormalWeekend = this._selectedMode === 'normal' && this._selectedScheduleType === 'weekend';

    html += `
      <button class="mode-btn ${isNormalWeekday ? 'active' : ''}" data-mode="normal" data-type="weekday">
        Normal - Weekday
      </button>
      <button class="mode-btn ${isNormalWeekend ? 'active' : ''}" data-mode="normal" data-type="weekend">
        Normal - Weekend
      </button>
    `;

    // Add other modes (excluding normal, manual, off)
    for (const mode of this._availableModes) {
      if (mode === 'normal' || mode === 'manual' || mode === 'off') continue;

      const isActive = this._selectedMode === mode;
      const displayName = mode.charAt(0).toUpperCase() + mode.slice(1);

      html += `
        <button class="mode-btn ${isActive ? 'active' : ''}" data-mode="${mode}" data-type="daily">
          ${displayName}
        </button>
      `;
    }

    return html;
  }

  renderBlockEditor(block, index) {
    const isSelected = this._selectedBlockIndex === index;
    return `
      <div class="block-editor ${isSelected ? 'selected' : ''}" data-index="${index}">
        <div class="block-label">Block ${index + 1}</div>

        <div class="input-group">
          <span class="input-label">Start</span>
          ${this.renderTimeInput(block.start_time, 'start-time', index, false)}
        </div>

        <div class="input-group">
          <span class="input-label">End</span>
          ${this.renderTimeInput(block.end_time, 'end-time', index, true)}
        </div>

        <div class="input-group">
          <span class="input-label">Temp (°C)</span>
          <input type="number"
                 class="temperature"
                 value="${block.temperature}"
                 step="0.5"
                 min="5"
                 max="30"
                 data-index="${index}">
        </div>

        <button class="delete-btn" data-index="${index}">🗑️</button>
      </div>
    `;
  }

  attachEventListeners() {
    // Mode buttons
    this.shadowRoot.querySelectorAll('.mode-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const mode = btn.dataset.mode;
        const type = btn.dataset.type;
        this.selectSchedule(mode, type);
      });
    });

    // Action buttons
    this.shadowRoot.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', () => {
        const action = btn.dataset.action;

        switch (action) {
          case 'edit':
            this._isEditing = true;
            this._selectedBlockIndex = null;
            this.render();
            break;
          case 'back':
            this._isEditing = false;
            this._selectedBlockIndex = null;
            this.render();
            break;
          case 'add':
            this.addBlock();
            break;
          case 'save':
            this.saveSchedule();
            break;
          case 'reset':
            this.loadSchedule();
            break;
        }
      });
    });

    // Block selection (click on block editor to select)
    this.shadowRoot.querySelectorAll('.block-editor').forEach(editor => {
      editor.addEventListener('click', (e) => {
        // Don't select if clicking delete button
        if (e.target.classList.contains('delete-btn')) return;
        const index = parseInt(editor.dataset.index);
        this._selectedBlockIndex = index;
        this.render();
      });
    });

    // Input changes - handles temperature inputs only (time inputs are readonly)
    this.shadowRoot.querySelectorAll('.temperature').forEach(input => {
      input.addEventListener('blur', (e) => {
        const index = parseInt(e.target.dataset.index);
        let temp = parseFloat(e.target.value);
        if (isNaN(temp) || temp < 5) temp = 5;
        if (temp > 30) temp = 30;
        this._editingBlocks[index].temperature = temp;
        this.render();
      });

      // Also handle Enter key
      input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.target.blur(); // Trigger blur event
        }
      });
    });

    // Inline dropdown time pickers
    this.shadowRoot.querySelectorAll('.time-part:not(.disabled)').forEach(part => {
      const dropdown = part.querySelector('.time-dropdown');
      if (!dropdown) return;

      // Toggle dropdown on click
      part.addEventListener('click', (e) => {
        e.stopPropagation(); // Prevent block selection

        // Close all other dropdowns first
        this.shadowRoot.querySelectorAll('.time-dropdown').forEach(dd => {
          if (dd !== dropdown) dd.classList.remove('open');
        });

        // Toggle this dropdown
        const wasOpen = dropdown.classList.contains('open');
        dropdown.classList.toggle('open');
        this._hasOpenDropdown = !wasOpen; // Track dropdown state

        // Position dropdown below the time part using fixed positioning
        if (!wasOpen) {
          const rect = part.getBoundingClientRect();
          dropdown.style.top = `${rect.bottom + 4}px`;
          dropdown.style.left = `${rect.left}px`;

          // Scroll selected option into view
          const selected = dropdown.querySelector('.time-option.selected');
          if (selected) {
            selected.scrollIntoView({ block: 'nearest' });
          }
        }
      });

      // Handle option selection
      dropdown.querySelectorAll('.time-option:not(.disabled)').forEach(option => {
        option.addEventListener('click', (e) => {
          e.stopPropagation();

          // Get context
          const timeInput = part.closest('.time-input-inline');
          const index = parseInt(timeInput.dataset.index);
          const isEndTime = timeInput.dataset.isEnd === 'true';
          const partType = part.dataset.part; // 'hours' or 'minutes'
          const newValue = parseInt(option.dataset.value);

          // Get current time
          const field = isEndTime ? 'end_time' : 'start_time';
          const [h, m] = this._editingBlocks[index][field].split(':').map(Number);

          // Update appropriate part
          let newHours = h;
          let newMinutes = m;
          if (partType === 'hours') {
            newHours = newValue;
            // Special case: if 24:00, force minutes to 00
            if (newHours === 24) newMinutes = 0;
          } else {
            newMinutes = newValue;
            // Can't have 24:XX except 24:00
            if (newHours === 24 && newMinutes !== 0) newMinutes = 0;
          }

          // Update block time
          const newTime = `${String(newHours).padStart(2, '0')}:${String(newMinutes).padStart(2, '0')}`;
          this._editingBlocks[index][field] = newTime;

          // Update adjacent blocks to maintain continuity
          if (isEndTime && index < this._editingBlocks.length - 1) {
            // Changed end time - update next block's start time
            this._editingBlocks[index + 1].start_time = newTime;
          } else if (!isEndTime && index > 0) {
            // Changed start time - update previous block's end time
            this._editingBlocks[index - 1].end_time = newTime;
          }

          // Close dropdown and re-render
          dropdown.classList.remove('open');
          this._hasOpenDropdown = false; // Mark dropdown closed before render
          this.render();
        });
      });
    });

    // Close dropdowns when clicking outside
    const closeDropdowns = (e) => {
      const isTimePart = e.target.closest('.time-part');
      if (!isTimePart) {
        this.shadowRoot.querySelectorAll('.time-dropdown').forEach(dd => {
          dd.classList.remove('open');
        });
        this._hasOpenDropdown = false; // Mark dropdown closed
      }
    };

    // Remove old listener if exists
    if (this._dropdownCloseHandler) {
      document.removeEventListener('click', this._dropdownCloseHandler, true);
    }
    document.addEventListener('click', closeDropdowns, true);
    this._dropdownCloseHandler = closeDropdowns;

    // Delete buttons
    this.shadowRoot.querySelectorAll('.delete-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation(); // Prevent block selection
        const index = parseInt(btn.dataset.index);
        this.deleteBlock(index);
      });
    });

    // Keyboard support - Delete key to remove selected block
    if (this._isEditing) {
      // Remove old listener if exists
      if (this._keyboardHandler) {
        document.removeEventListener('keydown', this._keyboardHandler);
      }

      this._keyboardHandler = (e) => {
        if (e.key === 'Delete' && this._selectedBlockIndex !== null) {
          e.preventDefault();
          this.deleteBlock(this._selectedBlockIndex);
        }
      };

      document.addEventListener('keydown', this._keyboardHandler);
    }

    // Timeline drag & drop and resize
    if (this._isEditing) {
      this.attachTimelineInteractions();
    }
  }

  attachTimelineInteractions() {
    const timeline = this.shadowRoot.querySelector('[data-timeline]');
    if (!timeline) return;

    const timelineBlocks = this.shadowRoot.querySelectorAll('.timeline-block.draggable');

    timelineBlocks.forEach(block => {
      // Click to select corresponding editor block
      block.addEventListener('click', (e) => {
        // Don't trigger if clicking on resize handles
        if (e.target.classList.contains('resize-handle')) return;

        const index = parseInt(block.dataset.blockIndex);
        this._selectedBlockIndex = index;
        this.render();
      });

      // Drag & drop for moving blocks
      block.addEventListener('dragstart', (e) => {
        const index = parseInt(block.dataset.blockIndex);
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('blockIndex', index);
        block.classList.add('dragging');
      });

      block.addEventListener('dragend', () => {
        block.classList.remove('dragging');
      });

      block.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
      });

      block.addEventListener('drop', (e) => {
        e.preventDefault();
        const draggedIndex = parseInt(e.dataTransfer.getData('blockIndex'));
        const targetIndex = parseInt(block.dataset.blockIndex);

        if (draggedIndex !== targetIndex) {
          // Swap blocks
          const temp = this._editingBlocks[draggedIndex];
          this._editingBlocks[draggedIndex] = this._editingBlocks[targetIndex];
          this._editingBlocks[targetIndex] = temp;
          this.render();
        }
      });

      // Resize handles
      const resizeHandles = block.querySelectorAll('.resize-handle');
      resizeHandles.forEach(handle => {
        handle.addEventListener('mousedown', (e) => {
          e.preventDefault();
          e.stopPropagation();

          const index = parseInt(block.dataset.blockIndex);
          const handleType = handle.dataset.handle; // 'left' or 'right'
          const timelineRect = timeline.getBoundingClientRect();
          const startX = e.clientX;
          const blockData = this._editingBlocks[index];
          const startMinutes = this.timeToMinutes(blockData.start_time);
          const endMinutes = this.timeToMinutes(blockData.end_time);

          const onMouseMove = (moveEvent) => {
            const deltaX = moveEvent.clientX - startX;
            const timelineWidth = timelineRect.width;
            const deltaMinutes = Math.round((deltaX / timelineWidth) * (24 * 60));
            const snappedDelta = this.snapToGrid(deltaMinutes);

            // Sort blocks by start time to find neighbors
            const sortedBlocks = [...this._editingBlocks].sort((a, b) => {
              return this.timeToMinutes(a.start_time) - this.timeToMinutes(b.start_time);
            });
            const sortedIndex = sortedBlocks.findIndex(b => b === blockData);

            if (handleType === 'left') {
              // Resize from left - change start time AND previous block's end time
              let newStart = startMinutes + snappedDelta;

              // Don't allow first block to move start time (must stay at 00:00)
              if (sortedIndex === 0) {
                newStart = 0;
              } else {
                // Limit based on previous block's start + 15min
                const prevBlock = sortedBlocks[sortedIndex - 1];
                const prevStart = this.timeToMinutes(prevBlock.start_time);
                newStart = Math.max(prevStart + 15, Math.min(newStart, endMinutes - 15));
              }

              const newTime = this.minutesToTime(newStart);

              if (this._editingBlocks[index].start_time !== newTime) {
                this._editingBlocks[index].start_time = newTime;

                // Update previous block's end time to match
                if (sortedIndex > 0) {
                  const prevBlock = sortedBlocks[sortedIndex - 1];
                  const prevIndex = this._editingBlocks.indexOf(prevBlock);
                  this._editingBlocks[prevIndex].end_time = newTime;
                }

                // Update this block's display
                const leftPercent = (newStart / 1440) * 100;
                const widthPercent = ((endMinutes - newStart) / 1440) * 100;
                block.style.left = `${leftPercent.toFixed(2)}%`;
                block.style.width = `${widthPercent.toFixed(2)}%`;
                const timeDisplay = block.querySelector('.timeline-time');
                if (timeDisplay) {
                  timeDisplay.textContent = `${this.formatTime(newTime)}-${this.formatTime(blockData.end_time)}`;
                }
              }
            } else {
              // Resize from right - change end time AND next block's start time
              let newEnd = endMinutes + snappedDelta;

              // Don't allow last block to move end time (must stay at 24:00)
              if (sortedIndex === sortedBlocks.length - 1) {
                newEnd = 1440;
              } else {
                // Limit based on next block's end - 15min
                const nextBlock = sortedBlocks[sortedIndex + 1];
                const nextEnd = this.timeToMinutes(nextBlock.end_time);
                newEnd = Math.max(startMinutes + 15, Math.min(newEnd, nextEnd - 15));
              }

              const newTime = this.minutesToTime(newEnd);

              if (this._editingBlocks[index].end_time !== newTime) {
                this._editingBlocks[index].end_time = newTime;

                // Update next block's start time to match
                if (sortedIndex < sortedBlocks.length - 1) {
                  const nextBlock = sortedBlocks[sortedIndex + 1];
                  const nextIndex = this._editingBlocks.indexOf(nextBlock);
                  this._editingBlocks[nextIndex].start_time = newTime;
                }

                // Update this block's display
                const widthPercent = ((newEnd - startMinutes) / 1440) * 100;
                block.style.width = `${widthPercent.toFixed(2)}%`;
                const timeDisplay = block.querySelector('.timeline-time');
                if (timeDisplay) {
                  timeDisplay.textContent = `${this.formatTime(blockData.start_time)}-${this.formatTime(newTime)}`;
                }
              }
            }
          };

          const onMouseUp = () => {
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
            // Full render after resize is complete to update everything
            this.render();
          };

          document.addEventListener('mousemove', onMouseMove);
          document.addEventListener('mouseup', onMouseUp);
        });
      });
    });
  }

  selectSchedule(mode, scheduleType) {
    // Toggle mode: if same mode clicked, collapse it
    if (this._selectedMode === mode && this._selectedScheduleType === scheduleType && this._modeExpanded) {
      this._modeExpanded = false;
      this._isEditing = false;
      this.render();
    } else {
      // Different mode or expanding collapsed mode
      this._selectedMode = mode;
      this._selectedScheduleType = scheduleType;
      this._modeExpanded = true;
      this._isEditing = false;
      this.loadSchedule();
    }
  }

  addBlock() {
    // Sort blocks by start time first
    const sortedBlocks = [...this._editingBlocks].sort((a, b) => {
      return this.timeToMinutes(a.start_time) - this.timeToMinutes(b.start_time);
    });

    let blockToSplit = null;
    let sortedIndex = -1;

    if (this._selectedBlockIndex !== null) {
      // Find the selected block in sorted array
      const selectedBlock = this._editingBlocks[this._selectedBlockIndex];
      sortedIndex = sortedBlocks.findIndex(b => b === selectedBlock);
      blockToSplit = selectedBlock;
    } else {
      // No block selected - find largest block
      let maxDuration = 0;
      sortedBlocks.forEach((block, idx) => {
        const start = this.timeToMinutes(block.start_time);
        const end = this.timeToMinutes(block.end_time);
        const duration = end - start;
        if (duration > maxDuration) {
          maxDuration = duration;
          blockToSplit = block;
          sortedIndex = idx;
        }
      });
    }

    if (!blockToSplit) {
      this.showError('No block to split');
      return;
    }

    const startMinutes = this.timeToMinutes(blockToSplit.start_time);
    const endMinutes = this.timeToMinutes(blockToSplit.end_time);
    const duration = endMinutes - startMinutes;

    // Can't split blocks smaller than 30 minutes (minimum 15-minute blocks)
    if (duration < 30) {
      this.showError('Block is too small to split (minimum 30 minutes needed)');
      return;
    }

    // Calculate split point - try 60 minutes, or half if smaller
    let splitMinutes;
    if (duration >= 120) {
      // Large block: create 60-minute first block
      splitMinutes = startMinutes + 60;
    } else {
      // Small block: split in half
      splitMinutes = startMinutes + Math.floor(duration / 2);
    }
    splitMinutes = this.snapToGrid(splitMinutes);

    // Ensure split is within bounds
    if (splitMinutes <= startMinutes) splitMinutes = startMinutes + 15;
    if (splitMinutes >= endMinutes) splitMinutes = endMinutes - 15;

    const splitTime = this.minutesToTime(splitMinutes);

    // Create new block
    const newBlock = {
      start_time: splitTime,
      end_time: blockToSplit.end_time,
      temperature: 21.0
    };

    // Update existing block's end time
    blockToSplit.end_time = splitTime;

    // Insert new block into sorted array
    sortedBlocks.splice(sortedIndex + 1, 0, newBlock);

    // Replace editing blocks with sorted blocks
    this._editingBlocks = sortedBlocks;

    // Select the new block
    this._selectedBlockIndex = sortedIndex + 1;

    this.render();
  }

  deleteBlock(index) {
    if (this._editingBlocks.length <= 1) {
      this.showError('Cannot delete the last block');
      return;
    }

    // Delete the block
    this._editingBlocks.splice(index, 1);

    // Auto-fill gap: extend adjacent blocks to fill the gap
    // Sort blocks first
    const sortedBlocks = [...this._editingBlocks].sort((a, b) => {
      return this.timeToMinutes(a.start_time) - this.timeToMinutes(b.start_time);
    });

    // Find gaps and fill them
    for (let i = 0; i < sortedBlocks.length - 1; i++) {
      const currentEnd = this.timeToMinutes(sortedBlocks[i].end_time);
      const nextStart = this.timeToMinutes(sortedBlocks[i + 1].start_time);

      if (nextStart > currentEnd) {
        // Gap found - extend current block to meet next
        sortedBlocks[i].end_time = sortedBlocks[i + 1].start_time;
      }
    }

    // Check if first block doesn't start at 00:00
    if (sortedBlocks[0].start_time !== '00:00') {
      sortedBlocks[0].start_time = '00:00';
    }

    // Check if last block doesn't end at 24:00
    const lastBlock = sortedBlocks[sortedBlocks.length - 1];
    if (lastBlock.end_time !== '24:00' && lastBlock.end_time !== '23:59') {
      lastBlock.end_time = '24:00';
    }

    this._editingBlocks = sortedBlocks;

    // Adjust selection
    if (this._selectedBlockIndex >= this._editingBlocks.length) {
      this._selectedBlockIndex = this._editingBlocks.length - 1;
    }

    this.render();
  }

  validateBlocks() {
    if (this._editingBlocks.length === 0) {
      return { valid: false, error: 'At least one block is required' };
    }

    // Sort blocks by start time
    const sorted = [...this._editingBlocks].sort((a, b) => {
      return this.timeToMinutes(a.start_time) - this.timeToMinutes(b.start_time);
    });

    // Check for overlaps and gaps
    for (let i = 0; i < sorted.length - 1; i++) {
      const endMinutes = this.timeToMinutes(sorted[i].end_time);
      const nextStartMinutes = this.timeToMinutes(sorted[i + 1].start_time);

      if (endMinutes > nextStartMinutes) {
        return { valid: false, error: `Block ${i + 1} overlaps with block ${i + 2}` };
      }
    }

    // Validate each block
    for (let i = 0; i < sorted.length; i++) {
      const startMinutes = this.timeToMinutes(sorted[i].start_time);
      const endMinutes = this.timeToMinutes(sorted[i].end_time);

      if (startMinutes >= endMinutes) {
        return { valid: false, error: `Block ${i + 1}: End time must be after start time` };
      }

      if (sorted[i].temperature < 5 || sorted[i].temperature > 30) {
        return { valid: false, error: `Block ${i + 1}: Temperature must be between 5°C and 30°C` };
      }
    }

    return { valid: true };
  }


  async saveSchedule() {
    const validation = this.validateBlocks();
    if (!validation.valid) {
      this.showError(validation.error);
      return;
    }

    try {
      await this._hass.callService(
        'tadiy',
        'set_schedule',
        {
          entity_id: this._config.entity,
          mode: this._selectedMode,
          schedule_type: this._selectedScheduleType,
          blocks: this._editingBlocks,
        }
      );

      this.showError('✓ Schedule saved successfully');
      this._isEditing = false;
      this.render();
    } catch (error) {
      console.error('Failed to save schedule:', error);
      this.showError('Failed to save schedule: ' + (error.message || error));
    }
  }

  showError(message) {
    const errorEl = this.shadowRoot.getElementById('validation-error');
    if (errorEl) {
      errorEl.textContent = message;
      setTimeout(() => {
        errorEl.textContent = '';
      }, 5000);
    }
  }

  getCardSize() {
    return this._isEditing ? 10 : 4;
  }
}

// Only define if not already defined
if (!customElements.get('tadiy-schedule-card')) {
  customElements.define('tadiy-schedule-card', TaDiyScheduleCard);
}
