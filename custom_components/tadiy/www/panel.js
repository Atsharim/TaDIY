/**
 * TaDIY Schedules Panel
 * Custom panel for centralized schedule management
 */

class TadiySchedulesPanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._panel = null;
    this._rooms = [];
    this._selectedRoom = null;
  }

  set panel(panel) {
    this._panel = panel;
  }

  set hass(hass) {
    this._hass = hass;
    this.loadRooms();
  }

  loadRooms() {
    if (!this._hass) return;

    // Find all TaDIY climate entities
    this._rooms = Object.keys(this._hass.states)
      .filter(entity_id => entity_id.startsWith('climate.'))
      .map(entity_id => {
        const state = this._hass.states[entity_id];
        // Check if it's a TaDIY entity by checking domain
        if (state.context && state.attributes.integration === 'tadiy') {
          return {
            entity_id: entity_id,
            name: state.attributes.friendly_name || entity_id,
          };
        }
        return null;
      })
      .filter(room => room !== null);

    this.render();
  }

  render() {
    if (!this._hass) return;

    this.innerHTML = `
      <style>
        .panel-container {
          padding: 20px;
          max-width: 1200px;
          margin: 0 auto;
        }
        .panel-header {
          margin-bottom: 24px;
        }
        .panel-title {
          font-size: 32px;
          font-weight: 300;
          margin: 0 0 8px 0;
          color: var(--primary-text-color);
        }
        .panel-subtitle {
          font-size: 16px;
          color: var(--secondary-text-color);
          margin: 0;
        }
        .rooms-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
          gap: 16px;
          margin-top: 24px;
        }
        .room-card {
          background: var(--card-background-color);
          border-radius: 12px;
          padding: 20px;
          box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,0.1));
          cursor: pointer;
          transition: transform 0.2s, box-shadow 0.2s;
        }
        .room-card:hover {
          transform: translateY(-2px);
          box-shadow: var(--ha-card-box-shadow, 0 4px 8px rgba(0,0,0,0.15));
        }
        .room-card.editing {
          grid-column: 1 / -1;
          cursor: default;
        }
        .room-card.editing:hover {
          transform: none;
        }
        .room-name {
          font-size: 20px;
          font-weight: 500;
          margin: 0 0 12px 0;
          color: var(--primary-text-color);
        }
        .room-preview {
          margin-top: 16px;
        }
        .back-button {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 8px 16px;
          background: var(--primary-color);
          color: white;
          border: none;
          border-radius: 8px;
          cursor: pointer;
          font-size: 14px;
          margin-bottom: 16px;
        }
        .back-button:hover {
          opacity: 0.9;
        }
        .no-rooms {
          text-align: center;
          padding: 40px;
          color: var(--secondary-text-color);
        }
        .no-rooms-icon {
          font-size: 64px;
          margin-bottom: 16px;
          opacity: 0.3;
        }
      </style>

      <div class="panel-container">
        ${this._selectedRoom ? this.renderEditor() : this.renderOverview()}
      </div>
    `;

    this.attachListeners();
  }

  renderOverview() {
    if (this._rooms.length === 0) {
      return `
        <div class="panel-header">
          <h1 class="panel-title">TaDIY Schedules</h1>
          <p class="panel-subtitle">Manage heating schedules for all rooms</p>
        </div>
        <div class="no-rooms">
          <div class="no-rooms-icon">📅</div>
          <h2>No rooms configured</h2>
          <p>Add rooms in Settings → Devices & Services → TaDIY</p>
        </div>
      `;
    }

    return `
      <div class="panel-header">
        <h1 class="panel-title">TaDIY Schedules</h1>
        <p class="panel-subtitle">Manage heating schedules for ${this._rooms.length} room(s)</p>
      </div>

      <div class="rooms-grid">
        ${this._rooms.map(room => `
          <div class="room-card" data-entity="${room.entity_id}">
            <h2 class="room-name">${room.name}</h2>
            <div class="room-preview">
              <p style="color: var(--secondary-text-color); margin: 0;">
                Click to edit schedules
              </p>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }

  renderEditor() {
    return `
      <button class="back-button">
        ← Back to Overview
      </button>
      <div class="room-card editing">
        <tadiy-schedule-card entity="${this._selectedRoom}"></tadiy-schedule-card>
      </div>
    `;
  }

  attachListeners() {
    // Room card clicks
    this.querySelectorAll('.room-card:not(.editing)').forEach(card => {
      card.addEventListener('click', (e) => {
        const entity = card.getAttribute('data-entity');
        this._selectedRoom = entity;
        this.render();
      });
    });

    // Back button
    const backButton = this.querySelector('.back-button');
    if (backButton) {
      backButton.addEventListener('click', () => {
        this._selectedRoom = null;
        this.render();
      });
    }
  }

  connectedCallback() {
    // Load the schedule card component
    if (!customElements.get('tadiy-schedule-card')) {
      import('/tadiy/tadiy-schedule-card.js');
    }
  }
}

customElements.define('tadiy-schedules-panel', TadiySchedulesPanel);
