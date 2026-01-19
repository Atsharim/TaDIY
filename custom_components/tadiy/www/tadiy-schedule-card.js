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
    this._selectedMode = 'normal';
    this._selectedScheduleType = 'weekday';
    this._isEditing = false;
    this._availableModes = [];
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Please define an entity (climate entity)');
    }
    this._config = config;
    this._selectedMode = config.default_mode || 'normal';
    this._selectedScheduleType = config.default_schedule_type || 'weekday';
    this.loadAvailableModes();
    this.loadSchedule();
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._availableModes.length) {
      this.loadAvailableModes();
    }
    this.render();
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
    const [hours, minutes] = time.split(':');
    return `${hours.padStart(2, '0')}:${minutes.padStart(2, '0')}`;
  }

  generateTimeline() {
    const totalMinutes = 24 * 60;
    let html = '<div class="timeline">';

    for (const block of this._editingBlocks) {
      const [startH, startM] = block.start_time.split(':').map(Number);
      const [endH, endM] = block.end_time.split(':').map(Number);

      const startTotal = startH * 60 + startM;
      let endTotal = endH * 60 + endM;

      if (endH === 23 && endM === 59) {
        endTotal = 24 * 60;
      }

      const duration = endTotal > startTotal
        ? endTotal - startTotal
        : (24 * 60) - startTotal + endTotal;

      const percentage = (duration / totalMinutes) * 100;
      const color = this.getTemperatureColor(block.temperature);
      const tempDisplay = this.formatTemperature(block.temperature);

      html += `
        <div class="timeline-block" style="flex: 0 0 ${percentage.toFixed(2)}%; background: ${color};">
          <div class="timeline-content">
            <div class="timeline-temp">${tempDisplay}</div>
            <div class="timeline-time">${this.formatTime(block.start_time)}-${this.formatTime(block.end_time)}</div>
          </div>
        </div>
      `;
    }

    html += '</div>';
    html += `
      <div class="timeline-labels">
        <span>00:00</span>
        <span>06:00</span>
        <span>12:00</span>
        <span>18:00</span>
        <span>23:59</span>
      </div>
    `;

    return html;
  }

  render() {
    if (!this._hass || !this._config) return;

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
        }
        .timeline-block {
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          font-weight: bold;
          border-right: 1px solid rgba(255,255,255,0.3);
        }
        .timeline-content {
          text-align: center;
          padding: 5px;
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
          grid-template-columns: 80px 80px 100px 60px;
          gap: 8px;
          align-items: center;
          margin-bottom: 12px;
          padding: 12px;
          background: var(--secondary-background-color);
          border-radius: 4px;
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
        input[type="time"],
        input[type="number"] {
          padding: 8px;
          border: 1px solid var(--divider-color);
          border-radius: 4px;
          background: var(--card-background-color);
          color: var(--primary-text-color);
          font-size: 14px;
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
    return `
      <div class="block-editor" data-index="${index}">
        <div class="block-label">Block ${index + 1}</div>

        <div class="input-group">
          <span class="input-label">Start</span>
          <input type="time"
                 class="start-time"
                 value="${this.formatTime(block.start_time)}"
                 data-index="${index}">
        </div>

        <div class="input-group">
          <span class="input-label">End</span>
          <input type="time"
                 class="end-time"
                 value="${this.formatTime(block.end_time)}"
                 data-index="${index}">
        </div>

        <div class="input-group">
          <span class="input-label">Temp (°C)</span>
          <input type="number"
                 class="temperature"
                 value="${block.temperature}"
                 step="0.1"
                 min="0"
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
            this.render();
            break;
          case 'back':
            this._isEditing = false;
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

    // Input changes
    this.shadowRoot.querySelectorAll('.start-time, .end-time, .temperature').forEach(input => {
      input.addEventListener('change', (e) => {
        const index = parseInt(e.target.dataset.index);
        const field = e.target.classList.contains('start-time') ? 'start_time' :
                      e.target.classList.contains('end-time') ? 'end_time' : 'temperature';

        if (field === 'temperature') {
          this._editingBlocks[index][field] = parseFloat(e.target.value);
        } else {
          this._editingBlocks[index][field] = e.target.value;
        }

        this.render();
      });
    });

    // Delete buttons
    this.shadowRoot.querySelectorAll('.delete-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const index = parseInt(btn.dataset.index);
        this.deleteBlock(index);
      });
    });
  }

  selectSchedule(mode, scheduleType) {
    this._selectedMode = mode;
    this._selectedScheduleType = scheduleType;
    this._isEditing = false;
    this.loadSchedule();
  }

  addBlock() {
    const lastBlock = this._editingBlocks[this._editingBlocks.length - 1];
    const newStart = lastBlock ? lastBlock.end_time : '12:00';

    this._editingBlocks.push({
      start_time: newStart,
      end_time: '23:59',
      temperature: 21.0
    });

    this.render();
  }

  deleteBlock(index) {
    if (this._editingBlocks.length <= 1) {
      this.showError('Cannot delete the last block');
      return;
    }

    this._editingBlocks.splice(index, 1);
    this.render();
  }

  validateBlocks() {
    if (this._editingBlocks.length === 0) {
      return { valid: false, error: 'At least one block is required' };
    }

    // Sort blocks by start time
    const sorted = [...this._editingBlocks].sort((a, b) => {
      const [aH, aM] = a.start_time.split(':').map(Number);
      const [bH, bM] = b.start_time.split(':').map(Number);
      return (aH * 60 + aM) - (bH * 60 + bM);
    });

    // Check for overlaps
    for (let i = 0; i < sorted.length - 1; i++) {
      const [endH, endM] = sorted[i].end_time.split(':').map(Number);
      const [nextStartH, nextStartM] = sorted[i + 1].start_time.split(':').map(Number);

      const endMinutes = endH * 60 + endM;
      const nextStartMinutes = nextStartH * 60 + nextStartM;

      if (endMinutes > nextStartMinutes) {
        return { valid: false, error: `Block ${i + 1} overlaps with block ${i + 2}` };
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

customElements.define('tadiy-schedule-card', TaDiyScheduleCard);
