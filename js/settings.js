// File Version: 1.0
let fieldIds = [];
    let SETTINGS_MONITORS_CACHE = [];
    let SETTINGS_MONITORS_READY = false;
    let SETTINGS_MONITORS_LOADING = null;
    let SETTINGS_TUYA_DEVICES_READY = false;
    let SETTINGS_TUYA_DEVICES_LOADING = null;
    let SETTINGS_BUTTONS_EDITOR_READY = false;
    let SETTINGS_MONITOR_POWER_READY = false;
    let SETTINGS_MONITOR_POWER_LOADING = null;
 
    function getTrackedFieldIds() {
      const seen = new Set();
      return Array.from(document.querySelectorAll('.section input[id], .section textarea[id], .section select[id]'))
        .filter((el) => !el.closest('#section-logs') && !el.closest('#section-sitemap') && !el.closest('#section-health'))
        .map((el) => String(el.id || '').trim())
        .filter((id) => {
          if (!id || id === 'liquidThemeCodePreview' || id.endsWith('_proxy') || seen.has(id)) return false;
          seen.add(id);
          return true;
        });
    }
 
    let SETTINGS_LIQUID_THEME_PRESETS = window.LIQUID_THEME_PRESETS || Object.freeze({
      default_glass: { label: 'Default Glass / Ice', vars: {} }
    });
    let SETTINGS_LIQUID_THEME_PRESETS_LOADED = !!window.LIQUID_THEME_PRESETS;
    let SETTINGS_LIQUID_CONTROLS_READY = false;
    let SETTINGS_LIQUID_CONTROLS_LOADING = null;
 
    function extractObjectLiteralAfterMarker(source, markerText) {
      const markerIndex = source.indexOf(markerText);
      if (markerIndex < 0) return '';
      const freezeIndex = source.indexOf('Object.freeze', markerIndex);
      const searchFrom = freezeIndex >= 0 ? freezeIndex : markerIndex;
      const startIndex = source.indexOf('{', searchFrom);
      if (startIndex < 0) return '';
      let depth = 0, quote = '', escaped = false, lineComment = false, blockComment = false;
      for (let i = startIndex; i < source.length; i++) {
        const ch = source[i], next = source[i + 1];
        if (lineComment) { if (ch === '\n' || ch === '\r') lineComment = false; continue; }
        if (blockComment) { if (ch === '*' && next === '/') { blockComment = false; i++; } continue; }
        if (quote) { if (escaped) { escaped = false; continue; } if (ch === '\\') { escaped = true; continue; } if (ch === quote) quote = ''; continue; }
        if (ch === '/' && next === '/') { lineComment = true; i++; continue; }
        if (ch === '/' && next === '*') { blockComment = true; i++; continue; }
        if (ch === '"' || ch === "'" || ch === '`') { quote = ch; continue; }
        if (ch === '{') depth++;
        if (ch === '}') { depth--; if (depth === 0) return source.slice(startIndex, i + 1); }
      }
      return '';
    }
 
    async function loadSettingsLiquidThemePresetsLocal(force = false) {
      const hasUsefulThemes = () => (
        window.LIQUID_THEME_PRESETS
        && typeof window.LIQUID_THEME_PRESETS === 'object'
        && Object.keys(window.LIQUID_THEME_PRESETS).length > 1
      );

      const adoptWindowThemes = () => {
        if (hasUsefulThemes()) {
          SETTINGS_LIQUID_THEME_PRESETS = window.LIQUID_THEME_PRESETS;
          SETTINGS_LIQUID_THEME_PRESETS_LOADED = true;
          return true;
        }
        return false;
      };

      if (!force && adoptWindowThemes()) {
        return SETTINGS_LIQUID_THEME_PRESETS;
      }

      // /liquid_themes.js can sometimes be stale or not loaded yet.
      // Fetch it with no-store and run it in the same page context so the
      // settings page always has the complete theme list.
      try {
        const res = await fetch(`/liquid_themes.js?_settings_reload=${Date.now()}`, { cache: 'no-store' });
        if (res.ok) {
          const source = await res.text();
          if (source && source.includes('LIQUID_THEME_PRESETS')) {
            Function(source)();
            adoptWindowThemes();
          }
        }
      } catch (err) {
        console.warn('Liquid themes reload failed:', err);
      }

      if (!adoptWindowThemes()) {
        SETTINGS_LIQUID_THEME_PRESETS_LOADED = true;
      }
      return SETTINGS_LIQUID_THEME_PRESETS;
    }
 
    const SETTINGS_LIQUID_THEME_DEFAULT_KEY = window.LIQUID_THEME_DEFAULT_KEY || 'default_glass';
 
    function getSettingsLiquidThemePreset(themeKey) {
      const key = String(themeKey || '').trim();
      return SETTINGS_LIQUID_THEME_PRESETS[key] || SETTINGS_LIQUID_THEME_PRESETS[SETTINGS_LIQUID_THEME_DEFAULT_KEY];
    }
 
    function buildSettingsLiquidThemeCode(themeKey) {
      const preset = getSettingsLiquidThemePreset(themeKey);
      const lines = [`/* ${preset.label} */`, '{'];
      Object.entries(preset.vars || {}).forEach(([name, value]) => { lines.push(`    ${name}: ${value};`); });
      lines.push('}');
      return lines.join('\n');
    }
 
    function applySettingsLiquidPreview(selectEl) {
      if (!selectEl) return;
      const target = selectEl.dataset.liquidPreview || '';
      const preview = document.getElementById(`liquidPreview${target.charAt(0).toUpperCase() + target.slice(1)}`);
      const preset = getSettingsLiquidThemePreset(selectEl.value || selectEl.dataset.default || SETTINGS_LIQUID_THEME_DEFAULT_KEY);
      if (preview && preset && preset.vars) {
        Object.entries(preset.vars).forEach(([name, value]) => {
          preview.style.setProperty(name.replace('--', '--preview-'), value);
        });
        preview.style.setProperty('--preview-shadow', preset.vars['--shadow'] || preset.vars['--liq-6'] || 'rgba(0,0,0,.35)');
        preview.title = preset.label || selectEl.value || '';
        preview.setAttribute('aria-label', `${selectEl.dataset.liquidPreview || 'liquid'} preview: ${preset.label || selectEl.value || ''}`);
      }
    }
 
    function updateSettingsLiquidCodePreview() {
      const codeEl = document.getElementById('liquidThemeCodePreview');
      if (!codeEl) return;
      const parts = [];
      ['cpu','gpu','ram','fps','power','shift'].forEach(k => {
        const el = document.getElementById(`frontend.liquid_theme_${k}`);
        if (el) parts.push(`.liquid-svg.theme-${k} ${buildSettingsLiquidThemeCode(el.value)}`);
      });
      codeEl.value = parts.join('\n\n');
    }
 
    function syncSettingsLiquidThemePreviews() {
      document.querySelectorAll('[data-liquid-preview]').forEach((selectEl) => applySettingsLiquidPreview(selectEl));
      updateSettingsLiquidCodePreview();
    }

    function syncSettingsLiquidLivePreview() {
      const control = document.getElementById('frontend.settings_liquid_live_preview_enabled');
      document.body.classList.toggle('settings-liquid-live-preview', !!(control && control.checked));
    }

    function syncSettingsRenderMode() {
      const control = document.getElementById('frontend.settings_visual_effects_enabled');
      document.body.classList.toggle('settings-lite-render', !(control && control.checked));
    }

    function ensureSelectOption(selectEl, value, label = '') {
      if (!selectEl || value === undefined || value === null || value === '') return;
      const strValue = String(value);
      const exists = Array.from(selectEl.options || []).some((option) => option.value === strValue);
      if (exists) return;
      const option = document.createElement('option');
      option.value = strValue;
      option.textContent = label || strValue;
      selectEl.appendChild(option);
    }
 
    function populateSettingsLiquidThemeOptions() {
      const optionEntries = [];
      const seenThemeKeys = new Set();

      if (Array.isArray(window.LIQUID_THEME_OPTIONS)) {
        window.LIQUID_THEME_OPTIONS.forEach((item) => {
          const key = String((item && item.key) || '').trim();
          if (!key || seenThemeKeys.has(key) || !SETTINGS_LIQUID_THEME_PRESETS[key]) return;
          seenThemeKeys.add(key);
          optionEntries.push([key, SETTINGS_LIQUID_THEME_PRESETS[key]]);
        });
      }

      Object.entries(SETTINGS_LIQUID_THEME_PRESETS).forEach(([key, preset]) => {
        if (seenThemeKeys.has(key)) return;
        seenThemeKeys.add(key);
        optionEntries.push([key, preset]);
      });

      document.querySelectorAll('[data-liquid-preview]').forEach((selectEl) => {
        if (!selectEl) return;
        const savedValue = getByPath(currentSettings || {}, selectEl.id, '');
        const current = savedValue || selectEl.value || selectEl.dataset.default || SETTINGS_LIQUID_THEME_DEFAULT_KEY;
        const fragment = document.createDocumentFragment();
        optionEntries.forEach(([key, preset]) => {
          const option = document.createElement('option');
          option.value = key;
          option.textContent = preset && preset.label ? preset.label : key;
          fragment.appendChild(option);
        });
        selectEl.innerHTML = '';
        selectEl.appendChild(fragment);
        selectEl.value = SETTINGS_LIQUID_THEME_PRESETS[current] ? current : SETTINGS_LIQUID_THEME_DEFAULT_KEY;
      });
    }
 
    async function bindSettingsLiquidThemeControls() {
      if (SETTINGS_LIQUID_CONTROLS_READY) return;
      if (SETTINGS_LIQUID_CONTROLS_LOADING) return SETTINGS_LIQUID_CONTROLS_LOADING;
      SETTINGS_LIQUID_CONTROLS_LOADING = (async () => {
      await loadSettingsLiquidThemePresetsLocal(true);
      populateSettingsLiquidThemeOptions();
      document.querySelectorAll('[data-liquid-preview]').forEach((selectEl) => {
        if (selectEl.dataset.liquidBound === '1') return;
        selectEl.dataset.liquidBound = '1';
        selectEl.addEventListener('change', syncSettingsLiquidThemePreviews);
      });
      syncSettingsLiquidThemePreviews();
        SETTINGS_LIQUID_CONTROLS_READY = true;
      })();
      try {
        await SETTINGS_LIQUID_CONTROLS_LOADING;
      } finally {
        SETTINGS_LIQUID_CONTROLS_LOADING = null;
      }
    }
 
    function getSectionIconSvg(sectionId) {
      const icons = {
        'section-home': '<svg viewBox="0 0 24 24"><path d="M3 11l9-7 9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/></svg>',
        'section-performance': '<svg viewBox="0 0 24 24"><path d="M4 14a8 8 0 1 1 16 0"/><path d="M12 12l4-4"/><path d="M12 12l3 5"/></svg>',
        'section-ui': '<svg viewBox="0 0 24 24"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>',
        'section-window': '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18"/><path d="M9 20V9"/></svg>',
        'section-tuya': '<svg viewBox="0 0 24 24"><path d="M12 2v8"/><path d="M8 6h8"/><path d="M6 13a6 6 0 1 0 12 0c0-2.2-1.2-3.8-3-5"/></svg>',
        'section-logging': '<svg viewBox="0 0 24 24"><path d="M4 19h16"/><path d="M7 16V8"/><path d="M12 16V5"/><path d="M17 16v-4"/></svg>',
        'section-frontend': '<svg viewBox="0 0 24 24"><path d="M12 3l2.5 5 5.5.8-4 3.9.9 5.5-4.9-2.6-4.9 2.6.9-5.5-4-3.9 5.5-.8z"/></svg>',
        'section-panel-buttons': '<svg viewBox="0 0 24 24"><rect x="4" y="4" width="6" height="6" rx="1.5"/><rect x="14" y="4" width="6" height="6" rx="1.5"/><rect x="4" y="14" width="6" height="6" rx="1.5"/><rect x="14" y="14" width="6" height="6" rx="1.5"/></svg>',
        'section-calendar': '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4"/><path d="M8 3v4"/><path d="M3 10h18"/></svg>',
        'section-health': '<svg viewBox="0 0 24 24"><path d="M22 12h-4l-2 5-4-10-3 7H2"/></svg>',
        'section-logs': '<svg viewBox="0 0 24 24"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/><path d="M8 13h8"/><path d="M8 17h5"/></svg>',
        'section-sitemap': '<svg viewBox="0 0 24 24"><circle cx="12" cy="5" r="2.5"/><circle cx="6" cy="18" r="2.5"/><circle cx="18" cy="18" r="2.5"/><path d="M12 7.5V12"/><path d="M12 12L6 15.5"/><path d="M12 12l6 3.5"/></svg>',
        'section-reset': '<svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 3v6h6"/></svg>',
        'section-api': '<svg viewBox="0 0 24 24"><path d="M8 12h8"/><path d="M12 8v8"/><rect x="3" y="6" width="5" height="12" rx="2"/><rect x="16" y="6" width="5" height="12" rx="2"/></svg>',
      };
      return icons[sectionId] || '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/></svg>';
    }

    function injectSectionHeadIcons() {
      document.querySelectorAll('.section').forEach((section) => {
        const headText = section.querySelector('.section-head-text');
        const title = headText ? headText.querySelector('h2') : null;
        if (!headText || !title || headText.querySelector('.section-title-row')) return;
        const row = document.createElement('div');
        row.className = 'section-title-row';
        const icon = document.createElement('div');
        icon.className = 'section-title-icon';
        icon.innerHTML = getSectionIconSvg(section.id);
        title.parentNode.insertBefore(row, title);
        row.appendChild(icon);
        row.appendChild(title);
      });
    }
 
    const statusDot     = document.getElementById('statusDot');
    const statusText    = document.getElementById('statusText');
    const statusSubtext = document.getElementById('statusSubtext');
    const summarySection = document.getElementById('summarySection');
    const summaryDescription = document.getElementById('summaryDescription');
    const settingsThemeStylesheet = document.getElementById('settingsThemeStylesheet');
    const summaryStatus  = document.getElementById('summaryStatus');
    const summaryMode    = document.getElementById('summaryMode');
    const panelLanguageTop = document.getElementById('frontend.panel_language_top');
    const panelButtonsEditor = document.getElementById('panelButtonsEditor');
    let currentSettings = {};

    const SETTINGS_FIELD_DEFAULTS = Object.freeze({
      'commands.nollie_state_path': 'D:\\Program\\pc-control\\nollie\\nollie_brightness_state.json',
      'commands.nollie_include_boot_canvases': true,
      'commands.lian_profile_path': 'D:\\Program\\pc-control\\lian\\lconnect_profiles.json',
      'commands.lian_state_cache_path': 'D:\\Program\\pc-control\\lian\\last_lconnect_state.json',
      'commands.lian_data_dir': 'C:\\ProgramData\\Lian-Li\\L-Connect 3',
      'commands.lian_merge_state_path': '',
      'commands.lian_service_url': 'http://127.0.0.1:11021/',
      'commands.lian_timeout_seconds': 2.5,
    });

    function getSettingsFieldDefault(id) {
      return Object.prototype.hasOwnProperty.call(SETTINGS_FIELD_DEFAULTS, id) ? SETTINGS_FIELD_DEFAULTS[id] : undefined;
    }

    const SECTION_SUMMARIES = Object.freeze({
      'section-home': 'sections.home.desc',
      'section-performance': 'sections.performance.desc',
      'section-ui': 'sections.ui.desc',
      'section-window': 'sections.window.desc',
      'section-tuya': 'sections.tuya.desc',
      'section-logging': 'sections.logging.desc',
      'section-frontend': 'sections.frontend.desc',
      'section-panel-buttons': 'sections.buttons.desc',
      'section-calendar': 'sections.calendar.desc',
      'section-health': 'sections.health.desc',
      'section-logs': 'sections.logs.desc',
      'section-sitemap': 'sections.sitemap.desc',
      'section-reset': 'sections.reset.desc',
      'section-api': 'sections.api.desc',
    });
 
    function applySettingsTheme() {
      const nextTheme = 'dark';
      if (settingsThemeStylesheet) {
        settingsThemeStylesheet.setAttribute('href', '/assets/css/settings-theme-dark.css?v=__ASSET_VERSION__');
      }
      try { localStorage.setItem('settings_theme', nextTheme); } catch (_) {}
      return nextTheme;
    }

    function initSettingsTheme() {
      applySettingsTheme();
    }
 
    function markSaved(saved, text, subtext = '') {
      const trText = (value, fallbackKey) => {
        if (typeof translateSettingsText === 'function') return translateSettingsText(value || (typeof t === 'function' ? t(fallbackKey, value) : value));
        return value || fallbackKey;
      };
      statusDot.classList.toggle('saved', !!saved);
      statusText.textContent = trText(text, saved ? 'global.status_saved' : 'global.not_saved');
      statusSubtext.textContent = trText(subtext, saved ? 'global.saved_default' : 'global.draft_default');
      if (summaryStatus) summaryStatus.textContent = trText(saved ? 'Saved' : 'Taslak', saved ? 'global.status_saved' : 'global.status_draft');
    }
 
    function setByPath(obj, path, value) {
      const parts = path.split('.');
      let node = obj;
      for (let i = 0; i < parts.length - 1; i++) {
        const key = parts[i];
        if (!node[key] || typeof node[key] !== 'object') node[key] = {};
        node = node[key];
      }
      node[parts[parts.length - 1]] = value;
    }
 
    function getByPath(obj, path, fallback = '') {
      return path.split('.').reduce((acc, key) => (acc && acc[key] !== undefined ? acc[key] : undefined), obj) ?? fallback;
    }

    function normalizePanelLanguageValue(value) {
      return String(value || '').trim().toLowerCase() === 'tr' ? 'tr' : 'en';
    }

    function syncPanelLanguageControls(value, source = '') {
      const next = normalizePanelLanguageValue(value);
      const mainSelect = document.getElementById('frontend.panel_language');
      if (panelLanguageTop && source !== 'top') panelLanguageTop.value = next;
      if (mainSelect && source !== 'main') mainSelect.value = next;
    }
 
    function parseFieldValue(el) {
      if (el.type === 'checkbox') return el.checked;
      if (el.type === 'number') {
        const raw = String(el.value || '').trim().replace(',', '.');
        const n = Number(raw);
        return Number.isFinite(n) ? n : 0;
      }
      return el.value;
    }
 
    function getSections() { return Array.from(document.querySelectorAll('.section')); }
    function getTabButtons() { return Array.from(document.querySelectorAll('.tab-button')); }
 
    function activateTab(sectionId) {
      getSections().forEach((section) => section.classList.toggle('is-active', section.id === sectionId));
      getTabButtons().forEach((button) => button.classList.toggle('is-active', button.dataset.tabTarget === sectionId));
      const activeSection = document.getElementById(sectionId);
      if (activeSection) {
        if (summarySection) summarySection.textContent = activeSection.dataset.sectionTitle || 'Settings';
        if (summaryDescription) summaryDescription.textContent = settingsText(SECTION_SUMMARIES[sectionId], 'Settings and tools for this section.');
        try { localStorage.setItem('panel_active_tab', sectionId); } catch (_) {}
        try { const nextHash = '#' + sectionId; if (window.location.hash !== nextHash) history.replaceState(null, '', nextHash); } catch (_) {}
        if (sectionId === 'section-frontend') {
          bindSettingsLiquidThemeControls().catch(console.error);
        }
        if (sectionId === 'section-window' || sectionId === 'section-ui') {
          ensureMonitorOptionsLoaded().catch(console.error);
        }
        if (sectionId === 'section-tuya') {
          ensureTuyaDeviceOptionsLoaded().catch(console.error);
          refreshTuyaSourceCards(currentSettings || {});
        }
        if (sectionId === 'section-panel-buttons') {
          ensurePanelButtonsEditorRendered();
        }
        if (sectionId === 'section-performance') {
          refreshHwinfoSettingsStatus();
        }
        if (typeof applySettingsLanguage === 'function') {
          requestAnimationFrame(() => applySettingsLanguage());
        }
      }
    }
 
    function initTabs() {
      getTabButtons().forEach((button) => {
        button.addEventListener('click', () => activateTab(button.dataset.tabTarget));
      });
      let hashTab = '';
      try { hashTab = String(window.location.hash || '').replace(/^#/, '').trim(); } catch (_) {}
      const defaultTab = 'section-home';
      const preferredTab = (hashTab && document.getElementById(hashTab) && hashTab) || defaultTab;
      activateTab(preferredTab);
    }

    function initHomeQuickNav() {
      const navigateToSection = (sectionId) => {
        const nextId = String(sectionId || '').trim();
        if (!nextId || !document.getElementById(nextId)) return;
        activateTab(nextId);
      };

      document.querySelectorAll('[data-home-target]').forEach((card) => {
        card.addEventListener('click', (event) => {
          if (event.target.closest('[data-tab-link]')) return;
          navigateToSection(card.getAttribute('data-home-target'));
        });
        card.addEventListener('keydown', (event) => {
          if (event.key !== 'Enter' && event.key !== ' ') return;
          event.preventDefault();
          navigateToSection(card.getAttribute('data-home-target'));
        });
      });

      document.querySelectorAll('[data-tab-link]').forEach((linkButton) => {
        linkButton.addEventListener('click', (event) => {
          event.preventDefault();
          event.stopPropagation();
          navigateToSection(linkButton.getAttribute('data-tab-link'));
        });
      });
    }

    function escapeHtml(value) {
      return String(value ?? '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    function settingsText(key, fallback = '') {
      return (typeof t === 'function') ? t(key, fallback) : fallback;
    }

    function settingsErrorText(error) {
      const raw = String((error && error.message) || error || '').trim();
      if (!raw) return settingsText('dynamic.network_error', 'Backend connection could not be reached.');
      if (/failed to fetch|networkerror|load failed/i.test(raw)) {
        return settingsText('dynamic.network_error', 'Backend connection could not be reached.');
      }
      return raw;
    }

    function settingsTranslate(value) {
      return (typeof translateSettingsText === 'function') ? translateSettingsText(value) : value;
    }

    function settingsRecordsText(count) {
      return `${count} ${settingsText('dynamic.records', 'records')}`;
    }
 
    function moveArrayItem(items, fromIndex, toIndex) {
      const next = Array.isArray(items) ? items.slice() : [];
      if (fromIndex < 0 || toIndex < 0 || fromIndex >= next.length || toIndex >= next.length || fromIndex === toIndex) return next;
      const [item] = next.splice(fromIndex, 1);
      next.splice(toIndex, 0, item);
      return next;
    }
 
    function normalizePanelButton(raw = {}, index = 0) {
      const fallbackId = `button_${index + 1}`;
      return {
        id: String(raw.id || fallbackId).trim() || fallbackId,
        label: String(raw.label || `${settingsText('tabs.buttons', 'Button')} ${index + 1}`),
        visible: raw.visible !== false,
        variant: String(raw.variant || 'white-glow'),
        command: String(raw.command || ''),
        secondary_command: String(raw.secondary_command || ''),
        method: String(raw.method || 'GET').toUpperCase(),
        confirm_text: String(raw.confirm_text || ''),
        icon_svg: String(raw.icon_svg || '').trim(),
      };
    }
 
    function renderPanelButtonsEditor(buttons = []) {
      if (!panelButtonsEditor) return;
      const normalized = Array.isArray(buttons) ? buttons.map(normalizePanelButton) : [];
      panelButtonsEditor.innerHTML = `
        ${normalized.map((button, index) => `
          <details class="button-editor-card" id="buttonCard-${index}">
            <summary>
              <div class="button-card-preview">${button.icon_svg ? button.icon_svg : `<div class="button-preview-empty">${escapeHtml(settingsText('sections.buttons.editor.svg', 'SVG'))}</div>`}</div>
              <div class="button-card-copy">
                <strong>${escapeHtml(button.label || `${settingsText('tabs.buttons', 'Button')} ${index + 1}`)}</strong>
                <div class="button-card-badges">
                  <span class="button-card-badge">${escapeHtml(button.id)}</span>
                  <span class="button-card-badge">${button.visible ? settingsText('dynamic.btn_visible', 'Visible') : settingsText('dynamic.btn_hidden', 'Hidden')}</span>
                  <span class="button-card-badge">${escapeHtml(button.method)}</span>
                </div>
              </div>
            </summary>
            <div class="button-editor-body">
              <div class="field"><label>${escapeHtml(settingsText('sections.buttons.editor.label', 'Label'))}</label><input type="text" data-btn="${index}" data-key="label" value="${escapeHtml(button.label)}"></div>
              <div class="field"><label>${escapeHtml(settingsText('sections.buttons.editor.variant', 'Variant'))}</label><input type="text" data-btn="${index}" data-key="variant" value="${escapeHtml(button.variant)}"></div>
              <div class="field"><label>${escapeHtml(settingsText('sections.buttons.editor.method', 'Method'))}</label><select data-btn="${index}" data-key="method"><option${button.method==='GET'?' selected':''}>GET</option><option${button.method==='POST'?' selected':''}>POST</option><option${button.method==='SPECIAL'?' selected':''}>SPECIAL</option></select></div>
              <div class="field"><div class="toggle"><div><strong>${escapeHtml(settingsText('sections.buttons.editor.visible', 'Visible'))}</strong><span>${escapeHtml(settingsText('sections.buttons.editor.visible_desc', 'Show on panel.'))}</span></div><input type="checkbox" data-btn="${index}" data-key="visible"${button.visible?' checked':''}></div></div>
              <div class="field full"><label>${escapeHtml(settingsText('sections.buttons.editor.cmd', 'Command / URL'))}</label><input type="text" data-btn="${index}" data-key="command" value="${escapeHtml(button.command)}"></div>
              <div class="field full"><label>${escapeHtml(settingsText('sections.buttons.editor.scmd', 'Secondary Command'))}</label><input type="text" data-btn="${index}" data-key="secondary_command" value="${escapeHtml(button.secondary_command)}"></div>
              <div class="field full"><label>${escapeHtml(settingsText('sections.buttons.editor.confirm', 'Confirm Text'))}</label><input type="text" data-btn="${index}" data-key="confirm_text" value="${escapeHtml(button.confirm_text)}"></div>
              <div class="field full"><label>${escapeHtml(settingsText('sections.buttons.editor.svg', 'Icon SVG'))}</label><textarea data-btn="${index}" data-key="icon_svg">${escapeHtml(button.icon_svg)}</textarea></div>
              <div class="button-preview"><div class="button-preview-empty">${button.icon_svg || escapeHtml(settingsText('dynamic.svg_preview', '(no icon)'))}</div></div>
            </div>
          </details>`).join('')}`;
    }

    function ensurePanelButtonsEditorRendered() {
      if (SETTINGS_BUTTONS_EDITOR_READY) return;
      const buttons = getByPath(currentSettings || {}, 'panel.left_buttons', []);
      renderPanelButtonsEditor(Array.isArray(buttons) ? buttons : []);
      SETTINGS_BUTTONS_EDITOR_READY = true;
    }
 
    async function fetchMonitorOptionsFromBackend() {
      try {
        const response = await fetch('/api/monitors', { cache: 'no-store' });
        const payload = await response.json();
        const monitors = payload && Array.isArray(payload.monitors) ? payload.monitors : [];
        return monitors;
      } catch (_) {
        return [];
      }
    }

    async function fetchMonitorPowerOptionsFromBackend() {
      try {
        const response = await fetch('/monitor/status', { cache: 'no-store' });
        const payload = await response.json();
        return payload && Array.isArray(payload.monitors) ? payload.monitors : [];
      } catch (_) {
        return [];
      }
    }

    function monitorPowerDisplayName(mon, index) {
      if (!mon || typeof mon !== 'object') return `Monitor ${index + 1}`;
      const label = mon.label || `Monitor ${index + 1}`;
      const fingerprint = String(mon.fingerprint || '').trim();
      return fingerprint ? label : `${label} - unavailable`;
    }

    function syncMonitorPowerTargetMeta() {
      const select = document.getElementById('monitor_power.target_fingerprint');
      const indexInput = document.getElementById('monitor_power.target_index');
      const descriptionInput = document.getElementById('monitor_power.target_description');
      const option = select && select.selectedOptions && select.selectedOptions[0] ? select.selectedOptions[0] : null;
      if (indexInput) indexInput.value = option && option.dataset.index !== undefined ? option.dataset.index : '-1';
      if (descriptionInput) descriptionInput.value = option && option.dataset.description !== undefined ? option.dataset.description : '';
    }

    async function ensureMonitorPowerOptionsLoaded(settings = currentSettings || {}) {
      const select = document.getElementById('monitor_power.target_fingerprint');
      if (!select) return;
      if (SETTINGS_MONITOR_POWER_READY) return;
      if (SETTINGS_MONITOR_POWER_LOADING) return SETTINGS_MONITOR_POWER_LOADING;
      SETTINGS_MONITOR_POWER_LOADING = (async () => {
        const monitors = await fetchMonitorPowerOptionsFromBackend();
        const savedValue = getByPath(settings || {}, 'monitor_power.target_fingerprint', '');
        select.innerHTML = `<option value="">${escapeHtml(settingsText('dynamic.select_monitor_power', 'Select DDC/CI monitor'))}</option>` + monitors.map((mon, index) => {
          const value = String(mon && mon.fingerprint ? mon.fingerprint : '').trim();
          const label = monitorPowerDisplayName(mon, index);
          const disabled = value && mon && mon.ddc === false ? ' disabled' : '';
          const physicalIndex = Number.isFinite(Number(mon && mon.index)) ? Number(mon.index) : index;
          const description = String(mon && mon.description ? mon.description : '').trim();
          return `<option value="${escapeHtml(value)}" data-index="${escapeHtml(String(physicalIndex))}" data-description="${escapeHtml(description)}"${disabled}>${escapeHtml(label)}</option>`;
        }).join('');
        if (savedValue) ensureSelectOption(select, savedValue, savedValue);
        select.value = savedValue || '';
        syncMonitorPowerTargetMeta();
        SETTINGS_MONITOR_POWER_READY = true;
      })();
      try {
        await SETTINGS_MONITOR_POWER_LOADING;
      } finally {
        SETTINGS_MONITOR_POWER_LOADING = null;
      }
    }

    function monitorDisplayName(mon, index) {
      if (!mon || typeof mon !== 'object') return `Monitor ${index + 1}`;
      const label = mon.label || mon.name || mon.device || mon.device_name || `Monitor ${index + 1}`;
      const left = mon.logical_left ?? mon.left ?? mon.x;
      const top = mon.logical_top ?? mon.top ?? mon.y;
      const width = mon.logical_width ?? mon.width;
      const height = mon.logical_height ?? mon.height;
      const geometry = (width && height) ? ` — ${width}×${height}` : '';
      const pos = (left !== undefined && top !== undefined) ? ` @ ${left},${top}` : '';
      return `${label}${geometry}${pos}`;
    }

    function monitorValue(mon) {
      if (!mon || typeof mon !== 'object') return '';
      return String(mon.device || mon.device_id || mon.device_name || mon.id || mon.name || '');
    }

    function applyMonitorGeometryToWindowFields(deviceValue) {
      const mon = (SETTINGS_MONITORS_CACHE || []).find((item) => monitorValue(item) === String(deviceValue || ''));
      if (!mon) return;

      const pairs = [
        ['window.target_monitor_left', mon.logical_left ?? mon.left ?? mon.x],
        ['window.target_monitor_top', mon.logical_top ?? mon.top ?? mon.y],
        ['window.target_monitor_width', mon.logical_width ?? mon.width],
        ['window.target_monitor_height', mon.logical_height ?? mon.height],
      ];

      pairs.forEach(([id, value]) => {
        const el = document.getElementById(id);
        if (el && value !== undefined && value !== null && value !== '') el.value = value;
      });
    }

    function setMonitorProxyPlaceholders(settings) {
      ['window.target_monitor_device_proxy', 'external_windows.spotify.target_monitor_device_proxy'].forEach((proxyId) => {
        const select = document.getElementById(proxyId);
        if (!select) return;
        const realId = proxyId.replace('_proxy', '');
        const realVal = getByPath(settings, realId, '');
        select.innerHTML = '<option value="">— Select monitor —</option>';
        if (realVal) ensureSelectOption(select, realVal, realVal);
        select.value = realVal || '';
      });
    }

    function populateMonitorProxyOptions(settings, monitors) {
      ['window.target_monitor_device_proxy', 'external_windows.spotify.target_monitor_device_proxy'].forEach((proxyId) => {
        const select = document.getElementById(proxyId);
        if (!select) return;
        const realId = proxyId.replace('_proxy', '');
        const realVal = getByPath(settings, realId, '');
        select.innerHTML = '<option value="">— Select monitor —</option>' + (monitors || []).map((m, index) => {
          const value = monitorValue(m);
          const label = monitorDisplayName(m, index);
          return `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`;
        }).join('');
        if (realVal) ensureSelectOption(select, realVal, realVal);
        select.value = realVal || '';
      });
    }

    async function ensureMonitorOptionsLoaded() {
      if (SETTINGS_MONITORS_READY) return;
      if (SETTINGS_MONITORS_LOADING) return SETTINGS_MONITORS_LOADING;
      SETTINGS_MONITORS_LOADING = (async () => {
        const monitorsRaw = getByPath(currentSettings || {}, 'monitors', []);
        let monitors = Array.isArray(monitorsRaw) ? monitorsRaw : [];
        if (!monitors.length) monitors = await fetchMonitorOptionsFromBackend();
        SETTINGS_MONITORS_CACHE = Array.isArray(monitors) ? monitors : [];
        populateMonitorProxyOptions(currentSettings || {}, SETTINGS_MONITORS_CACHE);
        SETTINGS_MONITORS_READY = true;
      })();
      try {
        await SETTINGS_MONITORS_LOADING;
      } finally {
        SETTINGS_MONITORS_LOADING = null;
      }
    }

    // ─── fill / collect form ────────────────────────────────────────────────
    async function fillForm(settings) {
      window.__settingsBulkUpdating = true;
      try {
        await ensureMonitorPowerOptionsLoaded(settings);
        fieldIds = getTrackedFieldIds();
        for (let index = 0; index < fieldIds.length; index += 1) {
          const id = fieldIds[index];
          const el = document.getElementById(id);
          if (!el) continue;
          const fallback = getSettingsFieldDefault(id);
          let val = getByPath(settings, id, fallback);
          if (typeof val === 'string' && !val.trim() && fallback !== undefined && fallback !== '') val = fallback;
          if (el.type === 'checkbox') el.checked = !!val;
          else {
            if (el.matches && el.matches('[data-liquid-preview]')) {
              ensureSelectOption(el, val || el.dataset.default || SETTINGS_LIQUID_THEME_DEFAULT_KEY);
            }
            if (el.type === 'number' && typeof val === 'string') val = val.trim().replace(',', '.');
            el.value = (val === undefined || val === null) ? '' : val;
          }
          if (index > 0 && index % 40 === 0) {
            await new Promise((resolve) => requestAnimationFrame(resolve));
          }
        }
        syncPanelLanguageControls(getByPath(settings, 'frontend.panel_language', 'en'));
        setMonitorProxyPlaceholders(settings);
        syncSettingsLiquidLivePreview();
        syncSettingsRenderMode();
      } finally {
        window.__settingsBulkUpdating = false;
      }
    }
 
    function collectForm() {
      const out = {};
      const mainPanelLanguage = document.getElementById('frontend.panel_language');
      if (mainPanelLanguage && panelLanguageTop) mainPanelLanguage.value = normalizePanelLanguageValue(panelLanguageTop.value);
      fieldIds.forEach((id) => {
        const el = document.getElementById(id);
        if (!el) return;
        setByPath(out, id, parseFieldValue(el));
      });
 
      ['window.target_monitor_device', 'external_windows.spotify.target_monitor_device'].forEach((realId) => {
        const proxyId = realId + '_proxy';
        const proxy = document.getElementById(proxyId);
        if (proxy) {
          const preserved = getByPath(currentSettings || {}, realId, '');
          setByPath(out, realId, proxy.value || preserved || '');
        }
      });

      const mainMonitorProxy = document.getElementById('window.target_monitor_device_proxy');
      if (mainMonitorProxy && SETTINGS_MONITORS_READY) {
        const selectedMonitor = (SETTINGS_MONITORS_CACHE || []).find((item) => monitorValue(item) === String(mainMonitorProxy.value || ''));
        if (selectedMonitor) {
          const geometryMap = {
            'window.target_monitor_left': selectedMonitor.logical_left ?? selectedMonitor.left ?? selectedMonitor.x,
            'window.target_monitor_top': selectedMonitor.logical_top ?? selectedMonitor.top ?? selectedMonitor.y,
            'window.target_monitor_width': selectedMonitor.logical_width ?? selectedMonitor.width,
            'window.target_monitor_height': selectedMonitor.logical_height ?? selectedMonitor.height,
          };
          Object.entries(geometryMap).forEach(([path, value]) => {
            if (value !== undefined && value !== null && value !== '') setByPath(out, path, value);
          });
        }
      }
 
      const buttonCards = panelButtonsEditor ? panelButtonsEditor.querySelectorAll('.button-editor-body') : [];
      const buttons = [];
      buttonCards.forEach((card, index) => {
        const btn = normalizePanelButton({}, index);
        card.querySelectorAll('[data-btn]').forEach((el) => {
          const key = el.dataset.key;
          if (!key) return;
          btn[key] = parseFieldValue(el);
        });
        buttons.push(btn);
      });
      if (buttons.length) setByPath(out, 'panel.left_buttons', buttons);
      else setByPath(out, 'panel.left_buttons', getByPath(currentSettings || {}, 'panel.left_buttons', []));

      const selectedTuyaKeys = collectSelectedTuyaDeviceKeys();
      setByPath(
        out,
        'tuya.visible_device_keys',
        selectedTuyaKeys.length ? selectedTuyaKeys : getByPath(currentSettings || {}, 'tuya.visible_device_keys', [])
      );
 
      return out;
    }
 
    async function refreshHwinfoSettingsStatus() {
      const uptimeEl = document.getElementById('hwinfoCurrentUptime');
      if (!uptimeEl) return;
      try {
        const res = await fetch('/api/health/report', { cache: 'no-store' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        const checks = Array.isArray(data.checks) ? data.checks : [];
        const hwinfo = checks.find((item) => item && item.key === 'hwinfo');
        const meta = hwinfo && hwinfo.meta ? hwinfo.meta : {};
        const running = meta.hwinfo_running ? settingsText('dynamic.running', 'running') : settingsText('dynamic.not_running', 'not running');
        const uptime = meta.hwinfo_uptime || '-';
        const started = meta.hwinfo_started_at || '-';
        const pid = meta.hwinfo_pid || '-';
        uptimeEl.textContent = `${running} | ${settingsText('dynamic.age', 'age')}: ${uptime} | ${settingsText('dynamic.started', 'started')}: ${started} | ${settingsText('dynamic.pid', 'pid')}: ${pid}`;
      } catch (err) {
        uptimeEl.textContent = settingsText('dynamic.status_unavailable', 'status unavailable');
      }
    }

    async function loadSettings() {
      try {
        const res = await fetch('/api/settings', { cache: 'no-store' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        currentSettings = data && typeof data === 'object' && data.settings ? data.settings : data;
        await fillForm(currentSettings);
        if (summaryMode) summaryMode.textContent = 'API';
        markSaved(true, settingsText('dynamic.msg_loaded', 'Settings loaded'), settingsText('dynamic.msg_loaded_desc', 'Live data from API endpoint.'));
      } catch (err) {
        console.error('loadSettings error:', err);
        markSaved(false, settingsText('dynamic.msg_load_failed', 'Load failed'), settingsErrorText(err));
      }
    }
 
    async function saveSettings() {
      try {
        const payload = collectForm();
        const res = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json().catch(() => ({}));
        currentSettings = data && typeof data === 'object' && data.settings ? data.settings : payload;
        await fillForm(currentSettings);
        try { await fetch('/trigger_refresh', { cache: 'no-store' }); } catch (_) {}
        markSaved(true, settingsText('global.status_saved', 'Saved'), settingsText('dynamic.msg_saved_backend_desc', 'All settings written to backend.'));
      } catch (err) {
        console.error('saveSettings error:', err);
        markSaved(false, settingsText('dynamic.msg_save_err', 'Save failed'), settingsErrorText(err));
      }
    }
 
    function exportJson() {
      const payload = collectForm();
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'panel_settings.json'; a.click();
      URL.revokeObjectURL(url);
    }
 
    function importJson(file) {
      const reader = new FileReader();
      reader.onload = async (e) => {
        try {
          const data = JSON.parse(e.target.result);
          currentSettings = data && typeof data === 'object' && data.settings ? data.settings : data;
          await fillForm(currentSettings);
          markSaved(false, settingsText('dynamic.msg_imported', 'Imported'), settingsText('dynamic.msg_review_save', 'Review and save to apply.'));
        } catch (err) {
          markSaved(false, settingsText('dynamic.msg_import_failed', 'Import failed'), settingsErrorText(err));
        }
      };
      reader.readAsText(file);
    }
 
    function normalizeSearchText(text) { return String(text || '').toLowerCase().replace(/[^a-z0-9]/g, ''); }
 
    function initSearch() {
      const searchInput = document.getElementById('searchSettings');
      if (!searchInput) return;
      searchInput.addEventListener('input', () => {
        const q = normalizeSearchText(searchInput.value);
        if (!q) {
          document.querySelectorAll('.field, .settings-group').forEach((el) => el.classList.remove('hidden-by-search'));
          return;
        }
        document.querySelectorAll('.field').forEach((el) => {
          const text = normalizeSearchText(el.textContent + (el.querySelector('input,select,textarea')?.id || ''));
          el.classList.toggle('hidden-by-search', !text.includes(q));
        });
        document.querySelectorAll('.settings-group').forEach((group) => {
          const visibleFields = group.querySelectorAll('.field:not(.hidden-by-search)');
          group.classList.toggle('hidden-by-search', visibleFields.length === 0);
        });
      });
    }
 
    // ─── Tuya Device Picker ─────────────────────────────────────────────────
    async function loadTuyaDeviceOptions(preferredOrder = null) {
      const picker = document.getElementById('tuyaDevicePicker');
      if (!picker) return;
      try {
        const res = await fetch('/tuya/status?all=1', { cache: 'no-store' });
        if (!res.ok) throw new Error('Tuya status could not be loaded');
        const data = await res.json();
        const rawDevices = Array.isArray(data) ? data : (Array.isArray(data && data.devices) ? data.devices : []);

        const devices = [];
        const seenKeys = new Set();
        for (const raw of rawDevices) {
          if (!raw || typeof raw !== 'object') continue;
          const key = String(raw.key || raw.device_key || raw.id || '').trim();
          if (!key || seenKeys.has(key)) continue;
          seenKeys.add(key);
          devices.push({
            key,
            name: String(raw.name || raw.label || key),
            ip: String(raw.ip || ''),
            type: String(raw.type || raw.category || ''),
          });
        }

        const savedSelected = getByPath(currentSettings, 'tuya.visible_device_keys', []);
        const selectedKeys = (Array.isArray(preferredOrder) ? preferredOrder : (Array.isArray(savedSelected) ? savedSelected : []))
          .map((key) => String(key || '').trim())
          .filter(Boolean);

        const allKeys = devices.map((d) => d.key);
        const orderedKeys = [...new Set([
          ...selectedKeys.filter((key) => allKeys.includes(key)),
          ...allKeys,
        ])];

        picker.innerHTML = orderedKeys.map((key) => {
          const device = devices.find((d) => d.key === key) || { name: key, key, ip: '', type: '' };
          const isSelected = selectedKeys.includes(key);
          const selIdx = selectedKeys.indexOf(key);
          return `<div class="device-chip${isSelected ? ' is-selected' : ''}" data-device-key="${escapeHtml(key)}">
            <div class="device-chip-main">
              <input type="checkbox" class="tuya-visible-device" data-device-key="${escapeHtml(key)}"${isSelected ? ' checked' : ''}>
              <div class="device-chip-meta">
                <strong>${escapeHtml(device.name || key)}</strong>
                <span>${escapeHtml(device.ip || device.type || key)}</span>
              </div>
            </div>
            <div class="device-chip-actions">
              <button type="button" class="device-order-btn tuya-device-move" data-device-key="${escapeHtml(key)}" data-direction="up"${!isSelected || selIdx <= 0 ? ' disabled' : ''}>▲</button>
              <button type="button" class="device-order-btn tuya-device-move" data-device-key="${escapeHtml(key)}" data-direction="down"${!isSelected || selIdx >= selectedKeys.length - 1 ? ' disabled' : ''}>▼</button>
            </div>
          </div>`;
        }).join('');
      } catch (err) {
        console.error('loadTuyaDeviceOptions error:', err);
        if (picker) picker.innerHTML = `<p style="color:var(--text-muted);font-size:13px;padding:8px 0;">${escapeHtml(settingsText('dynamic.tuya_load_err', 'Tuya devices could not be loaded. Check backend connectivity.'))}</p>`;
      }
    }

    async function ensureTuyaDeviceOptionsLoaded(preferredOrder = null) {
      if (preferredOrder) {
        SETTINGS_TUYA_DEVICES_READY = false;
      }
      if (SETTINGS_TUYA_DEVICES_READY) return;
      if (SETTINGS_TUYA_DEVICES_LOADING) return SETTINGS_TUYA_DEVICES_LOADING;
      SETTINGS_TUYA_DEVICES_LOADING = (async () => {
        await loadTuyaDeviceOptions(preferredOrder);
        SETTINGS_TUYA_DEVICES_READY = true;
      })();
      try {
        await SETTINGS_TUYA_DEVICES_LOADING;
      } finally {
        SETTINGS_TUYA_DEVICES_LOADING = null;
      }
    }

    function collectSelectedTuyaDeviceKeys() {
      return Array.from(document.querySelectorAll('.tuya-visible-device:checked')).map((el) => String(el.dataset.deviceKey || '').trim()).filter(Boolean);
    }

    function renderTuyaMaintenanceResult(data, actionLabel) {
      const cards = document.getElementById('tuyaMaintenanceCards');
      const rows = document.getElementById('tuyaMaintenanceDeviceRows');
      const status = document.getElementById('tuyaMaintenanceStatus');
      const total = Number(data && data.total) || 0;
      const online = Number(data && data.online) || 0;
      const offline = Number(data && data.offline) || 0;
      const errors = Number(data && data.error_count) || 0;
      if (cards) {
        cards.innerHTML = [
          { label: settingsText('extra.total', 'Total'), value: total },
          { label: settingsText('extra.online', 'Online'), value: online },
          { label: settingsText('extra.offline', 'Offline'), value: offline },
          { label: settingsText('extra.errors', 'Errors'), value: errors },
        ].map((item) => `<div class="native-card"><div class="native-card-label">${escapeHtml(item.label)}</div><div class="native-card-value">${escapeHtml(String(item.value))}</div></div>`).join('');
      }
      const devices = Array.isArray(data && data.devices) ? data.devices : [];
      if (rows) {
        rows.innerHTML = devices.length ? devices.map((device) => {
          const key = String((device && (device.key || device.device_key || device.id)) || '').trim();
          const name = String((device && device.name) || key || '-');
          const isOnline = !!(device && device.online === true);
          const rawPowerState = String((device && device.power_state) || (device && device.is_on === true ? 'On' : (device && device.is_on === false ? 'Off' : 'Unknown')));
          const powerState = rawPowerState === 'On'
            ? settingsText('global.on', 'On')
            : (rawPowerState === 'Off' ? settingsText('global.off', 'Off') : settingsText('dynamic.tuya_val_unknown', 'Unknown'));
          const type = String((device && device.type) || '');
          const ip = String((device && device.ip) || '');
          const details = String((device && device.details) || '-');
          const source = String((device && device.source) || '-');
          const error = String((device && device.error) || '');
          return `<tr>
            <td>${escapeHtml(name)}${key && key !== name ? `<span class="tuya-device-detail">${escapeHtml(key)}</span>` : ''}${(type || ip) ? `<span class="tuya-device-detail">${escapeHtml([type, ip].filter(Boolean).join(' | '))}</span>` : ''}</td>
            <td class="${isOnline ? 'tuya-device-ok' : 'tuya-device-warn'}">${isOnline ? settingsText('extra.online', 'Online') : settingsText('extra.offline', 'Offline')}<span class="tuya-device-detail">${escapeHtml(powerState)}</span></td>
            <td>${escapeHtml(details)}</td>
            <td>${escapeHtml(source)}</td>
            <td>${escapeHtml(error || '-')}</td>
          </tr>`;
        }).join('') : `<tr><td colspan="5">${escapeHtml(settingsText('extra.no_device', 'No device returned.'))}</td></tr>`;
      }
      if (status) status.textContent = `${actionLabel} ${settingsText('dynamic.tuya_complete', 'complete')}: ${online}/${total} ${settingsText('extra.online', 'online')}, ${errors} ${settingsText('extra.errors', 'errors')}.`;
    }

    async function runTuyaMaintenance(action) {
      const checkBtn = document.getElementById('tuyaCheckBtn');
      const resetBtn = document.getElementById('tuyaResetBtn');
      const status = document.getElementById('tuyaMaintenanceStatus');
      const isReset = action === 'reset';
      const endpoint = isReset ? '/api/tuya/reset' : '/api/tuya/check';
      const actionLabel = isReset ? settingsText('dynamic.tuya_reset', 'Reset') : settingsText('dynamic.tuya_check', 'Check');
      try {
        if (checkBtn) checkBtn.disabled = true;
        if (resetBtn) resetBtn.disabled = true;
        if (status) status.textContent = `${actionLabel} ${settingsText('dynamic.tuya_running', 'running...')}`;
        const res = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ clear_logs: false }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data || data.ok !== true) throw new Error((data && data.error) || `HTTP ${res.status}`);
        renderTuyaMaintenanceResult(data, actionLabel);
        SETTINGS_TUYA_DEVICES_READY = false;
        await ensureTuyaDeviceOptionsLoaded();
        refreshTuyaSourceCards(currentSettings || {});
        markSaved(true, `Tuya ${actionLabel.toLowerCase()} ${settingsText('dynamic.tuya_complete', 'complete')}`, `${Number(data.online) || 0}/${Number(data.total) || 0} ${settingsText('dynamic.tuya_devices_online', 'devices online.')}`);
      } catch (err) {
        if (status) status.textContent = `${actionLabel} ${settingsText('dynamic.tuya_failed', 'failed')}: ${settingsErrorText(err)}`;
        markSaved(false, `Tuya ${actionLabel.toLowerCase()} ${settingsText('dynamic.tuya_failed', 'failed')}`, settingsErrorText(err));
      } finally {
        if (checkBtn) checkBtn.disabled = false;
        if (resetBtn) resetBtn.disabled = false;
      }
    }

    function initTuyaMaintenanceTools() {
      const checkBtn = document.getElementById('tuyaCheckBtn');
      const resetBtn = document.getElementById('tuyaResetBtn');
      const clearLogsBtn = document.getElementById('tuyaClearLogsBtn');
      if (checkBtn) checkBtn.addEventListener('click', () => runTuyaMaintenance('check'));
      if (resetBtn) resetBtn.addEventListener('click', () => {
        if (!confirm(settingsText('dynamic.confirm_tuya_reset', 'Reset Tuya connection pool and check devices again?'))) return;
        runTuyaMaintenance('reset');
      });
      if (clearLogsBtn) {
        clearLogsBtn.addEventListener('click', async () => {
          if (!confirm(settingsText('extra.clear_only_tuya_logs', 'Clear only Tuya logs?'))) return;
          const originalText = clearLogsBtn.textContent;
          const status = document.getElementById('tuyaMaintenanceStatus');
          try {
            clearLogsBtn.disabled = true;
            clearLogsBtn.textContent = settingsText('dynamic.msg_clearing', 'Clearing...');
            const res = await fetch('/api/tuya/logs/clear', { method: 'POST' });
            const data = await res.json().catch(() => ({}));
            if (!res.ok || !data || data.ok !== true) throw new Error((data && data.error) || `HTTP ${res.status}`);
            if (status) status.textContent = settingsText('extra.tuya_logs_cleared', 'Tuya logs cleared.');
            markSaved(true, settingsText('extra.tuya_logs_cleared', 'Tuya logs cleared.'), settingsText('dynamic.only_tuya_log_cleared', 'Only Tuya log file was cleared.'));
          } catch (err) {
            if (status) status.textContent = settingsText('extra.tuya_log_clear_failed', 'Tuya log clear failed.');
            markSaved(false, settingsText('extra.tuya_log_clear_failed', 'Tuya log clear failed.'), settingsErrorText(err));
          } finally {
            clearLogsBtn.disabled = false;
            clearLogsBtn.textContent = originalText;
          }
        });
      }
    }
 
    function refreshTuyaSourceCards(settings) {
      const container = document.getElementById('tuyaSourceCards');
      if (!container) return;
      const plugKey = getByPath(settings, 'tuya.pc_plug_key', '—');
      const normalizeMode = (value) => {
        const text = String(value || '').trim().toLowerCase();
        return text === 'cloud' ? 'cloud' : 'local';
      };
      const deviceMode = normalizeMode(getByPath(settings, 'tuya.read_mode', 'local'));
      const modeLabel = (mode) => mode === 'cloud'
        ? settingsText('dynamic.tuya_val_cloud_only', 'Cloud only')
        : settingsText('dynamic.tuya_val_local_only', 'Local only');
      container.innerHTML = [
        { label: settingsText('dynamic.tuya_mode_device', 'Tuya source'), value: modeLabel(deviceMode) },
        { label: settingsText('dynamic.tuya_mode_plug', 'PC plug key'), value: plugKey ? String(plugKey).slice(0, 12) + '...' : '-' },
        { label: settingsText('dynamic.tuya_mode_local', 'Device query'), value: modeLabel(deviceMode) },
        { label: settingsText('dynamic.tuya_mode_cloud', 'Power query'), value: modeLabel(deviceMode) },
      ].map((item) => `<div class="native-card"><div class="native-card-label">${escapeHtml(item.label)}</div><div class="native-card-value">${escapeHtml(item.value)}</div></div>`).join('');
    }
 
    // ─── Health ──────────────────────────────────────────────────────────────
    function initNativeHealthV2() {
      const refreshBtn = document.getElementById('healthRefreshBtn');
      const autoRefreshBtn = document.getElementById('healthAutoRefreshBtn');
      const overallText = document.getElementById('healthOverallText');
      const statusText2 = document.getElementById('healthStatusText');
      if (!refreshBtn) return;
      let autoRefreshEnabled = true, autoRefreshTimer = null;
 
      async function fetchHealth() {
        if (statusText2) statusText2.textContent = settingsText('dynamic.msg_loading', 'Loading...');
        try {
          const res = await fetch('/api/health/report', { cache: 'no-store' });
          if (!res.ok) throw new Error('HTTP ' + res.status);
          const data = await res.json();
          renderHealth(data);
          if (statusText2) statusText2.textContent = `${settingsText('dynamic.updated_at', 'Updated:')} ${new Date().toLocaleTimeString('tr-TR')}`;
          if (overallText) overallText.textContent = String((data.summary && data.summary.overall_status) || data.status || 'ok').toUpperCase();
        } catch (err) {
          if (statusText2) statusText2.textContent = `${settingsText('dynamic.health_error', 'Error')}: ${settingsErrorText(err)}`;
        }
      }
 
      function renderHealth(data) {
        const summaryEl = document.getElementById('healthSummaryCards');
        const snapshotsEl = document.getElementById('healthSnapshotsGrid');
        const configEl = document.getElementById('healthConfigGrid');
        const checksEl = document.getElementById('healthChecksGrid');
        const issuesList = document.getElementById('healthIssuesList');
        const issuesMeta = document.getElementById('healthIssuesMeta');
        const eventsList = document.getElementById('healthEventsList');
        const eventsMeta = document.getElementById('healthEventsMeta');
 
        const summary = data.summary || {};
        const snapshots = Array.isArray(data.snapshots) ? data.snapshots : [];
        const configuration = Array.isArray(data.configuration) ? data.configuration : [];
        const checks = Array.isArray(data.checks) ? data.checks : [];
        const issues = Array.isArray(data.issues) ? data.issues : [];
        const events = Array.isArray(data.recent_events) ? data.recent_events : (Array.isArray(data.events) ? data.events : []);
        const toMetaRows = (meta) => {
          if (Array.isArray(meta)) return meta;
          if (meta && typeof meta === 'object') return Object.entries(meta).map(([label, value]) => ({ label, value }));
          return [];
        };
 
        if (summaryEl) {
          summaryEl.innerHTML = Object.entries(summary).slice(0, 6).map(([k, v]) =>
            `<div class="native-card"><div class="native-card-label">${escapeHtml(k)}</div><div class="native-card-value">${escapeHtml(String(v))}</div></div>`
          ).join('');
        }
        if (snapshotsEl) {
          snapshotsEl.innerHTML = snapshots.map((s) =>
            `<div class="health-snapshot-card native-card"><div class="native-card-label">${escapeHtml(s.label || '')}</div><div class="native-card-value">${escapeHtml(String(s.value || '-'))}</div><div class="health-snapshot-sub">${escapeHtml(s.subvalue || s.sub || '')}</div></div>`
          ).join('');
        }
        if (configEl) {
          configEl.innerHTML = configuration.map((item) => `
            <div class="health-check-card">
              <div class="health-check-head"><div class="health-check-title">${escapeHtml(item.label || item.title || '')}</div><span class="health-status-badge ${item.status || ''}">${escapeHtml(String(item.status || '').toUpperCase())}</span></div>
              <div class="health-check-summary">${escapeHtml(item.value || '')}</div>
              <div class="health-check-detail">${escapeHtml(item.detail || '')}</div>
            </div>`).join('');
        }
        if (checksEl) {
          checksEl.innerHTML = checks.map((check) => `
            <div class="health-check-card">
              <div class="health-check-head"><div class="health-check-title">${escapeHtml(check.label || check.title || '')}</div><span class="health-status-badge ${check.status || ''}">${escapeHtml((check.status || '').toUpperCase())}</span></div>
              <div class="health-check-summary">${escapeHtml(check.summary || '')}</div>
              <div class="health-check-detail">${escapeHtml(check.detail || '')}</div>
              <div class="health-meta-list">${toMetaRows(check.meta).map((m) => `<div class="health-meta-row"><span>${escapeHtml(m.label || '')}</span><span>${escapeHtml(String(m.value || ''))}</span></div>`).join('')}</div>
            </div>`).join('');
        }
        if (issuesList) {
          if (!issues.length) issuesList.innerHTML = `<div class="health-empty">${escapeHtml(settingsText('dynamic.empty_issues', 'No issues found.'))}</div>`;
          else issuesList.innerHTML = issues.map((issue) => `<div class="health-issue-card"><div class="health-issue-head"><div class="health-issue-title">${escapeHtml(issue.label || issue.title || '')}</div><span class="health-status-badge ${issue.status || 'error'}">${escapeHtml(String(issue.status || 'error').toUpperCase())}</span></div><div class="health-issue-detail">${escapeHtml(issue.detail || '')}</div>${issue.suggestion ? `<div class="health-issue-detail">${escapeHtml(issue.suggestion)}</div>` : ''}</div>`).join('');
          if (issuesMeta) issuesMeta.textContent = settingsRecordsText(issues.length);
        }
        if (eventsList) {
          if (!events.length) eventsList.innerHTML = `<div class="health-empty">${escapeHtml(settingsText('dynamic.empty_events', 'No events.'))}</div>`;
          else eventsList.innerHTML = events.map((ev) => `<div class="health-event-item"><div class="health-event-top"><span class="health-event-source">${escapeHtml(ev.source || '')}</span><span class="health-event-time">${escapeHtml(ev.time || ev.ts || '')}</span></div><div>${escapeHtml(ev.message || ev.detail || '')}</div></div>`).join('');
          if (eventsMeta) eventsMeta.textContent = settingsRecordsText(events.length);
        }
      }
 
      function startAutoRefresh() { autoRefreshTimer = setInterval(fetchHealth, 10000); }
      function stopAutoRefresh() { clearInterval(autoRefreshTimer); autoRefreshTimer = null; }
 
      refreshBtn.addEventListener('click', fetchHealth);
      if (autoRefreshBtn) {
        autoRefreshBtn.addEventListener('click', () => {
          autoRefreshEnabled = !autoRefreshEnabled;
          autoRefreshBtn.textContent = autoRefreshEnabled
            ? settingsText('sections.health.toolbar.auto_on', 'Auto Refresh: On')
            : settingsText('sections.health.toolbar.auto_off', 'Auto Refresh: Off');
          autoRefreshEnabled ? startAutoRefresh() : stopAutoRefresh();
        });
      }
 
      const healthSection = document.getElementById('section-health');
      if (healthSection) {
        new MutationObserver(() => {
          if (healthSection.classList.contains('is-active')) { fetchHealth(); if (autoRefreshEnabled) startAutoRefresh(); }
          else stopAutoRefresh();
        }).observe(healthSection, { attributes: true, attributeFilter: ['class'] });
        if (healthSection.classList.contains('is-active')) {
          fetchHealth();
          if (autoRefreshEnabled) startAutoRefresh();
        }
      }
    }
 
    // ─── Live Logs ───────────────────────────────────────────────────────────
    function initNativeLogs() {
      const searchInput = document.getElementById('logsSearchInput');
      const whichSelect = document.getElementById('logsWhichSelect');
      const levelSelect = document.getElementById('logsLevelSelect');
      const lineSelect  = document.getElementById('logsLineSelect');
      const clearBtn    = document.getElementById('clearLogsBtn');
      const statusEl    = document.getElementById('logsStatusText');
      if (!statusEl) return;
 
      let logsData = { errors: [], logs: [], tuya: [] };
 
      function renderLogs() {
        const q     = normalizeSearchText(searchInput ? searchInput.value : '');
        const which = whichSelect ? whichSelect.value : 'all';
        const level = levelSelect ? levelSelect.value : 'all';
 
        const filterRows = (rows) => rows.filter((r) => {
          if (level !== 'all' && r.level !== level) return false;
          if (q && !normalizeSearchText(JSON.stringify(r)).includes(q)) return false;
          return true;
        });
 
        const errors  = which === 'all' || which === 'errors' ? filterRows(logsData.errors) : [];
        const general = which === 'all' || which === 'logs' ? filterRows(logsData.logs) : [];
        const tuya    = which === 'all' || which === 'tuya' ? filterRows(logsData.tuya) : [];
 
        const renderRows = (rows) => rows.map((r) => `
          <tr>
            <td>${escapeHtml(r.time || r.ts || '')}</td>
            <td>
              <div class="log-main-cell">
                <div class="log-source">${escapeHtml(r.source || '')}</div>
                <div class="log-message">${escapeHtml(r.message || '')}</div>
              </div>
            </td>
          </tr>
        `).join('');

        const errorsBody = document.getElementById('logsErrorsBody');
        const generalBody = document.getElementById('logsGeneralBody');
        const tuyaBody = document.getElementById('logsTuyaBody');
        const summaryCards = document.getElementById('logsSummaryCards');
        if (errorsBody)  errorsBody.innerHTML  = renderRows(errors);
        if (generalBody) generalBody.innerHTML = renderRows(general);
        if (tuyaBody)    tuyaBody.innerHTML    = renderRows(tuya);
        if (summaryCards) {
          summaryCards.innerHTML = [
            { label: settingsText('dynamic.stats_err', 'Error records'), value: errors.length },
            { label: settingsText('dynamic.stats_log', 'General records'), value: general.length },
            { label: settingsText('extra.tuya_logs', 'Tuya records'), value: tuya.length },
          ].map((item) => `<div class="native-stat"><div class="native-stat-k">${escapeHtml(item.label)}</div><div class="native-stat-v">${escapeHtml(String(item.value))}</div></div>`).join('');
        }
 
        const errMeta  = document.getElementById('logsErrorsMeta');
        const genMeta  = document.getElementById('logsGeneralMeta');
        const tuyaMeta = document.getElementById('logsTuyaMeta');
        if (errMeta)  errMeta.textContent  = settingsRecordsText(errors.length);
        if (genMeta)  genMeta.textContent  = settingsRecordsText(general.length);
        if (tuyaMeta) tuyaMeta.textContent = settingsRecordsText(tuya.length);
      }
 
      async function fetchLogs() {
        if (statusEl) statusEl.textContent = settingsText('dynamic.msg_loading', 'Loading...');
        try {
          const lines = lineSelect ? lineSelect.value : 500;
          const res = await fetch(`/hata/data?lines=${lines}`, { cache: 'no-store' });
          if (!res.ok) throw new Error();
          const data = await res.json();
          logsData = {
            errors: Array.isArray(data.errors) ? data.errors : [],
            logs: Array.isArray(data.logs) ? data.logs : [],
            tuya: Array.isArray(data.tuya) ? data.tuya : [],
          };
          renderLogs();
          if (statusEl) statusEl.textContent = `${settingsText('dynamic.updated_at', 'Updated:')} ${new Date().toLocaleTimeString('tr-TR')}`;
        } catch {
          if (statusEl) statusEl.textContent = settingsText('global.api_error', 'API error');
        }
      }
 
      if (searchInput) searchInput.addEventListener('input', renderLogs);
      if (whichSelect) whichSelect.addEventListener('change', renderLogs);
      if (levelSelect) levelSelect.addEventListener('change', renderLogs);
      if (lineSelect)  lineSelect.addEventListener('change', fetchLogs);
      if (clearBtn) {
        clearBtn.addEventListener('click', async () => {
          if (!confirm(settingsText('dynamic.confirm_clear_logs', 'Clear all log files?'))) return;
          const originalText = clearBtn.textContent;
          try {
            clearBtn.disabled = true;
            clearBtn.textContent = settingsText('dynamic.msg_clearing', 'Clearing...');
            const res = await fetch('/api/logs/clear', { method: 'POST' });
            const data = await res.json().catch(() => ({}));
            if (!res.ok || !data || data.ok !== true) throw new Error((data && data.error) || `HTTP ${res.status}`);
            logsData = { errors: [], logs: [], tuya: [] };
            renderLogs();
            if (statusEl) statusEl.textContent = settingsText('dynamic.msg_logs_cleared', 'Logs cleared');
            markSaved(true, settingsText('dynamic.msg_logs_cleared', 'Logs cleared'), settingsText('dynamic.msg_logs_cleared_desc', 'All log files were truncated.'));
          } catch (err) {
            if (statusEl) statusEl.textContent = settingsText('dynamic.msg_clear_failed', 'Clear failed');
            markSaved(false, settingsText('dynamic.msg_log_clear_failed', 'Log clear failed'), settingsErrorText(err));
          } finally {
            clearBtn.disabled = false;
            clearBtn.textContent = originalText;
            fetchLogs();
          }
        });
      }

      const logsSection = document.getElementById('section-logs');
      if (logsSection) {
        new MutationObserver(() => {
          if (logsSection.classList.contains('is-active')) fetchLogs();
        }).observe(logsSection, { attributes: true, attributeFilter: ['class'] });
        if (logsSection.classList.contains('is-active')) fetchLogs();
      }
    }
 
    // ─── Sitemap ─────────────────────────────────────────────────────────────
    function initNativeSitemap() {
      const sitemapSearchInput   = document.getElementById('sitemapSearchInput');
      const sitemapCategorySelect = document.getElementById('sitemapCategorySelect');
      const sitemapMethodSelect  = document.getElementById('sitemapMethodSelect');
      const sitemapStatusText    = document.getElementById('sitemapStatusText');
      const sitemapStats         = document.getElementById('sitemapStats');
      const sitemapGroups        = document.getElementById('sitemapGroups');
      if (!sitemapStatusText) return;
 
      let sitemapData = [];
 
      function renderSitemap() {
        if (!sitemapGroups || !sitemapStats) return;
        const q      = normalizeSearchText(sitemapSearchInput ? sitemapSearchInput.value : '');
        const cat    = sitemapCategorySelect ? sitemapCategorySelect.value : 'all';
        const method = sitemapMethodSelect ? sitemapMethodSelect.value : 'all';
 
        const filtered = sitemapData.filter((item) => {
          if (cat !== 'all' && item.category !== cat) return false;
          if (method !== 'all' && !(Array.isArray(item.methods) ? item.methods : [item.method || 'GET']).includes(method)) return false;
          if (q && !normalizeSearchText(JSON.stringify(item)).includes(q)) return false;
          return true;
        });
 
        const groups = {};
        for (const item of filtered) {
          const g = item.category || 'General';
          if (!groups[g]) groups[g] = [];
          groups[g].push(item);
        }
 
        sitemapStats.innerHTML = [
          { label: settingsText('global.total_endpoints', 'Total endpoints'), value: sitemapData.length },
          { label: settingsText('global.filtered', 'Filtered'), value: filtered.length },
          { label: settingsText('global.category', 'Categories'), value: Object.keys(groups).length },
          { label: settingsText('global.get_methods', 'GET methods'), value: filtered.filter((r) => (Array.isArray(r.methods) ? r.methods : [r.method || 'GET']).includes('GET')).length },
        ].map((s) => `<div class="native-stat"><div class="native-stat-k">${escapeHtml(s.label)}</div><div class="native-stat-v">${s.value}</div></div>`).join('');
 
        sitemapGroups.innerHTML = Object.entries(groups).map(([groupName, items]) => `
          <div class="native-group">
            <div class="native-group-head"><h3>${escapeHtml(groupName)}</h3><span class="native-meta">${settingsRecordsText(items.length)}</span></div>
            <div style="padding:16px;display:grid;gap:12px;">
              ${items.map((item) => `
                <div class="native-item">
                  <div class="native-item-top">
                    <span class="native-title">${escapeHtml(item.title || item.name || item.path)}</span>
                    <div class="native-chips">
                      ${(Array.isArray(item.methods) ? item.methods : [item.method || 'GET']).map((m) => `<span class="native-chip">${escapeHtml(m)}</span>`).join('')}
                    </div>
                  </div>
                  <div class="native-path">${escapeHtml(item.path || '')}</div>
                  ${item.description ? `<div style="font-size:13px;color:var(--text-soft);margin-bottom:8px;">${escapeHtml(item.description)}</div>` : ''}
                  ${(item.examples || []).map((ex) => `
                    <div class="native-example">
                      <span class="native-example-url">${escapeHtml(ex.url || '')}</span>
                      <a href="${escapeHtml(ex.url || '#')}" target="_blank" style="font-size:12px;font-weight:700;color:var(--accent);">${escapeHtml(settingsText('global.open', 'Open'))}</a>
                    </div>`).join('')}
                </div>`).join('')}
            </div>
          </div>`).join('');
      }
 
      async function fetchSitemap() {
        if (sitemapStatusText) sitemapStatusText.textContent = settingsText('dynamic.msg_loading', 'Loading...');
        try {
          const res = await fetch('/sitemap/data', { cache: 'no-store' });
          if (!res.ok) throw new Error();
          const data = await res.json();
          sitemapData = Array.isArray(data) ? data : (Array.isArray(data && data.items) ? data.items : []);
          if (!Array.isArray(sitemapData)) sitemapData = [];
          const cats = [...new Set(sitemapData.map((r) => r.category).filter(Boolean))];
          if (sitemapCategorySelect) {
            sitemapCategorySelect.innerHTML = `<option value="all">${escapeHtml(settingsText('extra.all_categories', 'All categories'))}</option>` + cats.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
          }
          renderSitemap();
          if (sitemapStatusText) sitemapStatusText.textContent = `${settingsText('dynamic.updated_at', 'Updated:')} ${new Date().toLocaleTimeString('tr-TR')}`;
        } catch {
          if (sitemapStatusText) sitemapStatusText.textContent = settingsText('global.api_error', 'API error');
          if (sitemapGroups) sitemapGroups.innerHTML = `<p style="text-align:center;color:var(--text-muted);padding:24px;">${escapeHtml(settingsText('dynamic.empty_sitemap', 'Sitemap could not be loaded.'))}</p>`;
        }
      }
 
      if (sitemapSearchInput)    sitemapSearchInput.addEventListener('input', renderSitemap);
      if (sitemapCategorySelect) sitemapCategorySelect.addEventListener('change', renderSitemap);
      if (sitemapMethodSelect)   sitemapMethodSelect.addEventListener('change', renderSitemap);
 
      const sitemapSection = document.getElementById('section-sitemap');
      if (sitemapSection) {
        new MutationObserver(() => {
          if (sitemapSection.classList.contains('is-active')) fetchSitemap();
        }).observe(sitemapSection, { attributes: true, attributeFilter: ['class'] });
        if (sitemapSection.classList.contains('is-active')) fetchSitemap();
      }
    }
 
    function initTuyaSourcePanel() {
      const tuyaSection = document.getElementById('section-tuya');
      if (!tuyaSection) return;
      new MutationObserver(() => {
        if (tuyaSection.classList.contains('is-active')) refreshTuyaSourceCards(currentSettings || {});
      }).observe(tuyaSection, { attributes: true, attributeFilter: ['class'] });
      if (tuyaSection.classList.contains('is-active')) refreshTuyaSourceCards(currentSettings || {});
    }
 
    // ─── Event listeners ────────────────────────────────────────────────────
    document.addEventListener('click', async (event) => {
      const moveButton = event.target.closest('.tuya-device-move');
      if (!moveButton) return;
      event.preventDefault();
      const deviceKey = String(moveButton.dataset.deviceKey || '').trim();
      const direction = String(moveButton.dataset.direction || '').trim();
      if (!deviceKey || !direction) return;
      const selectedKeys = collectSelectedTuyaDeviceKeys();
      const currentIndex = selectedKeys.indexOf(deviceKey);
      if (currentIndex < 0) return;
      const targetIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1;
      const nextOrder = moveArrayItem(selectedKeys, currentIndex, targetIndex);
      await ensureTuyaDeviceOptionsLoaded(nextOrder);
      markSaved(false, settingsText('dynamic.msg_changed', 'Changed'), settingsText('dynamic.msg_tuya_changed', 'Tuya device order updated. Save to persist.'));
    });
 
    document.addEventListener('change', async (event) => {
      const checkbox = event.target.closest('.tuya-visible-device');
      if (!checkbox) return;
      const selectedKeys = collectSelectedTuyaDeviceKeys();
      await ensureTuyaDeviceOptionsLoaded(selectedKeys);
      markSaved(false, settingsText('dynamic.msg_changed', 'Changed'), settingsText('dynamic.msg_tuya_visibility_changed', 'Tuya device visibility updated. Save to persist.'));
    });
 
    initSettingsTheme();
    if (typeof applySettingsLanguage === 'function') applySettingsLanguage();
 
    document.getElementById('saveBtn').addEventListener('click', saveSettings);
 
    document.getElementById('panelRefreshBtn').addEventListener('click', async () => {
      try {
        const res = await fetch('/trigger_refresh');
        if (!res.ok) throw new Error('Panel refresh failed');
        markSaved(true, settingsText('dynamic.msg_refresh_ok', 'Refresh triggered'), settingsText('dynamic.msg_refresh_ok_desc', 'A refresh signal was sent to the panel.'));
      } catch (err) {
        markSaved(false, settingsText('dynamic.msg_refresh_fail', 'Refresh failed'), settingsText('dynamic.msg_refresh_fail_desc', 'The panel refresh endpoint did not respond.'));
      }
    });
 
    document.getElementById('panelRestartBtn').addEventListener('click', async () => {
      if (!confirm(typeof t === 'function' ? t('dynamic.confirm_restart', 'Restart the panel application?') : 'Restart the panel application?')) return;
      try {
        const res = await fetch('/restart_app');
        if (!res.ok) throw new Error('Panel restart failed');
        markSaved(true, settingsText('dynamic.msg_restart_ok', 'Restart triggered'), settingsText('dynamic.msg_restart_ok_desc', 'The panel application is restarting.'));
      } catch (err) {
        markSaved(false, settingsText('dynamic.msg_restart_fail', 'Restart failed'), settingsText('dynamic.msg_restart_fail_desc', 'The restart endpoint did not respond.'));
      }
    });

    const clearLogsConfigBtn = document.getElementById('clearLogsConfigBtn');
    const clearLogsConfigStatus = document.getElementById('clearLogsConfigStatus');
    if (clearLogsConfigBtn) {
      clearLogsConfigBtn.addEventListener('click', async () => {
        const originalText = clearLogsConfigBtn.textContent;
        try {
          if (!confirm(settingsText('dynamic.confirm_clear_logs', 'Clear all log files?'))) return;
          clearLogsConfigBtn.disabled = true;
          clearLogsConfigBtn.textContent = settingsText('dynamic.msg_clearing', 'Clearing...');
          const res = await fetch('/api/logs/clear', { method: 'POST' });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || !data || data.ok !== true) throw new Error((data && data.error) || `HTTP ${res.status}`);
          if (clearLogsConfigStatus) clearLogsConfigStatus.textContent = settingsText('dynamic.msg_logs_cleared_desc', 'Logs cleared successfully.');
          markSaved(true, settingsText('dynamic.msg_logs_cleared', 'Logs cleared'), settingsText('dynamic.msg_logs_cleared_desc', 'All log files were truncated.'));
        } catch (err) {
          if (clearLogsConfigStatus) clearLogsConfigStatus.textContent = `${settingsText('dynamic.msg_clear_failed', 'Clear failed')}: ${settingsErrorText(err)}`;
          markSaved(false, settingsText('dynamic.msg_log_clear_failed', 'Log clear failed'), settingsErrorText(err));
        } finally {
          clearLogsConfigBtn.disabled = false;
          clearLogsConfigBtn.textContent = originalText;
        }
      });
    }

    const hwinfoRestartBtn = document.getElementById('hwinfoRestartBtn');
    const hwinfoRestartStatus = document.getElementById('hwinfoRestartStatus');
    if (hwinfoRestartBtn) {
      hwinfoRestartBtn.addEventListener('click', async () => {
        if (!confirm(settingsText('dynamic.confirm_hwinfo_restart', 'Close and reopen HWiNFO?'))) return;
        const originalText = hwinfoRestartBtn.textContent;
        try {
          hwinfoRestartBtn.disabled = true;
          hwinfoRestartBtn.textContent = settingsText('dynamic.msg_hwinfo_restarting', 'Restarting...');
          if (hwinfoRestartStatus) hwinfoRestartStatus.textContent = settingsText('dynamic.msg_hwinfo_reopening', 'Closing and reopening HWiNFO...');
          const res = await fetch('/api/hwinfo/restart', { method: 'POST' });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || !data || data.ok !== true) throw new Error((data && data.error) || `HTTP ${res.status}`);
          const after = data.after || {};
      const uptime = after.uptime_text || 'just restarted';
          if (hwinfoRestartStatus) hwinfoRestartStatus.textContent = `${settingsText('dynamic.msg_hwinfo_restart_ok', 'HWiNFO restarted')}. ${settingsText('dynamic.msg_hwinfo_uptime', 'HWiNFO uptime:')} ${uptime}`;
          refreshHwinfoSettingsStatus();
          markSaved(true, settingsText('dynamic.msg_hwinfo_restart_ok', 'HWiNFO restarted'), `${settingsText('dynamic.msg_hwinfo_uptime', 'HWiNFO uptime:')} ${uptime}`);
        } catch (err) {
          if (hwinfoRestartStatus) hwinfoRestartStatus.textContent = `${settingsText('dynamic.msg_hwinfo_restart_failed', 'HWiNFO restart failed')}: ${settingsErrorText(err)}`;
          markSaved(false, settingsText('dynamic.msg_hwinfo_restart_failed', 'HWiNFO restart failed'), settingsErrorText(err));
        } finally {
          hwinfoRestartBtn.disabled = false;
          hwinfoRestartBtn.textContent = originalText;
        }
      });
    }

    const shiftRefreshBtn = document.getElementById('shiftRefreshBtn');
    const shiftRefreshStatus = document.getElementById('shiftRefreshStatus');
    if (shiftRefreshBtn) {
      shiftRefreshBtn.addEventListener('click', async () => {
        const originalText = shiftRefreshBtn.textContent;
        try {
          shiftRefreshBtn.disabled = true;
          shiftRefreshBtn.textContent = settingsText('dynamic.msg_shift_refreshing', 'Refreshing...');
          if (shiftRefreshStatus) shiftRefreshStatus.textContent = settingsText('dynamic.msg_shift_downloading', 'Downloading latest shift workbook...');
          const res = await fetch('/api/shift/refresh', { method: 'POST' });
          const data = await res.json().catch(() => ({}));
          if (!res.ok || !data || data.ok !== true) throw new Error((data && data.error) || `HTTP ${res.status}`);
          const shiftLabel = String(data.shift_text || '--');
          const shiftDate = String(data.shift_subtitle || data.target_date || '-');
          if (shiftRefreshStatus) shiftRefreshStatus.textContent = `${settingsText('dynamic.updated_at', 'Updated:')} ${shiftLabel} (${shiftDate})`;
          markSaved(true, settingsText('dynamic.msg_shift_refreshed', 'Shift refreshed'), `${settingsText('dynamic.msg_shift_refreshed_desc', 'Latest shift data loaded.')} ${shiftDate}`);
        } catch (err) {
          if (shiftRefreshStatus) shiftRefreshStatus.textContent = `${settingsText('dynamic.msg_shift_refresh_failed', 'Shift refresh failed')}: ${settingsErrorText(err)}`;
          markSaved(false, settingsText('dynamic.msg_shift_refresh_failed', 'Shift refresh failed'), settingsErrorText(err));
        } finally {
          shiftRefreshBtn.disabled = false;
          shiftRefreshBtn.textContent = originalText;
        }
      });
    }
 
    document.getElementById('resetBtn').addEventListener('click', async () => {
      if (!confirm(typeof t === 'function' ? t('dynamic.confirm_reset', 'Reset all settings to default?') : 'Reset all settings to default?')) return;
      try {
        const res = await fetch('/api/settings/reset', { method: 'POST' });
        if (!res.ok) throw new Error('Reset failed');
        const data = await res.json();
        currentSettings = data && typeof data === 'object' && data.settings ? data.settings : data;
        await fillForm(currentSettings);
        refreshHwinfoSettingsStatus();
        if (summaryMode) summaryMode.textContent = 'API';
        markSaved(true, settingsText('dynamic.msg_reset_ok', 'Defaults restored'), settingsText('dynamic.msg_reset_ok_desc', 'The form was refilled with default settings.'));
      } catch (err) {
        markSaved(false, settingsText('dynamic.msg_reset_fail', 'Reset failed'), settingsText('dynamic.msg_reset_fail_desc', 'The reset endpoint did not respond.'));
      }
    });
 
    document.getElementById('exportBtn').addEventListener('click', exportJson);
    document.getElementById('importBtn').addEventListener('click', () => document.getElementById('importFile').click());
    document.getElementById('importFile').addEventListener('change', (event) => {
      const file = event.target.files && event.target.files[0];
      if (file) importJson(file);
    });
 
    document.addEventListener('input', () => {
      markSaved(false, settingsText('dynamic.msg_changed', 'Unsaved changes'), settingsText('dynamic.msg_changed_desc', 'There are unsaved fields in the form.'));
    });

    document.addEventListener('change', (event) => {
      const target = event.target;
      if (target && target.id === 'frontend.panel_language_top') {
        syncPanelLanguageControls(target.value, 'top');
        markSaved(false, settingsText('dynamic.msg_changed', 'Unsaved changes'), settingsText('dynamic.msg_changed_desc', 'Panel language changed. Save to apply.'));
        return;
      }
      if (target && target.id === 'langToggleBtn') return;
      if (target && target.id === 'frontend.panel_language') {
        syncPanelLanguageControls(target.value, 'main');
        markSaved(false, settingsText('dynamic.msg_changed', 'Unsaved changes'), settingsText('dynamic.msg_changed_desc', 'Panel language changed. Save to apply.'));
        return;
      }
      if (target && target.id === 'frontend.settings_liquid_live_preview_enabled') {
        syncSettingsLiquidLivePreview();
        markSaved(false, settingsText('dynamic.msg_changed', 'Unsaved changes'), settingsText('dynamic.msg_changed_desc', 'There are unsaved fields in the form.'));
        return;
      }
      if (target && target.id === 'frontend.settings_visual_effects_enabled') {
        syncSettingsRenderMode();
        markSaved(false, settingsText('dynamic.msg_changed', 'Unsaved changes'), settingsText('dynamic.msg_changed_desc', 'There are unsaved fields in the form.'));
        return;
      }
      if (!target || !['tuya.read_mode', 'tuya.pc_plug_key'].includes(target.id)) return;
      refreshTuyaSourceCards(collectForm());
    });
 
    initTabs();
    initHomeQuickNav();
    initSearch();
    injectSectionHeadIcons();
    initNativeHealthV2();
    initNativeLogs();
    initNativeSitemap();
    initTuyaSourcePanel();
    initTuyaMaintenanceTools();
    document.addEventListener('settings-language-changed', () => {
      if (typeof applySettingsLanguage === 'function') applySettingsLanguage();
      const activeSection = document.querySelector('.section.is-active');
      if (activeSection) activateTab(activeSection.id);
    });
    loadSettings();
    document.addEventListener('change', (event) => {
      const target = event.target;
      if (!target) return;
      if (target.id === 'window.target_monitor_device_proxy') {
        applyMonitorGeometryToWindowFields(target.value);
        return;
      }
      if (target.id === 'monitor_power.target_fingerprint') {
        syncMonitorPowerTargetMeta();
      }
    });
