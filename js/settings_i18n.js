// File Version: 1.0
(() => {
  const CACHE_TAG = '20260508a';
  const VERSION_MATCH = (() => {
    const script = document.currentScript;
    const src = script ? String(script.src || '') : '';
    const match = src.match(/[?&]v=([^&]+)/);
    return match ? decodeURIComponent(match[1]) : String(Date.now());
  })();

  function normalizeLang(value) {
    value = String(value || '').trim().toLowerCase();
    return value === 'tr' || value === 'en' ? value : '';
  }

  function getStoredLang() {
    try { return normalizeLang(localStorage.getItem('settings_language')); } catch (_) { return ''; }
  }

  function getUrlLang() {
    try {
      const params = new URLSearchParams(window.location.search || '');
      if (params.has('tr')) return 'tr';
      if (params.has('en')) return 'en';
      return normalizeLang(params.get('lang'));
    } catch (_) { return ''; }
  }

  function getLang() {
    return getUrlLang() || getStoredLang() || 'en';
  }

  function langSrc(lang) {
    return `/settings_i18n_${lang}.js?v=${encodeURIComponent(VERSION_MATCH)}&i18n=${encodeURIComponent(CACHE_TAG)}`;
  }

  function resolvePath(obj, path) {
    return String(path || '').split('.').reduce((o, i) => (o ? o[i] : undefined), obj);
  }

  function currentDict() { return window.SETTINGS_I18N_TEXT || {}; }
  function packAliases() { return window.SETTINGS_I18N_ALIASES || {}; }
  function sourceAliases() {
    if (!window.SETTINGS_I18N_SOURCE_ALIASES || typeof window.SETTINGS_I18N_SOURCE_ALIASES !== 'object') {
      window.SETTINGS_I18N_SOURCE_ALIASES = {};
    }
    return window.SETTINGS_I18N_SOURCE_ALIASES;
  }
  function rememberCurrentAliases() {
    const source = sourceAliases();
    Object.entries(packAliases()).forEach(([text, key]) => {
      if (!source[text]) source[text] = key;
    });
    const rememberDictText = (node, path = '') => {
      if (typeof node === 'string') {
        const cleaned = node.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim();
        if (cleaned && path && !source[cleaned]) source[cleaned] = path;
        return;
      }
      if (!node || typeof node !== 'object' || Array.isArray(node)) return;
      Object.entries(node).forEach(([key, value]) => {
        rememberDictText(value, path ? `${path}.${key}` : key);
      });
    };
    rememberDictText(currentDict());
  }
  function currentAliases() { return Object.assign({}, sourceAliases(), packAliases()); }

  function findKeyFromText(text) {
    const cleaned = String(text || '').replace(/\s+/g, ' ').trim();
    return cleaned ? (currentAliases()[cleaned] || '') : '';
  }

  function translateValue(value) {
    const raw = String(value ?? '');
    const trimmed = raw.replace(/\s+/g, ' ').trim();
    if (!trimmed) return raw;
    const key = findKeyFromText(trimmed);
    if (!key) return raw;
    const translated = resolvePath(currentDict(), key);
    return typeof translated === 'string' ? translated.replace(/<[^>]*>/g, '').trim() : raw;
  }

  function t(key, fallback = '') {
    const val = resolvePath(currentDict(), key);
    return typeof val === 'string' ? val : (fallback || key);
  }

  function setButtonText(button, label) {
    if (!button || !label) return;
    const icon = button.querySelector('svg');
    button.textContent = '';
    if (icon) button.appendChild(icon);
    if (icon) button.appendChild(document.createTextNode(' '));
    button.appendChild(document.createTextNode(label));
  }

  function translateTree(root) {
    if (!root || !window.SETTINGS_I18N_TEXT) return;
    window.__settingsI18nApplying = true;
    try {
      root.querySelectorAll('[data-i18n]').forEach((el) => {
        const val = t(el.getAttribute('data-i18n'), el.textContent || '');
        if (val) el.innerHTML = val;
      });
      root.querySelectorAll('[data-i18n-placeholder]').forEach((el) => {
        const val = t(el.getAttribute('data-i18n-placeholder'), el.getAttribute('placeholder') || '');
        if (val) el.setAttribute('placeholder', val);
      });
      root.querySelectorAll('[data-i18n-title]').forEach((el) => {
        const val = t(el.getAttribute('data-i18n-title'), el.getAttribute('title') || '');
        if (val) el.setAttribute('title', val);
      });
      root.querySelectorAll('[data-i18n-aria-label]').forEach((el) => {
        const val = t(el.getAttribute('data-i18n-aria-label'), el.getAttribute('aria-label') || '');
        if (val) el.setAttribute('aria-label', val);
      });
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
        acceptNode(node) {
          const parent = node.parentElement;
          if (!parent) return NodeFilter.FILTER_REJECT;
          const tag = parent.tagName;
          if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'NOSCRIPT' || tag === 'TEXTAREA') return NodeFilter.FILTER_REJECT;
          return String(node.nodeValue || '').trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
        }
      });
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      nodes.forEach((node) => {
        const original = node.nodeValue;
        const leading = original.match(/^\s*/)[0];
        const trailing = original.match(/\s*$/)[0];
        const translated = translateValue(original);
        if (translated !== original && translated !== original.trim()) node.nodeValue = `${leading}${translated}${trailing}`;
      });
      root.querySelectorAll('input[placeholder], textarea[placeholder]').forEach((el) => {
        const next = translateValue(el.getAttribute('placeholder') || '');
        if (next) el.setAttribute('placeholder', next);
      });
      root.querySelectorAll('[title]').forEach((el) => {
        const next = translateValue(el.getAttribute('title') || '');
        if (next) el.setAttribute('title', next);
      });
      root.querySelectorAll('[aria-label]').forEach((el) => {
        const next = translateValue(el.getAttribute('aria-label') || '');
        if (next) el.setAttribute('aria-label', next);
      });
      root.querySelectorAll('[data-section-title]').forEach((el) => {
        const next = translateValue(el.getAttribute('data-section-title') || '');
        if (next) el.setAttribute('data-section-title', next);
      });
      root.querySelectorAll('[data-confirm]').forEach((el) => {
        const next = translateValue(el.getAttribute('data-confirm') || '');
        if (next) el.setAttribute('data-confirm', next);
      });
      root.querySelectorAll('option').forEach((el) => {
        const next = translateValue(el.textContent || '');
        if (next) el.textContent = next;
      });
    } finally {
      window.__settingsI18nApplying = false;
    }
  }

  function applyLanguage() {
    const lang = normalizeLang(window.SETTINGS_I18N_ACTIVE_LANG) || getLang();
    window.SETTINGS_I18N_ACTIVE_LANG = lang;
    document.documentElement.lang = lang;
    document.title = t('global.page_title', 'Panel Settings Studio');

    const brand = document.querySelector('.brand h1, .sidebar-brand-text');
    if (brand) brand.innerHTML = t('global.brand', '<span>Panel</span> Settings');
    const search = document.getElementById('searchSettings');
    if (search) search.placeholder = t('global.search_placeholder', 'Search settings...');
    setButtonText(document.getElementById('saveBtn'), t('global.save', 'Save'));

    const refreshBtn = document.getElementById('panelRefreshBtn');
    if (refreshBtn) refreshBtn.title = t('global.refresh_title', 'Refresh panel');
    const restartBtn = document.getElementById('panelRestartBtn');
    if (restartBtn) restartBtn.title = t('global.restart_title', 'Restart panel');

    const langBtn = document.getElementById('langToggleBtn');
    if (langBtn) {
      if (langBtn.tagName === 'SELECT') langBtn.value = lang;
      else langBtn.textContent = lang === 'tr' ? 'EN' : 'TR';
      langBtn.title = t('global.language_toggle', lang === 'tr' ? 'English' : 'Türkçe');
      langBtn.setAttribute('aria-label', t('global.language', 'Language'));
    }

    const statusText = document.getElementById('statusText');
    const statusSubtext = document.getElementById('statusSubtext');
    const summaryStatus = document.getElementById('summaryStatus');
    if (statusText) statusText.textContent = translateValue(statusText.textContent || t('global.loading'));
    if (statusSubtext) statusSubtext.textContent = translateValue(statusSubtext.textContent || t('global.connecting'));
    if (summaryStatus) summaryStatus.textContent = translateValue(summaryStatus.textContent || t('global.status_ready'));

    const tabMap = {
      'section-home': 'tabs.home', 'section-performance': 'tabs.performance', 'section-ui': 'tabs.ui',
      'section-window': 'tabs.window', 'section-tuya': 'tabs.tuya', 'section-logging': 'tabs.logging',
      'section-frontend': 'tabs.frontend', 'section-panel-buttons': 'tabs.buttons', 'section-calendar': 'tabs.calendar',
      'section-health': 'tabs.health', 'section-logs': 'tabs.logs', 'section-sitemap': 'tabs.sitemap',
      'section-reset': 'tabs.reset', 'section-api': 'tabs.api'
    };
    Object.entries(tabMap).forEach(([id, key]) => {
      const tab = document.querySelector(`[data-tab-target="${id}"]`);
      if (tab) setButtonText(tab, t(key, tab.textContent));
      const section = document.getElementById(id);
      if (section) section.dataset.sectionTitle = t(key, section.dataset.sectionTitle || '');
    });

    const sectionKeyById = {
      'section-home': 'home', 'section-performance': 'performance', 'section-ui': 'ui', 'section-window': 'window',
      'section-tuya': 'tuya', 'section-logging': 'logging', 'section-frontend': 'frontend', 'section-calendar': 'calendar',
      'section-health': 'health', 'section-logs': 'logs', 'section-sitemap': 'sitemap', 'section-reset': 'reset',
      'section-api': 'api', 'section-panel-buttons': 'buttons'
    };
    Object.entries(sectionKeyById).forEach(([id, key]) => {
      const section = document.getElementById(id);
      if (!section) return;
      const kicker = section.querySelector('.section-kicker');
      const title = section.querySelector('.section-head h2');
      const desc = section.querySelector('.section-head p');
      if (kicker) kicker.textContent = t(`sections.${key}.kicker`, kicker.textContent);
      if (title) title.textContent = t(`sections.${key}.title`, title.textContent);
      if (desc) desc.textContent = t(`sections.${key}.desc`, desc.textContent);
    });

    [document.querySelector('.sidebar'), document.querySelector('.topbar'), document.querySelector('.section.is-active')]
      .filter(Boolean)
      .forEach((root) => translateTree(root));
  }

  function loadLanguagePack(lang, id) {
    lang = normalizeLang(lang) || 'en';
    return new Promise((resolve, reject) => {
      const old = document.getElementById(id);
      if (old) old.remove();
      const script = document.createElement('script');
      script.id = id;
      script.src = langSrc(lang);
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });
  }

  function loadLanguage(lang) {
    lang = normalizeLang(lang) || 'en';
    rememberCurrentAliases();

    const loadTarget = () => loadLanguagePack(lang, 'settings-lang-pack').then(() => {
      window.SETTINGS_I18N_ACTIVE_LANG = lang;
      rememberCurrentAliases();
      if (lang === 'en') window.SETTINGS_I18N_SOURCE_ALIASES_READY = true;
    });

    if (lang !== 'en' && !window.SETTINGS_I18N_SOURCE_ALIASES_READY) {
      return loadLanguagePack('en', 'settings-lang-pack-source')
        .then(() => {
          rememberCurrentAliases();
          window.SETTINGS_I18N_SOURCE_ALIASES_READY = true;
          const sourceScript = document.getElementById('settings-lang-pack-source');
          if (sourceScript) sourceScript.remove();
        })
        .then(loadTarget);
    }

    return loadTarget();
  }

  function setLanguage(lang) {
    lang = normalizeLang(lang) || 'en';
    try { localStorage.setItem('settings_language', lang); } catch (_) {}
    return loadLanguage(lang).then(() => {
      applyLanguage();
      document.dispatchEvent(new CustomEvent('settings-language-changed', { detail: { lang } }));
    });
  }

  function initLanguageButton() {
    const btn = document.getElementById('langToggleBtn');
    if (!btn || btn.__settingsLangBound) return;
    btn.__settingsLangBound = true;
    btn.addEventListener(btn.tagName === 'SELECT' ? 'change' : 'click', () => {
      const current = normalizeLang(window.SETTINGS_I18N_ACTIVE_LANG) || getLang();
      const next = btn.tagName === 'SELECT' ? normalizeLang(btn.value) : (current === 'tr' ? 'en' : 'tr');
      setLanguage(next).catch(console.error);
    });
  }

  let observerTimer = null;
  function initObserver() {
    if (window.__settingsI18nObserver || !document.body) return;
    window.__settingsI18nObserver = { disabled: true };
  }

  window.getSettingsPageLanguage = () => normalizeLang(window.SETTINGS_I18N_ACTIVE_LANG) || getLang();
  window.setSettingsPageLanguage = setLanguage;
  window.applySettingsLanguage = applyLanguage;
  window.translateSettingsText = translateValue;
  window.t = t;

  window.SETTINGS_I18N_ACTIVE_LANG = getLang();
  try { localStorage.setItem('settings_language', window.SETTINGS_I18N_ACTIVE_LANG); } catch (_) {}

  function bootSettingsI18n() {
    initLanguageButton();
    setLanguage(window.SETTINGS_I18N_ACTIVE_LANG)
      .then(() => {
        applyLanguage();
        initObserver();
      })
      .catch((err) => {
        console.error('Settings i18n language pack could not be loaded:', err);
        const btn = document.getElementById('langToggleBtn');
        if (btn) {
          btn.title = 'Language file could not be loaded: settings_i18n_tr.js / settings_i18n_en.js';
        }
      });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootSettingsI18n, { once: true });
  } else {
    bootSettingsI18n();
  }
})();
