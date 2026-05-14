// File Version: 1.0
function fitPanel(){
    const root = document.querySelector('.panel-root');
    if(!root) return;

    const baseW = 1920;
    const baseH = 1080;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const scale = window.innerHeight / baseH;

    root.style.width = baseW + 'px';
    root.style.height = baseH + 'px';
    root.style.left = '55%';
    root.style.top = '50%';
    root.style.right = 'auto';
    root.style.bottom = 'auto';
    root.style.transformOrigin = 'center center';
    root.style.transform = `translate(-50%, -50%) scale(${scale})`;
}
window.addEventListener('resize', fitPanel);
window.addEventListener('load', fitPanel);
fitPanel();

// Saat+tarih: gereksiz DOM yazımını önlemek için önceki değerlerle karşılaştır
const _clockEl = document.getElementById('panelClock');
const _dateEl  = document.getElementById('panelDate');
let _lastMinute = -1;
let _lastDateStr = '';
window.__panelDateText = '';

function renderPanelDateWeatherSummary() {
    if (!_dateEl) return;
    const lang = (typeof window.getPanelLanguage === 'function' && window.getPanelLanguage() === 'tr') ? 'tr' : 'en';
    const dateText = String(window.__panelDateText || '').trim();
    const locationText = String(window.__panelWeatherLocation || 'Kayseri').trim() || 'Kayseri';
    const weatherText = String(window.__panelWeatherText || '').trim();
    const rainText = String(window.__panelWeatherRainText || '').trim();

    let combined = dateText ? (lang === 'tr' ? `Bugün ${dateText}.` : `Today is ${dateText}.`) : (lang === 'tr' ? 'Bugün.' : 'Today.');
    if (weatherText) {
        combined += lang === 'tr'
            ? ` ${locationText} için bugün hava ${weatherText}.`
            : ` Today's weather in ${locationText}: ${weatherText}.`;
    }
    if (rainText) {
        combined += ` ${rainText}`;
    }
    _dateEl.textContent = combined || '--';
}

function updatePanelDateTime(force = false) {
    if (!_clockEl || !_dateEl) return;
    const lang = (typeof window.getPanelLanguage === 'function' && window.getPanelLanguage() === 'tr') ? 'tr' : 'en';
    const locale = lang === 'tr' ? 'tr-TR' : 'en-US';
    const now = new Date();
    const minute = now.getHours() * 60 + now.getMinutes();
    if (force || minute !== _lastMinute) {
        _lastMinute = minute;
        _clockEl.textContent = now.toLocaleTimeString(locale, {
            hour: '2-digit', minute: '2-digit'
        });
    }
    const dateStr = now.toLocaleDateString(locale, {
        day: '2-digit', month: 'long', year: 'numeric', weekday: 'long'
    }).replace(/^(\d{2} [^\d]+ \d{4}) ([^\d]+)$/u, '$1, $2');
    if (force || dateStr !== _lastDateStr) {
        _lastDateStr = dateStr;
        window.__panelDateText = dateStr;
        renderPanelDateWeatherSummary();
    }
}
updatePanelDateTime();
setInterval(updatePanelDateTime, 15000); // 15 saniyede bir kontrol yeterli
