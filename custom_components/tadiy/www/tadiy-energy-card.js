/**
 * TaDIY Energy Savings Card
 * Visual representation of energy savings from smart heating decisions
 *
 * Config:
 *   entity: sensor.living_room_energy_savings_today
 *   name: "Living Room"                       (optional)
 *   period: "today"                           (today/week/month/last_30_days)
 *   show_breakdown: true                      (show breakdown by category)
 */

class TaDiyEnergyIQCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._hass = null;
    this._config = null;
  }

  static getStubConfig() {
    return { entity: '', period: 'today' };
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Please define an energy savings sensor entity');
    }
    this._config = {
      period: 'today',
      show_breakdown: true,
      ...config,
    };
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return this._config.show_breakdown ? 5 : 3;
  }

  /* ── helpers ───────────────────────────────────────────── */

  _formatEnergy(kwh) {
    if (kwh < 1) return `${(kwh * 1000).toFixed(0)} Wh`;
    return `${kwh.toFixed(2)} kWh`;
  }

  _formatMoney(euros) {
    return `${euros.toFixed(2)} €`;
  }

  _getCategoryIcon(category) {
    const icons = {
      window: '&#xf23e;',  // window-open
      away: '&#xe7fd;',    // directions_walk
      weather: '&#xe430;', // wb_sunny
    };
    return icons[category] || '&#xe86c;';
  }

  _getCategoryLabel(category) {
    const labels = {
      window: 'Fenster offen',
      away: 'Niemand zuhause',
      weather: 'Warmes Wetter',
    };
    return labels[category] || category;
  }

  _getCategoryColor(category) {
    const colors = {
      window: '#2196F3',  // Blue
      away: '#FF9800',    // Orange
      weather: '#FFC107', // Amber
    };
    return colors[category] || '#9E9E9E';
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

    const attrs = state.attributes || {};
    const period = this._config.period || 'today';

    // Get values based on selected period
    let kwh, euros, hours, windowHours, awayHours, weatherHours;

    if (period === 'week') {
      kwh = attrs.total_kwh_this_week || 0;
      euros = attrs.total_euros_this_week || 0;
      hours = attrs.total_hours_this_week || 0;
      // For breakdown, we only have today's data
      windowHours = attrs.window_open_hours || 0;
      awayHours = attrs.away_mode_hours || 0;
      weatherHours = attrs.weather_hours || 0;
    } else if (period === 'month') {
      kwh = attrs.total_kwh_this_month || 0;
      euros = attrs.total_euros_this_month || 0;
      hours = attrs.total_hours_this_month || 0;
      windowHours = attrs.window_open_hours || 0;
      awayHours = attrs.away_mode_hours || 0;
      weatherHours = attrs.weather_hours || 0;
    } else if (period === 'last_30_days') {
      kwh = attrs.total_kwh_last_30_days || 0;
      euros = attrs.total_euros_last_30_days || 0;
      hours = attrs.total_hours_last_30_days || 0;
      windowHours = attrs.window_open_hours || 0;
      awayHours = attrs.away_mode_hours || 0;
      weatherHours = attrs.weather_hours || 0;
    } else {  // today
      kwh = attrs.total_kwh_today || Number(state.state) || 0;
      euros = attrs.total_euros_today || 0;
      hours = attrs.total_hours_today || 0;
      windowHours = attrs.window_open_hours || 0;
      awayHours = attrs.away_mode_hours || 0;
      weatherHours = attrs.weather_hours || 0;
    }

    const name = this._config.name || state.attributes.friendly_name?.replace(' Energy Savings Today', '') || 'Energy Savings';
    const showBreakdown = this._config.show_breakdown !== false;

    // Calculate percentages for breakdown
    const totalHours = windowHours + awayHours + weatherHours;
    const windowPercent = totalHours > 0 ? (windowHours / totalHours) * 100 : 0;
    const awayPercent = totalHours > 0 ? (awayHours / totalHours) * 100 : 0;
    const weatherPercent = totalHours > 0 ? (weatherHours / totalHours) * 100 : 0;

    // Period labels
    const periodLabels = {
      today: 'Heute',
      week: 'Diese Woche',
      month: 'Dieser Monat',
      last_30_days: 'Letzte 30 Tage',
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
          margin-bottom: 16px;
        }

        .title {
          font-size: 16px;
          font-weight: 500;
          color: var(--primary-text-color);
        }

        .period-badge {
          padding: 4px 12px;
          border-radius: 12px;
          font-size: 12px;
          font-weight: 600;
          background: var(--primary-color);
          color: #fff;
        }

        .savings-summary {
          display: flex;
          justify-content: space-around;
          padding: 20px 0;
          background: linear-gradient(135deg, #4CAF5010 0%, #4CAF5020 100%);
          border-radius: 12px;
          margin-bottom: 16px;
        }

        .summary-item {
          text-align: center;
        }

        .summary-value {
          font-size: 28px;
          font-weight: 700;
          color: #4CAF50;
          line-height: 1;
        }

        .summary-unit {
          font-size: 16px;
          font-weight: 400;
          color: var(--secondary-text-color);
        }

        .summary-label {
          font-size: 12px;
          color: var(--secondary-text-color);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-top: 4px;
        }

        .breakdown {
          margin-top: 16px;
        }

        .breakdown-title {
          font-size: 13px;
          font-weight: 600;
          color: var(--secondary-text-color);
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 12px;
        }

        .category-item {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 10px 0;
          border-bottom: 1px solid var(--divider-color);
        }

        .category-item:last-child {
          border-bottom: none;
        }

        .category-icon {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-family: "Material Icons";
          font-size: 20px;
          color: #fff;
          flex-shrink: 0;
        }

        .category-info {
          flex: 1;
          min-width: 0;
        }

        .category-name {
          font-size: 14px;
          font-weight: 500;
          color: var(--primary-text-color);
          margin-bottom: 4px;
        }

        .category-bar-container {
          width: 100%;
          height: 6px;
          background: var(--divider-color);
          border-radius: 3px;
          overflow: hidden;
        }

        .category-bar {
          height: 100%;
          border-radius: 3px;
          transition: width 0.6s ease;
        }

        .category-value {
          text-align: right;
          min-width: 80px;
        }

        .category-hours {
          font-size: 16px;
          font-weight: 600;
          color: var(--primary-text-color);
        }

        .category-percent {
          font-size: 11px;
          color: var(--secondary-text-color);
        }

        .no-data {
          text-align: center;
          padding: 32px 0;
          color: var(--secondary-text-color);
        }

        .no-data-icon {
          font-family: "Material Icons";
          font-size: 48px;
          opacity: 0.3;
          margin-bottom: 8px;
        }

        .leaf-icon {
          color: #4CAF50;
          font-size: 32px;
          margin-bottom: 8px;
        }
      </style>

      <ha-card>
        <div class="header">
          <span class="title">${name}</span>
          <span class="period-badge">${periodLabels[period]}</span>
        </div>

        ${kwh > 0 || hours > 0 ? `
          <!-- Savings Summary -->
          <div class="savings-summary">
            <div class="summary-item">
              <div style="font-size: 32px; margin-bottom: 8px;">🌱</div>
              <div class="summary-value">${this._formatEnergy(kwh)}</div>
              <div class="summary-label">Energie gespart</div>
            </div>
            <div class="summary-item">
              <div style="font-size: 32px; margin-bottom: 8px;">💰</div>
              <div class="summary-value">${this._formatMoney(euros)}</div>
              <div class="summary-label">Geld gespart</div>
            </div>
            <div class="summary-item">
              <div style="font-size: 32px; margin-bottom: 8px;">⏱️</div>
              <div class="summary-value">${hours.toFixed(1)}<span class="summary-unit">h</span></div>
              <div class="summary-label">Vermieden</div>
            </div>
          </div>

          <!-- Breakdown by Category -->
          ${showBreakdown && totalHours > 0 ? `
            <div class="breakdown">
              <div class="breakdown-title">Aufschlüsselung</div>

              <!-- Window Open -->
              ${windowHours > 0 ? `
                <div class="category-item">
                  <div class="category-icon" style="background: ${this._getCategoryColor('window')}">
                    🪟
                  </div>
                  <div class="category-info">
                    <div class="category-name">${this._getCategoryLabel('window')}</div>
                    <div class="category-bar-container">
                      <div class="category-bar" style="width: ${windowPercent}%; background: ${this._getCategoryColor('window')}"></div>
                    </div>
                  </div>
                  <div class="category-value">
                    <div class="category-hours">${windowHours.toFixed(1)}h</div>
                    <div class="category-percent">${windowPercent.toFixed(0)}%</div>
                  </div>
                </div>
              ` : ''}

              <!-- Away Mode -->
              ${awayHours > 0 ? `
                <div class="category-item">
                  <div class="category-icon" style="background: ${this._getCategoryColor('away')}">
                    🚶
                  </div>
                  <div class="category-info">
                    <div class="category-name">${this._getCategoryLabel('away')}</div>
                    <div class="category-bar-container">
                      <div class="category-bar" style="width: ${awayPercent}%; background: ${this._getCategoryColor('away')}"></div>
                    </div>
                  </div>
                  <div class="category-value">
                    <div class="category-hours">${awayHours.toFixed(1)}h</div>
                    <div class="category-percent">${awayPercent.toFixed(0)}%</div>
                  </div>
                </div>
              ` : ''}

              <!-- Weather -->
              ${weatherHours > 0 ? `
                <div class="category-item">
                  <div class="category-icon" style="background: ${this._getCategoryColor('weather')}">
                    ☀️
                  </div>
                  <div class="category-info">
                    <div class="category-name">${this._getCategoryLabel('weather')}</div>
                    <div class="category-bar-container">
                      <div class="category-bar" style="width: ${weatherPercent}%; background: ${this._getCategoryColor('weather')}"></div>
                    </div>
                  </div>
                  <div class="category-value">
                    <div class="category-hours">${weatherHours.toFixed(1)}h</div>
                    <div class="category-percent">${weatherPercent.toFixed(0)}%</div>
                  </div>
                </div>
              ` : ''}
            </div>
          ` : ''}
        ` : `
          <div class="no-data">
            <div class="no-data-icon">💡</div>
            <div>Noch keine Einsparungen für ${periodLabels[period].toLowerCase()}</div>
          </div>
        `}
      </ha-card>
    `;
  }
}

customElements.define('tadiy-energy-card', TaDiyEnergyIQCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'tadiy-energy-card',
  name: 'TaDIY Energy Savings',
  description: 'Tado-inspired energy savings visualization with breakdown',
  preview: true,
  documentationURL: 'https://github.com/Atsharim/TaDIY',
});
