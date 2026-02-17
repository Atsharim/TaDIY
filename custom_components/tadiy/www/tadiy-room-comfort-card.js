/**
 * TaDIY Room Comfort Card
 * Tado-inspired comfort circle visualization showing temperature,
 * humidity, comfort score and level with an animated indicator dot.
 *
 * Config:
 *   entity: sensor.living_room_room_comfort   (room comfort sensor)
 *   name: "Living Room"                       (optional override)
 *   show_score: true                          (optional, default true)
 */

class TaDiyRoomComfortCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass = null;
    this._config = null;
  }

  static getStubConfig() {
    return { entity: '' };
  }

  static getConfigElement() {
    return document.createElement('tadiy-room-comfort-card-editor');
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Please define a comfort sensor entity');
    }
    this._config = {
      show_score: true,
      ...config,
    };
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 3;
  }

  /* ── helpers ───────────────────────────────────────────── */

  _levelLabel(level) {
    const labels = {
      optimal:   'Optimal',
      moderate:  'Comfortable',
      too_warm:  'Too Warm',
      too_cold:  'Too Cold',
      too_dry:   'Too Dry',
      too_humid: 'Too Humid',
      unknown:   'Unknown',
    };
    return labels[level] || level;
  }

  _levelIcon(level) {
    const icons = {
      optimal:   '&#xe86c;', // check_circle
      moderate:  '&#xe86c;',
      too_warm:  '&#xe430;', // wb_sunny / whatshot
      too_cold:  '&#xe80a;', // ac_unit
      too_dry:   '&#xe3c6;', // opacity (inverted concept)
      too_humid: '&#xe798;', // water_drop
      unknown:   '&#xe8fd;', // help
    };
    return icons[level] || icons.unknown;
  }

  /* ── render ────────────────────────────────────────────── */

  _render() {
    if (!this._hass || !this._config) return;

    const state = this._hass.states[this._config.entity];
    if (!state) {
      this.shadowRoot.innerHTML = `
        <ha-card>
          <div style="padding:16px;color:var(--error-color)">
            Entity not found: ${this._config.entity}
          </div>
        </ha-card>`;
      return;
    }

    const score       = Number(state.state) || 0;
    const attrs       = state.attributes || {};
    const level       = attrs.comfort_level || 'unknown';
    const color       = attrs.comfort_color || '#9E9E9E';
    const temp        = attrs.temperature;
    const humidity    = attrs.humidity;
    const pos         = attrs.comfort_position || { x: 50, y: 50 };
    const tempScore   = attrs.temp_score;
    const humScore    = attrs.humidity_score;
    const name        = this._config.name || state.attributes.friendly_name || 'Room Comfort';
    const showScore   = this._config.show_score !== false;

    // SVG circle parameters
    const cx = 90, cy = 90, r = 75;
    const circumference = 2 * Math.PI * r;
    const filled = circumference * (score / 100);
    const gap    = circumference - filled;

    // Indicator dot position on the comfort field (inside the circle)
    const dotAngle = ((score / 100) * 270 - 135) * (Math.PI / 180);
    const dotR = r - 12;
    const dotX = cx + dotR * Math.cos(dotAngle);
    const dotY = cy + dotR * Math.sin(dotAngle);

    // Softer background tint based on comfort color
    const bgTint = color + '18';

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card {
          padding: 16px;
          overflow: hidden;
        }
        .header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 12px;
        }
        .title {
          font-size: 16px;
          font-weight: 500;
          color: var(--primary-text-color);
        }
        .level-badge {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          padding: 3px 10px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 600;
          color: #fff;
          background: ${color};
        }
        .level-badge .mi {
          font-family: "Material Icons";
          font-size: 14px;
          -webkit-font-feature-settings: 'liga';
        }

        .circle-wrap {
          display: flex;
          justify-content: center;
          position: relative;
        }
        svg.ring {
          width: 180px;
          height: 180px;
          transform: rotate(-225deg);
        }
        .ring-bg {
          fill: none;
          stroke: var(--divider-color, #e0e0e0);
          stroke-width: 8;
          stroke-dasharray: ${circumference * 0.75} ${circumference * 0.25};
          stroke-linecap: round;
        }
        .ring-fg {
          fill: none;
          stroke: ${color};
          stroke-width: 8;
          stroke-dasharray: ${Math.min(filled, circumference * 0.75)} ${circumference};
          stroke-linecap: round;
          transition: stroke-dasharray 0.6s ease, stroke 0.6s ease;
        }

        .center-info {
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          text-align: center;
        }
        .score-value {
          font-size: 40px;
          font-weight: 700;
          line-height: 1;
          color: ${color};
          transition: color 0.6s ease;
        }
        .score-unit {
          font-size: 16px;
          font-weight: 400;
          color: var(--secondary-text-color);
        }
        .score-label {
          font-size: 13px;
          color: var(--secondary-text-color);
          margin-top: 2px;
        }

        .metrics {
          display: flex;
          justify-content: center;
          gap: 32px;
          margin-top: 12px;
        }
        .metric {
          text-align: center;
        }
        .metric-value {
          font-size: 22px;
          font-weight: 600;
          color: var(--primary-text-color);
        }
        .metric-unit {
          font-size: 13px;
          color: var(--secondary-text-color);
        }
        .metric-label {
          font-size: 11px;
          color: var(--secondary-text-color);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-top: 2px;
        }
        .metric-bar {
          width: 60px;
          height: 4px;
          border-radius: 2px;
          background: var(--divider-color, #e0e0e0);
          margin: 4px auto 0;
          overflow: hidden;
        }
        .metric-bar-fill {
          height: 100%;
          border-radius: 2px;
          transition: width 0.6s ease, background 0.6s ease;
        }

        .no-data {
          text-align: center;
          padding: 24px 0;
          color: var(--secondary-text-color);
          font-size: 14px;
        }
      </style>

      <ha-card>
        <div class="header">
          <span class="title">${name}</span>
          <span class="level-badge">${this._levelLabel(level)}</span>
        </div>

        ${temp != null ? `
          <div class="circle-wrap">
            <svg class="ring" viewBox="0 0 180 180">
              <circle class="ring-bg" cx="${cx}" cy="${cy}" r="${r}"/>
              <circle class="ring-fg" cx="${cx}" cy="${cy}" r="${r}"/>
            </svg>
            <div class="center-info">
              ${showScore ? `
                <div class="score-value">${score}<span class="score-unit">%</span></div>
                <div class="score-label">Comfort</div>
              ` : `
                <div class="score-value" style="font-size:32px">${temp != null ? temp.toFixed(1) + '°' : '--'}</div>
                <div class="score-label">${this._levelLabel(level)}</div>
              `}
            </div>
          </div>

          <div class="metrics">
            <div class="metric">
              <div class="metric-value">${temp != null ? temp.toFixed(1) : '--'}<span class="metric-unit">°C</span></div>
              <div class="metric-label">Temperature</div>
              ${tempScore != null ? `
                <div class="metric-bar">
                  <div class="metric-bar-fill" style="width:${tempScore}%;background:${tempScore >= 80 ? '#4CAF50' : tempScore >= 50 ? '#FF9800' : '#f44336'}"></div>
                </div>
              ` : ''}
            </div>
            <div class="metric">
              <div class="metric-value">${humidity != null ? humidity.toFixed(0) : '--'}<span class="metric-unit">%</span></div>
              <div class="metric-label">Humidity</div>
              ${humScore != null ? `
                <div class="metric-bar">
                  <div class="metric-bar-fill" style="width:${humScore}%;background:${humScore >= 80 ? '#4CAF50' : humScore >= 50 ? '#FF9800' : '#f44336'}"></div>
                </div>
              ` : ''}
            </div>
          </div>
        ` : `
          <div class="no-data">No temperature data available</div>
        `}
      </ha-card>
    `;
  }
}

customElements.define('tadiy-room-comfort-card', TaDiyRoomComfortCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'tadiy-room-comfort-card',
  name: 'TaDIY Room Comfort',
  description: 'Tado-inspired comfort circle showing temperature, humidity and comfort score',
  preview: true,
  documentationURL: 'https://github.com/Atsharim/TaDIY',
});
