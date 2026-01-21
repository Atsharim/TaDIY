/**
 * TaDIY Panel - Overview of all rooms and schedules
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
  }

  set hass(hass) {
    this._hass = hass;
    this.loadRooms();
    this.render();
  }

  set panel(panel) {
    this._config = panel.config;
  }

  loadRooms() {
    if (!this._hass) return;

    // Find all climate entities that belong to TaDIY rooms
    // Check for both 'integration' attribute AND 'tadiy' in entity_id
    this._rooms = Object.values(this._hass.states)
      .filter(entity => {
        if (!entity.entity_id.startsWith('climate.')) return false;

        // Check if integration attribute exists and equals 'tadiy'
        if (entity.attributes.integration === 'tadiy') return true;

        // Fallback: check if entity_id contains 'tadiy'
        if (entity.entity_id.includes('tadiy')) return true;

        // Also check if device_class or friendly_name mentions TaDIY
        const friendlyName = (entity.attributes.friendly_name || '').toLowerCase();
        if (friendlyName.includes('tadiy')) return true;

        return false;
      })
      .map(entity => ({
        entity_id: entity.entity_id,
        name: entity.attributes.friendly_name || entity.entity_id,
        current_temp: entity.attributes.current_temperature,
        target_temp: entity.attributes.temperature,
        hvac_action: entity.attributes.hvac_action,
        hvac_mode: entity.state,
      }))
      .sort((a, b) => a.name.localeCompare(b.name));

    console.log('TaDIY Panel: Found rooms:', this._rooms);

    // Get hub mode entity and options
    const hubModeEntity = Object.values(this._hass.states).find(
      entity => entity.entity_id.startsWith('select.') &&
                entity.entity_id.includes('hub_mode')
    );
    if (hubModeEntity) {
      this._hubMode = hubModeEntity.state;
      this._hubModeOptions = hubModeEntity.attributes.options || [];
      this._hubModeEntityId = hubModeEntity.entity_id;
      console.log('TaDIY Panel: Hub mode:', this._hubMode, 'Options:', this._hubModeOptions);
    }
  }

  render() {
    if (!this._hass) return;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          padding: 16px;
          background: var(--primary-background-color);
          min-height: 100vh;
        }
        .panel-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
          padding: 16px 0;
          border-bottom: 2px solid var(--divider-color);
        }
        .panel-title {
          font-size: 32px;
          font-weight: 300;
          color: var(--primary-text-color);
        }
        .hub-mode {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 16px;
          color: var(--secondary-text-color);
        }
        .hub-mode-selector {
          position: relative;
          display: inline-block;
        }
        .hub-mode-badge {
          padding: 8px 16px;
          border-radius: 16px;
          background: var(--primary-color);
          color: white;
          font-weight: bold;
          text-transform: capitalize;
          cursor: pointer;
          transition: opacity 0.2s;
          border: none;
          font-size: 16px;
        }
        .hub-mode-badge:hover {
          opacity: 0.9;
        }
        .hub-mode-dropdown {
          position: absolute;
          top: 100%;
          right: 0;
          margin-top: 8px;
          background: var(--card-background-color);
          border-radius: 8px;
          box-shadow: 0 4px 12px rgba(0,0,0,0.2);
          min-width: 160px;
          z-index: 1000;
          overflow: hidden;
        }
        .hub-mode-option {
          padding: 12px 16px;
          cursor: pointer;
          text-transform: capitalize;
          transition: background 0.2s;
          color: var(--primary-text-color);
        }
        .hub-mode-option:hover {
          background: var(--secondary-background-color);
        }
        .hub-mode-option.active {
          background: var(--primary-color);
          color: white;
          font-weight: bold;
        }
        .rooms-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
          gap: 16px;
          margin-bottom: 24px;
        }
        .room-card {
          background: var(--card-background-color);
          border-radius: 8px;
          padding: 16px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
          cursor: pointer;
          transition: transform 0.2s, box-shadow 0.2s;
        }
        .room-card:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        .room-name {
          font-size: 18px;
          font-weight: bold;
          margin-bottom: 12px;
          color: var(--primary-text-color);
        }
        .room-temps {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
        }
        .temp-current {
          font-size: 32px;
          font-weight: 300;
          color: var(--primary-text-color);
        }
        .temp-target {
          font-size: 18px;
          color: var(--secondary-text-color);
        }
        .room-status {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px;
          border-radius: 4px;
          background: var(--secondary-background-color);
        }
        .status-icon {
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }
        .status-icon.heating {
          background: #ff9800;
        }
        .status-icon.idle {
          background: #4caf50;
        }
        .status-icon.off {
          background: #9e9e9e;
        }
        .status-text {
          font-size: 14px;
          text-transform: capitalize;
          color: var(--secondary-text-color);
        }
        .edit-schedule-btn {
          width: 100%;
          margin-top: 12px;
          padding: 10px;
          background: var(--primary-color);
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          font-size: 14px;
          font-weight: bold;
          transition: opacity 0.2s;
        }
        .edit-schedule-btn:hover {
          opacity: 0.9;
        }
        .empty-state {
          text-align: center;
          padding: 48px;
          color: var(--secondary-text-color);
        }
        .empty-state-icon {
          font-size: 64px;
          margin-bottom: 16px;
        }
      </style>

      <div class="panel-header">
        <div class="panel-title">TaDIY Climate Control</div>
        <div class="hub-mode">
          <span>Mode:</span>
          <div class="hub-mode-selector">
            <button class="hub-mode-badge" data-action="toggle-mode-dropdown">
              ${this._hubMode}
            </button>
            <div class="hub-mode-dropdown" style="display: none;" data-dropdown>
              ${this._hubModeOptions.map(mode => `
                <div class="hub-mode-option ${mode === this._hubMode ? 'active' : ''}"
                     data-mode="${mode}">
                  ${mode}
                </div>
              `).join('')}
            </div>
          </div>
        </div>
      </div>

      ${this._rooms.length > 0 ? `
        <div class="rooms-grid">
          ${this._rooms.map(room => this.renderRoomCard(room)).join('')}
        </div>
      ` : `
        <div class="empty-state">
          <div class="empty-state-icon">🏠</div>
          <div>No rooms configured yet</div>
          <div>Add rooms in Settings → Devices & Services → TaDIY</div>
        </div>
      `}
    `;

    this.attachEventListeners();
  }

  renderRoomCard(room) {
    const currentTemp = room.current_temp !== null && room.current_temp !== undefined
      ? `${room.current_temp.toFixed(1)}°C`
      : '--°C';

    const targetTemp = room.target_temp !== null && room.target_temp !== undefined
      ? `${room.target_temp.toFixed(1)}°C`
      : '--°C';

    let statusClass = 'idle';
    let statusText = room.hvac_action || room.hvac_mode || 'idle';

    if (statusText === 'heating') {
      statusClass = 'heating';
    } else if (statusText === 'off') {
      statusClass = 'off';
    }

    return `
      <div class="room-card" data-entity="${room.entity_id}">
        <div class="room-name">${room.name}</div>
        <div class="room-temps">
          <div class="temp-current">${currentTemp}</div>
          <div class="temp-target">→ ${targetTemp}</div>
        </div>
        <div class="room-status">
          <div class="status-icon ${statusClass}"></div>
          <div class="status-text">${statusText}</div>
        </div>
        <button class="edit-schedule-btn" data-entity="${room.entity_id}">
          📅 Edit Schedule
        </button>
      </div>
    `;
  }

  attachEventListeners() {
    // Hub mode dropdown toggle
    const modeBtn = this.shadowRoot.querySelector('[data-action="toggle-mode-dropdown"]');
    const dropdown = this.shadowRoot.querySelector('[data-dropdown]');

    if (modeBtn && dropdown) {
      modeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isVisible = dropdown.style.display !== 'none';
        dropdown.style.display = isVisible ? 'none' : 'block';
      });

      // Close dropdown when clicking outside
      document.addEventListener('click', () => {
        dropdown.style.display = 'none';
      });

      // Hub mode options
      this.shadowRoot.querySelectorAll('.hub-mode-option').forEach(option => {
        option.addEventListener('click', async (e) => {
          e.stopPropagation();
          const newMode = option.dataset.mode;

          if (newMode !== this._hubMode && this._hubModeEntityId) {
            try {
              await this._hass.callService('select', 'select_option', {
                entity_id: this._hubModeEntityId,
                option: newMode
              });

              // Update local state
              this._hubMode = newMode;
              dropdown.style.display = 'none';
              this.render();
            } catch (error) {
              console.error('Failed to change hub mode:', error);
              alert(`Failed to change mode: ${error.message}`);
            }
          }
        });
      });
    }

    // Room card clicks - show more-info dialog
    this.shadowRoot.querySelectorAll('.room-card').forEach(card => {
      card.addEventListener('click', (e) => {
        // Don't trigger if clicking the button
        if (e.target.classList.contains('edit-schedule-btn')) return;

        const entityId = card.dataset.entity;
        this.showMoreInfo(entityId);
      });
    });

    // Edit schedule buttons
    this.shadowRoot.querySelectorAll('.edit-schedule-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const entityId = btn.dataset.entity;
        this.showScheduleEditor(entityId);
      });
    });
  }

  showMoreInfo(entityId) {
    // Dispatch Home Assistant event to show more-info dialog
    const event = new Event('hass-more-info', {
      bubbles: true,
      composed: true,
    });
    event.detail = { entityId };
    this.dispatchEvent(event);
  }

  showScheduleEditor(entityId) {
    // Show a popup with the schedule card
    const dialog = document.createElement('div');
    dialog.className = 'schedule-editor-dialog';

    dialog.innerHTML = `
      <div class="dialog-backdrop"></div>
      <div class="dialog-content">
        <div class="dialog-header">
          <h2>Edit Schedule</h2>
          <button class="close-btn">✕</button>
        </div>
        <div class="dialog-body">
          <tadiy-schedule-card></tadiy-schedule-card>
        </div>
      </div>
    `;

    const style = document.createElement('style');
    style.textContent = `
      .schedule-editor-dialog {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 10000;
      }
      .dialog-backdrop {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
      }
      .dialog-content {
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: var(--card-background-color);
        border-radius: 8px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
        max-width: 900px;
        width: 90%;
        max-height: 90vh;
        overflow: auto;
      }
      .dialog-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 16px 24px;
        border-bottom: 1px solid var(--divider-color);
      }
      .dialog-header h2 {
        margin: 0;
        color: var(--primary-text-color);
      }
      .close-btn {
        background: none;
        border: none;
        font-size: 24px;
        cursor: pointer;
        color: var(--secondary-text-color);
        padding: 4px 8px;
      }
      .close-btn:hover {
        color: var(--primary-text-color);
      }
      .dialog-body {
        padding: 16px 24px;
      }
    `;

    this.shadowRoot.appendChild(style);
    this.shadowRoot.appendChild(dialog);

    // Configure the schedule card
    const scheduleCard = dialog.querySelector('tadiy-schedule-card');
    scheduleCard.setConfig({ entity: entityId });
    scheduleCard.hass = this._hass;

    // Close button
    const closeBtn = dialog.querySelector('.close-btn');
    const backdrop = dialog.querySelector('.dialog-backdrop');

    const closeDialog = () => {
      this.shadowRoot.removeChild(dialog);
      this.shadowRoot.removeChild(style);
    };

    closeBtn.addEventListener('click', closeDialog);
    backdrop.addEventListener('click', closeDialog);
  }
}

customElements.define('tadiy-panel', TaDiyPanel);
