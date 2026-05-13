// Ver. 0.7
const sketchSvgTemplateCache = new Map();

function createSketchSVGTemplate(width, height, radius) {
    const cacheKey = `${width}x${height}r${radius}`;
    const cached = sketchSvgTemplateCache.get(cacheKey);
    if (cached) return cached;

    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    const rectangle = document.createElementNS('http://www.w3.org/2000/svg', 'rect');

    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);

    rectangle.setAttribute('x', '1');
    rectangle.setAttribute('y', '1');
    rectangle.setAttribute('width', String(Math.max(0, width - 2)));
    rectangle.setAttribute('height', String(Math.max(0, height - 2)));
    rectangle.setAttribute('rx', String(radius));
    rectangle.setAttribute('ry', String(radius));
    rectangle.setAttribute('pathLength', '10');

    svg.appendChild(rectangle);
    sketchSvgTemplateCache.set(cacheKey, svg);
    return svg;
}

function createSketchSVG(width, height, radius) {
    return createSketchSVGTemplate(width, height, radius).cloneNode(true);
}

function appendSketchSvgs(target, width, height, radius, count) {
    const fragment = document.createDocumentFragment();
    for (let i = 0; i < count; i += 1) {
        fragment.appendChild(createSketchSVG(width, height, radius));
    }
    target.appendChild(fragment);
}

function setupSketchButtons() {
    document.querySelectorAll('.sketch-button').forEach((button) => {
if (button.dataset.sketchReady === '1') return;

const radius = 4;
const width = Math.round(button.offsetWidth || button.getBoundingClientRect().width || 0);
const height = Math.round(button.offsetHeight || button.getBoundingClientRect().height || 0);
if (!width || !height) return;

button.dataset.sketchReady = '1';

        const lines = document.createElement('div');
        lines.classList.add('lines');

        const groupTop = document.createElement('div');
        const groupBottom = document.createElement('div');

        appendSketchSvgs(groupTop, width, height, radius, 4);
        appendSketchSvgs(groupBottom, width, height, radius, 4);

        lines.appendChild(groupTop);
        lines.appendChild(groupBottom);
        button.appendChild(lines);

        const startAnim = () => {
            // Eski gorsel efekt korunuyor; bug yapan forced reflow kaldirildi.
            // Previous animations are cancelled and SVGs are restarted cleanly with the Web Animations API.
            if (button._sketchAnimations && Array.isArray(button._sketchAnimations)) {
                button._sketchAnimations.forEach((anim) => {
                    try { anim.cancel(); } catch (_) {}
                });
            }

            const svgs = Array.from(lines.querySelectorAll('svg'));
            button._sketchAnimations = svgs.map((svg) => {
                svg.style.opacity = '0';
                svg.style.strokeDashoffset = '14';
                const anim = svg.animate([
                    { strokeDashoffset: '14', opacity: 0, offset: 0 },
                    { opacity: 1, offset: 0.12 },
                    { opacity: 1, offset: 0.30 },
                    { opacity: 1, offset: 0.58 },
                    { strokeDashoffset: '4', opacity: 0, offset: 1 }
                ], {
                    duration: 1000,
                    easing: 'linear',
                    fill: 'none'
                });
                anim.onfinish = () => {
                    svg.style.opacity = '0';
                    svg.style.strokeDashoffset = '14';
                };
                anim.oncancel = () => {
                    svg.style.opacity = '0';
                    svg.style.strokeDashoffset = '14';
                };
                return anim;
            });
        };

        button.addEventListener('pointerdown', startAnim, { passive: true });
    });
}

window.addEventListener('load', setupSketchButtons);
let _resizeDebounceTimer = null;
window.addEventListener('resize', () => {
    clearTimeout(_resizeDebounceTimer);
    _resizeDebounceTimer = setTimeout(() => {
        document.querySelectorAll('.sketch-button .lines').forEach(el => el.remove());
        document.querySelectorAll('.sketch-button').forEach(btn => btn.dataset.sketchReady = '0');
        setupSketchButtons();
        applyVolumeAspectCompensation();
        applyVolumeVisual(volumeSlider ? volumeSlider.value : 0);
    }, 150);
});

let pendingCmdUrl = null;
let pendingAction = null;

function hardReloadLikeCtrlF5() {
    const url = new URL(window.location.href);
    url.searchParams.set("_reload", Date.now());
    window.location.replace(url.toString());
}

function handleCmd(el, url) {
    const action = {
        command: url,
        method: 'GET',
        confirmText: el ? (el.getAttribute('data-confirm') || '') : '',
        label: (el && (el.getAttribute('aria-label') || el.getAttribute('title'))) || ''
    };
    if (typeof executePanelAction === 'function') return executePanelAction(action);
    pendingCmdUrl = url;
    const msgEl = document.getElementById('confirmMessage');
    if (!msgEl || !confirmOverlayEl) { cmd(url); return false; }
    msgEl.textContent = action.confirmText || 'Are you sure?';
    confirmOverlayEl.classList.remove('confirm-hidden');
    return false;
}

function closeConfirm() {
    pendingCmdUrl = null;
    pendingAction = null;
    if (confirmOverlayEl) confirmOverlayEl.classList.add('confirm-hidden');
}

async function approveConfirm() {
    const action = pendingAction;
    const url = pendingCmdUrl;
    if (confirmOverlayEl) confirmOverlayEl.classList.add('confirm-hidden');
    pendingCmdUrl = null;
    pendingAction = null;
    if (action && typeof runPanelAction === 'function') { await runPanelAction(action); return; }
    if (!url) return;
    if (typeof cmd === 'function') { cmd(url); }
else { fetch(url, { cache: 'no-store' }).catch(err => { console.error(err); alert('Command could not be sent.'); }); }
}

document.addEventListener('keydown', function (e) {
    const open = confirmOverlayEl && !confirmOverlayEl.classList.contains('confirm-hidden');
    if (!open) return;
    if (e.key === 'Escape') closeConfirm();
    if (e.key === 'Enter') approveConfirm();
});

let PANEL_SETTINGS_CACHE = null;
let PANEL_SETTINGS_LAST_FETCH_AT = 0;
let PANEL_SETTINGS_LAST_JSON = '';
let PANEL_LEFT_BUTTONS_LAST_JSON = '';
let PANEL_LYRICS_LOOP_SIGNATURE = '';
let PANEL_MEDIA_PROGRESS_SIGNATURE = '';
let PANEL_STATUS_POLL_INTERVAL_MS = null;
let PANEL_SETTINGS_POLL_TIMER = null;
let PANEL_SETTINGS_POLL_DELAY_MS = 30000;
let PANEL_SETTINGS_UNCHANGED_STREAK = 0;
const PANEL_SETTINGS_POLL_MIN_MS = 30000;
const PANEL_SETTINGS_POLL_MAX_MS = 300000;

function stableStringifySettings(value) {
    const seen = new WeakSet();
    const normalize = (item) => {
        if (item === null || typeof item !== 'object') return item;
        if (seen.has(item)) return null;
        seen.add(item);
        if (Array.isArray(item)) return item.map(normalize);
        const out = {};
        Object.keys(item).sort().forEach((key) => { out[key] = normalize(item[key]); });
        return out;
    };
    try { return JSON.stringify(normalize(value)); } catch (_) {
        try { return JSON.stringify(value); } catch (__) { return ''; }
    }
}

function getPanelSetting(path, fallback = undefined) {
    const src = PANEL_SETTINGS_CACHE;
    if (!src || typeof src !== 'object') return fallback;
    const parts = String(path || '').split('.').filter(Boolean);
    let cur = src;
    for (const part of parts) {
        if (!cur || typeof cur !== 'object' || !(part in cur)) return fallback;
        cur = cur[part];
    }
    return cur === undefined ? fallback : cur;
}

function getPanelSettingsPollBaseMs() {
    return Math.max(PANEL_SETTINGS_POLL_MIN_MS, getPerformanceNumber('status_poll_interval_ms', 5000) * 6);
}

function clearPanelSettingsPolling() {
    if (PANEL_SETTINGS_POLL_TIMER) {
        clearTimeout(PANEL_SETTINGS_POLL_TIMER);
        PANEL_SETTINGS_POLL_TIMER = null;
    }
}

function schedulePanelSettingsPolling(delayMs = null) {
    clearPanelSettingsPolling();
    const nextDelay = Math.max(
        PANEL_SETTINGS_POLL_MIN_MS,
        Math.min(PANEL_SETTINGS_POLL_MAX_MS, Number.isFinite(delayMs) ? delayMs : PANEL_SETTINGS_POLL_DELAY_MS)
    );
    PANEL_SETTINGS_POLL_DELAY_MS = nextDelay;
    PANEL_SETTINGS_POLL_TIMER = setTimeout(() => {
        PANEL_SETTINGS_POLL_TIMER = null;
        refreshPanelSettings(false);
    }, nextDelay);
}

function getFrontendSetting(path, fallback = undefined) {
    return getPanelSetting(`frontend.${path}`, fallback);
}

function getApiSetting(path, fallback = undefined) {
    return getPanelSetting(`api.${path}`, fallback);
}

function getPerformanceSetting(path, fallback = undefined) {
    return getPanelSetting(`performance.${path}`, fallback);
}

function getPerformanceNumber(path, fallback) {
    const raw = getPerformanceSetting(path, fallback);
    const n = Number(raw);
    return Number.isFinite(n) ? n : fallback;
}

function getFrontendNumber(path, fallback) {
    const raw = getFrontendSetting(path, fallback);
    const n = Number(raw);
    return Number.isFinite(n) ? n : fallback;
}

function getFrontendBool(path, fallback = false) {
    return !!getFrontendSetting(path, fallback);
}

function getFrontendString(path, fallback = '') {
    const raw = getFrontendSetting(path, fallback);
    return raw == null ? String(fallback ?? '') : String(raw);
}

function normalizePanelLanguage(value) {
    const raw = String(value || '').trim().toLowerCase();
    return raw === 'tr' ? 'tr' : 'en';
}

function getPanelLanguage() {
    return normalizePanelLanguage(getFrontendSetting('panel_language', 'en'));
}
window.getPanelLanguage = getPanelLanguage;

const PANEL_I18N = {
    en: {
        title: 'PC Control Panel',
        system_summary: 'System summary',
        climate_level: 'Climate Level',
        tomorrow: 'Tomorrow',
        brightness: 'Brightness',
        climate_settings: 'Climate Settings',
        climate_hint: '18-23: Cooling 23-30: Heating'
    },
    tr: {
        title: 'PC Kontrol Paneli',
        system_summary: 'Sistem özeti',
        climate_level: 'Klima Seviyesi',
        tomorrow: 'Yarın',
        brightness: 'Parlaklık',
        climate_settings: 'Klima Ayarları',
        climate_hint: '18-23: Soğutma 23-30: Isıtma'
    }
};

function panelText(key) {
    const lang = getPanelLanguage();
    return (PANEL_I18N[lang] && PANEL_I18N[lang][key]) || (PANEL_I18N.en && PANEL_I18N.en[key]) || '';
}

function applyPanelLanguageStatic() {
    const lang = getPanelLanguage();
    document.documentElement.lang = lang;
    document.title = panelText('title') || document.title;
    document.querySelectorAll('[data-panel-i18n]').forEach((el) => {
        const value = panelText(el.getAttribute('data-panel-i18n'));
        if (value) setTextIfChanged(el, value);
    });
    document.querySelectorAll('[data-panel-i18n-aria]').forEach((el) => {
        const value = panelText(el.getAttribute('data-panel-i18n-aria'));
        if (value) setAttrIfChanged(el, 'aria-label', value);
    });
}

function getIdleText() {
    return getFrontendString('idle_text', 'nihil infinitum est ');
}

function getLyricsWaitingText() {
    return getFrontendString('lyrics_waiting_text', 'Waiting for lyrics...');
}

function getNormalizedIdleText() {
    return getIdleText().trim().toLowerCase();
}

function getNormalizedLyricsWaitingText() {
    return getLyricsWaitingText().trim().toLowerCase();
}

function getNoMediaPlaceholderTitle() {
    return getFrontendString('no_media_placeholder_title', 'el. psy. congroo.');
}

function getNormalizedNoMediaPlaceholderTitle() {
    return getNoMediaPlaceholderTitle().trim().toLowerCase();
}


/* ===== FRONTEND LIQUID THEME PRESETS =====
   Theme colors come from liquid_themes.js as the single source of truth.
   If that file loads late because of cache/load order, each theme
   okumada window.LIQUID_THEME_PRESETS tekrar kontrol edilir.
*/
const LIQUID_THEME_FALLBACK_DEFAULT_KEY = 'default_glass';
const LIQUID_THEME_FALLBACK_PRESETS = Object.freeze({
    default_glass: {
        label: 'Default Glass / Ice',
        vars: {
            '--liq-1': 'rgba(255, 255, 255, 0.20)',
            '--liq-2': 'rgba(240, 248, 255, 0.10)',
            '--liq-3': 'rgba(224, 255, 255, 0.05)',
            '--liq-4': 'rgba(175, 238, 238, 0.10)',
            '--liq-5': 'rgba(135, 206, 235, 0.15)',
            '--liq-6': 'rgba(70, 130, 180, 0.25)',
            '--gloss-1': 'rgba(255, 255, 255, 0.25)',
            '--gloss-2': 'rgba(255, 255, 255, 0.05)',
            '--gloss-3': 'rgba(255, 255, 255, 0.01)',
            '--gloss-4': 'rgba(255, 255, 255, 0)',
            '--blob-a': 'rgba(200, 240, 255, 0.08)',
            '--blob-b': 'rgba(255, 255, 255, 0.12)',
            '--shadow': 'rgba(70, 130, 180, 0.30)',
        },
    },
});
function getLiquidThemeDefaultKey() {
    return String(window.LIQUID_THEME_DEFAULT_KEY || LIQUID_THEME_FALLBACK_DEFAULT_KEY);
}
function getLiquidThemePresets() {
    const presets = window.LIQUID_THEME_PRESETS;
    if (presets && typeof presets === 'object' && Object.keys(presets).length > 0) return presets;
    return LIQUID_THEME_FALLBACK_PRESETS;
}
let LAST_APPLIED_LIQUID_THEME_SIGNATURE = '';
let LIQUID_ANIMATION_LAST_FRAME_AT = 0;
let LIQUID_ANIMATION_TIMER = null;
let LIQUID_ANIMATION_RAF = null;
let LIQUID_ANIMATION_ACTIVE_UNTIL = 0;

function getAnimationLevel() {
    const raw = String(getFrontendSetting('animation_level', 'normal') || 'normal').trim().toLowerCase();
    return ['off', 'low', 'normal', 'high'].includes(raw) ? raw : 'normal';
}

function isLowPerformanceMode() {
    return getFrontendBool('low_performance_mode', false);
}

function shouldAnimateLiquidBars() {
    return getFrontendBool('liquid_animation_enabled', true) && !isLowPerformanceMode() && getAnimationLevel() !== 'off';
}

function shouldKeepLiquidWaveAlive() {
    return getLiquidAnimationMode() === 'full' && getFrontendBool('liquid_wave_when_idle', false);
}

function getLiquidAnimationSettleMs() {
    const mode = getLiquidAnimationMode();
    if (mode === 'static') return 0;
    if (mode === 'light') return 260;
    return 900;
}

function hasLiquidBarMotionPending() {
    const bars = [cpuBarEl, gpuBarEl, ramBarEl, shiftBarEl, powerBarEl];
    for (const barEl of bars) {
        if (!barEl) continue;
        const target = Number.isFinite(barEl._targetFill) ? barEl._targetFill : 0;
        const current = Number.isFinite(barEl._currentFill) ? barEl._currentFill : target;
        if (Math.abs(target - current) >= 0.05) return true;
    }
    return Date.now() < LIQUID_ANIMATION_ACTIVE_UNTIL;
}

function shouldRunLiquidLoop() {
    return (
        shouldAnimateLiquidBars()
        && document.visibilityState !== 'hidden'
        && (shouldKeepLiquidWaveAlive() || hasLiquidBarMotionPending())
    );
}

function getLiquidAnimationMode() {
    const raw = String(getFrontendSetting('liquid_animation_mode', 'full') || 'full').trim().toLowerCase();
    return ['static', 'light', 'full'].includes(raw) ? raw : 'full';
}

function getLiquidAnimationFps() {
    const raw = getFrontendNumber('liquid_animation_fps', 30);
    const n = Number.isFinite(raw) ? raw : 30;
    return Math.max(1, Math.min(60, n));
}

function getLiquidAnimationFrameMs() {
    const animated = shouldAnimateLiquidBars();
    const fps = animated ? getLiquidAnimationFps() : 2;
    const mode = getLiquidAnimationMode();
    const cappedFps = mode === 'light' ? Math.min(fps, 12) : fps;
    return 1000 / Math.max(1, cappedFps);
}

function clearLiquidAnimationSchedule() {
    if (LIQUID_ANIMATION_TIMER) {
        clearTimeout(LIQUID_ANIMATION_TIMER);
        LIQUID_ANIMATION_TIMER = null;
    }
    if (LIQUID_ANIMATION_RAF) {
        cancelAnimationFrame(LIQUID_ANIMATION_RAF);
        LIQUID_ANIMATION_RAF = null;
    }
}

function scheduleLiquidAnimationFrame(delayMs = null) {
    clearLiquidAnimationSchedule();
    if (!shouldRunLiquidLoop()) return;

    const waitMs = Math.max(0, Number.isFinite(delayMs) ? delayMs : getLiquidAnimationFrameMs());
    LIQUID_ANIMATION_TIMER = setTimeout(() => {
        LIQUID_ANIMATION_TIMER = null;
        if (!shouldRunLiquidLoop()) return;
        LIQUID_ANIMATION_RAF = requestAnimationFrame((timestamp) => {
            LIQUID_ANIMATION_RAF = null;
            animateLiquidBars(timestamp);
        });
    }, waitMs);
}

function getLiquidThemePreset(themeKey) {
    const presets = getLiquidThemePresets();
    const defaultKey = getLiquidThemeDefaultKey();
    const key = String(themeKey || '').trim();
    return presets[key] || presets[defaultKey] || LIQUID_THEME_FALLBACK_PRESETS.default_glass;
}

function getSelectedLiquidThemeKey(targetName) {
    const presets = getLiquidThemePresets();
    const defaultKey = getLiquidThemeDefaultKey();
    const raw = getFrontendSetting(`liquid_theme_${targetName}`, defaultKey);
    const key = String(raw || defaultKey).trim() || defaultKey;
    return presets[key] ? key : defaultKey;
}

function applyLiquidThemeVarsToSvg(svgEl, preset) {
    if (!svgEl || !preset || !preset.vars) return;
    Object.entries(preset.vars).forEach(([name, value]) => {
        svgEl.style.setProperty(name, value);
    });
}

function applyLiquidThemesToFrontend(force = false) {
    const selected = {
        cpu: getSelectedLiquidThemeKey('cpu'),
        gpu: getSelectedLiquidThemeKey('gpu'),
        ram: getSelectedLiquidThemeKey('ram'),
        shift: getSelectedLiquidThemeKey('shift'),
        fps: getSelectedLiquidThemeKey('fps'),
        power: getSelectedLiquidThemeKey('power'),
    };
    const signature = `${selected.cpu}|${selected.gpu}|${selected.ram}|${selected.shift}|${selected.fps}|${selected.power}`;
    if (!force && signature === LAST_APPLIED_LIQUID_THEME_SIGNATURE) return;
    LAST_APPLIED_LIQUID_THEME_SIGNATURE = signature;

    const targets = [
        ['cpu', '.liquid-svg.theme-cpu, #cpuCard .liquid-svg'],
        ['gpu', '.liquid-svg.theme-gpu, #gpuCard .liquid-svg'],
        ['ram', '.liquid-svg.theme-ram, #ramCard .liquid-svg'],
        ['shift', '.liquid-svg.theme-shift, #shiftCard .liquid-svg'],
        ['fps', '.liquid-svg.theme-fps'],
        ['power', '.liquid-svg.theme-power'],
    ];
    targets.forEach(([name, selector]) => {
        const preset = getLiquidThemePreset(selected[name]);
        document.querySelectorAll(selector).forEach((svgEl) => {
            if (!force && svgEl.dataset.appliedLiquidTheme === selected[name]) return;
            applyLiquidThemeVarsToSvg(svgEl, preset);
            svgEl.dataset.appliedLiquidTheme = selected[name];
        });
    });
}

function applyDynamicLowCardLiquidTheme(mode = 'fps', force = false) {
    const svgEl = document.querySelector('#lowCard .liquid-svg');
    if (!svgEl) return;
    const safeMode = mode === 'power' ? 'power' : 'fps';
    svgEl.classList.toggle('theme-fps', safeMode === 'fps');
    svgEl.classList.toggle('theme-power', safeMode === 'power');
    const key = getSelectedLiquidThemeKey(safeMode);
    if (!force && svgEl.dataset.appliedLiquidTheme === key && svgEl.dataset.liquidMode === safeMode) return;
    applyLiquidThemeVarsToSvg(svgEl, getLiquidThemePreset(key));
    svgEl.dataset.appliedLiquidTheme = key;
    svgEl.dataset.liquidMode = safeMode;
}

function getRatioFillPercent(value, maxValue) {
    const n = Number(value);
    const max = Number(maxValue);
    if (!Number.isFinite(n) || !Number.isFinite(max) || max <= 0) return 0;
    return clampUsage((Math.max(0, n) / max) * 100);
}

let SHIFT_LIQUID_RANDOM = { value: 42, nextAt: 0 };
function getShiftLiquidRandomFillPercent() {
    const now = Date.now();
    if (!Number.isFinite(SHIFT_LIQUID_RANDOM.value) || now >= SHIFT_LIQUID_RANDOM.nextAt) {
        SHIFT_LIQUID_RANDOM.value = 22 + Math.random() * 62;
        SHIFT_LIQUID_RANDOM.nextAt = now + 7000 + Math.random() * 5000;
    }
    return SHIFT_LIQUID_RANDOM.value;
}


/* ===== SETTINGS-DRIVEN PANEL BUTTONS ===== */
function getPanelLeftButtons() {
    const raw = getPanelSetting('panel.left_buttons', []);
    return Array.isArray(raw) ? raw : [];
}

function normalizePanelButtonConfig(raw, index = 0) {
    const fallbackId = `button_${index + 1}`;
    const method = String(raw && raw.method ? raw.method : 'GET').trim().toUpperCase();
    return {
        id: String(raw && raw.id ? raw.id : fallbackId).trim() || fallbackId,
        label: String(raw && raw.label ? raw.label : `Button ${index + 1}`).trim() || `Button ${index + 1}`,
        visible: !(raw && raw.visible === false),
        variant: String(raw && raw.variant ? raw.variant : 'white-glow').trim() || 'white-glow',
        command: String(raw && raw.command ? raw.command : '').trim(),
        secondaryCommand: String(raw && raw.secondary_command ? raw.secondary_command : '').trim(),
        method: ['GET', 'POST', 'SPECIAL'].includes(method) ? method : 'GET',
        confirmText: String(raw && raw.confirm_text ? raw.confirm_text : '').trim(),
        iconSvg: String(raw && raw.icon_svg ? raw.icon_svg : '').trim()
    };
}

function panelButtonDomId(buttonId) {
    const id = String(buttonId || '').trim();
    if (id === 'climate') return 'climateLevelBtn';
    if (id === 'youtube') return 'youtubeLaunchBtn';
    if (id === 'spotify') return 'spotifyLaunchBtn';
    return `panelButton_${id.replace(/[^a-zA-Z0-9_-]/g, '_')}`;
}

function renderPanelLeftButtons(force = false) {
    const container = document.getElementById('panelLeftButtons') || document.querySelector('.buttons3');
    if (!container) return;
    const buttons = getPanelLeftButtons().map(normalizePanelButtonConfig).filter((b) => b.visible && b.command);
    const signature = stableStringifySettings(buttons);
    if (!force && signature === PANEL_LEFT_BUTTONS_LAST_JSON) return;
    PANEL_LEFT_BUTTONS_LAST_JSON = signature;

    const html = buttons.map((button) => {
        const domId = panelButtonDomId(button.id);
        const safeVariant = String(button.variant || 'white-glow').replace(/[^a-zA-Z0-9_-]/g, '');
        const label = escapeHtml(button.label || button.id);
        const command = escapeHtml(button.command);
        const secondary = escapeHtml(button.secondaryCommand || '');
        const method = escapeHtml(button.method || 'GET');
        const confirmText = escapeHtml(button.confirmText || '');
        const icon = button.iconSvg || `<span class="panel-button-label">${label}</span>`;
        return `<button type="button" id="${domId}" class="btn sketch-button ${safeVariant}" data-panel-action="1" data-command="${command}" data-secondary-command="${secondary}" data-method="${method}" data-confirm="${confirmText}" aria-label="${label}" title="${label}">${icon}</button>`;
    }).join('');

    container.innerHTML = html;
    container.dataset.panelButtonsRendered = '1';
    setupSketchButtons();
    bindPanelButtons(container);
}

async function executeHttpCommand(path, method = 'GET') {
    const response = await fetch(path, { method, cache: 'no-store' });
    let payload = null;
    try { payload = await response.json(); } catch (_) { payload = null; }
    if (!response.ok) return { ok: false, error: (payload && payload.error) || `HTTP ${response.status}` };
    return payload && typeof payload === 'object' ? payload : { ok: true, raw: payload };
}

async function runPanelAction(action) {
    if (!action || !action.command) return { ok: false, error: 'No command' };
    if (action.method === 'SPECIAL' || action.command === '__climate_popup__') {
        if (typeof window.openClimateLevelPopup === 'function') {
            window.openClimateLevelPopup();
            return { ok: true, special: true };
        }
        setStatusText('Climate popup is not ready', true);
        return { ok: false, error: 'Climate popup is not ready' };
    }
    if (String(action.method || 'GET').toUpperCase() === 'POST') return executeHttpCommand(action.command, 'POST');
    return cmdJson(action.command);
}

async function executePanelAction(action) {
    if (!action || !action.command) return false;
    if (action.confirmText) {
        pendingAction = action;
        const msgEl = document.getElementById('confirmMessage');
        if (msgEl) msgEl.textContent = action.confirmText;
        if (confirmOverlayEl) confirmOverlayEl.classList.remove('confirm-hidden');
        else await runPanelAction(action);
        return false;
    }
    const result = await runPanelAction(action);
    if (result && result.ok === false) setStatusText(`${action.label || 'Command'} failed`, true);
    return false;
}

function bindPanelButtons(container) {
    if (!container || container.dataset.panelButtonsBound === '1') return;
    container.dataset.panelButtonsBound = '1';

    container.addEventListener('pointerdown', (event) => {
        const btn = event.target.closest('[data-panel-action]');
        if (!btn || !container.contains(btn)) return;
        const secondary = String(btn.dataset.secondaryCommand || '').trim();
        if (!secondary) return;
        btn._panelLongPressDone = false;
        clearTimeout(btn._panelLongPressTimer);
        btn._panelLongPressTimer = setTimeout(async () => {
            btn._panelLongPressDone = true;
            await executePanelAction({
                command: secondary,
                method: btn.dataset.method || 'GET',
                confirmText: '',
                label: btn.getAttribute('aria-label') || ''
            });
        }, APP_BUTTON_LONG_PRESS_MS || 550);
    });

    const clearLongPress = (event) => {
        const btn = event.target.closest('[data-panel-action]');
        if (!btn || !container.contains(btn)) return;
        clearTimeout(btn._panelLongPressTimer);
        btn._panelLongPressTimer = null;
    };
    container.addEventListener('pointerup', clearLongPress);
    container.addEventListener('pointercancel', clearLongPress);
    container.addEventListener('pointerleave', clearLongPress);

    container.addEventListener('click', (event) => {
        const btn = event.target.closest('[data-panel-action]');
        if (!btn || !container.contains(btn)) return;
        event.preventDefault();
        if (btn._panelLongPressDone) {
            btn._panelLongPressDone = false;
            return;
        }
        executePanelAction({
            command: btn.dataset.command || '',
            method: btn.dataset.method || 'GET',
            confirmText: btn.dataset.confirm || '',
            label: btn.getAttribute('aria-label') || ''
        });
    });
}

function _resolveDateWeatherBlock() {
    return document.querySelector('.date-weather-box')
        || document.querySelector('.datetime-card')
        || (document.getElementById('panelDate') ? document.getElementById('panelDate').closest('.date-weather-box') : null);
}

function applyFrontendVisibilitySettings() {
    const showFps = getFrontendBool('show_fps_card', true);
    const showDateWeather = getFrontendBool('show_date_weather_block', true);
    const showTuya = getFrontendBool('show_tuya_card', true);
    const showNowPlaying = getFrontendBool('show_now_playing_card', true);
    const showLyrics = getFrontendBool('show_lyrics_card', true);

    const fpsCard = document.getElementById('fpsCard');
    if (fpsCard) fpsCard.style.display = showFps ? '' : 'none';

    const dateWeatherBlock = _resolveDateWeatherBlock();
    if (dateWeatherBlock) dateWeatherBlock.style.display = showDateWeather ? '' : 'none';

    const tuyaCard = document.getElementById('tuyaCard') || document.getElementById('tuyaWrap');
    if (tuyaCard) tuyaCard.style.display = showTuya ? '' : 'none';

    const mediaCard = document.getElementById('nowPlayingCard') || document.getElementById('mediaWrap') || document.getElementById('bottomInfoRow');
    if (mediaCard) mediaCard.style.display = showNowPlaying ? '' : 'none';

    const lyricsCard = document.getElementById('bottomLyricCard') || document.getElementById('lyricsWrap');
    if (lyricsCard) lyricsCard.style.display = showLyrics ? '' : 'none';

    const bottomInfoRow = document.getElementById('bottomInfoRow');
    if (bottomInfoRow) {
        const mediaVisible = !mediaCard || mediaCard.style.display !== 'none';
        const lyricsVisible = !lyricsCard || lyricsCard.style.display !== 'none';
        bottomInfoRow.style.display = (mediaVisible || lyricsVisible) ? '' : 'none';
    }
}

function applyFrontendBehaviorSettings() {
    document.body.classList.toggle('low-performance-mode', getFrontendBool('low_performance_mode', false));
    document.body.dataset.animationLevel = String(getFrontendSetting('animation_level', 'normal') || 'normal');
    applyPanelLanguageStatic();
    applyFrontendVisibilitySettings();
    applyLiquidThemesToFrontend();
    applyDynamicLowCardLiquidTheme((document.querySelector('#lowCard .liquid-svg') && document.querySelector('#lowCard .liquid-svg').dataset.liquidMode) || 'fps');
    scheduleLiquidAnimationFrame(0);
    renderPanelLeftButtons();
}

function getLyricsLoopSignature() {
    return [
        getFrontendNumber('lyrics_animation_interval_ms', 90),
        getFrontendNumber('lyrics_refresh_interval_ms', 1000),
        getFrontendNumber('lyric_offset_sec', 0.8),
        getFrontendSetting('animation_level', 'normal'),
        getFrontendBool('low_performance_mode', false)
    ].join('|');
}

function refreshLyricsLoopIfNeeded(force = false) {
    const signature = getLyricsLoopSignature();
    if (!force && signature === PANEL_LYRICS_LOOP_SIGNATURE) return;
    PANEL_LYRICS_LOOP_SIGNATURE = signature;
    if (typeof startLyricsAnimationLoop === 'function') startLyricsAnimationLoop();
}

function getMediaProgressLoopSignature() {
    return [
        getFrontendNumber('seekbar_update_interval_ms', 250),
        getFrontendNumber('media_progress_interval_playing_ms', 150),
        getFrontendNumber('media_progress_interval_paused_ms', 500),
        getFrontendBool('show_media_progress_when_idle', false),
        getFrontendBool('hide_seekbar_when_idle', true),
        getFrontendSetting('animation_level', 'normal'),
        getFrontendBool('low_performance_mode', false)
    ].join('|');
}

function refreshMediaProgressLoopIfNeeded(force = false) {
    const signature = getMediaProgressLoopSignature();
    if (!force && signature === PANEL_MEDIA_PROGRESS_SIGNATURE) return;
    PANEL_MEDIA_PROGRESS_SIGNATURE = signature;
    if (typeof startMediaProgressLoop === 'function') startMediaProgressLoop();
}

function refreshStatusFallbackPollingIfNeeded(force = false) {
    const everyMs = Math.max(500, getPerformanceNumber('status_poll_interval_ms', 5000));
    if (!force && PANEL_STATUS_POLL_INTERVAL_MS === everyMs) return;
    PANEL_STATUS_POLL_INTERVAL_MS = everyMs;
    if (typeof scheduleStatusFallbackPolling === 'function') scheduleStatusFallbackPolling();
}

async function refreshPanelSettings(force = false) {
    const now = Date.now();
    const minFetchGapMs = force ? 0 : Math.max(1000, Math.min(PANEL_SETTINGS_POLL_DELAY_MS, getPanelSettingsPollBaseMs()));
    if (!force && (now - PANEL_SETTINGS_LAST_FETCH_AT) < minFetchGapMs) {
        schedulePanelSettingsPolling(PANEL_SETTINGS_POLL_DELAY_MS);
        return;
    }
    PANEL_SETTINGS_LAST_FETCH_AT = now;
    try {
        const resp = await fetch('/api/settings', { cache: 'no-store' });
        if (!resp.ok) {
            schedulePanelSettingsPolling(Math.min(PANEL_SETTINGS_POLL_MAX_MS, Math.max(getPanelSettingsPollBaseMs(), PANEL_SETTINGS_POLL_DELAY_MS * 2)));
            return;
        }
        const data = await resp.json();
        const payload = (data && typeof data === 'object' && data.settings && typeof data.settings === 'object') ? data.settings : data;
        if (payload && typeof payload === 'object') {
            const nextJson = stableStringifySettings(payload);
            if (!force && nextJson && nextJson === PANEL_SETTINGS_LAST_JSON) {
                PANEL_SETTINGS_UNCHANGED_STREAK += 1;
                const baseDelay = getPanelSettingsPollBaseMs();
                const nextDelay = Math.min(PANEL_SETTINGS_POLL_MAX_MS, Math.max(baseDelay, baseDelay * Math.pow(2, Math.min(PANEL_SETTINGS_UNCHANGED_STREAK, 3))));
                schedulePanelSettingsPolling(nextDelay);
                return;
            }
            PANEL_SETTINGS_LAST_JSON = nextJson;
            PANEL_SETTINGS_CACHE = payload;
            PANEL_SETTINGS_UNCHANGED_STREAK = 0;
            PANEL_SETTINGS_POLL_DELAY_MS = getPanelSettingsPollBaseMs();
            applyFrontendBehaviorSettings();
            if (Object.keys(lastStatusState || {}).length) applyWeatherFromStatus(lastStatusState, null);
            if (typeof updatePanelDateTime === 'function') updatePanelDateTime(true);
            refreshLyricsLoopIfNeeded(force);
            refreshMediaProgressLoopIfNeeded(force);
            refreshStatusFallbackPollingIfNeeded(force);
            schedulePanelSettingsPolling(PANEL_SETTINGS_POLL_DELAY_MS);
            return;
        }
        schedulePanelSettingsPolling(PANEL_SETTINGS_POLL_DELAY_MS);
    } catch (_) {
        schedulePanelSettingsPolling(Math.min(PANEL_SETTINGS_POLL_MAX_MS, Math.max(getPanelSettingsPollBaseMs(), PANEL_SETTINGS_POLL_DELAY_MS * 2)));
    }
}

const tuyaButtonElements = Object.create(null);

function getTuyaButtonElement(key) {
    const normalizedKey = String(key || '').trim();
    if (!normalizedKey) return null;
    return tuyaButtonElements[normalizedKey] || null;
}

function rememberTuyaButtonElement(key, button) {
    const normalizedKey = String(key || '').trim();
    if (!normalizedKey || !button) return;
    tuyaButtonElements[normalizedKey] = button;
}

function forgetTuyaButtonElement(key) {
    const normalizedKey = String(key || '').trim();
    if (!normalizedKey) return;
    delete tuyaButtonElements[normalizedKey];
}

// If liquid_themes.js loads after script.js, reapply the theme immediately.
window.addEventListener('load', () => {
    if (window.LIQUID_THEME_PRESETS) {
        LAST_APPLIED_LIQUID_THEME_SIGNATURE = '';
        applyLiquidThemesToFrontend(true);
        applyDynamicLowCardLiquidTheme((document.querySelector('#lowCard .liquid-svg') && document.querySelector('#lowCard .liquid-svg').dataset.liquidMode) || 'fps', true);
    }
});

function getLyricOffsetSec() { return getFrontendNumber('lyric_offset_sec', 0.8); }

let isDraggingVolume = false;
let volumeSendTimer = null;
let volumeVisualCurrent = 0;
let lastLocalVolumeChangeAt = 0;
let lastRenderedVolumeValue = null;
function getVolumeRemoteSyncDelayMs() { return getFrontendNumber('volume_remote_sync_delay_ms', 220); }
let localMuteState = null;
let localMuteOverrideUntil = 0;
function getMuteRemoteSyncDelayMs() { return getFrontendNumber('mute_remote_sync_delay_ms', 1200); }

let currentLrcData = null;
let parsedLyrics = [];
let mediaPos = 0;
let mediaDuration = 0;
let mediaSeekPreviewSec = null;
let mediaSeekIgnoreServerUntil = 0;
let mediaIsSeeking = false;
let mediaSeekPointerId = null;
let lastSyncTime = Date.now();
let isMediaPlaying = false;
let lastMediaTitle = "";
let lastMediaArtist = "";
let lastMediaTrackToken = "";
let mediaTrackChangeGuardUntil = 0;

let currentDisplayedText = "";
let isLyricAnimating = false;
let lyricAnimToken = 0;
let lastCoverSrc = "";

const DEFAULT_COVER = '';

let tuyaDeviceStates = {};
let tuyaBusyMap = {};
let tuyaPendingMap = {};
window.tuyaDeviceStates = tuyaDeviceStates;
function getTuyaPendingMs() { return getFrontendNumber('tuya_pending_ms', 1800); }

const WS_URL =
    (location.protocol === 'https:' ? 'wss://' : 'ws://') +
    location.host +
    '/ws/status';

const WS_RECONNECT_MIN_MS = 1000;
const WS_RECONNECT_MAX_MS = 8000;

let ws = null;
let wsReconnectTimer = null;
let wsReconnectDelay = WS_RECONNECT_MIN_MS;
let wsConnected = false;
let lastWsMessageAt = 0;
let wsRequestCounter = 0;
const wsPendingRequests = new Map();
let lastStatusState = Object.create(null);

function nextWsRequestId() {
    wsRequestCounter += 1;
    return `req_${Date.now()}_${wsRequestCounter}`;
}

function wsSendRequest(message, timeoutMs = 10000) {
    return new Promise((resolve, reject) => {
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            reject(new Error('WebSocket is not connected.'));
            return;
        }

        const requestId = nextWsRequestId();
        const timer = setTimeout(() => {
            wsPendingRequests.delete(requestId);
        reject(new Error('WebSocket command timed out.'));
        }, timeoutMs);

        wsPendingRequests.set(requestId, { resolve, reject, timer });

        try {
            ws.send(JSON.stringify({ ...message, request_id: requestId }));
        } catch (err) {
            clearTimeout(timer);
            wsPendingRequests.delete(requestId);
            reject(err);
        }
    });
}

async function wsCommand(path, params = {}, timeoutMs = 10000) {
    const result = await wsSendRequest({ type: 'command', path, params }, timeoutMs);
    if (!result || result.ok !== true) {
        throw new Error((result && result.error) || `Command failed: ${path}`);
    }
    return result.payload;
}

function setTextIfChanged(el, value) {
    if (!el) return false;
    const next = String(value ?? '');
    if (el.textContent !== next) {
        el.textContent = next;
        return true;
    }
    return false;
}

function setStyleIfChanged(el, prop, value) {
    if (!el || !prop) return false;
    const next = String(value ?? '');
    if (el.style[prop] !== next) {
        el.style[prop] = next;
        return true;
    }
    return false;
}

function setAttrIfChanged(el, name, value) {
    if (!el || !name) return false;
    const next = String(value ?? '');
    if (el.getAttribute(name) !== next) {
        el.setAttribute(name, next);
        return true;
    }
    return false;
}

function markTuyaPending(key, expectedState) {
    tuyaPendingMap[key] = {
        until: Date.now() + getTuyaPendingMs(),
        expectedState: !!expectedState
    };
}

function getTuyaPending(key) {
    const item = tuyaPendingMap[key];
    if (!item) return null;
    if (Date.now() > item.until) {
        delete tuyaPendingMap[key];
        return null;
    }
    return item;
}

function clearTuyaPending(key) {
    delete tuyaPendingMap[key];
}

const volumeSlider = document.getElementById('volumeSlider');
const muteButtonEl = document.getElementById('muteButton');
const cpuTempEl = document.getElementById('cpuTemp');
const gpuTempEl = document.getElementById('gpuTemp');
const ramUsageEl = document.getElementById('ramUsage');
const cpuPowerEl = document.getElementById('cpuPower');
const gpuPowerEl = document.getElementById('gpuPower');
const ramExtraValueEl = document.getElementById('ramExtraValue');
const shiftValueEl = document.getElementById('shiftValue') || document.getElementById('fpsValue');
const fpsLowMainValueEl = document.getElementById('fpsLowMainValue');
const vramInfoValueEl = document.getElementById('vramInfoValue');
const shiftSubtitleEl = document.getElementById('shiftSubtitle') || document.getElementById('gpuUtilValue');
const shiftCardLabelEl = document.getElementById('shiftCardLabel') || document.getElementById('fpsCardLabel');
const lowCardLabelEl = document.getElementById('lowCardLabel');
const mediaTitleEl = document.getElementById('mediaTitle');
const mediaArtistEl = document.getElementById('mediaArtist');
const coverEl = document.getElementById('coverArt');
const nowPlayingEl = document.getElementById('nowPlaying');
const mediaProgressTrackEl = document.getElementById('mediaProgressTrack');
const mediaProgressFillEl = document.getElementById('mediaProgressFill');
const mediaProgressThumbEl = document.getElementById('mediaProgressThumb');
const mediaElapsedEl = document.getElementById('mediaElapsed');
const mediaRemainingEl = document.getElementById('mediaRemaining');
const mediaProgressHeadEl = document.querySelector('.media-progress-head');
const mediaProgressWrapEl = document.getElementById('mediaProgressWrap');
const lyricEl = document.getElementById('singleLyricLine');
const statusEl = document.getElementById('status');
const tuyaGridEl = document.getElementById('tuyaGrid');

function bindExistingTuyaButtons() {
    if (!tuyaGridEl) return;
    tuyaGridEl.querySelectorAll('[data-tuya-device]').forEach((button) => {
        const key = String(button.dataset.tuyaDevice || '').trim();
        if (!key) return;
        rememberTuyaButtonElement(key, button);
        button.type = 'button';
    });
}
const panelDownloadEl = document.getElementById('panelDownload');
const panelUploadEl = document.getElementById('panelUpload');
const panelMbVmosTempsEl = document.getElementById('panelMbVmosTemps');
const panelUptimeEl = document.getElementById('panelUptime');
const panelWeatherEl = document.getElementById('panelWeather');
const panelDiskCEl = document.getElementById('panelDiskC');
// Frequently accessed elements are cached to avoid repeated getElementById calls.
const cpuBarEl = document.getElementById('cpuUsageBar');
const gpuBarEl = document.getElementById('gpuUsageBar');
const ramBarEl = document.getElementById('ramUsageBar');
const cpuGlossEl = document.getElementById('cpuUsageGloss');
const gpuGlossEl = document.getElementById('gpuUsageGloss');
const ramGlossEl = document.getElementById('ramUsageGloss');
const cpuShadowEl = document.getElementById('cpuUsageShadow');
const gpuShadowEl = document.getElementById('gpuUsageShadow');
const ramShadowEl = document.getElementById('ramUsageShadow');
const cpuMaskEl = document.getElementById('cpuUsageMask');
const gpuMaskEl = document.getElementById('gpuUsageMask');
const ramMaskEl = document.getElementById('ramUsageMask');
const cpuBlobAEl = document.getElementById('cpuUsageBlobA');
const gpuBlobAEl = document.getElementById('gpuUsageBlobA');
const ramBlobAEl = document.getElementById('ramUsageBlobA');
const cpuBlobBEl = document.getElementById('cpuUsageBlobB');
const gpuBlobBEl = document.getElementById('gpuUsageBlobB');
const ramBlobBEl = document.getElementById('ramUsageBlobB');
const cpuSurfaceMaskEl = document.getElementById('cpuUsageSurfaceMask');
const gpuSurfaceMaskEl = document.getElementById('gpuUsageSurfaceMask');
const ramSurfaceMaskEl = document.getElementById('ramUsageSurfaceMask');
const shiftBarEl = document.getElementById('shiftUsageBar');
const shiftGlossEl = document.getElementById('shiftUsageGloss');
const shiftShadowEl = document.getElementById('shiftUsageShadow');
const shiftMaskEl = document.getElementById('shiftUsageMask');
const shiftBlobAEl = document.getElementById('shiftUsageBlobA');
const shiftBlobBEl = document.getElementById('shiftUsageBlobB');
const shiftSurfaceMaskEl = document.getElementById('shiftUsageSurfaceMask');
const powerBarEl = document.getElementById('powerUsageBar');
const powerGlossEl = document.getElementById('powerUsageGloss');
const powerShadowEl = document.getElementById('powerUsageShadow');
const powerMaskEl = document.getElementById('powerUsageMask');
const powerBlobAEl = document.getElementById('powerUsageBlobA');
const powerBlobBEl = document.getElementById('powerUsageBlobB');
const powerSurfaceMaskEl = document.getElementById('powerUsageSurfaceMask');
const confirmOverlayEl = document.getElementById('confirmOverlay');
const volumeSliderContainerEl = volumeSlider ? volumeSlider.closest('.slider-container') : null;
const volumeKnobEl = document.getElementById('volumeKnob');
const volumeKnobSurroundEl = document.getElementById('volumeKnobSurround');
const tickContainerEl = document.getElementById('tickContainer');

const HTML_ESCAPE_MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (ch) => HTML_ESCAPE_MAP[ch]);
}



function setStatusText(message, isError = false) {
    if (!statusEl) return;
    setTextIfChanged(statusEl, message);
    statusEl.classList.toggle('is-error', !!isError);
}

function updateMuteButtonState(isMuted) {
    if (!muteButtonEl) return;
    const muted = isMuted === true;
    muteButtonEl.classList.toggle('is-muted', muted);
    muteButtonEl.setAttribute('aria-pressed', muted ? 'true' : 'false');
}

async function toggleMuteButton(event) {
    if (event) event.preventDefault();

    const optimisticMuted = !(localMuteState === true);
    localMuteState = optimisticMuted;
    localMuteOverrideUntil = Date.now() + getMuteRemoteSyncDelayMs();
    updateMuteButtonState(optimisticMuted);

    try {
        const d = await wsCommand('/mute');

        if (d && d.ok) {
            if (d.volume_percent !== null && d.volume_percent !== undefined && volumeSlider && !isDraggingVolume) {
                volumeSlider.value = d.volume_percent;
                setVolumeText(d.volume_percent, true);
            }
            localMuteState = d.is_muted === true;
            localMuteOverrideUntil = Date.now() + getMuteRemoteSyncDelayMs();
            updateMuteButtonState(localMuteState);
        } else {
            throw new Error((d && d.error) || 'Mute command failed.');
        }
    } catch (err) {
        console.error(err);
        localMuteState = null;
        localMuteOverrideUntil = 0;
    }

    return false;
}

function renderTuyaButtons(devices) {
    if (!tuyaGridEl || !Array.isArray(devices)) return;

    devices.forEach((device) => {
        const key = String(device.key || '').trim();
        if (!key) return;

        let button = getTuyaButtonElement(key);
        if (button && button.isConnected) {
            if (!button.onclick) button.onclick = () => toggleTuyaDevice(key);
            tuyaGridEl.appendChild(button);
            return;
        }

        button = document.createElement('button');
        button.type = 'button';
        button.className = 'btn tuya-btn sketch-button is-loading is-off';
        button.dataset.tuyaDevice = key;
        button.onclick = () => toggleTuyaDevice(key);
        button.innerHTML = `
            <span class="tuya-label">
                <span class="tuya-name">${escapeHtml(device.name || key)}</span>
            </span>
        `;
        tuyaGridEl.appendChild(button);
        rememberTuyaButtonElement(key, button);
    });

    setupSketchButtons();
}

function applyTuyaButtonVisualState(button, isOn) {
    if (!button) return;
    const asset = isOn ? 'resimler/on.png' : 'resimler/off.png';
    button.style.background = `url('${asset}') center center / 100% 100% no-repeat`;
    button.style.backgroundColor = 'transparent';
}

function updateTuyaButtons(devices) {
    if (!Array.isArray(devices) || !tuyaGridEl) return;
    bindExistingTuyaButtons();

    const incomingKeys = new Set(
        devices
            .map((device) => String(device && device.key ? device.key : '').trim())
            .filter(Boolean)
    );

    Object.keys(tuyaButtonElements).forEach((key) => {
        const btn = getTuyaButtonElement(key);
        if (!btn || !btn.isConnected) {
            forgetTuyaButtonElement(key);
            return;
        }
        if (!key || incomingKeys.has(key)) return;
        btn.remove();
        forgetTuyaButtonElement(key);
        delete tuyaDeviceStates[key];
        delete tuyaBusyMap[key];
        delete tuyaPendingMap[key];
    });

    renderTuyaButtons(devices);

    devices.forEach((device) => {
        const key = String(device.key || '').trim();
        const btn = getTuyaButtonElement(key);
        if (!btn) return;

        const isOnline = device.online !== false;
        const serverIsOn = device.is_on === true;
        const busy = tuyaBusyMap[key] === true;
        const pending = getTuyaPending(key);

        if (!tuyaDeviceStates[key]) {
            tuyaDeviceStates[key] = {
                is_on: serverIsOn,
                online: isOnline,
                name: device.name || key
            };
        } else {
            tuyaDeviceStates[key] = {
                ...tuyaDeviceStates[key],
                online: isOnline,
                name: device.name || key
            };

            if (!busy && !pending) {
                tuyaDeviceStates[key].is_on = serverIsOn;
            }
        }

        const visualIsOn = pending ? !!pending.expectedState : !!tuyaDeviceStates[key].is_on;

        btn.classList.remove('is-loading', 'is-on', 'is-off');
        btn.classList.add(visualIsOn ? 'is-on' : 'is-off');
        btn.dataset.powerState = visualIsOn ? 'on' : 'off';
        btn.dataset.online = isOnline ? '1' : '0';
        btn.setAttribute('aria-pressed', visualIsOn ? 'true' : 'false');
        applyTuyaButtonVisualState(btn, visualIsOn);

        if (busy) btn.classList.add('is-loading');
    });
}

async function toggleTuyaDevice(deviceKey) {
    const key = String(deviceKey || '').trim();
    if (!key) {
        setStatusText('Invalid Tuya device key.', true);
        return;
    }
    if (tuyaBusyMap[key]) {
    setStatusText(`${key}: command already sent, waiting for response...`);
        return;
    }

    const prevState = tuyaDeviceStates[key] ? !!tuyaDeviceStates[key].is_on : false;
    const nextState = !prevState;

    tuyaBusyMap[key] = true;
    markTuyaPending(key, nextState);

    tuyaDeviceStates[key] = {
        ...(tuyaDeviceStates[key] || {}),
        is_on: nextState,
        online: true
    };

    updateTuyaButtons(Object.keys(tuyaDeviceStates).map((k) => ({ key: k, ...tuyaDeviceStates[k] })));
    setStatusText(`${key}: sending command...`);

    try {
        let d = null;
        try {
            d = await wsCommand(`/tuya/toggle/${encodeURIComponent(key)}`);
        } catch (wsErr) {
            console.warn('Tuya WebSocket command failed; trying HTTP fallback:', key, wsErr);
            const resp = await fetch(`/tuya/toggle/${encodeURIComponent(key)}`, { cache: 'no-store' });
            d = await resp.json().catch(() => ({ ok: false, error: `HTTP ${resp.status}` }));
            if (!resp.ok || !d || d.ok !== true) {
                throw new Error((d && d.error) || `HTTP ${resp.status}`);
            }
        }
        const diag = (d && d.diag) || {};

        if (d && d.ok && d.device) {
            tuyaDeviceStates[key] = {
                is_on: d.device.is_on === true,
                online: d.device.online !== false,
                name: d.device.name || key
            };
            clearTuyaPending(key);
            const parts = [`${tuyaDeviceStates[key].name || key}: ${d.device.is_on === true ? 'ON' : 'OFF'}`];
            if (diag.attempt !== undefined) parts.push(`attempt ${diag.attempt}`);
            if (diag.elapsed_ms !== undefined) parts.push(`${diag.elapsed_ms} ms`);
            if (diag.classification && diag.classification !== 'OK') parts.push(diag.classification);
            setStatusText(parts.join(' · '));
        } else {
            if (d && d.device) {
                tuyaDeviceStates[key] = {
                    ...(tuyaDeviceStates[key] || {}),
                    is_on: d.device.is_on === true,
                    online: d.device.online !== false,
                    name: d.device.name || key
                };
            } else {
                tuyaDeviceStates[key] = {
                    ...(tuyaDeviceStates[key] || {}),
                    is_on: prevState
                };
            }
            clearTuyaPending(key);
            const errText = (d && d.error) || 'Tuya command failed.';
            const extra = diag.classification ? ` · ${diag.classification}` : '';
            throw new Error(`${errText}${extra}`);
        }
    } catch (err) {
        console.error(err);
        tuyaDeviceStates[key] = {
            ...(tuyaDeviceStates[key] || {}),
            is_on: prevState
        };
        clearTuyaPending(key);
        setStatusText(`Tuya error (${key}): ${err.message || err}`, true);
    } finally {
        tuyaBusyMap[key] = false;
        updateTuyaButtons(Object.keys(tuyaDeviceStates).map((k) => ({ key: k, ...tuyaDeviceStates[k] })));

    }
}

if (tuyaGridEl && tuyaGridEl.dataset.tuyaDelegated !== '1') {
    tuyaGridEl.dataset.tuyaDelegated = '1';
    tuyaGridEl.addEventListener('click', (event) => {
        const btn = event.target.closest('[data-tuya-device]');
        if (!btn || !tuyaGridEl.contains(btn)) return;
        const key = String(btn.dataset.tuyaDevice || '').trim();
        if (!key) return;
        event.preventDefault();
        toggleTuyaDevice(key);
    });
}

if (volumeSlider) {
    const initialVolume = Math.max(0, Math.min(100, parseInt(volumeSlider.value, 10) || 0));
    setVolumeText(initialVolume, true);
}

if (lyricEl) {
    setLyricText(getIdleText());
    lyricEl.classList.remove('hide');
}

if (coverEl) {
    coverEl.style.display = 'none';
    coverEl.removeAttribute('src');
    lastCoverSrc = '';
    coverEl.onerror = null;
}

updateMuteButtonState(false);

function fmtTemp(v){ return (v === null || v === undefined) ? 'Yok' : Math.round(Number(v)) + '°C'; }
function fmtWatt(v){ return (v === null || v === undefined) ? 'Yok' : Number(v).toFixed(0); }
function fmtWattWithUnit(v){ const base = fmtWatt(v); return base === 'Yok' ? base : `${base} W`; }
// NVIDIA OVERLAY: round for integer display.
function fmtFps(v){ return (v === null || v === undefined || v === 0) ? '-' : Math.round(v).toString(); }
function fmtPercent(v){ return (v === null || v === undefined) ? '-' : Number(v).toFixed(0) + '%'; }

function finiteMetricNumber(v) {
    if (v === null || v === undefined || v === '') return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
}

function resolvePcPlugPowerWatts(d) {
    const plugPower = finiteMetricNumber(d.pc_plug_power_w);
    if (plugPower !== null && plugPower > 0) return plugPower;
    return null;
}

function isLikelyGamingLoad(d) {
    const gpuUtil = finiteMetricNumber(d && d.gpu_util);
    const gpuPower = finiteMetricNumber(d && d.gpu_power);
    return (gpuUtil !== null && gpuUtil >= 35) || (gpuPower !== null && gpuPower >= 70);
}

function fmtRamUsageGb(v){
    const n = Number(v);
    return Number.isFinite(n) ? ` ${n.toFixed(1)} GB` : '';
}

const WEATHER_CODE_LABELS_EN = {
    0: 'Clear',
    1: 'Mostly clear',
    2: 'Partly cloudy',
    3: 'Cloudy',
    45: 'Fog',
    48: 'Rime fog',
    51: 'Light drizzle',
    53: 'Drizzle',
    55: 'Heavy drizzle',
    56: 'Light freezing drizzle',
    57: 'Freezing drizzle',
    61: 'Light rain',
    63: 'Rain',
    65: 'Heavy rain',
    66: 'Light freezing rain',
    67: 'Freezing rain',
    71: 'Light snow',
    73: 'Snow',
    75: 'Heavy snow',
    77: 'Snow grains',
    80: 'Rain showers',
    81: 'Heavy rain showers',
    82: 'Violent rain showers',
    85: 'Snow showers',
    86: 'Heavy snow showers',
    95: 'Thunderstorm',
    96: 'Thunderstorm with hail',
    99: 'Severe thunderstorm with hail'
};

const WEATHER_CODE_LABELS_TR = {
    0: 'Açık',
    1: 'Çoğunlukla açık',
    2: 'Parçalı bulutlu',
    3: 'Bulutlu',
    45: 'Sisli',
    48: 'Kırağılı sis',
    51: 'Hafif çisenti',
    53: 'Çisenti',
    55: 'Yoğun çisenti',
    56: 'Hafif donan çisenti',
    57: 'Donan çisenti',
    61: 'Hafif yağmur',
    63: 'Yağmur',
    65: 'Şiddetli yağmur',
    66: 'Hafif donan yağmur',
    67: 'Donan yağmur',
    71: 'Hafif kar',
    73: 'Kar',
    75: 'Yoğun kar',
    77: 'Kar taneleri',
    80: 'Sağanak yağmur',
    81: 'Şiddetli sağanak',
    82: 'Çok şiddetli sağanak',
    85: 'Kar sağanağı',
    86: 'Şiddetli kar sağanağı',
    95: 'Gök gürültülü fırtına',
    96: 'Dolu ile fırtına',
    99: 'Şiddetli dolu ile fırtına'
};

function getWeatherCodeLabel(code) {
    const n = Number(code);
    if (!Number.isFinite(n)) return '';
    const labels = getPanelLanguage() === 'tr' ? WEATHER_CODE_LABELS_TR : WEATHER_CODE_LABELS_EN;
    return labels[n] || '';
}

function normalizeWeatherSummary(value) {
    const raw = String(value || '').trim();
    if (!raw) return '';
    const locale = getPanelLanguage() === 'tr' ? 'tr-TR' : 'en-US';
    return raw.charAt(0).toLocaleLowerCase(locale) + raw.slice(1);
}

function setWeatherText(value) {
    if (panelWeatherEl) setTextIfChanged(panelWeatherEl, value);
}

function applyWeatherFromStatus(d, changedKeys = null) {
    if (!d || typeof d !== 'object') return;
    if (!hasAnyChanged(changedKeys, ['weather_ok', 'weather_location', 'weather_summary', 'weather_code', 'weather_min_c', 'weather_max_c', 'weather_error'])) return;

    const codeSummary = getWeatherCodeLabel(d.weather_code);
    const summary = normalizeWeatherSummary(codeSummary || d.weather_summary);
    const location = String(d.weather_location || 'Kayseri').trim() || 'Kayseri';
    const weatherError = String(d.weather_error || '').trim();
    const shortWeatherError = weatherError ? (getPanelLanguage() === 'tr' ? 'Meteo hatası' : 'Meteo error') : '';
    const unavailableText = getPanelLanguage() === 'tr' ? 'kullanılamıyor' : 'unavailable';
    const hasWeather = d.weather_ok === true && summary !== '';

    window.__panelWeatherLocation = location;
    window.__panelWeatherText = hasWeather ? summary : (shortWeatherError ? unavailableText : '');
    window.__panelWeatherRainText = hasWeather ? (window.__panelWeatherRainText || '') : (shortWeatherError ? `${shortWeatherError}.` : '');

    if (typeof renderPanelDateWeatherSummary === 'function') {
        renderPanelDateWeatherSummary();
    }

    if (panelWeatherEl) {
        setWeatherText(hasWeather ? summary : '');
    }
}
function fmtSpeed(v, dir = 'down'){
    const prefix = dir === 'up' ? '' : '';

    if (v === null || v === undefined || !Number.isFinite(Number(v))) {
        return prefix + '--';
    }

    const n = Number(v);

    if (n < 0.1) {
        return prefix + '0 Mbps';
    }

    return prefix + Math.round(n) + ' Mbps';
}
function truncateText(text, maxLen){
    const t = (text || '').trim();
    return t.length > maxLen ? t.slice(0, maxLen) + '...' : t;
}




function fmtClock(sec) {
    const n = Number(sec);
    if (!Number.isFinite(n) || n < 0) return '0:00';
    const total = Math.max(0, Math.floor(n));
    const h = Math.floor(total / 3600);
    const m = Math.floor(total / 60);
    const s = total % 60;
    if (h > 0) {
        const mm = Math.floor((total % 3600) / 60);
        return `${h}:${String(mm).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }
    return `${m}:${String(s).padStart(2, '0')}`;
}

function normalizeMediaTimeline(positionSec, durationSec) {
    let pos = Math.max(0, Number(positionSec) || 0);
    let dur = Math.max(0, Number(durationSec) || 0);

    // Bazi kaynaklar saniye yerine milisaniye (veya nadiren 100ns tick) yollayabiliyor.
    const looksLikeMs = dur >= 36000 || (dur > 0 && pos > dur * 8 && (pos / 1000) <= (dur * 1.2));
    const looksLikeTicks = dur >= 360000000;

    if (looksLikeTicks) {
        pos /= 10000000;
        dur /= 10000000;
    } else if (looksLikeMs) {
        pos /= 1000;
        dur /= 1000;
    }

    if (dur > 0 && pos > dur) pos = dur;
    return { position: pos, duration: dur };
}

function isNoMediaTitle(title) {
    const normalizedTitle = String(title || '').trim().toLowerCase();
    const normalizedIdleText = getNormalizedIdleText();
    const normalizedNoMediaTitle = getNormalizedNoMediaPlaceholderTitle();
    return (
        !normalizedTitle ||
        (!!normalizedIdleText && normalizedTitle === normalizedIdleText) ||
        (!!normalizedNoMediaTitle && normalizedTitle === normalizedNoMediaTitle) ||
        normalizedTitle === 'media info unavailable' ||
        normalizedTitle === 'info unavailable' ||
        normalizedTitle === 'spotify ekrani' ||
        normalizedTitle.startsWith('spotify ekrani') ||
        normalizedTitle.includes('spotify ekrani')
    );
}

function buildMediaTrackToken(data, normalizedTimeline) {
    const explicit = String((data && data.media_track_token) || '').trim();
    if (explicit) return explicit;
    const title = String((data && data.media_title) || '').trim();
    const artist = String((data && data.media_artist) || '').trim();
    const source = String((data && data.media_source_app) || '').trim().toLowerCase();
    const duration = Math.round(Math.max(0, Number(normalizedTimeline && normalizedTimeline.duration) || 0) * 10) / 10;
    return `${source}|${title}|${artist}|${duration}`;
}

function getCurrentMediaPositionSec() {
    if (mediaSeekPreviewSec !== null) {
        return Math.max(0, Number(mediaSeekPreviewSec) || 0);
    }

    let currentPos = Number(mediaPos) || 0;
    if (isMediaPlaying) {
        currentPos += (Date.now() - lastSyncTime) / 1000;
    }

    // If elapsed time exceeds total duration, clamp it to the total so it does not jump ahead.
    if (mediaDuration > 0 && currentPos > mediaDuration) {
        return mediaDuration;
    }
    
    return Math.max(0, currentPos);
}

function getSeekRatioFromClientX(clientX) {
    if (!mediaProgressTrackEl) return 0;
    const rect = mediaProgressTrackEl.getBoundingClientRect();
    if (!rect.width) return 0;
    return Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
}

function setMediaSeekPreviewFromClientX(clientX) {
    if (mediaDuration <= 0.5) return;
    const ratio = getSeekRatioFromClientX(clientX);
    mediaSeekPreviewSec = mediaDuration * ratio;
    updateMediaProgressUi();
}

async function commitMediaSeek(positionSec) {
    const target = Math.max(0, Number(positionSec) || 0);
    mediaSeekPreviewSec = null;
    mediaPos = target;
    lastSyncTime = Date.now();
    mediaSeekIgnoreServerUntil = Date.now() + 2500;
    updateMediaProgressUi();

    try {
        const d = await wsCommand('/media/seek', { position: target });
        if (d && d.ok) {
            if (d.position !== undefined && d.position !== null) {
                mediaPos = Math.max(0, Number(d.position) || target);
                lastSyncTime = Date.now();
            }
            if (d.duration !== undefined && d.duration !== null) {
                mediaDuration = Math.max(0, Number(d.duration) || mediaDuration);
            }
        }
    } catch (err) {
        console.error(err);
    }
}

function bindMediaSeekBar() {
    if (!mediaProgressTrackEl || mediaProgressTrackEl.dataset.seekBound === '1') return;
    mediaProgressTrackEl.dataset.seekBound = '1';

    const stopSeeking = async (commit) => {
        if (!mediaIsSeeking) return;
        const preview = mediaSeekPreviewSec;
        mediaIsSeeking = false;
        if (mediaSeekPointerId !== null) {
            try { mediaProgressTrackEl.releasePointerCapture(mediaSeekPointerId); } catch (e) {}
        }
        mediaSeekPointerId = null;
        if (commit && preview !== null && mediaDuration > 0.5) {
            await commitMediaSeek(preview);
        } else {
            mediaSeekPreviewSec = null;
            updateMediaProgressUi();
        }
    };

    mediaProgressTrackEl.addEventListener('pointerdown', (e) => {
        if (mediaDuration <= 0.5) return;
        mediaIsSeeking = true;
        mediaSeekPointerId = e.pointerId;
        try { mediaProgressTrackEl.setPointerCapture(e.pointerId); } catch (err) {}
        setMediaSeekPreviewFromClientX(e.clientX);
        e.preventDefault();
    });

    mediaProgressTrackEl.addEventListener('pointermove', (e) => {
        if (!mediaIsSeeking) return;
        setMediaSeekPreviewFromClientX(e.clientX);
    });

    mediaProgressTrackEl.addEventListener('pointerup', () => { stopSeeking(true); });
    mediaProgressTrackEl.addEventListener('pointercancel', () => { stopSeeking(false); });
    mediaProgressTrackEl.addEventListener('lostpointercapture', () => {
        if (mediaIsSeeking) stopSeeking(true);
    });
}


function forceMediaProgressVisible(show) {
    if (!mediaProgressWrapEl) return;
    mediaProgressWrapEl.classList.toggle('is-hidden', !show);
    // classList yeterli olmadiği durumlarda CSS'i direkt ez.
    mediaProgressWrapEl.style.display = show ? 'block' : 'none';
    mediaProgressWrapEl.style.visibility = show ? 'visible' : 'hidden';
    mediaProgressWrapEl.style.opacity = show ? '1' : '0';
}

function updateMediaVisibility(title, durationSec, playingState = null) {
    const noMedia = isNoMediaTitle(title);
    const hideWhenIdle = getFrontendBool('hide_seekbar_when_idle', true);
    const showIdleProgress = getFrontendBool('show_media_progress_when_idle', false);
    const hasRealTitle = !!String(title || '').trim() && !noMedia;
    // Seekbar şarkı varsa her zaman görünsün; duration yoksa boş bar olarak kalır.
    const showProgress = hideWhenIdle ? (hasRealTitle || (showIdleProgress && noMedia)) : true;

    forceMediaProgressVisible(showProgress);

    if (mediaProgressHeadEl) {
        mediaProgressHeadEl.classList.remove('is-hidden');
        mediaProgressHeadEl.style.display = '';
        mediaProgressHeadEl.style.visibility = 'visible';
        mediaProgressHeadEl.style.opacity = '1';
    }

    if (nowPlayingEl) nowPlayingEl.classList.toggle('no-media', noMedia);

    if (noMedia) {
        if (mediaTitleEl) setTextIfChanged(mediaTitleEl, getNoMediaPlaceholderTitle());
        if (mediaArtistEl) setTextIfChanged(mediaArtistEl, '');
        if (mediaElapsedEl) setTextIfChanged(mediaElapsedEl, '0:00');
        if (mediaRemainingEl) setTextIfChanged(mediaRemainingEl, '--:--');
        syncNoMediaPlaceholderVisuals();
    } else {
        clearPlainPlaceholderVisual(mediaTitleEl);
    }
}

function updateMediaProgressUi() {
    if (!mediaProgressFillEl || !mediaElapsedEl || !mediaRemainingEl) return;

    const total = Math.max(0, Number(mediaDuration) || 0);
    updateMediaVisibility(lastMediaTitle, total, isMediaPlaying === true);

    const safePos = total > 0
        ? Math.min(getCurrentMediaPositionSec(), total)
        : Math.max(0, getCurrentMediaPositionSec());

    setTextIfChanged(mediaElapsedEl, fmtClock(safePos));

    if (total > 0.5) {
        const remain = Math.max(0, total - safePos);
        const ratio = Math.max(0, Math.min(1, safePos / total));
        const percent = ratio * 100;
        setTextIfChanged(mediaRemainingEl, remain < 0.5 ? '0:00' : `-${fmtClock(remain)}`);
        setStyleIfChanged(mediaProgressFillEl, 'width', `${percent}%`);
        if (mediaProgressThumbEl) setStyleIfChanged(mediaProgressThumbEl, 'left', `${percent}%`);
        if (mediaProgressTrackEl) setAttrIfChanged(mediaProgressTrackEl, 'aria-valuenow', String(Math.round(percent)));
    } else {
        // Duration gelmiyorsa seek yapılamaz ama bar yine görünür kalsın.
        setTextIfChanged(mediaRemainingEl, '--:--');
        setStyleIfChanged(mediaProgressFillEl, 'width', '0%');
        if (mediaProgressThumbEl) setStyleIfChanged(mediaProgressThumbEl, 'left', '0%');
        if (mediaProgressTrackEl) {
            setAttrIfChanged(mediaProgressTrackEl, 'aria-valuenow', '0');
            mediaProgressTrackEl.style.pointerEvents = 'none';
        }
    }
    if (total > 0.5 && mediaProgressTrackEl) {
        mediaProgressTrackEl.style.pointerEvents = '';
    }
}

let mediaProgressTimer = null;

function clearMediaProgressTimer() {
    if (mediaProgressTimer) {
        clearTimeout(mediaProgressTimer);
        mediaProgressTimer = null;
    }
}

function shouldRunMediaProgressTimer() {
    if (document.visibilityState === 'hidden') return false;
    if (mediaIsSeeking) return true;
    return Boolean(isMediaPlaying || (lastMediaTitle && !isNoMediaTitle(lastMediaTitle)));
}

function getMediaProgressIntervalMs(playing) {
    const seekbarRaw = getFrontendNumber('seekbar_update_interval_ms', 250);
    const seekbarBase = Math.max(30, seekbarRaw);
    const base = playing
        ? (seekbarRaw !== 250 ? seekbarBase : Math.max(30, getFrontendNumber('media_progress_interval_playing_ms', 150)))
        : Math.max(120, getFrontendNumber('media_progress_interval_paused_ms', Math.max(120, seekbarBase)));
    if (isLowPerformanceMode()) return playing ? Math.max(base, 180) : Math.max(base, 900);
    const level = getAnimationLevel();
    if (level === 'off') return playing ? Math.max(base, 260) : Math.max(base, 1000);
    if (level === 'low') return playing ? Math.max(base, 120) : Math.max(base, 700);
    if (level === 'high') return playing ? Math.min(base, 40) : Math.min(base, 350);
    return base;
}

function _tickMediaProgress() {
    updateMediaProgressUi();
    if (!shouldRunMediaProgressTimer()) {
        mediaProgressTimer = null;
        return;
    }
    const next = getMediaProgressIntervalMs(true);
    mediaProgressTimer = setTimeout(_tickMediaProgress, next);
}

function startMediaProgressLoop() {
    clearMediaProgressTimer();
    updateMediaProgressUi();
    if (shouldRunMediaProgressTimer()) {
        mediaProgressTimer = setTimeout(_tickMediaProgress, getMediaProgressIntervalMs(true));
    }
}

bindMediaSeekBar();
startMediaProgressLoop();

function buildTempOdometerMarkup(value) {
    const text = String(value || '-');
    const parts = [];

    for (const ch of text) {
        if (/\d/.test(ch)) {
            const digit = Number(ch);
            const translate = -(digit * 1.0);
            const nums = Array.from({length: 10}, (_, i) => `<span class="temp-odo-num">${i}</span>`).join('');
            parts.push(
                `<span class="temp-odo-digit" data-digit="${digit}">
                    <span class="temp-odo-track" style="transform:translateY(${translate}em)">
                        ${nums}
                    </span>
                </span>`
            );
        } else {
            parts.push(`<span class="temp-odo-char">${ch}</span>`);
        }
    }

    return `<span class="temp-odo">${parts.join('')}</span>`;
}

function setOdoText(el, value) {
    if (!el) return;

    const nextText = String(value || '-');
    const prevText = el.dataset.tempValue || '';

    if (!el.dataset.tempInit || !el.querySelector('.temp-odo')) {
        el.innerHTML = buildTempOdometerMarkup(nextText);
        el.dataset.tempInit = '1';
        el.dataset.tempValue = nextText;
        return;
    }

    if (prevText === nextText) return;

    const prevChars = prevText.split('');
    const nextChars = nextText.split('');

    const sameLength = prevChars.length === nextChars.length;
    const sameMask = sameLength && prevChars.map(c => /\d/.test(c)).join('') === nextChars.map(c => /\d/.test(c)).join('');

    if (!sameMask) {
        el.innerHTML = buildTempOdometerMarkup(nextText);
        el.dataset.tempValue = nextText;
        return;
    }

    const digitNodes = Array.from(el.querySelectorAll('.temp-odo-digit'));
    let digitIndex = 0;

    for (let i = 0; i < nextChars.length; i++) {
        const nextCh = nextChars[i];
        const prevCh = prevChars[i];

        if (!/\d/.test(nextCh)) continue;

        const node = digitNodes[digitIndex++];
        if (!node) continue;

        const track = node.querySelector('.temp-odo-track');
        if (!track) continue;

        const nextDigit = Number(nextCh);
        const prevDigit = Number(prevCh);

        if (nextDigit === prevDigit) {
            node.dataset.digit = String(nextDigit);
            continue;
        }

        // Slide downward while increasing, upward while decreasing.
        const translate = -(nextDigit * 1.0);
        track.style.transform = `translateY(${translate}em)`;
        node.dataset.digit = String(nextDigit);
    }

    el.dataset.tempValue = nextText;
}


function applyTooltipPosition(value) {
    return;
}


function getVolumeAspectCompensation() {
    const host = volumeSliderContainerEl || volumeKnobSurroundEl;
    if (!host) return { scaleX: 1, scaleY: 1 };

    const rect = host.getBoundingClientRect();
    if (!rect.width || !rect.height) return { scaleX: 1, scaleY: 1 };

    const ratio = rect.width / rect.height;
    if (Math.abs(1 - ratio) < 0.01) return { scaleX: 1, scaleY: 1 };

    if (ratio < 1) {
        return { scaleX: rect.height / rect.width, scaleY: 1 };
    }
    return { scaleX: 1, scaleY: rect.width / rect.height };
}

function applyVolumeAspectCompensation() {
    const wrap = volumeSlider ? volumeSlider.closest('.volume-wrap.new-vol-wrap') : null;
    const { scaleX, scaleY } = getVolumeAspectCompensation();
    if (wrap) {
        wrap.style.setProperty('--vol-scale-x', String(scaleX));
        wrap.style.setProperty('--vol-scale-y', String(scaleY));
    }
    return { scaleX, scaleY };
}

function createVolumeTicks(numTicks, highlightNumTicks) {
    if (!tickContainerEl) return;
    while (tickContainerEl.firstChild) {
        tickContainerEl.removeChild(tickContainerEl.firstChild);
    }

    const totalTicks = Math.max(2, Number(numTicks) || 49);
    const activeTicks = Math.max(0, Math.min(totalTicks, Number(highlightNumTicks) || 0));
    const startAngle = -135;
    const endAngle = 135;
    const step = (endAngle - startAngle) / (totalTicks - 1);

    for (let i = 0; i < totalTicks; i += 1) {
        const tick = document.createElement('div');
        tick.className = (i < activeTicks) ? 'tick activetick' : 'tick';
        tick.style.transform = `rotate(${startAngle + (i * step)}deg)`;
        tickContainerEl.appendChild(tick);
    }
}

function applyVolumeVisual(value) {
    if (!volumeSlider) return;
    const v = Math.max(0, Math.min(100, Number(value) || 0));
    volumeVisualCurrent = v;

    const totalTicks = 49;
    const startAngle = -135;
    const endAngle = 135;
    const angle = startAngle + ((v / 100) * (endAngle - startAngle));
    const tickHighlightPosition = Math.round((v / 100) * (totalTicks - 1)) + 1;

    const { scaleX, scaleY } = applyVolumeAspectCompensation();

    if (volumeKnobEl) {
        volumeKnobEl.style.transform = `translate3d(-50%, -50%, 0) rotate(${angle}deg) scaleX(${scaleX}) scaleY(${scaleY})`;
        volumeKnobEl.setAttribute('aria-valuenow', String(v));
    }

    createVolumeTicks(totalTicks, tickHighlightPosition);
}

function setVolumeText(value, immediate = false) {
    const v = Math.max(0, Math.min(100, parseInt(value, 10) || 0));
    const tooltip = document.getElementById('volumeTooltip');
    if (tooltip) setTextIfChanged(tooltip, `${v}`);

    const knobLabel = document.getElementById('volumeKnobLabel');
    if (knobLabel) {
        const ui = ensureVolumeKnobLabelUi(knobLabel);
        const changed = setTextIfChanged(ui.current, String(v));
        const prev = Number.isFinite(lastRenderedVolumeValue) ? Number(lastRenderedVolumeValue) : v;
        const direction = v > prev ? 'up' : (v < prev ? 'down' : '');
        if (!immediate && changed) {
            animateVolumeKnobLabel(ui, String(prev), String(v), direction);
        }
    }
    lastRenderedVolumeValue = v;

    applyTooltipPosition(v);
    applyVolumeVisual(v);
}

function ensureVolumeKnobLabelUi(el) {
    if (!el) return null;
    if (el._volumeLabelUi) return el._volumeLabelUi;

    const initial = String(el.textContent || '0');
    el.textContent = '';

    const stack = document.createElement('span');
    stack.className = 'knob-vol-stack';

    const current = document.createElement('span');
    current.className = 'knob-vol-current';
    current.textContent = initial;

    const ghost = document.createElement('span');
    ghost.className = 'knob-vol-ghost';
    ghost.textContent = '';
    ghost.style.opacity = '0';

    stack.appendChild(ghost);
    stack.appendChild(current);
    el.appendChild(stack);

    el._volumeLabelUi = { root: el, stack, current, ghost };
    return el._volumeLabelUi;
}

function animateVolumeKnobLabel(ui, fromText, toText, direction = '') {
    if (!ui || !ui.current || typeof ui.current.animate !== 'function') return;

    try {
        if (ui.current._volumeAnim) {
            try { ui.current._volumeAnim.cancel(); } catch (_) {}
            ui.current._volumeAnim = null;
        }
        if (ui.ghost._volumeAnim) {
            try { ui.ghost._volumeAnim.cancel(); } catch (_) {}
            ui.ghost._volumeAnim = null;
        }
    } catch (_) {}

    ui.current.textContent = toText;
    ui.ghost.textContent = fromText;
    ui.ghost.style.opacity = '1';

    const enterY = direction === 'up' ? '7%' : (direction === 'down' ? '-7%' : '4%');
    const exitY = direction === 'up' ? '-7%' : (direction === 'down' ? '7%' : '-4%');

    const currentAnim = ui.current.animate([
        {
            transform: `translate3d(0, ${enterY}, 0)`,
            opacity: 0.18
        },
        {
            transform: 'translate3d(0, 0, 0)',
            opacity: 1
        }
    ], {
        duration: 240,
        easing: 'cubic-bezier(.22,.61,.36,1)',
        fill: 'none'
    });

    const ghostAnim = ui.ghost.animate([
        {
            transform: 'translate3d(0, 0, 0)',
            opacity: 0.88
        },
        {
            transform: `translate3d(0, ${exitY}, 0)`,
            opacity: 0
        }
    ], {
        duration: 220,
        easing: 'cubic-bezier(.22,.61,.36,1)',
        fill: 'none'
    });

    const cleanup = () => {
        ui.current.style.transform = '';
        ui.current.style.opacity = '';
        ui.ghost.style.transform = '';
        ui.ghost.style.opacity = '0';
    };
    currentAnim.oncancel = cleanup;
    currentAnim.onfinish = cleanup;
    ghostAnim.oncancel = cleanup;
    ghostAnim.onfinish = cleanup;
    ui.current._volumeAnim = currentAnim;
    ui.ghost._volumeAnim = ghostAnim;
}
function knobValueFromPointer(clientX, clientY) {
    if (!volumeKnobSurroundEl) return 0;
    const rect = volumeKnobSurroundEl.getBoundingClientRect();
    const cx = rect.left + (rect.width / 2);
    const cy = rect.top + (rect.height / 2);
    const dx = clientX - cx;
    const dy = clientY - cy;

    let deg = Math.atan2(dy, dx) * 180 / Math.PI;
    deg += 90;
    if (deg > 180) deg -= 360;

    const clamped = Math.max(-135, Math.min(135, deg));
    return Math.round(((clamped + 135) / 270) * 100);
}

function updateKnobFromPointer(clientX, clientY, shouldSend = true) {
    if (!volumeSlider) return;
    const nextValue = knobValueFromPointer(clientX, clientY);
    volumeSlider.value = String(nextValue);
    setVolumeText(nextValue, false);
    if (shouldSend) scheduleVolumeSet(nextValue);
}

let knobDragPointerId = null;

function scheduleVolumeSet(value) {
    const v = Math.max(0, Math.min(100, parseInt(value, 10) || 0));
    lastLocalVolumeChangeAt = Date.now();
    setVolumeText(v, false);

    if (volumeSendTimer) clearTimeout(volumeSendTimer);
    volumeSendTimer = setTimeout(() => sendVolume(v), getVolumeRemoteSyncDelayMs());
}

async function sendVolume(value) {
    try {
        const d = await wsCommand('/setvolume', { value });

        const resolvedVolume =
            (d && d.volume_percent !== null && d.volume_percent !== undefined)
                ? d.volume_percent
                : value;

        if (volumeSlider && !isDraggingVolume) {
            volumeSlider.value = resolvedVolume;
        }

        if (!isDraggingVolume) {
            setVolumeText(resolvedVolume, false);
        }
    } catch (e) {
        if (volumeSlider && !isDraggingVolume) {
            volumeSlider.value = value;
        }
        if (!isDraggingVolume) {
            setVolumeText(value, false);
        }
    }
    volumeSendTimer = null;
}

if (volumeSlider) {
    volumeSlider.addEventListener('pointerdown', () => { isDraggingVolume = true; });
    volumeSlider.addEventListener('input', (e) => { scheduleVolumeSet(e.target.value); });
    volumeSlider.addEventListener('change', (e) => {
        isDraggingVolume = false;
        scheduleVolumeSet(e.target.value);
    });
}

if (volumeKnobEl && volumeSlider) {
    volumeKnobEl.addEventListener('pointerdown', (e) => {
        isDraggingVolume = true;
        knobDragPointerId = e.pointerId;
        try {
            volumeKnobEl.setPointerCapture(e.pointerId);
        } catch (err) {}
        updateKnobFromPointer(e.clientX, e.clientY, true);
        e.preventDefault();
    });

    volumeKnobEl.addEventListener('pointermove', (e) => {
        if (!isDraggingVolume) return;
        if (knobDragPointerId !== null && e.pointerId !== knobDragPointerId) return;
        updateKnobFromPointer(e.clientX, e.clientY, true);
    });

    volumeKnobEl.addEventListener('pointerup', (e) => {
        if (knobDragPointerId !== null && e.pointerId !== knobDragPointerId) return;
        isDraggingVolume = false;
        knobDragPointerId = null;
        try {
            volumeKnobEl.releasePointerCapture(e.pointerId);
        } catch (err) {}
        scheduleVolumeSet(volumeSlider.value);
    });

    volumeKnobEl.addEventListener('pointercancel', (e) => {
        if (knobDragPointerId !== null && e.pointerId !== knobDragPointerId) return;
        isDraggingVolume = false;
        knobDragPointerId = null;
        try {
            volumeKnobEl.releasePointerCapture(e.pointerId);
        } catch (err) {}
        scheduleVolumeSet(volumeSlider.value);
    });

    volumeKnobEl.addEventListener('keydown', (e) => {
        const currentValue = Math.max(0, Math.min(100, parseInt(volumeSlider.value, 10) || 0));
        let nextValue = currentValue;
        if (e.key === 'ArrowRight' || e.key === 'ArrowUp') nextValue = Math.min(100, currentValue + 2);
        if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') nextValue = Math.max(0, currentValue - 2);
        if (e.key === 'Home') nextValue = 0;
        if (e.key === 'End') nextValue = 100;
        if (nextValue !== currentValue) {
            volumeSlider.value = String(nextValue);
            setVolumeText(nextValue, false);
            scheduleVolumeSet(nextValue);
            e.preventDefault();
        }
    });
}

window.addEventListener('pointerup', () => {
    if (isDraggingVolume && volumeSlider) {
        isDraggingVolume = false;
        scheduleVolumeSet(volumeSlider.value);
    }
    const active = document.activeElement;
    if (active && typeof active.blur === 'function') {
        active.blur();
    }
});

window.addEventListener('pointercancel', () => {
    if (isDraggingVolume && volumeSlider) {
        isDraggingVolume = false;
        scheduleVolumeSet(volumeSlider.value);
    }
});

function clampUsage(v){
    v = Number(v);
    if (!Number.isFinite(v)) return 0;
    return Math.max(0, Math.min(100, v));
}


function getLiquidLevelY(fillPercent) {
    const rawFill = clampUsage(fillPercent) / 100;
    const bottomY = 174;
    const topTravel = 156;
    return bottomY - (rawFill * topTravel);
}



function buildLiquidWavePath(fillPercent, phase = 0, waveBias = 0) {
    const levelY = getLiquidLevelY(fillPercent);
    const bottomY = 174;
    const left = levelY + Math.sin(phase + waveBias) * 5.8;
    const c1 = levelY + Math.sin(phase + 0.9 + waveBias) * 2.0;
    const mid = levelY - Math.cos(phase + 1.4 + waveBias) * 7.0;
    const c2 = levelY - Math.sin(phase + 2.0 + waveBias) * 1.8;
    const right = levelY + Math.sin(phase + 2.8 + waveBias) * 5.6;
    return `M 0 ${bottomY} L 0 ${left.toFixed(2)} C 42 ${c1.toFixed(2)}, 78 ${mid.toFixed(2)}, 102 ${mid.toFixed(2)} C 134 ${mid.toFixed(2)}, 164 ${c2.toFixed(2)}, 204 ${right.toFixed(2)} L 204 ${bottomY} Z`;
}

function buildLiquidSurfaceMaskPath(fillPercent, phase = 0, waveBias = 0) {
    const levelY = getLiquidLevelY(fillPercent);
    const band = 26;
    const left = levelY + Math.sin(phase + waveBias) * 6.2;
    const c1 = levelY + Math.sin(phase + 0.9 + waveBias) * 2.2;
    const mid = levelY - Math.cos(phase + 1.4 + waveBias) * 7.6;
    const c2 = levelY - Math.sin(phase + 2.0 + waveBias) * 2.0;
    const right = levelY + Math.sin(phase + 2.8 + waveBias) * 6.0;

    const leftB = left + band;
    const c1B = c1 + band + 1.4;
    const midB = mid + band + 0.8;
    const c2B = c2 + band - 0.8;
    const rightB = right + band - 1.2;

    return `M 0 ${left.toFixed(2)} C 42 ${c1.toFixed(2)}, 78 ${mid.toFixed(2)}, 102 ${mid.toFixed(2)} C 134 ${mid.toFixed(2)}, 164 ${c2.toFixed(2)}, 204 ${right.toFixed(2)} L 204 ${rightB.toFixed(2)} C 164 ${c2B.toFixed(2)}, 134 ${midB.toFixed(2)}, 102 ${midB.toFixed(2)} C 78 ${midB.toFixed(2)}, 42 ${c1B.toFixed(2)}, 0 ${leftB.toFixed(2)} Z`;
}

function buildLiquidGlossPath(fillPercent, phase = 0, waveBias = 0) {
    return buildLiquidSurfaceMaskPath(fillPercent, phase, waveBias);
}

function buildLiquidShadowPath(fillPercent, phase = 0, waveBias = 0) {
    const levelY = getLiquidLevelY(fillPercent);
    const bottomY = 174;
    const shadowLevel = levelY + 5;
    const left = shadowLevel + Math.sin((phase * 0.9) + waveBias) * 3.2;
    const mid = shadowLevel - Math.cos((phase * 0.9) + 1.3 + waveBias) * 3.8;
    const right = shadowLevel + Math.sin((phase * 0.9) + 2.6 + waveBias) * 3.0;
    return `M 0 ${bottomY} L 0 ${left.toFixed(2)} C 42 ${(left + 7).toFixed(2)}, 78 ${mid.toFixed(2)}, 102 ${mid.toFixed(2)} C 134 ${mid.toFixed(2)}, 166 ${(right + 7).toFixed(2)}, 204 ${right.toFixed(2)} L 204 ${bottomY} Z`;
}


function resetLiquidBlob(blobEl) {
    if (!blobEl) return;
    try {
        blobEl.setAttribute('rx', '0');
        blobEl.setAttribute('ry', '0');
        blobEl.setAttribute('cx', '102');
        blobEl.setAttribute('cy', '87');
        blobEl.removeAttribute('transform');
        blobEl.style.opacity = '0';
    } catch (_) {}
}

function updateLiquidBlob(blobEl, fillPercent, phase, waveBias, variant = 0) {
    if (!blobEl) return;
    blobEl.setAttribute('rx', '0');
    blobEl.setAttribute('ry', '0');
    blobEl.setAttribute('cx', '102');
    blobEl.setAttribute('cy', '87');
    blobEl.removeAttribute('transform');
}

function paintLiquidBarNow(barEl, fillPercent, glossEl = null, shadowEl = null, maskEl = null, blobAEl = null, blobBEl = null, surfaceMaskEl = null, bias = 0) {
    if (!barEl) return;
    const safeFill = clampUsage(fillPercent);
    const mode = getLiquidAnimationMode();
    const phase = 0;
    const fillPath = buildLiquidWavePath(safeFill, phase, bias);
    barEl.setAttribute('d', fillPath);
    if (maskEl) maskEl.setAttribute('d', fillPath);

    if (mode === 'full') {
        if (glossEl) glossEl.setAttribute('d', buildLiquidGlossPath(safeFill, phase, bias));
        if (shadowEl) shadowEl.setAttribute('d', buildLiquidShadowPath(safeFill, phase, bias));
        if (surfaceMaskEl) surfaceMaskEl.setAttribute('d', buildLiquidSurfaceMaskPath(safeFill, phase, bias));
        updateLiquidBlob(blobAEl, safeFill, phase, bias, 0);
        updateLiquidBlob(blobBEl, safeFill, phase + 0.35, bias + 0.4, 1);
    } else {
        if (glossEl) glossEl.setAttribute('d', fillPath);
        if (shadowEl) shadowEl.setAttribute('d', fillPath);
        if (surfaceMaskEl) surfaceMaskEl.setAttribute('d', fillPath);
        resetLiquidBlob(blobAEl);
        resetLiquidBlob(blobBEl);
    }
}

function applyHeatBar(barEl, value, glossEl = null, shadowEl = null, maskEl = null, blobAEl = null, blobBEl = null, surfaceMaskEl = null, bias = 0) {
    if (!barEl) return;
    const v = clampUsage(value);
    const previousCurrent = Number.isFinite(barEl._currentFill) ? barEl._currentFill : null;
    const previousTarget = Number.isFinite(barEl._targetFill) ? barEl._targetFill : previousCurrent;
    const wasEmpty = previousCurrent === null || previousCurrent <= 0.05;

    barEl._targetFill = v;

    // The animation loop may draw level 0 before the first status arrives.
    // Draw the first real value immediately so the liquid does not look like it disappeared.
    if (!shouldRunLiquidLoop()) {
        barEl._currentFill = v;
        paintLiquidBarNow(barEl, v, glossEl, shadowEl, maskEl, blobAEl, blobBEl, surfaceMaskEl, bias);
    } else if (wasEmpty && v > 0) {
        barEl._currentFill = v;
        paintLiquidBarNow(barEl, v, glossEl, shadowEl, maskEl, blobAEl, blobBEl, surfaceMaskEl, bias);
    } else if (previousCurrent === null) {
        barEl._currentFill = v;
        paintLiquidBarNow(barEl, v, glossEl, shadowEl, maskEl, blobAEl, blobBEl, surfaceMaskEl, bias);
    }

    if (glossEl) glossEl._linkedLiquid = barEl;
    if (shadowEl) shadowEl._linkedLiquid = barEl;
    if (maskEl) maskEl._linkedLiquid = barEl;
    if (blobAEl) blobAEl._linkedLiquid = barEl;
    if (blobBEl) blobBEl._linkedLiquid = barEl;
    if (surfaceMaskEl) surfaceMaskEl._linkedLiquid = barEl;

    const targetChanged = previousTarget === null || Math.abs(v - previousTarget) >= 0.35;
    const settleMs = getLiquidAnimationSettleMs();
    if (shouldAnimateLiquidBars() && targetChanged && settleMs > 0) {
        LIQUID_ANIMATION_ACTIVE_UNTIL = Math.max(LIQUID_ANIMATION_ACTIVE_UNTIL, Date.now() + settleMs);
        scheduleLiquidAnimationFrame(0);
    }
}

function animateLiquidBars(timestamp) {
    let nextFrameMs = getLiquidAnimationFrameMs();
    try {
        const animated = shouldAnimateLiquidBars();
        const mode = getLiquidAnimationMode();
        const frameMs = nextFrameMs;
        LIQUID_ANIMATION_LAST_FRAME_AT = timestamp;

        const keepWaveAlive = shouldKeepLiquidWaveAlive();
        const phase = animated ? timestamp * 0.00055 : 0;
        const bars = [
            [cpuBarEl, cpuGlossEl, cpuShadowEl, cpuMaskEl, cpuBlobAEl, cpuBlobBEl, cpuSurfaceMaskEl, 0.0],
            [gpuBarEl, gpuGlossEl, gpuShadowEl, gpuMaskEl, gpuBlobAEl, gpuBlobBEl, gpuSurfaceMaskEl, 0.9],
            [ramBarEl, ramGlossEl, ramShadowEl, ramMaskEl, ramBlobAEl, ramBlobBEl, ramSurfaceMaskEl, 1.8],
            [shiftBarEl, shiftGlossEl, shiftShadowEl, shiftMaskEl, shiftBlobAEl, shiftBlobBEl, shiftSurfaceMaskEl, 2.7],
            [powerBarEl, powerGlossEl, powerShadowEl, powerMaskEl, powerBlobAEl, powerBlobBEl, powerSurfaceMaskEl, 3.6],
        ];

        for (const [barEl, glossEl, shadowEl, maskEl, blobAEl, blobBEl, surfaceMaskEl, bias] of bars) {
            if (!barEl) continue;
            const target = Number.isFinite(barEl._targetFill) ? barEl._targetFill : 0;
            const current = Number.isFinite(barEl._currentFill) ? barEl._currentFill : target;
            const speed = (animated && mode !== 'static') ? (mode === 'light' ? 0.45 : 0.16) : 1;
            const eased = current + ((target - current) * speed);
            barEl._currentFill = Math.abs(target - eased) < 0.05 ? target : eased;
            const isSettling = Math.abs(target - barEl._currentFill) >= 0.05;
            const wavePhase = (animated && mode === 'full' && (keepWaveAlive || isSettling)) ? phase * 5.2 : 0;
            const fillPath = buildLiquidWavePath(barEl._currentFill, wavePhase, bias);
            barEl.setAttribute('d', fillPath);
            if (maskEl) maskEl.setAttribute('d', fillPath);

            if (mode === 'full') {
                if (glossEl) glossEl.setAttribute('d', buildLiquidGlossPath(barEl._currentFill, wavePhase, bias));
                if (shadowEl) shadowEl.setAttribute('d', buildLiquidShadowPath(barEl._currentFill, wavePhase, bias));
                if (surfaceMaskEl) surfaceMaskEl.setAttribute('d', buildLiquidSurfaceMaskPath(barEl._currentFill, wavePhase, bias));
                updateLiquidBlob(blobAEl, barEl._currentFill, phase, bias, 0);
                updateLiquidBlob(blobBEl, barEl._currentFill, phase + 0.35, bias + 0.4, 1);
            } else {
                if (glossEl) glossEl.setAttribute('d', fillPath);
                if (shadowEl) shadowEl.setAttribute('d', fillPath);
                if (surfaceMaskEl) surfaceMaskEl.setAttribute('d', fillPath);
                resetLiquidBlob(blobAEl);
                resetLiquidBlob(blobBEl);
            }
        }
    } catch (err) {
        console.error('Liquid animation loop error:', err);
    }

    if (shouldRunLiquidLoop()) scheduleLiquidAnimationFrame(nextFrameMs);
}

scheduleLiquidAnimationFrame(0);
document.addEventListener('visibilitychange', () => {
    LIQUID_ANIMATION_LAST_FRAME_AT = 0;
    scheduleLiquidAnimationFrame(0);
});


function parseLRC(lrc) {
    if (!lrc) return [];
    const lines = lrc.split('\n');
    const result = [];
    const regex = /\[(\d{2,}):(\d{2})(?:\.(\d{2,3}))?\](.*)/;
    for (const line of lines) {
        const match = line.match(regex);
        if (match) {
            const m = parseInt(match[1], 10);
            const s = parseInt(match[2], 10);
            const msStr = match[3] || '0';
            const ms = msStr.length === 2 ? parseInt(msStr, 10) * 10 : parseInt(msStr, 10);
            const time = m * 60 + s + ms / 1000;
            const text = (match[4] || '').trim();
            result.push({ time, text });
        }
    }
    return result.sort((a, b) => a.time - b.time);
}

function updateLyricLayout(text) {
    if (!lyricEl) return;
    const t = (text || '').trim();
    const isLong = t.length > 42 || t.includes('  ');
    lyricEl.classList.toggle('one-line', !isLong);
    lyricEl.classList.toggle('two-line', isLong);
}

function setLyricText(text) {
    if (!lyricEl) return;
    const safeText = text || '';
    setTextIfChanged(lyricEl, safeText);
    updateLyricLayout(safeText);
}
function isStaticLyricPlaceholder(text) {
    const t = String(text || '').trim().toLowerCase();
    const idleText = getNormalizedIdleText();
    const lyricsWaitingText = getNormalizedLyricsWaitingText();
    const noMediaTitle = getNormalizedNoMediaPlaceholderTitle();
    return (
        (!!idleText && t === idleText) ||
        (!!lyricsWaitingText && t === lyricsWaitingText) ||
        (!!noMediaTitle && t === noMediaTitle)
    );
}

function applyPlainPlaceholderVisual(el) {
    if (!el) return;
    el.style.animation = 'none';
    el.style.transform = 'none';
    el.style.filter = 'none';
    el.style.opacity = '1';
    el.style.color = '#ffffff';
    el.style.textShadow = '0 0 0 transparent';
    el.style.webkitTextStroke = '0 transparent';
    el.style.letterSpacing = '0';
    el.style.fontWeight = '400';
}

function clearPlainPlaceholderVisual(el) {
    if (!el) return;
    el.style.animation = '';
    el.style.transform = '';
    el.style.filter = '';
    el.style.opacity = '';
    el.style.color = '';
    el.style.textShadow = '';
    el.style.webkitTextStroke = '';
    el.style.letterSpacing = '';
    el.style.fontWeight = '';
}

function syncNoMediaPlaceholderVisuals() {
    applyPlainPlaceholderVisual(mediaTitleEl);
    applyPlainPlaceholderVisual(lyricEl);
}

function resetLyricVisualState() {
    if (!lyricEl) return;
    if (lyricEl._lyricAnimation && typeof lyricEl._lyricAnimation.cancel === 'function') {
        try { lyricEl._lyricAnimation.cancel(); } catch (_) {}
        lyricEl._lyricAnimation = null;
    }
    lyricEl.classList.remove('hide', 'lyric-drop-in', 'lyric-drop-out');
    applyPlainPlaceholderVisual(lyricEl);
    void lyricEl.offsetWidth;
    lyricEl.style.animation = '';
}

function playLyricTransition(el, direction = 'in') {
    if (!el) return Promise.resolve();
    if (el._lyricAnimation && typeof el._lyricAnimation.cancel === 'function') {
        try { el._lyricAnimation.cancel(); } catch (_) {}
    }

    const isOut = direction === 'out';
    const frames = isOut
        ? [
            { opacity: 1, transform: 'translate3d(0, 0, 0) scale(1)' },
            { opacity: 0, transform: 'translate3d(18px, -12px, 0) scale(.98)' },
        ]
        : [
            { opacity: 0, transform: 'translate3d(-28px, 14px, 0) scale(.94)' },
            { opacity: 1, transform: 'translate3d(5px, -2px, 0) scale(1.02)', offset: 0.62 },
            { opacity: 1, transform: 'translate3d(0, 0, 0) scale(1)' },
        ];
    const timing = {
        duration: isOut ? 260 : 440,
        easing: isOut ? 'cubic-bezier(.55,.08,.68,.53)' : 'cubic-bezier(.22,.75,.25,1)',
        fill: 'both',
    };

    el.classList.remove('lyric-drop-in', 'lyric-drop-out', 'hide');
    void el.offsetWidth;

    if (typeof el.animate === 'function') {
        const animation = el.animate(frames, timing);
        el._lyricAnimation = animation;
        return animation.finished.catch(() => {}).finally(() => {
            if (el._lyricAnimation === animation) el._lyricAnimation = null;
            if (!isOut) {
                el.style.opacity = '';
                el.style.transform = '';
            }
        });
    }

    el.classList.add(isOut ? 'lyric-drop-out' : 'lyric-drop-in');
    return new Promise((resolve) => {
        setTimeout(() => {
            el.classList.remove('lyric-drop-in', 'lyric-drop-out');
            resolve();
        }, timing.duration);
    });
}

function animateLyricText(nextText) {
    if (!lyricEl) return;

    const safeText = nextText || '♪';

    if (isStaticLyricPlaceholder(safeText)) {
        setLyricText(safeText);
        resetLyricVisualState();
        currentDisplayedText = safeText;
        isLyricAnimating = false;
        return;
    }

    clearPlainPlaceholderVisual(lyricEl);

    const sameText = currentDisplayedText === safeText;

    if (!currentDisplayedText) {
        setLyricText(safeText);
        currentDisplayedText = safeText;
        playLyricTransition(lyricEl, 'in');
        return;
    }

    if (sameText || isLyricAnimating) return;

    isLyricAnimating = true;
    lyricAnimToken += 1;
    const myToken = lyricAnimToken;

    playLyricTransition(lyricEl, 'out').then(() => {
        if (myToken !== lyricAnimToken || !lyricEl) return;
        setLyricText(safeText);
        currentDisplayedText = safeText;
        playLyricTransition(lyricEl, 'in').then(() => {
            if (myToken !== lyricAnimToken || !lyricEl) return;
            isLyricAnimating = false;
        });
    });
}

let lyricsAnimationTimer = null;

function clearLyricsAnimationTimer() {
    if (lyricsAnimationTimer) {
        clearTimeout(lyricsAnimationTimer);
        clearInterval(lyricsAnimationTimer);
        lyricsAnimationTimer = null;
    }
}

function shouldRunLyricsAnimationTimer() {
    return Boolean(
        lyricEl
        && parsedLyrics.length > 0
        && isMediaPlaying
        && document.visibilityState !== 'hidden'
    );
}

function updateLyricsAnimation() {
    if (!lyricEl || parsedLyrics.length === 0) return;

    let estTime = mediaPos;
    if (isMediaPlaying) estTime += (Date.now() - lastSyncTime) / 1000;
    estTime += getLyricOffsetSec();

    let activeText = '';
    for (let i = 0; i < parsedLyrics.length; i++) {
        if (estTime >= parsedLyrics[i].time) activeText = parsedLyrics[i].text;
        else break;
    }

    animateLyricText(activeText || '♪');
}

function getLyricsAnimationIntervalMs() {
    const animationBase = Math.max(40, getFrontendNumber('lyrics_animation_interval_ms', 90));
    const lyricsRefreshRaw = getFrontendNumber('lyrics_refresh_interval_ms', 1000);
    const base = Number.isFinite(lyricsRefreshRaw) && lyricsRefreshRaw !== 1000 ? Math.max(40, lyricsRefreshRaw) : animationBase;
    if (isLowPerformanceMode()) return Math.max(base, 220);
    const level = getAnimationLevel();
    if (level === 'off') return Math.max(base, 320);
    if (level === 'low') return Math.max(base, 150);
    if (level === 'high') return Math.min(base, 65);
    return base;
}

function startLyricsAnimationLoop() {
    clearLyricsAnimationTimer();
    updateLyricsAnimation();
    if (!shouldRunLyricsAnimationTimer()) return;
    const tick = () => {
        lyricsAnimationTimer = null;
        updateLyricsAnimation();
        if (shouldRunLyricsAnimationTimer()) {
            lyricsAnimationTimer = setTimeout(tick, getLyricsAnimationIntervalMs());
        }
    };
    lyricsAnimationTimer = setTimeout(tick, getLyricsAnimationIntervalMs());
}

startLyricsAnimationLoop();

document.addEventListener('visibilitychange', () => {
    startMediaProgressLoop();
    startLyricsAnimationLoop();
});

function hasAnyChanged(changedKeys, keys) {
    if (!changedKeys) return true;
    for (const key of keys) {
        if (changedKeys.has(key)) return true;
    }
    return false;
}

function applyStatusPayload(d, changedKeys = null) {
    if (!d || typeof d !== 'object') return;
    const metricsChanged = hasAnyChanged(changedKeys, [
        'cpu_temp', 'gpu_temp', 'ram_percent', 'cpu_power', 'cpu_percent',
        'tomorrow_shift_text', 'tomorrow_shift_subtitle', 'fps',
        'fps_1_low', 'pc_plug_power_w', 'gpu_power', 'gpu_util', 'vram_percent',
        'download_speed_mbps', 'download_speed', 'net_down_mbps', 'net_down',
        'upload_speed_mbps', 'upload_speed', 'net_up_mbps', 'net_up',
        'motherboard_temp', 'mobo_temp', 'vmos_temp', 'vrm_temp', 'vrmos_temp', 'ram_slot_temps', 'ram_used_gb',
        'uptime', 'disks_cde'
    ]);
    const mediaChanged = hasAnyChanged(changedKeys, [
        'media_title', 'media_artist', 'media_position', 'media_duration',
        'media_is_playing', 'lyrics', 'media_track_token', 'media_source_app'
    ]);
    const tuyaChanged = hasAnyChanged(changedKeys, ['tuya_devices']);
    const audioChanged = hasAnyChanged(changedKeys, ['volume_percent', 'is_muted']);
    if (metricsChanged) {

    if (cpuTempEl) setOdoText(cpuTempEl, fmtTemp(d.cpu_temp).replace('°C', ''));
    if (gpuTempEl) setOdoText(gpuTempEl, fmtTemp(d.gpu_temp).replace('°C', ''));
    if (ramUsageEl) setOdoText(ramUsageEl, fmtPercent(d.ram_percent).replace('%', ''));
	if (cpuPowerEl) setTextIfChanged(cpuPowerEl, `${fmtWattWithUnit(d.cpu_power)} · ${fmtPercent(d.cpu_percent)}`);

    const tomorrowShiftText = String(d.tomorrow_shift_text || '').trim();
    const tomorrowShiftSubtitle = String(d.tomorrow_shift_subtitle || '').trim() || '';
    if (shiftCardLabelEl) setTextIfChanged(shiftCardLabelEl, 'SHIFT');
    if (shiftValueEl) setTextIfChanged(shiftValueEl, tomorrowShiftText || '--');
    if (shiftSubtitleEl) setTextIfChanged(shiftSubtitleEl, tomorrowShiftSubtitle);

    const fpsNumber = finiteMetricNumber(d.fps);
    const hasFpsValue = fpsNumber !== null && fpsNumber > 0;
    const totalSystemPowerRaw = resolvePcPlugPowerWatts(d);
    const totalSystemPowerText = Number.isFinite(totalSystemPowerRaw) && totalSystemPowerRaw > 0
        ? fmtWatt(totalSystemPowerRaw)
        : '--';

    const nowMs = Date.now();
    if (hasFpsValue) {
        applyStatusPayload._lastVisibleFpsAt = nowMs;
        applyStatusPayload._lastVisibleFps = fpsNumber;
        applyStatusPayload._lastVisibleFpsLow = finiteMetricNumber(d.fps_1_low);
    }

    const canUseRecentFps = (
        !hasFpsValue
        && Number.isFinite(applyStatusPayload._lastVisibleFps)
        && (nowMs - (applyStatusPayload._lastVisibleFpsAt || 0)) <= 2500
    );

    const keepFpsModeForGame = !hasFpsValue && isLikelyGamingLoad(d);
    const shouldShowFpsCard = hasFpsValue || keepFpsModeForGame;

    if (shouldShowFpsCard) {
        const displayFps = hasFpsValue ? fpsNumber : (canUseRecentFps ? applyStatusPayload._lastVisibleFps : null);
        const displayFpsLow = hasFpsValue ? finiteMetricNumber(d.fps_1_low) : (canUseRecentFps ? applyStatusPayload._lastVisibleFpsLow : null);
        if (lowCardLabelEl) setTextIfChanged(lowCardLabelEl, 'FPS');
        if (fpsLowMainValueEl) setTextIfChanged(fpsLowMainValueEl, `${fmtFps(displayFps)}`);
        if (vramInfoValueEl) setTextIfChanged(vramInfoValueEl, `LOW ${fmtFps(displayFpsLow)}`);
        applyDynamicLowCardLiquidTheme('fps');
        const fpsFill = getRatioFillPercent(displayFps || 0, 180);
        if (applyStatusPayload._lastPowerCardMode !== 'fps' || Math.abs((applyStatusPayload._lastPowerBarPct ?? -999) - fpsFill) >= 0.2) {
            applyStatusPayload._lastPowerCardMode = 'fps';
            applyStatusPayload._lastPowerBarPct = fpsFill;
            applyHeatBar(powerBarEl, fpsFill, powerGlossEl, powerShadowEl, powerMaskEl, powerBlobAEl, powerBlobBEl, powerSurfaceMaskEl, 3.6);
        }
    } else {
        if (lowCardLabelEl) setTextIfChanged(lowCardLabelEl, 'POWER');
        if (fpsLowMainValueEl) setTextIfChanged(fpsLowMainValueEl, totalSystemPowerText);
        if (vramInfoValueEl) setTextIfChanged(vramInfoValueEl, 'Watt');
        applyDynamicLowCardLiquidTheme('power');
        const powerFill = getRatioFillPercent(totalSystemPowerRaw || 0, 370);
        if (applyStatusPayload._lastPowerCardMode !== 'power' || Math.abs((applyStatusPayload._lastPowerBarPct ?? -999) - powerFill) >= 0.2) {
            applyStatusPayload._lastPowerCardMode = 'power';
            applyStatusPayload._lastPowerBarPct = powerFill;
            applyHeatBar(powerBarEl, powerFill, powerGlossEl, powerShadowEl, powerMaskEl, powerBlobAEl, powerBlobBEl, powerSurfaceMaskEl, 3.6);
        }
    }

    const shiftLiquidFill = getShiftLiquidRandomFillPercent();
    if (Math.abs((applyStatusPayload._lastShiftBarPct ?? -999) - shiftLiquidFill) >= 0.2) {
        applyStatusPayload._lastShiftBarPct = shiftLiquidFill;
        applyHeatBar(shiftBarEl, shiftLiquidFill, shiftGlossEl, shiftShadowEl, shiftMaskEl, shiftBlobAEl, shiftBlobBEl, shiftSurfaceMaskEl, 2.7);
    }

    const gpuPowerText = fmtWattWithUnit(d.gpu_power);
    const gpuUtilPercentText = fmtPercent(d.gpu_util);
    const vramPercentText = fmtPercent(d.vram_percent);

	if (gpuPowerEl) {
        setTextIfChanged(gpuPowerEl, `${gpuPowerText} · ${gpuUtilPercentText} · ${vramPercentText}`);
    }

    const smoothMetricPct = (key, raw, alpha = 0.35) => {
        const n = finiteMetricNumber(raw);
        if (n === null) return Math.round(Number(applyStatusPayload[key]) || 0);
        const clamped = Math.max(0, Math.min(100, n));
        const prev = finiteMetricNumber(applyStatusPayload[key]);
        const next = prev === null ? clamped : (prev + (clamped - prev) * alpha);
        applyStatusPayload[key] = next;
        return Math.round(next);
    };
    const cpuPct = smoothMetricPct('_smoothCpuPct', d.cpu_percent, 0.45);
    const gpuPct = smoothMetricPct('_smoothGpuPct', d.gpu_util, 0.25);
    const ramPct = smoothMetricPct('_smoothRamPct', d.ram_percent, 0.35);
    if (applyStatusPayload._lastCpuBarPct !== cpuPct) {
        applyStatusPayload._lastCpuBarPct = cpuPct;
        applyHeatBar(cpuBarEl, cpuPct, cpuGlossEl, cpuShadowEl, cpuMaskEl, cpuBlobAEl, cpuBlobBEl, cpuSurfaceMaskEl, 0.0);
    }
    if (applyStatusPayload._lastGpuBarPct !== gpuPct) {
        applyStatusPayload._lastGpuBarPct = gpuPct;
        applyHeatBar(gpuBarEl, gpuPct, gpuGlossEl, gpuShadowEl, gpuMaskEl, gpuBlobAEl, gpuBlobBEl, gpuSurfaceMaskEl, 0.9);
    }
    if (applyStatusPayload._lastRamBarPct !== ramPct) {
        applyStatusPayload._lastRamBarPct = ramPct;
        applyHeatBar(ramBarEl, ramPct, ramGlossEl, ramShadowEl, ramMaskEl, ramBlobAEl, ramBlobBEl, ramSurfaceMaskEl, 1.8);
    }

const downSpeed = d.download_speed_mbps ?? d.download_speed ?? d.net_down_mbps ?? d.net_down;
const upSpeed = d.upload_speed_mbps ?? d.upload_speed ?? d.net_up_mbps ?? d.net_up;

if (panelDownloadEl) setTextIfChanged(panelDownloadEl, fmtSpeed(downSpeed, 'down'));
if (panelUploadEl) setTextIfChanged(panelUploadEl, fmtSpeed(upSpeed, 'up'));

    if (panelMbVmosTempsEl) {
        const mb = d.motherboard_temp ?? d.mobo_temp;
        const vm = d.vmos_temp ?? d.vrm_temp ?? d.vrmos_temp;
        const parts = [];
        if (mb !== null && mb !== undefined && mb !== '') parts.push(`${fmtTemp(mb)}`);
        if (vm !== null && vm !== undefined && vm !== '') parts.push(`${fmtTemp(vm)}`);

        setTextIfChanged(panelMbVmosTempsEl, parts.length ? parts.join(' · ') : '—');
    }
	

	
const ramExtraParts = [];
const ramSlots = Array.isArray(d.ram_slot_temps) ? d.ram_slot_temps : [];

if (ramSlots.length > 0) {
    const line = ramSlots.map((s) => {
        const t = s.temp_c ?? s.temp;
        return (t !== null && t !== undefined && t !== '')
            ? `${Math.round(Number(t))}°C`
            : '—';
    }).join(' · ');
    ramExtraParts.push(line);
}

if (d.ram_used_gb !== undefined) {
    const ramUsedText = fmtRamUsageGb(d.ram_used_gb).trim();
    if (ramUsedText) ramExtraParts.push(ramUsedText);
}

const ramExtraContent = ramExtraParts.length > 0 ? ramExtraParts.join(' · ') : '—';
if (ramExtraValueEl) setTextIfChanged(ramExtraValueEl, ramExtraContent);
if (panelUptimeEl) setTextIfChanged(panelUptimeEl, d.uptime || '-');

	
	
    if (panelDiskCEl) {
        const disks = d.disks_cde && typeof d.disks_cde === 'object' ? d.disks_cde : {};
        const diskC = disks.C;
        if (!diskC) {
            setTextIfChanged(panelDiskCEl, '—');
        } else if (typeof diskC === 'number') {
            setTextIfChanged(panelDiskCEl, `${Math.round(Number(diskC))}°C`);
        } else {
            const pct = diskC.percent;
            const temp = diskC.temp_c ?? diskC.temp;
            const text = (pct !== null && pct !== undefined && pct !== '')
                ? `${Number(pct).toFixed(1)}%`
                : ((temp !== null && temp !== undefined && temp !== '') ? `${Math.round(Number(temp))}°C` : '—');
            setTextIfChanged(panelDiskCEl, text);
        }
    }
    }

    if (mediaChanged) {
    const rawMediaTitle = String(d.media_title || '').trim();
    const noMedia = isNoMediaTitle(rawMediaTitle);

    if (mediaTitleEl) {
        setTextIfChanged(
            mediaTitleEl,
            noMedia ? getNoMediaPlaceholderTitle() : truncateText(rawMediaTitle, 40)
        );
        if (noMedia) {
            syncNoMediaPlaceholderVisuals();
        } else {
            clearPlainPlaceholderVisual(mediaTitleEl);
        }
    }
    if (mediaArtistEl) {
        setTextIfChanged(mediaArtistEl, noMedia ? '' : truncateText(d.media_artist, 24));
    }
    const normalizedTimeline = normalizeMediaTimeline(d.media_position, d.media_duration);
    updateMediaVisibility(rawMediaTitle, normalizedTimeline.duration, d.media_is_playing === true);

    const incomingTitle = String(d.media_title || '');
    const incomingArtist = String(d.media_artist || '');
    const incomingTrackToken = buildMediaTrackToken(d, normalizedTimeline);
    const incomingTrackKey = `${incomingTitle}__${incomingArtist}`;
    const currentTrackKey = `${lastMediaTitle || ''}__${lastMediaArtist || ''}`;
    const incomingDuration = normalizedTimeline.duration;
    const incomingPos = normalizedTimeline.position;
    const serverIsPlaying = (d.media_is_playing === true);
    const now = Date.now();

    if (noMedia) {
        // Do not keep the previous video position during transitions or empty sessions.
        lastMediaTitle = incomingTitle;
        lastMediaArtist = incomingArtist;
        lastMediaTrackToken = incomingTrackToken;
        mediaPos = 0;
        mediaDuration = 0;
        lastSyncTime = now;
        isMediaPlaying = false;
    } else {
        const estimatedNowPos = getCurrentMediaPositionSec();
        const looksLikeRestart =
            !mediaIsSeeking &&
            incomingDuration > 0.5 &&
            mediaDuration > 0.5 &&
            incomingPos <= 1.5 &&
            estimatedNowPos >= 5 &&
            Math.abs(incomingDuration - mediaDuration) <= 2.0;


        const tokenChanged = !!incomingTrackToken && incomingTrackToken !== lastMediaTrackToken;
        if (incomingTrackKey !== currentTrackKey || Math.abs(incomingDuration - mediaDuration) > 2.0 || looksLikeRestart || tokenChanged) {
            // Force sync when the track changes or the time drifts by more than 2 seconds.
            const trackChanged = incomingTrackKey !== currentTrackKey || tokenChanged;
            lastMediaTitle = incomingTitle;
            lastMediaArtist = incomingArtist;
            if (incomingTrackToken) lastMediaTrackToken = incomingTrackToken;
            mediaPos = incomingPos;
            mediaDuration = incomingDuration;
            lastSyncTime = now;
            isMediaPlaying = serverIsPlaying;
            if (trackChanged) {
                // Right after a video switch, the backend can return the old position for one or two cycles.
                mediaTrackChangeGuardUntil = now + 4500;
            }
        } else if (d.media_position !== undefined && d.media_position !== null && !mediaIsSeeking) {
            if (Date.now() > mediaSeekIgnoreServerUntil) {
                const guardActive = now < mediaTrackChangeGuardUntil && incomingPos > 8.0 && incomingDuration > 0.5;
                if (!guardActive) {
                    const myGuess = mediaPos + (isMediaPlaying ? (now - lastSyncTime) / 1000 : 0);
                    const drift = incomingPos - myGuess;
                    const rewound = drift < -1.25;
                    const jumped = drift > 2.0;
                    const transientPause =
                        !serverIsPlaying &&
                        isMediaPlaying &&
                        incomingDuration > 0.5 &&
                        Math.abs(drift) <= 1.25 &&
                        (now - lastSyncTime) <= 2200;
                    const effectiveServerIsPlaying = transientPause ? true : serverIsPlaying;
                    const playStateChanged = effectiveServerIsPlaying !== isMediaPlaying;
                    const durationChanged = Math.abs(incomingDuration - mediaDuration) > 0.75;

                    if (rewound || jumped || playStateChanged || durationChanged) {
                        mediaPos = incomingPos;
                        lastSyncTime = now;
                    }
                    isMediaPlaying = effectiveServerIsPlaying;
                }
                else {
                    isMediaPlaying = serverIsPlaying;
                }
            }
        }
    }

    if (incomingDuration > 0) {
        mediaDuration = incomingDuration;
        if (mediaPos > mediaDuration) {
            mediaPos = mediaDuration;
            lastSyncTime = now;
        }
    }

    if (normalizedTimeline.duration > 0 || (d.media_duration !== undefined && d.media_duration !== null)) {
        mediaDuration = incomingDuration;
        if (mediaDuration > 0 && mediaPos > mediaDuration) {
            mediaPos = mediaDuration;
        }
    }

    // The backend sometimes omits `lyrics` when it has not changed.
    // In that case, keep the current lyrics on the frontend.
    const hasLyrics = (typeof d.lyrics === 'string');
    const incomingLyrics = hasLyrics ? d.lyrics.trim() : null;

    if (incomingLyrics !== null && incomingLyrics !== currentLrcData) {
        currentLrcData = incomingLyrics;
        parsedLyrics = parseLRC(incomingLyrics);
        currentDisplayedText = '';
        if (parsedLyrics.length === 0) {
            const plainText = incomingLyrics || (noMedia ? getNoMediaPlaceholderTitle() : getLyricsWaitingText());
            setLyricText(plainText);
            if (lyricEl) lyricEl.classList.remove('hide');
            currentDisplayedText = '';
            if (noMedia) setLyricText(getIdleText());
            animateLyricText(noMedia ? getIdleText() : plainText);
        } else if (lyricEl) {
            lyricEl.classList.remove('hide');
        }
    } else if (incomingLyrics === null) {
        // Assume lyrics did not change: do nothing.
    } else if (!incomingLyrics && parsedLyrics.length === 0) {
        const plainText = noMedia ? getNoMediaPlaceholderTitle() : getLyricsWaitingText();
        setLyricText(plainText);
        if (lyricEl) lyricEl.classList.remove('hide');
        currentDisplayedText = '';
        if (noMedia) setLyricText(getIdleText());
        animateLyricText(noMedia ? getIdleText() : plainText);
    }

    startMediaProgressLoop();
    startLyricsAnimationLoop();
    }

    if (tuyaChanged && Array.isArray(d.tuya_devices)) {
        updateTuyaButtons(d.tuya_devices);
    }

    if (audioChanged) {
    const canApplyRemoteVolume =
        !isDraggingVolume &&
        (Date.now() - lastLocalVolumeChangeAt) > getVolumeRemoteSyncDelayMs();

    if (canApplyRemoteVolume && d.volume_percent !== null && d.volume_percent !== undefined && volumeSlider) {
        volumeSlider.value = d.volume_percent;
        setVolumeText(d.volume_percent, false);
    }

    if (d.is_muted !== null && d.is_muted !== undefined) {
        const remoteMuted = d.is_muted === true;
        const canApplyRemoteMute = Date.now() >= localMuteOverrideUntil || localMuteState === remoteMuted;
        if (canApplyRemoteMute) {
            localMuteState = remoteMuted;
            if (Date.now() >= localMuteOverrideUntil) localMuteOverrideUntil = 0;
            updateMuteButtonState(remoteMuted);
        }
    }

    }

    if (coverEl && coverEl.style.display !== 'none') {
        coverEl.style.display = 'none';
        coverEl.removeAttribute('src');
        lastCoverSrc = '';
    }

    if (statusEl) {
        setStatusText(wsConnected ? 'WebSocket connected' : 'Waiting for WebSocket...');
    }
}

function handleWsPayload(payload) {
    lastWsMessageAt = Date.now();

    if (payload && typeof payload === 'object' && payload.type === 'command_result' && payload.request_id) {
        const pending = wsPendingRequests.get(payload.request_id);
        if (pending) {
            clearTimeout(pending.timer);
            wsPendingRequests.delete(payload.request_id);
            pending.resolve(payload);
        }
        return;
    }

    let data = payload;
    let changedKeys = null;
    if (data && typeof data === 'object' && data.type === 'status' && data.payload) {
        changedKeys = new Set(Object.keys(data.payload || {}));
        data = { ...lastStatusState, ...data.payload };
        lastStatusState = data;
    } else if (data && typeof data === 'object' && data.type === 'full_status' && data.payload) {
        lastStatusState = { ...data.payload };
        data = lastStatusState;
    } else if (data && typeof data === 'object') {
        changedKeys = new Set(Object.keys(data));
        data = { ...lastStatusState, ...data };
        lastStatusState = data;
    }

    if (!data || typeof data !== 'object') return;
    applyStatusPayload(data, changedKeys);
    applyWeatherFromStatus(data, changedKeys);
}

function scheduleWsReconnect() {
    if (wsReconnectTimer) return;
    wsReconnectTimer = setTimeout(() => {
        wsReconnectTimer = null;
        connectWebSocket();
    }, wsReconnectDelay);
    wsReconnectDelay = Math.min(wsReconnectDelay * 2, WS_RECONNECT_MAX_MS);
}

async function bootstrapInitialStatus() {
    try {
        const response = await fetch('/status', { cache: 'no-store' });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (!data || typeof data !== 'object') return;
        lastStatusState = { ...data };
        applyStatusPayload(data);
        applyWeatherFromStatus(data);
    } catch (err) {
console.error('Initial status data could not be loaded:', err);
    }
}

function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;

    try {
        ws = new WebSocket(WS_URL);
    } catch (err) {
console.error('WebSocket could not be started:', err);
        scheduleStatusFallbackPolling();
        scheduleWsReconnect();
        return;
    }

ws.addEventListener('open', () => {
    wsConnected = true;
    wsReconnectDelay = WS_RECONNECT_MIN_MS;
    lastWsMessageAt = Date.now();
    clearStatusFallbackPolling();

    if (statusEl) {
        setStatusText('WebSocket connected');
    }

    try {
        ws.send('refresh');
    } catch (err) {
        console.error('WebSocket refresh request could not be sent:', err);
    }
});

    ws.addEventListener('message', (event) => {
        try {
            const payload = JSON.parse(event.data);

            if (payload && payload.type === 'reload') {
                hardReloadLikeCtrlF5();
                return;
            }

            handleWsPayload(payload);
        } catch (err) {
            const text = String(event.data || '').trim().toLowerCase();
            if (text === 'pong') return;
            console.error('WebSocket message parse error:', err, event.data);
        }
    });

    ws.addEventListener('close', () => {
        wsConnected = false;
        ws = null;
        wsPendingRequests.forEach((pending) => {
            clearTimeout(pending.timer);
            pending.reject(new Error('WebSocket connection closed.'));
        });
        wsPendingRequests.clear();
        if (statusEl) {
            setStatusText('WebSocket koptu', true);
        }
        scheduleStatusFallbackPolling();
        scheduleWsReconnect();
    });

    ws.addEventListener('error', (err) => {
        console.error('WebSocket error:', err);
    });
}

async function cmd(path) {
    try {
        await wsCommand(path);
    } catch (e) {
        console.error(e);
    }
}


async function cmdJson(path) {
    try {
        const payload = await wsCommand(path);
        return payload && typeof payload === 'object' ? payload : { ok: true, raw: payload };
    } catch (e) {
        console.error(e);
        return { ok: false, error: String(e) };
    }
}
const APP_BUTTON_LONG_PRESS_MS = 550;

function bindLaunchHoldButton(buttonId, launchPath, killPath, label) {
    const el = document.getElementById(buttonId);
    if (!el || el.dataset.launchHoldReady === '1') return;
    el.dataset.launchHoldReady = '1';

    let longPressTimer = null;
    let longPressTriggered = false;
    let activePointerId = null;

    const clearPressTimer = () => {
        if (longPressTimer) {
            clearTimeout(longPressTimer);
            longPressTimer = null;
        }
    };

    const cancelPress = () => {
        clearPressTimer();
        activePointerId = null;
        longPressTriggered = false;
    };

    el.addEventListener('pointerdown', (ev) => {
        activePointerId = ev.pointerId;
        longPressTriggered = false;
        clearPressTimer();
        longPressTimer = setTimeout(async () => {
            longPressTriggered = true;
            const data = await cmdJson(killPath);
            if (data && data.ok) {
                setStatusText(`${label} stopped`);
            } else {
                setStatusText(`${label} stop failed`, true);
            }
        }, APP_BUTTON_LONG_PRESS_MS);
    });

    el.addEventListener('pointerup', async (ev) => {
        if (activePointerId !== null && ev.pointerId !== activePointerId) return;
        clearPressTimer();
        if (!longPressTriggered) {
            const data = await cmdJson(launchPath);
            if (data && data.ok) {
                setStatusText(`${label} started`);
            } else {
                setStatusText(`${label} start failed`, true);
            }
        }
        activePointerId = null;
        longPressTriggered = false;
    });

    el.addEventListener('pointercancel', cancelPress);
    el.addEventListener('pointerleave', cancelPress);
}


let statusPollTimer = null;
function clearStatusFallbackPolling() {
    if (statusPollTimer) {
        clearInterval(statusPollTimer);
        statusPollTimer = null;
    }
}
async function fetchStatusFallbackOnce() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        clearStatusFallbackPolling();
        return;
    }
    try {
        const resp = await fetch('/status', { cache: 'no-store' });
        if (!resp.ok) return;
        const data = await resp.json();
        if (data && typeof data === 'object') {
            lastStatusState = { ...data };
            applyStatusPayload(data);
            applyWeatherFromStatus(data);
        }
    } catch (_) {}
}
function scheduleStatusFallbackPolling() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        clearStatusFallbackPolling();
        return;
    }
    clearStatusFallbackPolling();
    const everyMs = Math.max(500, getPerformanceNumber('status_poll_interval_ms', 5000));
    statusPollTimer = setInterval(fetchStatusFallbackOnce, everyMs);
}

refreshPanelSettings(true);
bootstrapInitialStatus();
connectWebSocket();
scheduleStatusFallbackPolling();


/* ===== TUYA BRIGHTNESS APPEND PATCH ===== */
(function(){
    const tuyaBrightnessOverlayEl = document.getElementById('tuyaBrightnessOverlay');
    const tuyaBrightnessSliderEl = document.getElementById('tuyaBrightnessSlider');
    const tuyaBrightnessValueEl = document.getElementById('tuyaBrightnessValue');
    const tuyaBrightnessNameEl = document.getElementById('tuyaBrightnessName');

    if (!tuyaBrightnessOverlayEl || !tuyaBrightnessSliderEl) return;

    let tuyaBrightnessLongPressTimer = null;
    let tuyaBrightnessLongPressTriggered = false;
    let tuyaBrightnessDragging = false;
    let activeTuyaBrightnessKey = '';
    let tuyaBrightnessSendTimer = null;
    let tuyaBrightnessPendingMap = {};
    let lastLocalTuyaBrightnessChangeAt = 0;

    const TUYA_BRIGHTNESS_LONG_PRESS_MS = 420;
    function getTuyaBrightnessSettleMs() { return Math.max(500, Number(getPanelSetting('tuya.brightness_popup_timeout_ms', 1600)) || 1600); }
    const TUYA_BRIGHTNESS_REMOTE_SYNC_DELAY_MS = 1800;
    const TUYA_BRIGHTNESS_ACCEPT_TOLERANCE = 2;

    function markPending(key, value) {
        tuyaBrightnessPendingMap[String(key || '')] = {
            value: Math.max(1, Math.min(100, parseInt(value, 10) || 1)),
            until: Date.now() + getTuyaBrightnessSettleMs()
        };
    }

    function getPending(key) {
        const k = String(key || '');
        const item = tuyaBrightnessPendingMap[k];
        if (!item) return null;
        if (Date.now() > item.until) {
            delete tuyaBrightnessPendingMap[k];
            return null;
        }
        return item;
    }

    function clearPending(key) {
        delete tuyaBrightnessPendingMap[String(key || '')];
    }

    function applyVisual(value) {
        const v = Math.max(1, Math.min(100, parseInt(value, 10) || 1));
        tuyaBrightnessSliderEl.style.setProperty('--tuya-brightness-progress', `${v}%`);
        if (tuyaBrightnessValueEl) setTextIfChanged(tuyaBrightnessValueEl, `${v}%`);
    }

    function setSliderValue(value, force = false) {
        const v = Math.max(1, Math.min(100, parseInt(value, 10) || 1));
        if (force || !tuyaBrightnessDragging) {
            tuyaBrightnessSliderEl.value = String(v);
        }
        applyVisual(v);
    }

    window.closeTuyaBrightnessPopup = function() {
        activeTuyaBrightnessKey = '';
        tuyaBrightnessDragging = false;
        tuyaBrightnessOverlayEl.classList.add('confirm-hidden');
    };

    function openBrightnessPopup(deviceKey) {
        const key = String(deviceKey || '');
        activeTuyaBrightnessKey = key;
        const state = (window.tuyaDeviceStates && window.tuyaDeviceStates[key]) ? window.tuyaDeviceStates[key] : {};
        const pending = getPending(key);
        if (tuyaBrightnessNameEl) setTextIfChanged(tuyaBrightnessNameEl, state.name || '');
        setSliderValue(pending ? pending.value : (state.brightness_percent ?? 100), true);
        tuyaBrightnessOverlayEl.classList.remove('confirm-hidden');
    }

    async function sendBrightness(deviceKey, value) {
        const key = String(deviceKey || '');
        const v = Math.max(1, Math.min(100, parseInt(value, 10) || 1));
        try {
            const d = await wsCommand(`/tuya/brightness/${encodeURIComponent(key)}`, { value: v });
            if (d && d.ok && d.device && window.tuyaDeviceStates) {
                const remote = Math.max(1, Math.min(100, parseInt(d.device.brightness_percent ?? v, 10) || v));
                const pending = getPending(key);
                const acceptRemote = !pending || Math.abs(remote - pending.value) <= TUYA_BRIGHTNESS_ACCEPT_TOLERANCE;
                window.tuyaDeviceStates[key] = {
                    ...(window.tuyaDeviceStates[key] || {}),
                    is_on: d.device.is_on === true,
                    online: d.device.online !== false,
                    name: d.device.name || key,
                    brightness_percent: acceptRemote ? remote : (pending ? pending.value : remote)
                };
                if (acceptRemote) clearPending(key);
                if (activeTuyaBrightnessKey === key && !tuyaBrightnessDragging) {
                    setSliderValue(window.tuyaDeviceStates[key].brightness_percent || v, true);
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            tuyaBrightnessSendTimer = null;
        }
    }

    function scheduleBrightness(value) {
        if (!activeTuyaBrightnessKey) return;
        const v = Math.max(1, Math.min(100, parseInt(value, 10) || 1));
        lastLocalTuyaBrightnessChangeAt = Date.now();
        markPending(activeTuyaBrightnessKey, v);
        if (window.tuyaDeviceStates && window.tuyaDeviceStates[activeTuyaBrightnessKey]) {
            window.tuyaDeviceStates[activeTuyaBrightnessKey].brightness_percent = v;
        }
        setSliderValue(v, true);
        if (tuyaBrightnessSendTimer) clearTimeout(tuyaBrightnessSendTimer);
        tuyaBrightnessSendTimer = setTimeout(() => sendBrightness(activeTuyaBrightnessKey, v), getVolumeRemoteSyncDelayMs());
    }

    function bindLongPress(btn) {
        if (!btn || btn.dataset.brightnessBound === '1') return;
        btn.dataset.brightnessBound = '1';
        const key = btn.getAttribute('data-tuya-device');
        if (!key) return;

        const cancel = () => {
            if (tuyaBrightnessLongPressTimer) {
                clearTimeout(tuyaBrightnessLongPressTimer);
                tuyaBrightnessLongPressTimer = null;
            }
        };

        btn.addEventListener('pointerdown', () => {
            tuyaBrightnessLongPressTriggered = false;
            cancel();
            tuyaBrightnessLongPressTimer = setTimeout(() => {
                tuyaBrightnessLongPressTriggered = true;
                openBrightnessPopup(key);
            }, TUYA_BRIGHTNESS_LONG_PRESS_MS);
        });

        btn.addEventListener('pointerup', cancel);
        btn.addEventListener('pointerleave', cancel);
        btn.addEventListener('pointercancel', cancel);

        btn.addEventListener('click', (e) => {
            if (tuyaBrightnessLongPressTriggered) {
                e.preventDefault();
                e.stopImmediatePropagation();
                tuyaBrightnessLongPressTriggered = false;
            }
        }, true);
    }

    document.querySelectorAll('[data-tuya-device]').forEach(bindLongPress);

    const _renderTuyaButtons = window.renderTuyaButtons;
    if (typeof _renderTuyaButtons === 'function') {
        window.renderTuyaButtons = function(devices) {
            const result = _renderTuyaButtons(devices);
            document.querySelectorAll('[data-tuya-device]').forEach(bindLongPress);
            return result;
        };
    }

    const _updateTuyaButtons = window.updateTuyaButtons;
    if (typeof _updateTuyaButtons === 'function') {
        window.updateTuyaButtons = function(devices) {
            const result = _updateTuyaButtons(devices);
            if (Array.isArray(devices) && window.tuyaDeviceStates) {
                devices.forEach((device) => {
                    const key = String(device.key || '');
                    if (!key) return;
                    const pending = getPending(key);
                    if (window.tuyaDeviceStates[key]) {
                        window.tuyaDeviceStates[key].brightness_percent = pending ? pending.value : (device.brightness_percent ?? window.tuyaDeviceStates[key].brightness_percent ?? null);
                    }
                });
            }

            if (activeTuyaBrightnessKey) {
                const activeDevice = Array.isArray(devices) ? devices.find(x => String(x.key || '') === activeTuyaBrightnessKey) : null;
                const pending = getPending(activeTuyaBrightnessKey);
                const canApplyRemote = !tuyaBrightnessDragging && (Date.now() - lastLocalTuyaBrightnessChangeAt) > TUYA_BRIGHTNESS_REMOTE_SYNC_DELAY_MS;

                if (activeDevice && activeDevice.brightness_percent !== null && activeDevice.brightness_percent !== undefined) {
                    const remote = Math.max(1, Math.min(100, parseInt(activeDevice.brightness_percent, 10) || 1));
                    const acceptRemote = canApplyRemote && (!pending || Math.abs(remote - pending.value) <= TUYA_BRIGHTNESS_ACCEPT_TOLERANCE);
                    if (acceptRemote) {
                        if (pending) clearPending(activeTuyaBrightnessKey);
                        setSliderValue(remote, true);
                    } else if (pending) {
                        setSliderValue(pending.value, true);
                    }
                } else if (pending) {
                    setSliderValue(pending.value, true);
                }
            }

            document.querySelectorAll('[data-tuya-device]').forEach(bindLongPress);
            return result;
        };
    }

    tuyaBrightnessSliderEl.addEventListener('pointerdown', () => { tuyaBrightnessDragging = true; });
    tuyaBrightnessSliderEl.addEventListener('input', (e) => scheduleBrightness(e.target.value));
    tuyaBrightnessSliderEl.addEventListener('change', (e) => {
        tuyaBrightnessDragging = false;
        scheduleBrightness(e.target.value);
    });

    window.addEventListener('pointerup', () => {
        if (tuyaBrightnessDragging) {
            tuyaBrightnessDragging = false;
            scheduleBrightness(tuyaBrightnessSliderEl.value);
        }
    });
    window.addEventListener('pointercancel', () => {
        if (tuyaBrightnessDragging) {
            tuyaBrightnessDragging = false;
            scheduleBrightness(tuyaBrightnessSliderEl.value);
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !tuyaBrightnessOverlayEl.classList.contains('confirm-hidden')) {
            window.closeTuyaBrightnessPopup();
        }
    });

    applyVisual(tuyaBrightnessSliderEl.value || 100);
})();


window.addEventListener('load', () => {
    applyVolumeAspectCompensation();
    if (volumeSlider) applyVolumeVisual(volumeSlider.value);
});


/* ===== SMARTTHINGS CLIMATE POPUP PATCH ===== */
(function(){
    const climateButtonEl = document.getElementById('climateLevelBtn');
    const climateOverlayEl = document.getElementById('climateLevelOverlay');
    const climateSliderEl = document.getElementById('climateLevelSlider');
    const climateValueEl = document.getElementById('climateLevelValue');
    const climatePowerOnBtn = document.getElementById('climatePowerOnBtn');
    const climatePowerOffBtn = document.getElementById('climatePowerOffBtn');
    const climateStatusDebugEl = document.getElementById('climateStatusDebug');

    if (!climateButtonEl || !climateOverlayEl || !climateSliderEl || !climateValueEl || !climatePowerOnBtn || !climatePowerOffBtn || !climateStatusDebugEl) return;

    const CLIMATE_MIN = 18;
    const CLIMATE_MAX = 30;
    const CLIMATE_LONG_PRESS_MS = 420;

    let climateLongPressTimer = null;
    let climateLongPressTriggered = false;
    let climateDragging = false;
    let climateSendTimer = null;
    let climateStatusLoading = false;
    let lastClimateValue = Math.max(CLIMATE_MIN, Math.min(CLIMATE_MAX, parseInt(climateSliderEl.value, 10) || 24));
    let lastClimatePowerState = 'off';

    function clampClimateValue(value) {
        return Math.max(CLIMATE_MIN, Math.min(CLIMATE_MAX, parseInt(value, 10) || CLIMATE_MIN));
    }

    function applyClimateVisual(value, force = false) {
        const v = clampClimateValue(value);
        if (force || !climateDragging) {
            climateSliderEl.value = String(v);
        }
        const progress = ((v - CLIMATE_MIN) / (CLIMATE_MAX - CLIMATE_MIN)) * 100;
        climateSliderEl.style.setProperty('--tuya-brightness-progress', `${progress}%`);
        setTextIfChanged(climateValueEl, `${v}°`);
        lastClimateValue = v;
    }

    function updateClimatePowerButtons(powerState) {
        const isOn = String(powerState || '').toLowerCase() === 'on';
        climatePowerOnBtn.classList.toggle('active', isOn);
        climatePowerOffBtn.classList.toggle('active', !isOn);
        climatePowerOnBtn.style.opacity = isOn ? '1' : '0.72';
        climatePowerOffBtn.style.opacity = isOn ? '0.72' : '1';
        lastClimatePowerState = isOn ? 'on' : 'off';
    }

    function updateClimateDebug(rawLevel, rawPower) {
        const levelText = rawLevel == null ? '-' : String(rawLevel);
        const powerText = rawPower == null ? '-' : String(rawPower);
        setTextIfChanged(climateStatusDebugEl, `API level: ${levelText}\nAPI switch: ${powerText}`);
    }

    async function fetchClimateStatus() {
        if (climateStatusLoading) return;
        climateStatusLoading = true;
        try {
            const res = await fetch('/smartthings/climate/status', { method: 'GET', cache: 'no-store' });
            const data = await res.json().catch(() => ({}));
            if (!res.ok || !data || data.ok !== true) throw new Error((data && data.error) || `SmartThings HTTP ${res.status}`);
            const rawLevel = data.level;
            const rawPower = data.power;

            updateClimateDebug(rawLevel, rawPower);
            if (rawLevel != null) applyClimateVisual(rawLevel, true);
            if (rawPower != null) updateClimatePowerButtons(rawPower);
        } catch (err) {
            updateClimateDebug('error', 'error');
            console.error('Climate status could not be read:', err);
        } finally {
            climateStatusLoading = false;
        }
    }

    async function sendClimateLevel(value) {
        const v = clampClimateValue(value);
        try {
            const res = await fetch('/smartthings/climate/level', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ level: v }),
                cache: 'no-store'
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok || !data || data.ok !== true) throw new Error((data && data.error) || `SmartThings HTTP ${res.status}`);
            lastClimateValue = v;
        } catch (err) {
            console.error('Climate level could not be sent:', err);
        }
    }

    async function sendClimatePower(command) {
        try {
            const res = await fetch('/smartthings/climate/power', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ command }),
                cache: 'no-store'
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok || !data || data.ok !== true) throw new Error((data && data.error) || `SmartThings HTTP ${res.status}`);
            updateClimatePowerButtons(command);
        } catch (err) {
            console.error(`Climate power could not be sent (${command}):`, err);
        }
    }

    function scheduleClimateSend(value) {
        const v = clampClimateValue(value);
        applyClimateVisual(v, true);
        if (climateSendTimer) clearTimeout(climateSendTimer);
        climateSendTimer = setTimeout(() => sendClimateLevel(v), 90);
    }

    window.closeClimateLevelPopup = function() {
        climateDragging = false;
        climateOverlayEl.classList.add('confirm-hidden');
    };

function openClimateLevelPopup() {
    applyClimateVisual(lastClimateValue, true);
    climateOverlayEl.classList.remove('confirm-hidden');

    requestAnimationFrame(() => {
        if (typeof setupSketchButtons === 'function') {
            setupSketchButtons();
        }
    });

    fetchClimateStatus();
}
    window.openClimateLevelPopup = openClimateLevelPopup;

    function cancelClimateLongPress() {
        if (climateLongPressTimer) {
            clearTimeout(climateLongPressTimer);
            climateLongPressTimer = null;
        }
    }

climateButtonEl.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopImmediatePropagation();
    openClimateLevelPopup();
}, true);

    climateSliderEl.addEventListener('pointerdown', () => { climateDragging = true; });
    climateSliderEl.addEventListener('input', (e) => scheduleClimateSend(e.target.value));
    climateSliderEl.addEventListener('change', (e) => {
        climateDragging = false;
        scheduleClimateSend(e.target.value);
    });
    window.addEventListener('pointerup', () => {
        if (climateDragging) {
            climateDragging = false;
            scheduleClimateSend(climateSliderEl.value);
        }
    });
    window.addEventListener('pointercancel', () => {
        if (climateDragging) {
            climateDragging = false;
            scheduleClimateSend(climateSliderEl.value);
        }
    });

    climatePowerOnBtn.addEventListener('click', () => sendClimatePower('on'));
    climatePowerOffBtn.addEventListener('click', () => sendClimatePower('off'));

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !climateOverlayEl.classList.contains('confirm-hidden')) {
            window.closeClimateLevelPopup();
        }
    });



    applyClimateVisual(lastClimateValue, true);
    updateClimatePowerButtons(lastClimatePowerState);
    updateClimateDebug('-', '-');
})();

/* ===== SYSTEM ISSUES POPUP ===== */
(function() {
    const overlayEl = document.getElementById('systemIssuesOverlay');
    const listEl = document.getElementById('systemIssuesList');
    if (!overlayEl || !listEl) return;

    window.closeSystemIssuesOverlay = function() {
        overlayEl.classList.add('confirm-hidden');
    };

    window.openSystemIssuesOverlay = async function() {
        overlayEl.classList.remove('confirm-hidden');
        listEl.innerHTML = '<div class="no-issues-msg">Yükleniyor...</div>';
        
        try {
            const res = await fetch('/hata/data?lines=50');
            const data = await res.json();
            
            if (!data.ok || !data.errors || data.errors.length === 0) {
                listEl.innerHTML = '<div class="no-issues-msg">Kayıtlı hata bulunamadı.</div>';
                return;
            }

            listEl.innerHTML = '';
            data.errors.forEach(err => {
                const item = document.createElement('div');
                item.className = 'issue-item error';
                item.innerHTML = `
                    <div style="display:flex; justify-content:space-between; margin-bottom:10px; opacity:0.7; font-size:20px;">
                        <span>${err.source}</span>
                        <span>${err.ts}</span>
                    </div>
                    <div style="font-size:24px; line-height:1.4; word-break:break-word;">${err.message}</div>
                `;
                listEl.appendChild(item);
            });
        } catch (e) {
            listEl.innerHTML = '<div class="no-issues-msg">Veriler alınamadı.</div>';
        }
    };

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !overlayEl.classList.contains('confirm-hidden')) {
            window.closeSystemIssuesOverlay();
        }
    });
})();
