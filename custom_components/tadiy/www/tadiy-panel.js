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
    this._hasOpenDialog = false; // Track if schedule editor dialog is open
  }

  set hass(hass) {
    const oldHass = this._hass;
    this._hass = hass;

    // NEVER re-render while dialog is open to prevent dropdown/dialog closure
    if (this._hasOpenDialog) {
      return;
    }

    // Only re-render if relevant state actually changed
    if (!oldHass || this._shouldRerender(oldHass, hass)) {
      this.loadRooms();
      this.render();
    }
  }

  _shouldRerender(oldHass, newHass) {
    // Check if any TaDIY entity or hub mode changed
    const oldStates = Object.keys(oldHass.states).filter(id =>
      id.includes('tadiy') || id.includes('hub_mode')
    );
    const newStates = Object.keys(newHass.states).filter(id =>
      id.includes('tadiy') || id.includes('hub_mode')
    );

    // Different number of entities
    if (oldStates.length !== newStates.length) return true;

    // Check if any relevant entity changed
    for (const entityId of oldStates) {
      const oldState = oldHass.states[entityId];
      const newState = newHass.states[entityId];

      if (!newState ||
          oldState.state !== newState.state ||
          JSON.stringify(oldState.attributes) !== JSON.stringify(newState.attributes)) {
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
        .room-card-wrapper {
          background: var(--card-background-color);
          border-radius: 8px;
          padding: 16px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
          transition: transform 0.2s, box-shadow 0.2s;
          display: flex;
          flex-direction: column;
          gap: 12px;
        }
        .room-card-wrapper:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 8px rgba(0,0,0,0.15);
        }
        .room-climate-container {
          flex: 1;
          min-height: 200px;
        }
        .room-climate-container > * {
          width: 100%;
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
    this.embedClimateCards();
  }

  renderRoomCard(room) {
    // We'll embed the climate card dynamically after render
    return `
      <div class="room-card-wrapper" data-entity="${room.entity_id}">
        <div class="room-climate-container" data-climate="${room.entity_id}">
          <!-- Climate card will be inserted here -->
        </div>
        <button class="edit-schedule-btn" data-entity="${room.entity_id}">
          📅 Edit Schedule
        </button>
      </div>
    `;
  }

  embedClimateCards() {
    // Embed actual Home Assistant climate cards into containers
    this.shadowRoot.querySelectorAll('.room-climate-container').forEach(container => {
      const entityId = container.dataset.climate;

      // Clear existing content
      container.innerHTML = '';

      // Create a thermostat card element
      const card = document.createElement('hui-thermostat-card');
      card.setConfig({
        entity: entityId,
        show_current_as_primary: true
      });
      card.hass = this._hass;

      container.appendChild(card);
    });
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
        this._hasOpenDialog = !isVisible; // Track dropdown state (using same flag as dialog)
      });

      // Prevent dropdown from closing when clicking inside it
      dropdown.addEventListener('click', (e) => {
        e.stopPropagation();
      });

      // Close dropdown when clicking outside
      const closeDropdownHandler = (e) => {
        // Check if click is outside both button and dropdown
        if (!modeBtn.contains(e.target) && !dropdown.contains(e.target)) {
          dropdown.style.display = 'none';
          this._hasOpenDialog = false; // Mark dropdown closed
        }
      };

      // Use capture phase to ensure we catch clicks before they bubble
      document.addEventListener('click', closeDropdownHandler, true);

      // Clean up old listeners if re-rendering
      if (this._dropdownCloseHandler) {
        document.removeEventListener('click', this._dropdownCloseHandler, true);
      }
      this._dropdownCloseHandler = closeDropdownHandler;

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
              this._hasOpenDialog = false; // Mark dropdown closed before render
              this.render();
            } catch (error) {
              console.error('Failed to change hub mode:', error);
              alert(`Failed to change mode: ${error.message}`);
            }
          }
        });
      });
    }

    // Edit schedule buttons
    this.shadowRoot.querySelectorAll('.edit-schedule-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const entityId = btn.dataset.entity;
        this.showScheduleEditor(entityId);
      });
    });
  }

  showScheduleEditor(entityId) {
    // Show a popup with the schedule card
    const dialog = document.createElement('div');
    dialog.className = 'schedule-editor-dialog';

    // Create backdrop
    const backdrop = document.createElement('div');
    backdrop.className = 'dialog-backdrop';

    // Create content container
    const content = document.createElement('div');
    content.className = 'dialog-content';

    // Create header
    const header = document.createElement('div');
    header.className = 'dialog-header';
    const title = document.createElement('h2');
    title.textContent = 'Edit Schedule';
    const closeBtn = document.createElement('button');
    closeBtn.className = 'close-btn';
    closeBtn.textContent = '✕';
    header.appendChild(title);
    header.appendChild(closeBtn);

    // Create body
    const body = document.createElement('div');
    body.className = 'dialog-body';

    // Create schedule card using createElement (not innerHTML!)
    const scheduleCard = document.createElement('tadiy-schedule-card');

    body.appendChild(scheduleCard);
    content.appendChild(header);
    content.appendChild(body);
    dialog.appendChild(backdrop);
    dialog.appendChild(content);

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

    // Auto-detect schedule type based on current day
    const today = new Date().getDay();
    const initialScheduleType = (today === 0 || today === 6) ? 'weekend' : 'weekday';

    // Configure the schedule card AFTER it's added to DOM
    // Open expanded with current hub mode pre-selected
    scheduleCard.setConfig({
      entity: entityId,
      initialMode: this._hubMode || 'normal',
      initialScheduleType: initialScheduleType
    });
    scheduleCard.hass = this._hass;

    // Mark dialog as open
    this._hasOpenDialog = true;

    // Close dialog function
    const closeDialog = () => {
      this._hasOpenDialog = false;
      this.shadowRoot.removeChild(dialog);
      this.shadowRoot.removeChild(style);
    };

    // Close button - don't close on backdrop click to prevent accidental closes
    closeBtn.addEventListener('click', closeDialog);

    // Only close on backdrop click if explicitly clicking it (not on focus loss)
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) {
        closeDialog();
      }
    });
  }
}

// Only define if not already defined
if (!customElements.get('tadiy-panel')) {
  customElements.define('tadiy-panel', TaDiyPanel);
}
