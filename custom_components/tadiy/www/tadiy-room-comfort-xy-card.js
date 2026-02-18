/**
 * TaDIY Room Comfort XY Card (Tado-inspired)
 * 2D comfort field visualization showing temperature vs humidity
 * with optimal zone in center and current position as animated dot
 *
 * Config:
 *   entity: sensor.living_room_room_comfort
 *   name: "Living Room"                       (optional)
 *   show_score: true                          (optional, show score or just position)
 *   temp_range: [19, 22]                      (optional, temperature range for x-axis)
 *   humidity_range: [40, 60]                  (optional, humidity range for y-axis)
 */

class TaDiyRoomComfortXYCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass = null;
    this._config = null;
  }

  static getStubConfig() {
    return { entity: '' };
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Please define a comfort sensor entity');
    }
    this._config = {
      show_score: true,
      temp_range: [19, 22],  // Default temp range (optimal comfort zone)
      humidity_range: [40, 60],  // Default humidity range (optimal comfort zone)
      ...config,
    };
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 4;
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

  _getZoneColor(temp, humidity) {
    // Optimal zone: 20-22°C, 45-55%
    if (temp >= 20 && temp <= 22 && humidity >= 45 && humidity <= 55) {
      return '#4CAF50';  // Green
    }
    // Good zone: 19-23°C, 40-60%
    if (temp >= 19 && temp <= 23 && humidity >= 40 && humidity <= 60) {
      return '#8BC34A';  // Light green
    }
    // Acceptable zone: 18-24°C, 35-65%
    if (temp >= 18 && temp <= 24 && humidity >= 35 && humidity <= 65) {
      return '#FFC107';  // Amber
    }
    // Poor zone
    return '#FF5722';  // Red
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
    const tempScore   = attrs.temp_score;
    const humScore    = attrs.humidity_score;
    const name        = this._config.name || state.attributes.friendly_name || 'Room Comfort';
    const showScore   = this._config.show_score !== false;

    // XY Diagram parameters
    const [tempMin, tempMax] = this._config.temp_range;
    const [humMin, humMax] = this._config.humidity_range;
    const gridSize = 200;  // SVG grid size
    const padding = 20;

    // Calculate current position on grid
    let dotX = gridSize / 2;
    let dotY = gridSize / 2;
    if (temp != null && humidity != null) {
      // Map temperature to x-axis (left = cold, right = warm)
      dotX = padding + ((temp - tempMin) / (tempMax - tempMin)) * (gridSize - 2 * padding);
      // Map humidity to y-axis (top = dry, bottom = humid)
      dotY = padding + ((humMax - humidity) / (humMax - humMin)) * (gridSize - 2 * padding);

      // Clamp to grid bounds
      dotX = Math.max(padding, Math.min(gridSize - padding, dotX));
      dotY = Math.max(padding, Math.min(gridSize - padding, dotY));
    }

    // Define comfort zones as rectangles
    const optimalZone = {
      x1: padding + ((20 - tempMin) / (tempMax - tempMin)) * (gridSize - 2 * padding),
      x2: padding + ((22 - tempMin) / (tempMax - tempMin)) * (gridSize - 2 * padding),
      y1: padding + ((humMax - 55) / (humMax - humMin)) * (gridSize - 2 * padding),
      y2: padding + ((humMax - 45) / (humMax - humMin)) * (gridSize - 2 * padding),
    };

    const goodZone = {
      x1: padding + ((19 - tempMin) / (tempMax - tempMin)) * (gridSize - 2 * padding),
      x2: padding + ((23 - tempMin) / (tempMax - tempMin)) * (gridSize - 2 * padding),
      y1: padding + ((humMax - 60) / (humMax - humMin)) * (gridSize - 2 * padding),
      y2: padding + ((humMax - 40) / (humMax - humMin)) * (gridSize - 2 * padding),
    };

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

        .xy-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 16px;
        }

        .xy-diagram {
          position: relative;
          width: 240px;
          height: 240px;
        }

        svg.comfort-grid {
          width: 100%;
          height: 100%;
        }

        .zone-optimal {
          fill: #4CAF50;
          opacity: 0.3;
        }

        .zone-good {
          fill: #8BC34A;
          opacity: 0.2;
        }

        .grid-line {
          stroke: var(--divider-color, #e0e0e0);
          stroke-width: 1;
          opacity: 0.5;
        }

        .axis-label {
          fill: var(--secondary-text-color);
          font-size: 10px;
          font-weight: 500;
        }

        .center-cross {
          stroke: var(--divider-color, #e0e0e0);
          stroke-width: 1.5;
          opacity: 0.3;
          stroke-dasharray: 3, 3;
        }

        .current-dot {
          fill: ${color};
          stroke: #fff;
          stroke-width: 2.5;
          filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
          animation: pulse 2s ease-in-out infinite;
        }

        @keyframes pulse {
          0%, 100% { r: 6; opacity: 1; }
          50% { r: 7; opacity: 0.8; }
        }

        .score-display {
          text-align: center;
        }

        .score-value {
          font-size: 36px;
          font-weight: 700;
          color: ${color};
          line-height: 1;
        }

        .score-unit {
          font-size: 18px;
          font-weight: 400;
        }

        .score-label {
          font-size: 13px;
          color: var(--secondary-text-color);
          margin-top: 4px;
        }

        .metrics {
          display: flex;
          justify-content: center;
          gap: 32px;
          margin-top: 8px;
        }

        .metric {
          text-align: center;
        }

        .metric-value {
          font-size: 20px;
          font-weight: 600;
          color: var(--primary-text-color);
        }

        .metric-unit {
          font-size: 12px;
          color: var(--secondary-text-color);
        }

        .metric-label {
          font-size: 11px;
          color: var(--secondary-text-color);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-top: 2px;
        }

        .legend {
          display: flex;
          justify-content: center;
          gap: 16px;
          margin-top: 12px;
          font-size: 11px;
        }

        .legend-item {
          display: flex;
          align-items: center;
          gap: 4px;
        }

        .legend-color {
          width: 12px;
          height: 12px;
          border-radius: 2px;
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

        ${temp != null && humidity != null ? `
          <div class="xy-container">
            <!-- XY Diagram -->
            <div class="xy-diagram">
              <svg class="comfort-grid" viewBox="0 0 ${gridSize} ${gridSize}">
                <!-- Background zones -->
                <!-- Good zone (outer) -->
                <rect
                  x="${goodZone.x1}" y="${goodZone.y1}"
                  width="${goodZone.x2 - goodZone.x1}"
                  height="${goodZone.y2 - goodZone.y1}"
                  class="zone-good"
                  rx="4"
                />
                <!-- Optimal zone (center) -->
                <rect
                  x="${optimalZone.x1}" y="${optimalZone.y1}"
                  width="${optimalZone.x2 - optimalZone.x1}"
                  height="${optimalZone.y2 - optimalZone.y1}"
                  class="zone-optimal"
                  rx="4"
                />

                <!-- Grid lines -->
                <!-- Vertical center line (21°C) -->
                <line
                  x1="${gridSize / 2}" y1="${padding}"
                  x2="${gridSize / 2}" y2="${gridSize - padding}"
                  class="center-cross"
                />
                <!-- Horizontal center line (50%) -->
                <line
                  x1="${padding}" y1="${gridSize / 2}"
                  x2="${gridSize - padding}" y2="${gridSize / 2}"
                  class="center-cross"
                />

                <!-- Axis labels -->
                <!-- Temperature (X-axis) -->
                <text x="${padding}" y="${gridSize - 5}" class="axis-label">${tempMin}°</text>
                <text x="${gridSize - padding - 20}" y="${gridSize - 5}" class="axis-label">${tempMax}°</text>
                <text x="${gridSize / 2 - 15}" y="${gridSize - 5}" class="axis-label">Temp</text>

                <!-- Humidity (Y-axis) -->
                <text x="5" y="${gridSize - padding}" class="axis-label">${humMin}%</text>
                <text x="5" y="${padding + 10}" class="axis-label">${humMax}%</text>
                <text
                  x="${padding / 2 - 5}" y="${gridSize / 2}"
                  class="axis-label"
                  transform="rotate(-90, ${padding / 2 - 5}, ${gridSize / 2})"
                >Humidity</text>

                <!-- Current position dot -->
                <circle
                  cx="${dotX}" cy="${dotY}"
                  class="current-dot"
                />
              </svg>
            </div>

            <!-- Score Display -->
            ${showScore ? `
              <div class="score-display">
                <div class="score-value">${score}<span class="score-unit">%</span></div>
                <div class="score-label">Comfort Score</div>
              </div>
            ` : ''}

            <!-- Metrics -->
            <div class="metrics">
              <div class="metric">
                <div class="metric-value">${temp.toFixed(1)}<span class="metric-unit">°C</span></div>
                <div class="metric-label">Temperature</div>
              </div>
              <div class="metric">
                <div class="metric-value">${humidity.toFixed(0)}<span class="metric-unit">%</span></div>
                <div class="metric-label">Humidity</div>
              </div>
            </div>

            <!-- Legend -->
            <div class="legend">
              <div class="legend-item">
                <div class="legend-color" style="background: #4CAF50; opacity: 0.7;"></div>
                <span>Optimal</span>
              </div>
              <div class="legend-item">
                <div class="legend-color" style="background: #8BC34A; opacity: 0.7;"></div>
                <span>Good</span>
              </div>
            </div>
          </div>
        ` : `
          <div class="no-data">No temperature/humidity data available</div>
        `}
      </ha-card>
    `;
  }
}

customElements.define('tadiy-room-comfort-xy-card', TaDiyRoomComfortXYCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'tadiy-room-comfort-xy-card',
  name: 'TaDIY Room Comfort XY',
  description: 'Tado-inspired 2D comfort field showing temperature vs humidity',
  preview: true,
  documentationURL: 'https://github.com/Atsharim/TaDIY',
});
