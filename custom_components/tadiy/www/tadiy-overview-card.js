/**
 * TaDIY Overview Card - Lovelace card version of the panel
 * Shows all TaDIY rooms with embedded climate cards
 */

class TaDiyOverviewCard extends HTMLElement {
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

  setConfig(config) {
    this._config = config;
  }

  set hass(hass) {
    const oldHass = this._hass;
    this._hass = hass;

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

  getCardSize() {
    return 3 + Math.ceil(this._rooms.length / 3);
  }

  loadRooms() {
    if (!this._hass) return;

    // Find all climate entities that belong to TaDIY rooms
    this._rooms = Object.values(this._hass.states)
      .filter(entity => {
        if (!entity.entity_id.startsWith('climate.')) return false;

        // Check if integration attribute exists and equals 'tadiy'
        if (entity.attributes.integration === 'tadiy') return true;

        // Fallback: check if entity_id contains 'tadiy'
        if (entity.entity_id.includes('tadiy')) return true;

        // Also check if friendly_name mentions TaDIY
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

    // Get hub mode entity and options
    const hubModeEntity = Object.values(this._hass.states).find(
      entity => entity.entity_id.startsWith('select.') &&
                entity.entity_id.includes('hub_mode')
    );
    if (hubModeEntity) {
      this._hubMode = hubModeEntity.state;
      this._hubModeOptions = hubModeEntity.attributes.options || [];
      this._hubModeEntityId = hubModeEntity.entity_id;
    }
  }

  render() {
    if (!this._hass) return;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }
        ha-card {
          padding: 16px;
        }
        .card-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
        }
        .card-title {
          font-size: 24px;
          font-weight: 300;
          color: var(--primary-text-color);
        }
        .hub-mode {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 14px;
          color: var(--secondary-text-color);
        }
        .hub-mode-selector {
          position: relative;
          display: inline-block;
        }
        .hub-mode-badge {
          padding: 6px 12px;
          border-radius: 12px;
          background: var(--primary-color);
          color: white;
          font-weight: bold;
          text-transform: capitalize;
          cursor: pointer;
          transition: opacity 0.2s;
          border: none;
          font-size: 14px;
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
          min-width: 140px;
          z-index: 1000;
          overflow: hidden;
        }
        .hub-mode-option {
          padding: 10px 14px;
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

      <ha-card>
        <div class="card-header">
          <div class="card-title">TaDIY Climate</div>
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
            <div>No TaDIY rooms configured</div>
          </div>
        `}
      </ha-card>
    `;

    this.attachEventListeners();
    this.embedClimateCards();
  }

  renderRoomCard(room) {
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
    this.shadowRoot.querySelectorAll('.room-climate-container').forEach(container => {
      const entityId = container.dataset.climate;
      container.innerHTML = '';

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
      });

      dropdown.addEventListener('click', (e) => {
        e.stopPropagation();
      });

      const closeDropdownHandler = (e) => {
        if (!modeBtn.contains(e.target) && !dropdown.contains(e.target)) {
          dropdown.style.display = 'none';
        }
      };

      document.addEventListener('click', closeDropdownHandler, true);

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

              this._hubMode = newMode;
              dropdown.style.display = 'none';
              this.render();
            } catch (error) {
              console.error('Failed to change hub mode:', error);
            }
          }
        });
      });
    }

    // Edit schedule buttons - open more-info dialog with schedule card
    this.shadowRoot.querySelectorAll('.edit-schedule-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const entityId = btn.dataset.entity;
        this.openScheduleDialog(entityId);
      });
    });
  }

  openScheduleDialog(entityId) {
    // Fire event to open more-info dialog with the climate entity
    const event = new CustomEvent('hass-more-info', {
      bubbles: true,
      composed: true,
      detail: { entityId: entityId }
    });
    this.dispatchEvent(event);

    // Note: Users can add tadiy-schedule-card to their dashboard separately
    // for full schedule editing capabilities
  }
}

// Only define if not already defined
if (!customElements.get('tadiy-overview-card')) {
  customElements.define('tadiy-overview-card', TaDiyOverviewCard);
}

// Register the card with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'tadiy-overview-card',
  name: 'TaDIY Overview Card',
  description: 'Overview of all TaDIY rooms with climate controls',
  preview: false,
  documentationURL: 'https://github.com/Atsharim/TaDIY'
});

console.info(
  '%c TaDIY Overview Card %c v0.2.6.2 ',
  'background-color: #ef5350; color: #fff; font-weight: bold;',
  'background-color: #424242; color: #fff; font-weight: bold;'
);
