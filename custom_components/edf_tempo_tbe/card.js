/*
 * EDF Tempo Rev TBE Lovelace card
 *
 * The EDF Tempo Rev TBE integration exposes and registers this module automatically.
 * Use type: custom:edf-tempo-card, type: custom:edf-tempo-season-card,
 *    type: custom:edf-tempo-season-calendar-card or type: custom:edf-tempo-month-card
 */

const EDF_TEMPO_CARD_TRANSLATIONS = {
  en: {
    blue_days: "Blue days",
    calendar_title: "EDF Tempo Rev TBE Calendar",
    columns: "Columns",
    display_days: "Days to display",
    display_days_both: "Today and tomorrow",
    display_days_today: "Today only",
    display_days_tomorrow: "Tomorrow only",
    update_info: "Tomorrow: update information",
    update_info_hidden: "Hidden",
    update_info_top: "Below the title",
    update_info_bottom: "Below the days",
    rte_updated: "Tomorrow · RTE update",
    rte_updated_after_fetch: "RTE date is later than retrieval",
    last_fetch: "Last successful retrieval",
    timestamp_unknown: "Not available",
    daily_today_entity: "Today's entity",
    daily_tomorrow_entity: "Tomorrow's entity",
    load_month_failed: "Failed to load month data",
    load_season_failed: "Failed to load season data",
    month_help: "This card automatically uses the displayed month and navigation arrows.",
    monthly_title: "EDF Tempo Rev TBE Monthly",
    next: "Next",
    previous: "Previous",
    red_days: "Red days",
    season_entity: "Season summary entity",
    season_summary_title: "Season summary",
    season_updated_on: "Updated on",
    season_update_unknown: "Update date unknown",
    season_to: "to",
    season_unavailable: "No season summary known yet",
    title: "Title",
    white_days: "White days",
  },
  fr: {
    blue_days: "Jours bleus",
    calendar_title: "Calendrier EDF Tempo Rev TBE",
    columns: "Colonnes",
    display_days: "Jours à afficher",
    display_days_both: "Aujourd’hui et demain",
    display_days_today: "Aujourd’hui uniquement",
    display_days_tomorrow: "Demain uniquement",
    update_info: "Demain : informations de mise à jour",
    update_info_hidden: "Masquées",
    update_info_top: "Sous le titre",
    update_info_bottom: "Sous les jours",
    rte_updated: "Demain · Mise à jour RTE",
    rte_updated_after_fetch: "Date RTE postérieure à la récupération",
    last_fetch: "Dernière récupération réussie",
    timestamp_unknown: "Non disponible",
    daily_today_entity: "Entité d'aujourd'hui",
    daily_tomorrow_entity: "Entité de demain",
    load_month_failed: "Impossible de charger les données du mois",
    load_season_failed: "Impossible de charger les données de la saison",
    month_help: "Cette carte utilise automatiquement le mois affiché et les flèches de navigation.",
    monthly_title: "EDF Tempo Rev TBE mensuel",
    next: "Suivant",
    previous: "Précédent",
    red_days: "Jours rouges",
    season_entity: "Entité de synthèse de la saison",
    season_summary_title: "Synthèse de la saison",
    season_updated_on: "MAJ le",
    season_update_unknown: "Date de MAJ inconnue",
    season_to: "au",
    season_unavailable: "Aucune synthèse connue pour cette saison",
    title: "Titre",
    white_days: "Jours blancs",
  },
};

function edfTempoCardIsFrench(hass) {
  const language =
    hass?.locale?.language ||
    hass?.language ||
    hass?.selectedLanguage ||
    navigator.language ||
    "en";
  return String(language).toLowerCase().startsWith("fr");
}

function edfTempoCardText(hass, key) {
  const language = edfTempoCardIsFrench(hass) ? "fr" : "en";
  return EDF_TEMPO_CARD_TRANSLATIONS[language][key] || key;
}

function edfTempoDailyColumns(value) {
  const parsed = Number.parseInt(String(value ?? 2), 10);
  return Number.isNaN(parsed) ? 2 : Math.min(2, Math.max(1, parsed));
}

function edfTempoDisplayDays(value) {
  return ["today", "tomorrow"].includes(value) ? value : "both";
}

function edfTempoUpdateInfo(value) {
  return ["top", "bottom"].includes(value) ? value : "hidden";
}

let edfTempoEntityPickerLoading;

async function edfTempoLoadEntityPicker() {
  if (customElements.get("ha-entity-picker")) return;
  if (!edfTempoEntityPickerLoading) {
    edfTempoEntityPickerLoading = (async () => {
      const helpers = await window.loadCardHelpers();
      const card = await helpers.createCardElement({ type: "entities", entities: [] });
      await card.constructor.getConfigElement();
      if (!customElements.get("ha-entity-picker")) {
        throw new Error("Home Assistant entity picker is not registered");
      }
    })().finally(() => { edfTempoEntityPickerLoading = undefined; });
  }
  try {
    await edfTempoEntityPickerLoading;
  } catch (error) {
    console.warn("EDF Tempo Rev TBE: entity picker loading failed; using text inputs.", error);
  }
}

function edfTempoSyncEntityControls(editor, fields) {
  if (editor._usesEntityPicker) {
    for (const id of fields) {
      const picker = editor.shadowRoot.querySelector(`#${id}`);
      picker.hass = editor._hass;
      picker.includeDomains = ["sensor"];
      picker.allowCustomEntity = true;
    }
  } else {
    edfTempoUpdateSensorOptions(editor.shadowRoot, editor._hass);
  }
}

function edfTempoUpdateSensorOptions(root, hass) {
  const escape = value => String(value)
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
  const options = Object.entries(hass?.states || {})
    .filter(([id]) => id.startsWith("sensor."))
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([id, state]) => `<option value="${escape(id)}" label="${escape(state.attributes?.friendly_name || id)}"></option>`)
    .join("");
  const list = root.querySelector("#tempo-sensor-options");
  if (list.innerHTML !== options) list.innerHTML = options;
}

class EdfTempoCardEditor extends HTMLElement {
  set hass(hass) {
    const languageChanged = edfTempoCardIsFrench(this._hass) !== edfTempoCardIsFrench(hass);
    this._hass = hass;
    if (!this._config) {
      return;
    }

    const resolvedToday = this._resolveTodayEntity(this._config.today_entity);
    const resolvedTomorrow = this._resolveTomorrowEntity(this._config.tomorrow_entity);
    const entitiesChanged = (
      resolvedToday !== this._config.today_entity ||
      resolvedTomorrow !== this._config.tomorrow_entity
    );
    if (entitiesChanged) {
      this._config = {
        ...this._config,
        today_entity: resolvedToday,
        tomorrow_entity: resolvedTomorrow,
      };
    }
    // Keep active form controls intact during Home Assistant state updates.
    if (entitiesChanged || languageChanged || !this._initialized) {
      this._render();
    } else {
      edfTempoSyncEntityControls(this, ["today_entity", "tomorrow_entity"]);
    }
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._initialized = false;
  }

  setConfig(config) {
    const nextConfig = {
      type: "custom:edf-tempo-card",
      title: config.title || "EDF Tempo Rev TBE",
      today_entity: this._resolveTodayEntity(config.today_entity),
      tomorrow_entity: this._resolveTomorrowEntity(config.tomorrow_entity),
      columns: edfTempoDailyColumns(config.columns),
      display_days: edfTempoDisplayDays(config.display_days),
      update_info: edfTempoUpdateInfo(config.update_info),
    };

    if (this._isSameConfig(this._config, nextConfig)) {
      return;
    }

    this._config = nextConfig;
    this._render();
  }

  _render() {
    if (!this.shadowRoot) {
      return;
    }

    this._usesEntityPicker = Boolean(customElements.get("ha-entity-picker"));
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }

        .form {
          display: grid;
          gap: 16px;
          padding: 8px 4px 4px;
        }

        .field {
          display: grid;
          gap: 6px;
        }

        label {
          color: var(--primary-text-color);
          font-size: 0.9rem;
          font-weight: 600;
        }

        ha-entity-picker,
        input,
        select {
          background: var(--card-background-color, #fff);
          border: 1px solid var(--divider-color, #d8dde6);
          border-radius: 10px;
          color: var(--primary-text-color);
          font: inherit;
          padding: 10px 12px;
        }

        .hint {
          color: var(--secondary-text-color);
          font-size: 0.8rem;
        }
      </style>
      <datalist id="tempo-sensor-options"></datalist>
      <div class="form">
        <div class="field">
          <label for="title">${edfTempoCardText(this._hass, "title")}</label>
          <input id="title" type="text" value="${this._escapeAttribute(this._config.title)}" />
        </div>
        <div class="field">
          <label for="today_entity">${edfTempoCardText(this._hass, "daily_today_entity")}</label>
          ${this._usesEntityPicker ? `<ha-entity-picker id="today_entity"></ha-entity-picker>` : `<input id="today_entity" type="text" list="tempo-sensor-options" autocomplete="off" spellcheck="false" />`}
        </div>
        <div class="field">
          <label for="tomorrow_entity">${edfTempoCardText(this._hass, "daily_tomorrow_entity")}</label>
          ${this._usesEntityPicker ? `<ha-entity-picker id="tomorrow_entity"></ha-entity-picker>` : `<input id="tomorrow_entity" type="text" list="tempo-sensor-options" autocomplete="off" spellcheck="false" />`}
        </div>
        <div class="field">
          <label for="display_days">${edfTempoCardText(this._hass, "display_days")}</label>
          <select id="display_days">
            ${["both", "today", "tomorrow"].map(days => `<option value="${days}" ${this._config.display_days === days ? "selected" : ""}>${edfTempoCardText(this._hass, `display_days_${days}`)}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label for="columns">${edfTempoCardText(this._hass, "columns")}</label>
          <input id="columns" type="number" min="1" max="2" step="1" value="${this._config.columns}" />
        </div>
        <div class="field">
          <label for="update_info">${edfTempoCardText(this._hass, "update_info")}</label>
          <select id="update_info">
            ${["hidden", "top", "bottom"].map(position => `<option value="${position}" ${this._config.update_info === position ? "selected" : ""}>${edfTempoCardText(this._hass, `update_info_${position}`)}</option>`).join("")}
          </select>
        </div>
      </div>
    `;

    for (const fieldId of ["today_entity", "tomorrow_entity"]) {
      const picker = this.shadowRoot.querySelector(`#${fieldId}`);
      picker.value = this._config[fieldId];
    }

    edfTempoSyncEntityControls(this, ["today_entity", "tomorrow_entity"]);
    this._syncDisplayControls();

    if (!this._initialized) {
      this._initialized = true;
      this.shadowRoot.addEventListener("input", this._handleInput.bind(this));
      this.shadowRoot.addEventListener("change", (event) => {
        if (["update_info", "display_days"].includes(event.target?.id)) this._handleInput(event);
      });
      this.shadowRoot.addEventListener("value-changed", this._handleInput.bind(this));
    }
  }

  _syncDisplayControls() {
    const columns = this.shadowRoot.querySelector("#columns");
    columns.disabled = this._config.display_days !== "both";
    columns.value = columns.disabled ? 1 : this._config.columns;
    const info = this.shadowRoot.querySelector("#update_info");
    info.disabled = this._config.display_days === "today";
    info.value = info.disabled ? "hidden" : this._config.update_info;
  }

  _handleInput(event) {
    const target = event.target;
    if (["update_info", "display_days"].includes(target?.id) && event.type === "input") return;
    if (!target?.id || !["title", "today_entity", "tomorrow_entity", "columns", "update_info", "display_days"].includes(target.id)) {
      return;
    }

    const value = event.detail?.value ?? target.value ?? "";

    const nextConfig = {
      ...this._config,
      type: "custom:edf-tempo-card",
      [target.id]: target.id === "columns" ? edfTempoDailyColumns(value)
        : target.id === "update_info" ? edfTempoUpdateInfo(value)
        : target.id === "display_days" ? edfTempoDisplayDays(value) : String(value).trim(),
    };

    this._config = nextConfig;
    this._syncDisplayControls();
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: nextConfig },
        bubbles: true,
        composed: true,
      }),
    );
  }

  _resolveTodayEntity(entityId) {
    return this._resolveEntity(entityId, [
      "sensor.edf_tempo_tbe_today",
    ]);
  }

  _resolveTomorrowEntity(entityId) {
    return this._resolveEntity(entityId, [
      "sensor.edf_tempo_tbe_tomorrow",
    ]);
  }

  _resolveEntity(entityId, fallbacks) {
    // Preserve an explicitly cleared field while editing.
    if (typeof entityId === "string") {
      return entityId;
    }

    if (!this._hass) {
      return fallbacks[0];
    }

    for (const candidate of fallbacks) {
      if (this._hass.states?.[candidate]) {
        return candidate;
      }
    }

    return fallbacks[0];
  }

  _isSameConfig(currentConfig, nextConfig) {
    return (
      currentConfig?.type === nextConfig.type &&
      currentConfig?.title === nextConfig.title &&
      currentConfig?.today_entity === nextConfig.today_entity &&
      currentConfig?.tomorrow_entity === nextConfig.tomorrow_entity &&
      currentConfig?.columns === nextConfig.columns &&
      currentConfig?.update_info === nextConfig.update_info &&
      currentConfig?.display_days === nextConfig.display_days
    );
  }

  _escapeAttribute(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll('"', "&quot;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }
}

class EdfTempoCard extends HTMLElement {
  static async getConfigElement() {
    await edfTempoLoadEntityPicker();
    return new EdfTempoCardEditor();
  }

  static getStubConfig() {
    return {
      type: "custom:edf-tempo-card",
      title: "EDF Tempo Rev TBE",
      today_entity: "sensor.edf_tempo_tbe_today",
      tomorrow_entity: "sensor.edf_tempo_tbe_tomorrow",
      columns: 2,
      display_days: "both",
    };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._lastSignature = null;
  }

  setConfig(config) {
    const todayEntity = this._resolveTodayEntity(config.today_entity);
    const tomorrowEntity = this._resolveTomorrowEntity(config.tomorrow_entity);

    if (!todayEntity || !tomorrowEntity) {
      throw new Error("today_entity and tomorrow_entity must be defined");
    }

    this._config = {
      type: "custom:edf-tempo-card",
      title: config.title || "EDF Tempo Rev TBE",
      today_entity: todayEntity,
      tomorrow_entity: tomorrowEntity,
      columns: edfTempoDailyColumns(config.columns),
      display_days: edfTempoDisplayDays(config.display_days),
      update_info: edfTempoUpdateInfo(config.update_info),
    };

    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const signature = this._computeSignature();
    if (signature !== this._lastSignature) {
      this._lastSignature = signature;
      this._render();
    }
  }

  getCardSize() {
    return this._config?.display_days === "both" && this._config?.columns === 1 ? 4 : 2;
  }

  _computeSignature() {
    if (!this._config || !this._hass) {
      return null;
    }

    const todayState = this._hass.states[this._config.today_entity];
    const tomorrowState = this._hass.states[this._config.tomorrow_entity];
    return JSON.stringify({
      language: this._isFrench(),
      timeZone: this._hass.config?.time_zone,
      today: todayState ? { state: todayState.state, attributes: todayState.attributes } : null,
      tomorrow: tomorrowState
        ? { state: tomorrowState.state, attributes: tomorrowState.attributes }
        : null,
    });
  }

  _resolveTodayEntity(entityId) {
    return this._resolveEntity(entityId, [
      "sensor.edf_tempo_tbe_today",
    ]);
  }

  _resolveTomorrowEntity(entityId) {
    return this._resolveEntity(entityId, [
      "sensor.edf_tempo_tbe_tomorrow",
    ]);
  }

  _resolveEntity(entityId, fallbacks) {
    if (entityId) {
      return entityId;
    }

    if (!this._hass) {
      return fallbacks[0];
    }

    for (const candidate of fallbacks) {
      if (this._hass.states?.[candidate]) {
        return candidate;
      }
    }

    return fallbacks[0];
  }

  _render() {
    if (!this._config || !this.shadowRoot) {
      return;
    }

    const todayState = this._hass?.states?.[this._config.today_entity];
    const tomorrowState = this._hass?.states?.[this._config.tomorrow_entity];
    const showToday = this._config.display_days !== "tomorrow";
    const showTomorrow = this._config.display_days !== "today";
    const columns = showToday && showTomorrow ? this._config.columns : 1;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --tempo-red: #e85130;
          --tempo-blue: #1057c8;
          --tempo-white: #f4f4f4;
          --tempo-text-dark: #122033;
          --tempo-surface: var(--ha-card-background, var(--card-background-color, #ffffff));
          --tempo-muted: var(--secondary-text-color, #667085);
          display: block;
        }

        ha-card {
          background:
            radial-gradient(circle at top right, rgba(16, 87, 200, 0.12), transparent 36%),
            linear-gradient(180deg, rgba(255, 255, 255, 0.08), transparent 60%),
            var(--tempo-surface);
          border: 1px solid rgba(116, 127, 151, 0.22);
          border-radius: 24px;
          box-shadow: 0 16px 36px rgba(15, 23, 42, 0.08);
          overflow: hidden;
        }

        .card {
          padding: 20px;
        }

        .update-info {
          color: var(--secondary-text-color, #667085);
          font-size: 0.7rem;
          line-height: 1.4;
          overflow-wrap: anywhere;
          text-align: center;
        }

        .update-info.top { margin-bottom: 12px; }
        .update-info.bottom { margin-top: 12px; }

        .update-info .rte-date-future {
          color: var(--error-color, #c62828);
        }

        .header {
          align-items: center;
          display: flex;
          justify-content: center;
          margin-bottom: 18px;
          text-align: center;
        }

        .title {
          color: var(--primary-text-color);
          font-size: 1.02rem;
          font-weight: 700;
          letter-spacing: 0.02em;
        }

        .grid {
          display: grid;
          gap: 14px;
          grid-template-columns: repeat(${columns}, minmax(0, 1fr));
        }

        .panel {
          align-items: center;
          border: 1px solid transparent;
          border-radius: 20px;
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
          min-height: 220px;
          min-width: 0;
          overflow-wrap: anywhere;
          padding: 18px 18px 20px;
          position: relative;
          text-align: center;
        }

        .grid.two-columns {
          row-gap: 0;
        }

        .grid.two-columns .panel {
          align-items: start;
          display: grid;
          grid-row: span 3;
          grid-template-rows: subgrid;
          justify-items: center;
          row-gap: 0;
        }

        .grid.two-columns .label {
          align-items: center;
          align-self: stretch;
        }

        .label {
          border-radius: 999px;
          box-sizing: border-box;
          display: inline-flex;
          font-size: 0.76rem;
          font-weight: 800;
          letter-spacing: 0.08em;
          max-width: 100%;
          padding: 6px 12px;
          text-transform: uppercase;
        }

        .date-block {
          align-content: start;
          display: grid;
          gap: 3px;
          margin-top: 18px;
          max-width: 100%;
          justify-items: center;
        }

        .weekday {
          font-size: 0.96rem;
          font-weight: 700;
          letter-spacing: 0.03em;
          opacity: 0.92;
        }

        .day {
          font-size: 3.4rem;
          font-weight: 900;
          letter-spacing: -0.06em;
          line-height: 0.96;
          margin-top: 2px;
        }

        .year {
          font-size: 0.92rem;
          font-weight: 700;
          letter-spacing: 0.14em;
          margin-top: 2px;
          opacity: 0.74;
          text-transform: uppercase;
        }

        .color {
          font-size: 1.38rem;
          font-weight: 800;
          letter-spacing: 0.01em;
          line-height: 1.15;
          margin-top: 18px;
          text-align: center;
        }

        .blue {
          background: linear-gradient(145deg, #1057c8, #0b429d);
          color: #ffffff;
        }

        .blue .label {
          background: rgba(255, 255, 255, 0.16);
          color: #ffffff;
        }

        .red {
          background: linear-gradient(145deg, #e85130, #cb3b1d);
          color: #ffffff;
        }

        .red .label {
          background: rgba(255, 255, 255, 0.16);
          color: #ffffff;
        }

        .white {
          background: linear-gradient(145deg, #f4f4f4, #e7ebf0);
          border: 1px solid rgba(17, 24, 39, 0.08);
          color: var(--tempo-text-dark);
        }

        .white .label {
          background: rgba(17, 24, 39, 0.08);
          color: var(--tempo-text-dark);
        }

        .unknown {
          background: linear-gradient(145deg, #eef2f7, #dde5f0);
          color: var(--tempo-text-dark);
        }

        .unknown .label {
          background: rgba(17, 24, 39, 0.08);
          color: var(--tempo-text-dark);
        }

      </style>
      <ha-card>
        <div class="card">
          <div class="header">
            <div class="title">${this._escapeHtml(this._config.title)}</div>
          </div>
          ${showTomorrow && this._config.update_info === "top" ? this._renderUpdateInfo(tomorrowState) : ""}
          <div class="grid ${columns === 2 ? "two-columns" : ""}">
            ${showToday ? this._renderPanel(this._t("today"), todayState) : ""}
            ${showTomorrow ? this._renderPanel(this._t("tomorrow"), tomorrowState) : ""}
          </div>
          ${showTomorrow && this._config.update_info === "bottom" ? this._renderUpdateInfo(tomorrowState) : ""}
        </div>
      </ha-card>
    `;
  }

  _formatTimestamp(value) {
    const unknown = edfTempoCardText(this._hass, "timestamp_unknown");
    if (typeof value !== "string" || !value.trim()) return unknown;
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return unknown;
    return new Intl.DateTimeFormat(this._isFrench() ? "fr-FR" : "en-GB", {
      timeZone: this._hass?.config?.time_zone || "Europe/Paris",
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    }).format(date);
  }

  _renderUpdateInfo(entity) {
    // Unavailable sensors can retain attributes from an expired daily snapshot.
    const attributes = entity?.state === "unavailable" ? {} : entity?.attributes || {};
    const updatedAt = Date.parse(attributes.updated_date);
    const fetchedAt = Date.parse(attributes.fetched_at);
    // Allow a small clock difference, but never present a later RTE timestamp
    // as an update that had already happened when the data was retrieved.
    const rteDateIsFuture = Number.isFinite(updatedAt) && Number.isFinite(fetchedAt)
      && updatedAt > fetchedAt + 5 * 60 * 1000;
    const rteDateClass = rteDateIsFuture ? ' class="rte-date-future"' : "";
    return `<div class="update-info ${this._config.update_info}">
      <div${rteDateClass}>${edfTempoCardText(this._hass, "rte_updated")} : ${this._escapeHtml(this._formatTimestamp(attributes.updated_date))}</div>
      ${rteDateIsFuture ? `<div class="rte-date-future">${edfTempoCardText(this._hass, "rte_updated_after_fetch")}</div>` : ""}
      <div>${edfTempoCardText(this._hass, "last_fetch")} : ${this._escapeHtml(this._formatTimestamp(attributes.fetched_at))}</div>
    </div>`;
  }

  _renderPanel(label, entity) {
    const model = this._buildModel(entity);

    return `
      <section class="panel ${model.themeClass}">
        <div class="label">${label}</div>
        <div class="date-block">
          <div class="weekday">${this._escapeHtml(model.weekday)}</div>
          <div class="day">${this._escapeHtml(model.day)}</div>
          <div class="year">${this._escapeHtml(model.year)}</div>
        </div>
        <div class="color">${this._escapeHtml(model.state)}</div>
      </section>
    `;
  }

  _buildModel(entity) {
    const dateParts = this._getDateParts(entity?.attributes?.date);

    if (!entity) {
      return {
        themeClass: "unknown",
        state: this._t("color_to_come"),
        weekday: dateParts.weekday,
        day: dateParts.day,
        year: dateParts.year,
      };
    }

    const state = entity.state;

    if (
      state === "unknown" ||
      state === "unavailable" ||
      state === null ||
      state === undefined ||
      state === ""
    ) {
      return {
        themeClass: "unknown",
        state: this._t("color_to_come"),
        weekday: dateParts.weekday,
        day: dateParts.day,
        year: dateParts.year,
      };
    }

    const themeClass = {
      Blue: "blue",
      White: "white",
      Red: "red",
      blue: "blue",
      white: "white",
      red: "red",
    }[state] || "unknown";

    return {
      themeClass,
      state: this._formatColorLabel(state),
      weekday: dateParts.weekday,
      day: dateParts.day,
      year: dateParts.year,
    };
  }

  _getDateParts(value) {
    if (!value) {
      return {
        weekday: this._t("date_to_come"),
        day: "--",
        year: "----",
      };
    }

    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) {
      return {
        weekday: this._t("date_to_come"),
        day: "--",
        year: "----",
      };
    }

    const locale = this._isFrench() ? "fr-FR" : "en-GB";
    const weekday = new Intl.DateTimeFormat(locale, { weekday: "long" }).format(date);
    const day = new Intl.DateTimeFormat(locale, { day: "2-digit" }).format(date);
    const year = new Intl.DateTimeFormat(locale, { year: "numeric" }).format(date);

    return {
      weekday: this._capitalize(weekday),
      day,
      year,
    };
  }

  _t(key) {
    const translations = this._isFrench()
      ? {
          source: "",
          today: "Aujourd’hui",
          tomorrow: "Demain",
          color_to_come: "Couleur à venir",
          date_to_come: "Date à venir",
        }
      : {
          source: "",
          today: "Today",
          tomorrow: "Tomorrow",
          color_to_come: "Color to come",
          date_to_come: "Date to come",
        };

    return translations[key] || key;
  }

  _formatColorLabel(value) {
    if (!value) {
      return this._t("color_to_come");
    }

    if (this._isFrench()) {
      return (
        {
          Blue: "Bleu",
          Red: "Rouge",
          White: "Blanc",
          blue: "Bleu",
          red: "Rouge",
          white: "Blanc",
        }[value] || value
      );
    }

    return (
      {
        blue: "Blue",
        red: "Red",
        white: "White",
      }[value] || value
    );
  }

  _isFrench() {
    const language =
      this._hass?.locale?.language ||
      this._hass?.language ||
      this._hass?.selectedLanguage ||
      "en";
    return String(language).toLowerCase().startsWith("fr");
  }

  _escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  _capitalize(value) {
    if (!value) {
      return "";
    }

    return value.charAt(0).toUpperCase() + value.slice(1);
  }
}

class EdfTempoSeasonCardEditor extends HTMLElement {
  set hass(hass) {
    const languageChanged = edfTempoCardIsFrench(this._hass) !== edfTempoCardIsFrench(hass);
    this._hass = hass;
    if (!this._config) return;
    const resolvedEntity = this._resolveSeasonEntity(this._config.entity);
    const entityChanged = resolvedEntity !== this._config.entity;
    if (entityChanged) {
      this._config = { ...this._config, entity: resolvedEntity };
    }
    if (entityChanged || languageChanged || !this._initialized) {
      this._render();
    } else {
      edfTempoSyncEntityControls(this, ["entity"]);
    }
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = null;
    this._initialized = false;
  }

  setConfig(config) {
    const nextConfig = {
      type: "custom:edf-tempo-season-card",
      title: config.title || edfTempoCardText(this._hass, "season_summary_title"),
      entity: this._resolveSeasonEntity(config.entity),
    };

    if (
      this._config?.type === nextConfig.type &&
      this._config?.title === nextConfig.title &&
      this._config?.entity === nextConfig.entity
    ) {
      return;
    }

    this._config = nextConfig;
    this._render();
  }

  _render() {
    if (!this.shadowRoot) {
      return;
    }

    this._usesEntityPicker = Boolean(customElements.get("ha-entity-picker"));
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }

        .form {
          display: grid;
          gap: 16px;
          padding: 8px 4px 4px;
        }

        .field {
          display: grid;
          gap: 6px;
        }

        label {
          color: var(--primary-text-color);
          font-size: 0.9rem;
          font-weight: 600;
        }

        ha-entity-picker,
        input {
          background: var(--card-background-color, #fff);
          border: 1px solid var(--divider-color, #d8dde6);
          border-radius: 10px;
          color: var(--primary-text-color);
          font: inherit;
          padding: 10px 12px;
        }
      </style>
      <datalist id="tempo-sensor-options"></datalist>
      <div class="form">
        <div class="field">
          <label for="title">${edfTempoCardText(this._hass, "title")}</label>
          <input id="title" type="text" value="${this._escapeAttribute(this._config.title)}" />
        </div>
        <div class="field">
          <label for="entity">${edfTempoCardText(this._hass, "season_entity")}</label>
          ${this._usesEntityPicker ? `<ha-entity-picker id="entity"></ha-entity-picker>` : `<input id="entity" type="text" list="tempo-sensor-options" autocomplete="off" spellcheck="false" />`}
        </div>
      </div>
    `;

    const picker = this.shadowRoot.querySelector("#entity");
    picker.value = this._config.entity;
    edfTempoSyncEntityControls(this, ["entity"]);

    if (!this._initialized) {
      this._initialized = true;
      this.shadowRoot.addEventListener("input", this._handleInput.bind(this));
      this.shadowRoot.addEventListener("value-changed", this._handleInput.bind(this));
    }
  }

  _handleInput(event) {
    const target = event.target;
    if (!target?.id || !["title", "entity"].includes(target.id)) {
      return;
    }

    const value = event.detail?.value ?? target.value ?? "";

    const nextConfig = {
      ...this._config,
      type: "custom:edf-tempo-season-card",
      [target.id]: String(value).trim(),
    };

    this._config = nextConfig;
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: nextConfig },
        bubbles: true,
        composed: true,
      }),
    );
  }

  _resolveSeasonEntity(entityId) {
    return this._resolveEntity(entityId, [
      "sensor.edf_tempo_tbe_season_summary",
    ]);
  }

  _resolveEntity(entityId, fallbacks) {
    // Preserve an explicitly cleared field while editing.
    if (typeof entityId === "string") {
      return entityId;
    }

    if (!this._hass) {
      return fallbacks[0];
    }

    for (const candidate of fallbacks) {
      if (this._hass.states?.[candidate]) {
        return candidate;
      }
    }

    return fallbacks[0];
  }

  _escapeAttribute(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll('"', "&quot;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }
}

class EdfTempoSeasonCard extends HTMLElement {
  static async getConfigElement() {
    await edfTempoLoadEntityPicker();
    return new EdfTempoSeasonCardEditor();
  }

  static getStubConfig() {
    return {
      type: "custom:edf-tempo-season-card",
      title: edfTempoCardText(null, "season_summary_title"),
      entity: "sensor.edf_tempo_tbe_season_summary",
    };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._lastSignature = null;
  }

  setConfig(config) {
    this._config = {
      type: "custom:edf-tempo-season-card",
      title: config.title || edfTempoCardText(this._hass, "season_summary_title"),
      entity: this._resolveSeasonEntity(config.entity),
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const signature = JSON.stringify(this._hass?.states?.[this._config?.entity] || null);
    if (signature !== this._lastSignature) {
      this._lastSignature = signature;
      this._render();
    }
  }

  getCardSize() {
    return 3;
  }

  _resolveSeasonEntity(entityId) {
    if (entityId) {
      return entityId;
    }

    const candidates = [
      "sensor.edf_tempo_tbe_season_summary",
    ];
    for (const candidate of candidates) {
      if (this._hass?.states?.[candidate]) {
        return candidate;
      }
    }

    return candidates[0];
  }

  _render() {
    if (!this.shadowRoot || !this._config) {
      return;
    }

    const entity = this._hass?.states?.[this._config.entity];
    const model = this._buildSeasonModel(entity);

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }

        ha-card {
          background:
            radial-gradient(circle at top right, rgba(16, 87, 200, 0.1), transparent 34%),
            linear-gradient(180deg, rgba(255, 255, 255, 0.08), transparent 60%),
            var(--ha-card-background, var(--card-background-color, #ffffff));
          border: 1px solid rgba(116, 127, 151, 0.22);
          border-radius: 24px;
          box-shadow: 0 16px 36px rgba(15, 23, 42, 0.08);
          overflow: hidden;
        }

        .card {
          padding: 24px 22px 22px;
          text-align: center;
        }

        .title {
          color: var(--primary-text-color);
          font-size: 1.24rem;
          font-weight: 800;
          letter-spacing: 0.01em;
        }

        .subtitle {
          color: var(--primary-text-color);
          font-size: 1.24rem;
          font-weight: 800;
          letter-spacing: 0.01em;
          margin-top: 4px;
        }

        .season {
          color: var(--secondary-text-color, #667085);
          font-size: 0.82rem;
          font-weight: 600;
          line-height: 1.45;
          margin-top: 8px;
        }

        .stats {
          display: grid;
          gap: 12px;
          margin-top: 24px;
        }

        .row {
          align-items: center;
          display: grid;
          gap: 10px;
          grid-template-columns: minmax(0, 2.2fr) repeat(3, minmax(0, 0.7fr));
          text-align: left;
        }

        .row.blue {
          color: #1057c8;
        }

        .row.white {
          color: #475467;
        }

        .row.red {
          color: #e85130;
        }

        .label-cell {
          font-size: 1.06rem;
          font-weight: 800;
          line-height: 1.25;
        }

        .value-cell {
          font-size: 1.62rem;
          font-weight: 800;
          letter-spacing: -0.02em;
          line-height: 1;
          text-align: center;
        }

        .empty {
          color: var(--secondary-text-color, #667085);
          font-size: 1rem;
          font-weight: 600;
          margin-top: 24px;
        }

        .summary-updated {
          color: var(--secondary-text-color, #667085);
          font-size: 0.82rem;
          margin-top: 20px;
        }
      </style>
      <ha-card>
        <div class="card">
          <div class="title">${this._escapeHtml(this._config.title)}</div>
          <div class="subtitle">EDF Tempo Rev TBE</div>
          <div class="season">${this._escapeHtml(model.seasonLabel)}</div>
          ${
            model.available
              ? `<div class="stats">
                  ${this._renderSeasonRow(model.blueRow, "blue")}
                  ${this._renderSeasonRow(model.whiteRow, "white")}
                  ${this._renderSeasonRow(model.redRow, "red")}
                </div>
                <div class="summary-updated">${this._escapeHtml(model.updatedLabel)}</div>`
              : `<div class="empty">${this._escapeHtml(model.emptyLabel)}</div>`
          }
        </div>
      </ha-card>
    `;
  }

  _buildSeasonModel(entity) {
    if (!entity) {
      return {
        available: false,
        seasonLabel: `${this._formatSeasonStart(null)} ${edfTempoCardText(this._hass, "season_to")} ${this._formatSeasonEnd(null)}`,
        emptyLabel: edfTempoCardText(this._hass, "season_unavailable"),
      };
    }

    const attrs = entity.attributes || {};
    if (
      entity.state === "unavailable" ||
      entity.state === "unknown" ||
      ["season_start", "season_end", "blue_days", "white_days", "red_days"].some(
        (key) => attrs[key] == null,
      )
    ) {
      return {
        available: false,
        seasonLabel: `${this._formatSeasonStart(attrs.season_start)} ${edfTempoCardText(this._hass, "season_to")} ${this._formatSeasonEnd(attrs.season_end)}`,
        emptyLabel: edfTempoCardText(this._hass, "season_unavailable"),
      };
    }
    const seasonLabel = `${this._formatSeasonStart(attrs.season_start)} ${edfTempoCardText(
      this._hass,
      "season_to",
    )} ${this._formatSeasonEnd(attrs.season_end)}`;
    const blueDays = this._toNumber(attrs.blue_days);
    const whiteDays = this._toNumber(attrs.white_days);
    const redDays = this._toNumber(attrs.red_days);
    const blueTotal = this._toNumber(attrs.blue_total, 300);
    const whiteTotal = this._toNumber(attrs.white_total, 43);
    const redTotal = this._toNumber(attrs.red_total, 22);

    return {
      available: true,
      seasonLabel,
      updatedLabel: this._formatSummaryUpdatedAt(attrs.summary_updated_at),
      blueRow: {
        label: edfTempoCardText(this._hass, "blue_days"),
        left: blueTotal - blueDays,
        placed: blueDays,
        total: blueTotal,
      },
      whiteRow: {
        label: edfTempoCardText(this._hass, "white_days"),
        left: whiteTotal - whiteDays,
        placed: whiteDays,
        total: whiteTotal,
      },
      redRow: {
        label: edfTempoCardText(this._hass, "red_days"),
        left: redTotal - redDays,
        placed: redDays,
        total: redTotal,
      },
    };
  }

  _renderSeasonRow(row, themeClass) {
    return `
      <div class="row ${themeClass}">
        <div class="label-cell">${this._escapeHtml(row.label)}</div>
        <div class="value-cell">${this._escapeHtml(row.left)}</div>
        <div class="value-cell">${this._escapeHtml(row.placed)}</div>
        <div class="value-cell">${this._escapeHtml(row.total)}</div>
      </div>
    `;
  }

  _formatSummaryUpdatedAt(value) {
    const timestamp = typeof value === "string" ? Date.parse(value) : NaN;
    if (!Number.isFinite(timestamp)) {
      return edfTempoCardText(this._hass, "season_update_unknown");
    }
    const parts = new Intl.DateTimeFormat("en-GB", {
      timeZone: "Europe/Paris",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    }).formatToParts(new Date(timestamp));
    const dateParts = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    return `${edfTempoCardText(this._hass, "season_updated_on")} ${dateParts.day}-${dateParts.month}-${dateParts.year}`;
  }

  _formatSeasonStart(value) {
    const date = this._parseIsoDate(value);
    if (!date) {
      return edfTempoCardIsFrench(this._hass) ? "1er septembre ----" : "1 September ----";
    }

    return new Intl.DateTimeFormat(edfTempoCardIsFrench(this._hass) ? "fr-FR" : "en-GB", {
      day: "numeric",
      month: "long",
      year: "numeric",
    }).format(date);
  }

  _formatSeasonEnd(value) {
    const date = this._parseIsoDate(value);
    if (!date) {
      return edfTempoCardIsFrench(this._hass) ? "31 août ----" : "31 August ----";
    }

    return new Intl.DateTimeFormat(edfTempoCardIsFrench(this._hass) ? "fr-FR" : "en-GB", {
      day: "numeric",
      month: "long",
      year: "numeric",
    }).format(date);
  }

  _parseIsoDate(value) {
    if (!value) {
      return null;
    }

    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) {
      return null;
    }

    return date;
  }

  _toNumber(value, fallback = 0) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
  }

  _escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }
}

class EdfTempoSeasonCalendarCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._initialized = false;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  setConfig(config) {
    const nextConfig = {
      type: "custom:edf-tempo-season-calendar-card",
      title: config.title || edfTempoCardText(this._hass, "calendar_title"),
      columns: this._normalizeColumns(config.columns),
    };

    if (
      this._config?.type === nextConfig.type &&
      this._config?.title === nextConfig.title &&
      this._config?.columns === nextConfig.columns
    ) {
      return;
    }

    this._config = nextConfig;
    this._render();
  }

  _render() {
    if (!this.shadowRoot) {
      return;
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }

        .form {
          display: grid;
          gap: 16px;
          padding: 8px 4px 4px;
        }

        .field {
          display: grid;
          gap: 6px;
        }

        label {
          color: var(--primary-text-color);
          font-size: 0.9rem;
          font-weight: 600;
        }

        input {
          background: var(--card-background-color, #fff);
          border: 1px solid var(--divider-color, #d8dde6);
          border-radius: 10px;
          color: var(--primary-text-color);
          font: inherit;
          padding: 10px 12px;
        }
      </style>
      <div class="form">
        <div class="field">
          <label for="title">${edfTempoCardText(this._hass, "title")}</label>
          <input id="title" type="text" value="${this._escapeAttribute(this._config.title)}" />
        </div>
        <div class="field">
          <label for="columns">${edfTempoCardText(this._hass, "columns")}</label>
          <input
            id="columns"
            type="number"
            min="1"
            max="2"
            step="1"
            value="${this._escapeAttribute(this._config.columns)}"
          />
        </div>
      </div>
    `;

    if (!this._initialized) {
      this._initialized = true;
      this.shadowRoot.addEventListener("input", this._handleInput.bind(this));
    }
  }

  _handleInput(event) {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) {
      return;
    }

    const nextConfig = {
      ...this._config,
      type: "custom:edf-tempo-season-calendar-card",
      [target.id]:
        target.id === "columns" ? this._normalizeColumns(target.value) : target.value.trim(),
    };

    this._config = nextConfig;
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: nextConfig },
        bubbles: true,
        composed: true,
      }),
    );
  }

  _escapeAttribute(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll('"', "&quot;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  _normalizeColumns(value) {
    const parsed = Number.parseInt(String(value ?? 2), 10);
    if (Number.isNaN(parsed)) {
      return 2;
    }
    return Math.min(2, Math.max(1, parsed));
  }
}

class EdfTempoSeasonCalendarCard extends HTMLElement {
  static getConfigElement() {
    return new EdfTempoSeasonCalendarCardEditor();
  }

  static getStubConfig() {
    return {
      type: "custom:edf-tempo-season-calendar-card",
      title: edfTempoCardText(null, "calendar_title"),
      columns: 2,
    };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._selectedSeasonStartYear = null;
    this._currentSeasonStartYear = this._computeCurrentSeasonStartYear();
    this._minSeasonStartYear = 2015;
    this._pendingLoads = new Map();
    this._loadErrors = new Map();
    this._seasonCache = new Map();
    this._seasonData = null;
    this._responsiveColumns = null;
    this._resizeObserver = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect?.width;
      if (width) {
        this._updateResponsiveColumns(width);
      }
    });
  }

  connectedCallback() {
    this._resizeObserver.observe(this);
  }

  disconnectedCallback() {
    this._resizeObserver.disconnect();
  }

  setConfig(config) {
    const nextConfig = {
      type: "custom:edf-tempo-season-calendar-card",
      title: config.title || edfTempoCardText(this._hass, "calendar_title"),
      columns: this._normalizeColumns(config.columns),
    };
    const configChanged =
      this._config?.title !== nextConfig.title ||
      this._config?.columns !== nextConfig.columns;
    this._config = nextConfig;
    this._updateResponsiveColumns(this.getBoundingClientRect().width);
    if (this._selectedSeasonStartYear === null) {
      this._selectedSeasonStartYear = this._currentSeasonStartYear;
    }
    if (configChanged) {
      this._render();
    }
  }

  _updateResponsiveColumns(width) {
    const configuredColumns = this._config?.columns || 2;
    let responsiveColumns = configuredColumns;
    if (width > 0 && width <= 800) {
      responsiveColumns = Math.min(configuredColumns, 2);
    }
    if (responsiveColumns === this._responsiveColumns) {
      return;
    }
    this._responsiveColumns = responsiveColumns;
    this.style.setProperty("--tempo-responsive-columns", String(responsiveColumns));
  }

  set hass(hass) {
    const isFirstUpdate = this._hass === null;
    const previousLocale = isFirstUpdate ? null : this._locale();
    this._hass = hass;
    if (this._selectedSeasonStartYear === null) {
      this._selectedSeasonStartYear = this._currentSeasonStartYear;
    }
    this._ensureSeasonData(this._selectedSeasonStartYear);
    if (!isFirstUpdate && previousLocale !== this._locale()) {
      this._render();
    }
  }

  getCardSize() {
    return 12;
  }

  _ensureSeasonData(seasonStartYear) {
    if (!this._hass) {
      return Promise.resolve(null);
    }
    if (this._seasonCache.has(seasonStartYear)) {
      if (seasonStartYear === this._selectedSeasonStartYear) {
        this._seasonData = this._seasonCache.get(seasonStartYear);
      }
      return Promise.resolve(this._seasonCache.get(seasonStartYear));
    }
    const pendingLoad = this._pendingLoads.get(seasonStartYear);
    if (pendingLoad) {
      return pendingLoad;
    }

    this._loadErrors.delete(seasonStartYear);
    const loadPromise = Promise.resolve()
      .then(() =>
        this._hass.connection.sendMessagePromise({
          type: "edf_tempo_tbe/get_season_calendar",
          season_start_year: seasonStartYear,
        }),
      )
      .then((result) => {
        this._currentSeasonStartYear = result.current_season_start_year;
        this._minSeasonStartYear = result.min_season_start_year;
        this._seasonCache.set(seasonStartYear, result);
        if (seasonStartYear === this._selectedSeasonStartYear) {
          this._seasonData = result;
        }
        return result;
      })
      .catch((err) => {
        this._loadErrors.set(
          seasonStartYear,
          err?.message || edfTempoCardText(this._hass, "load_season_failed"),
        );
        return null;
      })
      .finally(() => {
        this._pendingLoads.delete(seasonStartYear);
        this._render();
      });

    this._pendingLoads.set(seasonStartYear, loadPromise);
    this._render();
    return loadPromise;
  }

  _render() {
    if (!this.shadowRoot || !this._config) {
      return;
    }

    const canGoPrevious = this._selectedSeasonStartYear > this._minSeasonStartYear;
    const canGoNext = this._selectedSeasonStartYear < this._currentSeasonStartYear;
    const model = this._buildCalendarModel();
    const isLoading = this._pendingLoads.has(this._selectedSeasonStartYear);
    const loadError = this._loadErrors.get(this._selectedSeasonStartYear);

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --tempo-calendar-columns: ${this._config.columns};
          container-type: inline-size;
          display: block;
        }

        ha-card {
          background:
            radial-gradient(circle at top right, rgba(16, 87, 200, 0.1), transparent 34%),
            linear-gradient(180deg, rgba(255, 255, 255, 0.08), transparent 60%),
            var(--ha-card-background, var(--card-background-color, #ffffff));
          border: 1px solid rgba(116, 127, 151, 0.22);
          border-radius: 24px;
          box-shadow: 0 16px 36px rgba(15, 23, 42, 0.08);
          overflow: hidden;
        }

        .card {
          padding: 20px;
        }

        .header {
          align-items: center;
          display: grid;
          gap: 12px;
          grid-template-columns: 40px 1fr 40px;
        }

        .nav {
          align-items: center;
          appearance: none;
          background: rgba(15, 23, 42, 0.04);
          border: 0;
          border-radius: 999px;
          color: var(--primary-text-color);
          cursor: pointer;
          display: inline-flex;
          font-size: 1.2rem;
          height: 40px;
          justify-content: center;
          transition: background 160ms ease, color 160ms ease;
          width: 40px;
        }

        .nav:hover:not(:disabled) {
          background: rgba(16, 87, 200, 0.12);
          color: #1057c8;
        }

        .nav:disabled {
          color: rgba(102, 112, 133, 0.45);
          cursor: default;
        }

        .heading {
          text-align: center;
        }

        .title {
          color: var(--primary-text-color);
          font-size: 1.12rem;
          font-weight: 800;
          letter-spacing: 0.01em;
        }

        .season {
          color: var(--secondary-text-color, #667085);
          font-size: 0.92rem;
          font-weight: 600;
          margin-top: 6px;
        }

        .state {
          color: var(--secondary-text-color, #667085);
          font-size: 0.95rem;
          font-weight: 600;
          margin-top: 18px;
          text-align: center;
        }

        .months {
          display: grid;
          gap: 14px;
          grid-template-columns: repeat(var(--tempo-responsive-columns, var(--tempo-calendar-columns)), minmax(0, 1fr));
          margin-top: 20px;
        }

        .month {
          background: rgba(255, 255, 255, 0.48);
          border: 1px solid rgba(116, 127, 151, 0.16);
          border-radius: 18px;
          min-width: 0;
          padding: 14px 12px 12px;
        }

        .month-title {
          color: var(--primary-text-color);
          font-size: 0.92rem;
          font-weight: 800;
          margin-bottom: 10px;
          text-align: center;
        }

        .weekday-row {
          color: var(--secondary-text-color, #667085);
          display: grid;
          font-size: 0.72rem;
          font-weight: 800;
          gap: 4px;
          grid-template-columns: repeat(7, minmax(0, 1fr));
          justify-items: center;
          margin-bottom: 8px;
          text-transform: uppercase;
        }

        .days {
          display: grid;
          gap: 6px 3px;
          grid-template-columns: repeat(7, minmax(0, 1fr));
        }

        .day {
          align-items: center;
          aspect-ratio: 1;
          border-radius: 999px;
          box-sizing: border-box;
          display: inline-flex;
          font-size: 0.76rem;
          font-weight: 800;
          justify-content: center;
          justify-self: stretch;
          line-height: 1;
          max-width: none;
          min-width: 0;
          overflow: hidden;
          width: auto;
        }

        .day.empty {
          background: transparent;
        }

        .day.none {
          background: #eadfcb;
          color: #5c4632;
        }

        .day.blue {
          background: #1057c8;
          color: #ffffff;
        }

        .day.white {
          background: #f4f4f4;
          border: 1px solid rgba(17, 24, 39, 0.08);
          color: #111827;
        }

        .day.red {
          background: #e85130;
          color: #ffffff;
        }

        @container (max-width: 760px) {
          .months {
            grid-template-columns: repeat(var(--tempo-responsive-columns, 2), minmax(0, 1fr));
          }
        }

        @container (max-width: 500px) {
          .months {
            grid-template-columns: repeat(var(--tempo-responsive-columns, 2), minmax(0, 1fr));
          }
        }
      </style>
      <ha-card>
        <div class="card">
          <div class="header">
            <button class="nav" data-action="previous" aria-label="${edfTempoCardText(this._hass, "previous")}" title="${edfTempoCardText(this._hass, "previous")}" ${canGoPrevious ? "" : "disabled"}>&larr;</button>
            <div class="heading">
              <div class="title">${this._escapeHtml(this._config.title)}</div>
              <div class="season">${this._escapeHtml(model.seasonLabel)}</div>
            </div>
            <button class="nav" data-action="next" aria-label="${edfTempoCardText(this._hass, "next")}" title="${edfTempoCardText(this._hass, "next")}" ${canGoNext ? "" : "disabled"}>&rarr;</button>
          </div>
          ${
            isLoading
              ? `<div class="state">${this._escapeHtml(this._t("loading"))}</div>`
              : loadError
                ? `<div class="state">${this._escapeHtml(loadError)}</div>`
                : `<div class="months">${model.monthsHtml}</div>`
          }
        </div>
      </ha-card>
    `;

    this.shadowRoot.querySelector('[data-action="previous"]')?.addEventListener("click", () => {
      this._navigate(-1);
    });
    this.shadowRoot.querySelector('[data-action="next"]')?.addEventListener("click", () => {
      this._navigate(1);
    });
  }

  _buildCalendarModel() {
    const seasonStartYear = this._selectedSeasonStartYear ?? this._currentSeasonStartYear;
    const seasonEndYear = seasonStartYear + 1;
    const seasonLabel = `${this._formatSeasonRange(seasonStartYear, seasonEndYear)}`;
    const seasonData = this._seasonData;

    const monthSequence = [
      { monthIndex: 8, year: seasonStartYear },
      { monthIndex: 9, year: seasonStartYear },
      { monthIndex: 10, year: seasonStartYear },
      { monthIndex: 11, year: seasonStartYear },
      { monthIndex: 0, year: seasonEndYear },
      { monthIndex: 1, year: seasonEndYear },
      { monthIndex: 2, year: seasonEndYear },
      { monthIndex: 3, year: seasonEndYear },
      { monthIndex: 4, year: seasonEndYear },
      { monthIndex: 5, year: seasonEndYear },
      { monthIndex: 6, year: seasonEndYear },
      { monthIndex: 7, year: seasonEndYear },
    ];

    return {
      seasonLabel,
      monthsHtml: monthSequence.map((item) => this._renderMonth(item, seasonData)).join(""),
    };
  }

  _renderMonth(item, seasonData) {
    const monthTitle = this._monthLabel(item.monthIndex, item.year);
    const weekdayHeaders = this._weekdayLabels()
      .map((label) => `<div>${this._escapeHtml(label)}</div>`)
      .join("");
    const dayCells = this._buildMonthCells(item.year, item.monthIndex, seasonData)
      .map((cell) => {
        if (cell.empty) {
          return `<div class="day empty"></div>`;
        }
        return `<div class="day ${cell.className}" title="${this._escapeHtml(cell.title)}">${this._escapeHtml(
          cell.label,
        )}</div>`;
      })
      .join("");

    return `
      <section class="month">
        <div class="month-title">${this._escapeHtml(monthTitle)}</div>
        <div class="weekday-row">${weekdayHeaders}</div>
        <div class="days">${dayCells}</div>
      </section>
    `;
  }

  _buildMonthCells(year, monthIndex, seasonData) {
    const firstDay = new Date(year, monthIndex, 1);
    const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
    const leadingEmpty = (firstDay.getDay() + 6) % 7;
    const cells = [];

    for (let index = 0; index < leadingEmpty; index += 1) {
      cells.push({ empty: true });
    }

    for (let day = 1; day <= daysInMonth; day += 1) {
      const isoDate = this._toIsoDate(year, monthIndex, day);
      const colorCode = seasonData?.day_colors?.[isoDate] || null;
      const className =
        {
          BLUE: "blue",
          WHITE: "white",
          RED: "red",
        }[colorCode] || "none";
      cells.push({
        empty: false,
        label: String(day),
        className,
        title: colorCode ? `${isoDate} - ${colorCode}` : isoDate,
      });
    }

    return cells;
  }

  _navigate(offset) {
    const nextYear = (this._selectedSeasonStartYear ?? this._currentSeasonStartYear) + offset;
    if (nextYear < this._minSeasonStartYear || nextYear > this._currentSeasonStartYear) {
      return;
    }
    this._selectedSeasonStartYear = nextYear;
    const cachedSeason = this._seasonCache.get(nextYear);
    if (cachedSeason) {
      this._seasonData = cachedSeason;
      this._render();
      return;
    }
    this._seasonData = null;
    this._ensureSeasonData(nextYear);
  }

  _computeCurrentSeasonStartYear() {
    const now = new Date();
    return now.getMonth() >= 8 ? now.getFullYear() : now.getFullYear() - 1;
  }

  _normalizeColumns(value) {
    const parsed = Number.parseInt(String(value ?? 2), 10);
    if (Number.isNaN(parsed)) {
      return 2;
    }
    return Math.min(2, Math.max(1, parsed));
  }

  _monthLabel(monthIndex, year) {
    return new Intl.DateTimeFormat(this._locale(), {
      month: "long",
    }).format(new Date(year, monthIndex, 1));
  }

  _weekdayLabels() {
    const baseDate = new Date(2024, 0, 1);
    const labels = [];
    for (let offset = 0; offset < 7; offset += 1) {
      const day = new Date(baseDate);
      day.setDate(baseDate.getDate() + offset);
      labels.push(
        new Intl.DateTimeFormat(this._locale(), { weekday: "short" })
          .format(day)
          .replace(".", "")
          .slice(0, 2),
      );
    }
    return labels;
  }

  _formatSeasonRange(startYear, endYear) {
    return `${this._t("season")} ${startYear}-${endYear}`;
  }

  _toIsoDate(year, monthIndex, day) {
    return `${String(year)}-${String(monthIndex + 1).padStart(2, "0")}-${String(day).padStart(
      2,
      "0",
    )}`;
  }

  _t(key) {
    const translations = this._isFrench()
      ? {
          season: "Saison",
          loading: "Chargement du calendrier Tempo...",
        }
      : {
          season: "Season",
          loading: "Loading Tempo calendar...",
        };
    return translations[key] || key;
  }

  _locale() {
    return this._isFrench() ? "fr-FR" : "en-GB";
  }

  _isFrench() {
    const language =
      this._hass?.locale?.language ||
      this._hass?.language ||
      this._hass?.selectedLanguage ||
      "en";
    return String(language).toLowerCase().startsWith("fr");
  }

  _escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }
}

class EdfTempoMonthCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  setConfig(config) {
    this._config = {
      type: "custom:edf-tempo-month-card",
    };
    this._render();
  }

  _render() {
    if (!this.shadowRoot) {
      return;
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }

        .message {
          color: var(--secondary-text-color, #667085);
          font-size: 0.92rem;
          line-height: 1.5;
          padding: 8px 4px 4px;
        }
      </style>
      <div class="message">
        ${edfTempoCardText(this._hass, "month_help")}
      </div>
    `;
  }
}

class EdfTempoMonthCard extends HTMLElement {
  static getConfigElement() {
    return new EdfTempoMonthCardEditor();
  }

  static getStubConfig() {
    return {
      type: "custom:edf-tempo-month-card",
    };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._minMonth = { year: 2015, monthIndex: 8 };
    this._selectedMonth = this._computeCurrentMonth();
    this._currentMonth = this._computeCurrentMonth();
    this._pendingLoads = new Map();
    this._loadErrors = new Map();
    this._seasonCache = new Map();
    this._seasonData = null;
  }

  setConfig(config) {
    this._config = {
      type: "custom:edf-tempo-month-card",
    };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._currentMonth = this._computeCurrentMonth();
    this._ensureMonthData(this._selectedMonth);
    this._render();
  }

  getCardSize() {
    return 5;
  }

  _ensureMonthData(monthRef) {
    const seasonStartYear = this._seasonStartYearForMonth(monthRef.year, monthRef.monthIndex);
    if (!this._hass) {
      return Promise.resolve(null);
    }
    if (this._seasonCache.has(seasonStartYear)) {
      if (
        seasonStartYear ===
        this._seasonStartYearForMonth(this._selectedMonth.year, this._selectedMonth.monthIndex)
      ) {
        this._seasonData = this._seasonCache.get(seasonStartYear);
      }
      return Promise.resolve(this._seasonCache.get(seasonStartYear));
    }
    const pendingLoad = this._pendingLoads.get(seasonStartYear);
    if (pendingLoad) {
      return pendingLoad;
    }

    this._loadErrors.delete(seasonStartYear);
    const loadPromise = Promise.resolve()
      .then(() =>
        this._hass.connection.sendMessagePromise({
          type: "edf_tempo_tbe/get_season_calendar",
          season_start_year: seasonStartYear,
        }),
      )
      .then((result) => {
        this._currentMonth = this._computeCurrentMonth();
        this._seasonCache.set(seasonStartYear, result);
        if (
          seasonStartYear ===
          this._seasonStartYearForMonth(this._selectedMonth.year, this._selectedMonth.monthIndex)
        ) {
          this._seasonData = result;
        }
        return result;
      })
      .catch((err) => {
        this._loadErrors.set(
          seasonStartYear,
          err?.message || edfTempoCardText(this._hass, "load_month_failed"),
        );
        return null;
      })
      .finally(() => {
        this._pendingLoads.delete(seasonStartYear);
        this._render();
      });

    this._pendingLoads.set(seasonStartYear, loadPromise);
    this._render();
    return loadPromise;
  }

  _render() {
    if (!this.shadowRoot || !this._config) {
      return;
    }

    const model = this._buildMonthModel();
    const canGoPrevious = this._compareMonthRef(this._selectedMonth, this._minMonth) > 0;
    const canGoNext = this._compareMonthRef(this._selectedMonth, this._currentMonth) < 0;
    const selectedSeasonStartYear = this._seasonStartYearForMonth(
      this._selectedMonth.year,
      this._selectedMonth.monthIndex,
    );
    const isLoading = this._pendingLoads.has(selectedSeasonStartYear);
    const loadError = this._loadErrors.get(selectedSeasonStartYear);

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }

        ha-card {
          background:
            radial-gradient(circle at top right, rgba(16, 87, 200, 0.1), transparent 34%),
            linear-gradient(180deg, rgba(255, 255, 255, 0.08), transparent 60%),
            var(--ha-card-background, var(--card-background-color, #ffffff));
          border: 1px solid rgba(116, 127, 151, 0.22);
          border-radius: 24px;
          box-shadow: 0 16px 36px rgba(15, 23, 42, 0.08);
          overflow: hidden;
        }

        .card {
          padding: 20px;
        }

        .header {
          align-items: center;
          display: grid;
          gap: 12px;
          grid-template-columns: 40px 1fr 40px;
        }

        .nav {
          align-items: center;
          appearance: none;
          background: rgba(15, 23, 42, 0.04);
          border: 0;
          border-radius: 999px;
          color: var(--primary-text-color);
          cursor: pointer;
          display: inline-flex;
          font-size: 1.2rem;
          height: 40px;
          justify-content: center;
          transition: background 160ms ease, color 160ms ease;
          width: 40px;
        }

        .nav:hover:not(:disabled) {
          background: rgba(16, 87, 200, 0.12);
          color: #1057c8;
        }

        .nav:disabled {
          color: rgba(102, 112, 133, 0.45);
          cursor: default;
        }

        .heading {
          text-align: center;
        }

        .card-title {
          color: var(--primary-text-color);
          font-size: 1.08rem;
          font-weight: 800;
          letter-spacing: 0.01em;
          margin-bottom: 8px;
        }

        .title {
          color: var(--primary-text-color);
          font-size: 1.22rem;
          font-weight: 900;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }

        .year {
          color: var(--secondary-text-color, #667085);
          font-size: 0.92rem;
          font-weight: 700;
          letter-spacing: 0.16em;
          margin-top: 6px;
          text-transform: uppercase;
        }

        .state {
          color: var(--secondary-text-color, #667085);
          font-size: 0.95rem;
          font-weight: 600;
          margin-top: 18px;
          text-align: center;
        }

        .month {
          background: rgba(255, 255, 255, 0.48);
          border: 1px solid rgba(116, 127, 151, 0.16);
          border-radius: 18px;
          margin-top: 20px;
          padding: 16px 14px 14px;
        }

        .weekday-row {
          color: var(--secondary-text-color, #667085);
          display: grid;
          font-size: 0.78rem;
          font-weight: 800;
          gap: 8px;
          grid-template-columns: repeat(7, minmax(0, 1fr));
          justify-items: center;
          margin-bottom: 10px;
          text-transform: uppercase;
        }

        .days {
          display: grid;
          gap: 8px;
          grid-template-columns: repeat(7, minmax(0, 1fr));
          justify-items: center;
        }

        .day {
          align-items: center;
          border-radius: 999px;
          display: inline-flex;
          font-size: 0.88rem;
          font-weight: 800;
          height: 34px;
          justify-content: center;
          width: 34px;
        }

        .day.empty {
          background: transparent;
        }

        .day.none {
          background: #eadfcb;
          color: #5c4632;
        }

        .day.blue {
          background: #1057c8;
          color: #ffffff;
        }

        .day.white {
          background: #f4f4f4;
          border: 1px solid rgba(17, 24, 39, 0.08);
          color: #111827;
        }

        .day.red {
          background: #e85130;
          color: #ffffff;
        }
      </style>
      <ha-card>
        <div class="card">
          <div class="header">
            <button class="nav" data-action="previous" aria-label="${edfTempoCardText(this._hass, "previous")}" title="${edfTempoCardText(this._hass, "previous")}" ${canGoPrevious ? "" : "disabled"}>&larr;</button>
            <div class="heading">
              <div class="card-title">${this._escapeHtml(edfTempoCardText(this._hass, "monthly_title"))}</div>
              <div class="title">${this._escapeHtml(model.title)}</div>
              <div class="year">${this._escapeHtml(model.year)}</div>
            </div>
            <button class="nav" data-action="next" aria-label="${edfTempoCardText(this._hass, "next")}" title="${edfTempoCardText(this._hass, "next")}" ${canGoNext ? "" : "disabled"}>&rarr;</button>
          </div>
          ${
            isLoading
              ? `<div class="state">${this._escapeHtml(this._t("loading_month"))}</div>`
              : loadError
                ? `<div class="state">${this._escapeHtml(loadError)}</div>`
                : `<section class="month">
                    <div class="weekday-row">${model.weekdaysHtml}</div>
                    <div class="days">${model.daysHtml}</div>
                  </section>`
          }
        </div>
      </ha-card>
    `;

    this.shadowRoot.querySelector('[data-action="previous"]')?.addEventListener("click", () => {
      this._navigate(-1);
    });
    this.shadowRoot.querySelector('[data-action="next"]')?.addEventListener("click", () => {
      this._navigate(1);
    });
  }

  _buildMonthModel() {
    const title = this._monthLabel(this._selectedMonth.monthIndex, this._selectedMonth.year).toUpperCase();
    const year = String(this._selectedMonth.year);
    const weekdaysHtml = this._weekdayLabels()
      .map((label) => `<div>${this._escapeHtml(label)}</div>`)
      .join("");
    const daysHtml = this._buildMonthCells(
      this._selectedMonth.year,
      this._selectedMonth.monthIndex,
      this._seasonData,
    )
      .map((cell) => {
        if (cell.empty) {
          return `<div class="day empty"></div>`;
        }
        return `<div class="day ${cell.className}" title="${this._escapeHtml(cell.title)}">${this._escapeHtml(
          cell.label,
        )}</div>`;
      })
      .join("");

    return {
      title,
      year,
      weekdaysHtml,
      daysHtml,
    };
  }

  _buildMonthCells(year, monthIndex, seasonData) {
    const firstDay = new Date(year, monthIndex, 1);
    const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
    const leadingEmpty = (firstDay.getDay() + 6) % 7;
    const cells = [];

    for (let index = 0; index < leadingEmpty; index += 1) {
      cells.push({ empty: true });
    }

    for (let day = 1; day <= daysInMonth; day += 1) {
      const isoDate = this._toIsoDate(year, monthIndex, day);
      const colorCode = seasonData?.day_colors?.[isoDate] || null;
      const className =
        {
          BLUE: "blue",
          WHITE: "white",
          RED: "red",
        }[colorCode] || "none";
      cells.push({
        empty: false,
        label: String(day),
        className,
        title: colorCode ? `${isoDate} - ${colorCode}` : isoDate,
      });
    }

    return cells;
  }

  _navigate(offset) {
    const nextMonth = this._addMonths(this._selectedMonth, offset);
    if (
      this._compareMonthRef(nextMonth, this._minMonth) < 0 ||
      this._compareMonthRef(nextMonth, this._currentMonth) > 0
    ) {
      return;
    }

    this._selectedMonth = nextMonth;
    this._seasonData =
      this._seasonCache.get(this._seasonStartYearForMonth(nextMonth.year, nextMonth.monthIndex)) || null;
    this._ensureMonthData(nextMonth);
    this._render();
  }

  _computeCurrentMonth() {
    const now = new Date();
    return { year: now.getFullYear(), monthIndex: now.getMonth() };
  }

  _seasonStartYearForMonth(year, monthIndex) {
    return monthIndex >= 8 ? year : year - 1;
  }

  _addMonths(monthRef, offset) {
    const date = new Date(monthRef.year, monthRef.monthIndex + offset, 1);
    return {
      year: date.getFullYear(),
      monthIndex: date.getMonth(),
    };
  }

  _compareMonthRef(left, right) {
    if (left.year !== right.year) {
      return left.year - right.year;
    }
    return left.monthIndex - right.monthIndex;
  }

  _monthLabel(monthIndex, year) {
    return new Intl.DateTimeFormat(this._locale(), {
      month: "long",
    }).format(new Date(year, monthIndex, 1));
  }

  _weekdayLabels() {
    const baseDate = new Date(2024, 0, 1);
    const labels = [];
    for (let offset = 0; offset < 7; offset += 1) {
      const day = new Date(baseDate);
      day.setDate(baseDate.getDate() + offset);
      labels.push(
        new Intl.DateTimeFormat(this._locale(), { weekday: "short" })
          .format(day)
          .replace(".", "")
          .slice(0, 2),
      );
    }
    return labels;
  }

  _toIsoDate(year, monthIndex, day) {
    return `${String(year)}-${String(monthIndex + 1).padStart(2, "0")}-${String(day).padStart(
      2,
      "0",
    )}`;
  }

  _t(key) {
    const translations = this._isFrench()
      ? {
          loading_month: "Chargement du mois Tempo...",
        }
      : {
          loading_month: "Loading Tempo month...",
        };
    return translations[key] || key;
  }

  _locale() {
    return this._isFrench() ? "fr-FR" : "en-GB";
  }

  _isFrench() {
    const language =
      this._hass?.locale?.language ||
      this._hass?.language ||
      this._hass?.selectedLanguage ||
      "en";
    return String(language).toLowerCase().startsWith("fr");
  }

  _escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }
}

if (!customElements.get("edf-tempo-card-editor")) {
  customElements.define("edf-tempo-card-editor", EdfTempoCardEditor);
}

if (!customElements.get("edf-tempo-season-card-editor")) {
  customElements.define("edf-tempo-season-card-editor", EdfTempoSeasonCardEditor);
}

if (!customElements.get("edf-tempo-season-calendar-card-editor")) {
  customElements.define("edf-tempo-season-calendar-card-editor", EdfTempoSeasonCalendarCardEditor);
}

if (!customElements.get("edf-tempo-month-card-editor")) {
  customElements.define("edf-tempo-month-card-editor", EdfTempoMonthCardEditor);
}

if (!customElements.get("edf-tempo-card")) {
  customElements.define("edf-tempo-card", EdfTempoCard);
}

if (!customElements.get("edf-tempo-season-card")) {
  customElements.define("edf-tempo-season-card", EdfTempoSeasonCard);
}

if (!customElements.get("edf-tempo-season-calendar-card")) {
  customElements.define("edf-tempo-season-calendar-card", EdfTempoSeasonCalendarCard);
}

if (!customElements.get("edf-tempo-month-card")) {
  customElements.define("edf-tempo-month-card", EdfTempoMonthCard);
}

const edfTempoPickerIsFrench = navigator.language?.toLowerCase().startsWith("fr");

window.customCards = window.customCards || [];
if (!window.customCards.find((card) => card.type === "edf-tempo-card")) {
  window.customCards.push({
    type: "edf-tempo-card",
    name: edfTempoPickerIsFrench ? "EDF Tempo Rev TBE Quotidien" : "EDF Tempo Rev TBE Daily",
    description: edfTempoPickerIsFrench
      ? "Affiche les couleurs EDF Tempo Rev TBE d'aujourd'hui et de demain."
      : "Displays EDF Tempo Rev TBE colors for today and tomorrow.",
    preview: true,
  });
}

if (!window.customCards.find((card) => card.type === "edf-tempo-season-card")) {
  window.customCards.push({
    type: "edf-tempo-season-card",
    name: edfTempoPickerIsFrench ? "EDF Tempo Rev TBE Synthèse Saison" : "EDF Tempo Rev TBE Season Summary",
    description: edfTempoPickerIsFrench
      ? "Affiche la synthèse de la saison EDF Tempo Rev TBE en cours."
      : "Displays the current EDF Tempo Rev TBE season summary.",
    preview: true,
  });
}

if (!window.customCards.find((card) => card.type === "edf-tempo-season-calendar-card")) {
  window.customCards.push({
    type: "edf-tempo-season-calendar-card",
    name: edfTempoPickerIsFrench ? "Calendrier EDF Tempo Rev TBE" : "EDF Tempo Rev TBE Season Calendar",
    description: edfTempoPickerIsFrench
      ? "Affiche le calendrier complet d'une saison EDF Tempo Rev TBE avec navigation."
      : "Displays a full EDF Tempo Rev TBE season calendar with navigation.",
    preview: true,
  });
}

if (!window.customCards.find((card) => card.type === "edf-tempo-month-card")) {
  window.customCards.push({
    type: "edf-tempo-month-card",
    name: edfTempoPickerIsFrench ? "EDF Tempo Rev TBE Mensuel" : "EDF Tempo Rev TBE Monthly",
    description: edfTempoPickerIsFrench
      ? "Affiche le calendrier mensuel EDF Tempo Rev TBE avec navigation par mois."
      : "Displays the monthly EDF Tempo Rev TBE calendar with month navigation.",
    preview: true,
  });
}
