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
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Please define an entity (climate entity)');
    }
    this._config = config;
    this._selectedMode = config.default_mode || 'normal';
    this._selectedScheduleType = config.default_schedule_type || 'weekday';
    this.loadSchedule();
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  async loadSchedule() {
    if (!this._hass || !this._config) return;

    try {
      // Load schedule via service call
      const result = await this._hass.callService(
        'tadiy',
        'get_schedule',
        {
          entity_id: this._config.entity,
          mode: this._selectedMode,
          schedule_type: this._selectedScheduleType,
        },
        true  // return_response
      );

      if (result && result.response && result.response.blocks) {
        this._editingBlocks = result.response.blocks;
      } else {
        // Default schedule
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
      // daily
      return [
        { start_time: '00:00', end_time: '06:00', temperature: 18.0 },
        { start_time: '06:00', end_time: '22:00', temperature: 21.0 },
        { start_time: '22:00', end_time: '23:59', temperature: 18.0 },
      ];
    }
  }

  getTemperatureColor(temperature) {
    if (typeof temperature === 'string') {
      return '#6c757d'; // Gray for OFF
    }
    if (temperature <= 15) return '#0d6efd'; // Blue
    if (temperature <= 18) return '#0dcaf0'; // Cyan
    if (temperature <= 20) return '#20c997'; // Teal
    if (temperature <= 22) return '#fd7e14'; // Orange
    return '#dc3545'; // Red
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

  generateTimeline() {
    const totalMinutes = 24 * 60;
    let html = '<div class="timeline">';

    for (const block of this._editingBlocks) {
      const [startH, startM] = block.start_time.split(':').map(Number);
      const [endH, endM] = block.end_time.split(':').map(Number);

      const startTotal = startH * 60 + startM;
      let endTotal = endH * 60 + endM;

      // Handle 23:59 as end of day
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
            <div class="timeline-time">${block.start_time}-${block.end_time}</div>
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
          <button class="mode-btn ${this._selectedMode === 'normal' && this._selectedScheduleType === 'weekday' ? 'active' : ''}"
                  @click="${() => this.selectSchedule('normal', 'weekday')}">
            Normal - Weekday
          </button>
          <button class="mode-btn ${this._selectedMode === 'normal' && this._selectedScheduleType === 'weekend' ? 'active' : ''}"
                  @click="${() => this.selectSchedule('normal', 'weekend')}">
            Normal - Weekend
          </button>
          <button class="mode-btn ${this._selectedMode === 'homeoffice' ? 'active' : ''}"
                  @click="${() => this.selectSchedule('homeoffice', 'daily')}">
            Homeoffice
          </button>
        </div>

        ${this.generateTimeline()}

        <div class="blocks-container">
          ${this._editingBlocks.map((block, index) => this.renderBlockEditor(block, index)).join('')}
        </div>

        <div class="actions">
          <button class="btn btn-success" @click="${() => this.addBlock()}">
            ➕ Add Block
          </button>
          <button class="btn btn-primary" @click="${() => this.saveSchedule()}">
            💾 Save
          </button>
          <button class="btn btn-secondary" @click="${() => this.loadSchedule()}">
            🔄 Reset
          </button>
        </div>

        <div id="validation-error" class="validation-error"></div>
      </ha-card>
    `;

    this.attachEventListeners();
  }

  renderBlockEditor(block, index) {
    return `
      <div class="block-editor" data-index="${index}">
        <div class="block-label">Block ${index + 1}</div>

        <div class="input-group">
          <span class="input-label">Start</span>
          <input type="time"
                 class="start-time"
                 value="${block.start_time}"
                 data-index="${index}">
        </div>

        <div class="input-group">
          <span class="input-label">End</span>
          <input type="time"
                 class="end-time"
                 value="${block.end_time}"
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
    this.shadowRoot.querySelectorAll('.mode-btn').forEach((btn, index) => {
      btn.addEventListener('click', () => {
        if (index === 0) this.selectSchedule('normal', 'weekday');
        else if (index === 1) this.selectSchedule('normal', 'weekend');
        else if (index === 2) this.selectSchedule('homeoffice', 'daily');
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
      btn.addEventListener('click', (e) => {
        const index = parseInt(e.target.dataset.index);
        this.deleteBlock(index);
      });
    });

    // Action buttons
    const actions = this.shadowRoot.querySelectorAll('.actions .btn');
    actions[0]?.addEventListener('click', () => this.addBlock());
    actions[1]?.addEventListener('click', () => this.saveSchedule());
    actions[2]?.addEventListener('click', () => this.loadSchedule());
  }

  selectSchedule(mode, scheduleType) {
    this._selectedMode = mode;
    this._selectedScheduleType = scheduleType;
    this.loadSchedule();
  }

  addBlock() {
    // Add a new block at the end
    const lastBlock = this._editingBlocks[this._editingBlocks.length - 1];
    if (lastBlock && lastBlock.end_time === '23:59') {
      // Split the last block in half
      const [startH, startM] = lastBlock.start_time.split(':').map(Number);
      const startMinutes = startH * 60 + startM;
      const midMinutes = Math.floor((startMinutes + 24 * 60) / 2);
      const midH = Math.floor(midMinutes / 60) % 24;
      const midM = midMinutes % 60;
      const midTime = `${String(midH).padStart(2, '0')}:${String(midM).padStart(2, '0')}`;

      lastBlock.end_time = midTime;
      this._editingBlocks.push({
        start_time: midTime,
        end_time: '23:59',
        temperature: lastBlock.temperature,
      });
    } else {
      // Default: add a 1-hour block
      this._editingBlocks.push({
        start_time: '22:00',
        end_time: '23:59',
        temperature: 18.0,
      });
    }
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
    // Sort blocks by start time
    this._editingBlocks.sort((a, b) => a.start_time.localeCompare(b.start_time));

    // Check first block starts at 00:00
    if (this._editingBlocks[0].start_time !== '00:00') {
      return 'First block must start at 00:00';
    }

    // Check last block ends at 23:59
    const lastBlock = this._editingBlocks[this._editingBlocks.length - 1];
    if (lastBlock.end_time !== '23:59') {
      return 'Last block must end at 23:59';
    }

    // Check for gaps and overlaps
    for (let i = 0; i < this._editingBlocks.length - 1; i++) {
      const current = this._editingBlocks[i];
      const next = this._editingBlocks[i + 1];

      if (current.end_time !== next.start_time) {
        if (current.end_time < next.start_time) {
          return `Gap between ${current.end_time} and ${next.start_time}`;
        } else {
          return `Overlap between blocks ${i + 1} and ${i + 2}`;
        }
      }

      // Check block time range
      if (current.start_time >= current.end_time) {
        return `Block ${i + 1} has invalid time range`;
      }
    }

    return null;
  }

  showError(message) {
    const errorDiv = this.shadowRoot.getElementById('validation-error');
    if (errorDiv) {
      errorDiv.textContent = message;
      setTimeout(() => {
        errorDiv.textContent = '';
      }, 5000);
    }
  }

  async saveSchedule() {
    // Validate
    const error = this.validateBlocks();
    if (error) {
      this.showError(error);
      return;
    }

    try {
      // Save via service call
      await this._hass.callService('tadiy', 'set_schedule', {
        entity_id: this._config.entity,
        mode: this._selectedMode,
        schedule_type: this._selectedScheduleType,
        blocks: this._editingBlocks,
      });

      this.showError('✓ Schedule saved successfully');
    } catch (error) {
      console.error('Failed to save schedule:', error);
      this.showError('Failed to save schedule: ' + (error.message || error));
    }
  }

  getCardSize() {
    return 6;
  }
}

customElements.define('tadiy-schedule-card', TaDiyScheduleCard);

// Add card to custom cards list
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'tadiy-schedule-card',
  name: 'TaDIY Schedule Card',
  description: 'Interactive schedule editor for TaDIY heating controller',
  preview: true,
});

console.info(
  '%c TaDIY Schedule Card %c v1.0.0 ',
  'background-color: #28a745; color: white; font-weight: bold;',
  'background-color: #333; color: white;'
);
