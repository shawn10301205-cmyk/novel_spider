/**
 * 小说排行榜前端 - Material 3 磨砂玻璃风格
 * 支持多数据源切换、汇总模式、按天缓存
 */

// ============================================================
// 状态管理
// ============================================================
const state = {
    source: '',
    gender: '',
    period: '',
    sort: 'rank',
    selectedCategories: [],
    categories: [],
    sources: [],
    results: [],
    loading: false,
    cached: false,
    date: '',
};

// ============================================================
// 初始化
// ============================================================
document.addEventListener('DOMContentLoaded', async () => {
    const saved = localStorage.getItem('theme');
    if (saved === 'dark') document.documentElement.setAttribute('data-theme', 'dark');

    await loadSources();
    loadCategories();
    // 自动加载当天数据
    autoLoad();
});

// ============================================================
// API
// ============================================================
const API_BASE = '';

async function api(path, options = {}) {
    const resp = await fetch(`${API_BASE}${path}`, options);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
}

async function loadSources() {
    try {
        const res = await api('/api/sources');
        state.sources = res.data || [];
        renderSourceChips();
    } catch (e) {
        console.error('加载数据源失败:', e);
        document.getElementById('sourceChips').innerHTML = '<span class="loading-text">加载失败</span>';
    }
}

async function loadCategories() {
    try {
        const params = state.source ? `?source=${state.source}` : '';
        const res = await api(`/api/categories${params}`);
        state.categories = res.data || [];
        renderCategoryChips();
    } catch (e) {
        document.getElementById('categoryChips').innerHTML = '<span class="loading-text">加载失败</span>';
    }
}

async function autoLoad() {
    // 检查是否有缓存，自动加载
    const hasCached = state.sources.some(s => s.has_today);
    if (hasCached) {
        await doScrape(false); // 不强制刷新，优先用缓存
    }
}

async function doScrape(force = false) {
    if (state.loading) return;
    state.loading = true;

    const btn = document.getElementById('btnScrape');
    btn.classList.add('loading');
    btn.disabled = true;
    showSection('loading');

    const isAllSources = !state.source;
    updateLoadingMsg(force ? '正在重新抓取最新数据...' : '正在加载数据...');

    const startTime = Date.now();

    try {
        let url;
        const params = new URLSearchParams();
        if (state.gender) params.set('gender', state.gender);
        if (state.period) params.set('period', state.period);
        if (state.sort) params.set('sort', state.sort);
        if (force) params.set('force', '1');

        if (isAllSources) {
            url = `/api/scrape/all-sources?${params.toString()}`;
        } else {
            params.set('source', state.source);
            if (state.selectedCategories.length > 0)
                params.set('category', state.selectedCategories.join(','));
            url = `/api/scrape?${params.toString()}`;
        }

        const res = await api(url);
        state.results = res.data || [];
        state.cached = res.from_storage || false;
        state.date = res.date || '';

        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        updateStats(state.results.length, elapsed);
        renderResults(state.results);
        showSection('results');

        const msg = state.cached
            ? `已加载 ${state.results.length} 条缓存数据（${state.date}）`
            : `成功抓取 ${state.results.length} 条新数据`;
        showToast(state.cached ? 'info' : 'success', msg);

        document.getElementById('btnFeishu').disabled = state.results.length === 0;

        // 刷新数据源状态
        loadSources();
    } catch (e) {
        showToast('error', `加载失败: ${e.message}`);
        showSection('empty');
    } finally {
        state.loading = false;
        btn.classList.remove('loading');
        btn.disabled = false;
    }
}

async function pushFeishu() {
    if (state.results.length === 0) return showToast('error', '没有数据');
    const btn = document.getElementById('btnFeishu');
    btn.classList.add('loading');
    btn.disabled = true;
    try {
        const res = await api('/api/feishu/push', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ data: state.results, clear: true }),
        });
        showToast(res.code === 0 ? 'success' : 'error', res.msg || '操作完成');
    } catch (e) {
        showToast('error', `推送失败: ${e.message}`);
    } finally {
        btn.classList.remove('loading');
        btn.disabled = false;
    }
}

// ============================================================
// UI 交互
// ============================================================
function selectSource(el) {
    el.parentElement.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
    el.classList.add('active');
    state.source = el.dataset.value;
    state.selectedCategories = [];
    loadCategories();
}

function selectChip(el, type) {
    el.parentElement.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
    el.classList.add('active');
    state[type] = el.dataset.value;
    if (type === 'gender') renderCategoryChips();
}

function toggleCategory(el) {
    const name = el.dataset.name;
    el.classList.toggle('active');
    if (el.classList.contains('active')) {
        if (!state.selectedCategories.includes(name)) state.selectedCategories.push(name);
    } else {
        state.selectedCategories = state.selectedCategories.filter(c => c !== name);
    }
}

function toggleTheme() {
    const html = document.documentElement;
    const isDark = html.getAttribute('data-theme') === 'dark';
    html.setAttribute('data-theme', isDark ? '' : 'dark');
    localStorage.setItem('theme', isDark ? '' : 'dark');
}

function getSourceName(id) {
    const s = state.sources.find(s => s.id === id);
    return s ? s.name : id;
}

// ============================================================
// 渲染
// ============================================================
function renderSourceChips() {
    const container = document.getElementById('sourceChips');
    let html = `
        <button class="chip active" data-value="" onclick="selectSource(this)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            全部汇总
        </button>`;

    for (const src of state.sources) {
        const cachedDot = src.has_today ? ' <span class="cache-dot" title="今日已有数据">●</span>' : '';
        html += `
            <button class="chip" data-value="${src.id}" onclick="selectSource(this)">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" stroke="currentColor" stroke-width="2"/></svg>
                ${escapeHtml(src.name)}${cachedDot}
            </button>`;
    }

    container.innerHTML = html;
}

function renderCategoryChips() {
    const container = document.getElementById('categoryChips');
    if (!state.source) {
        container.innerHTML = '<span class="loading-text">汇总模式下自动抓取所有分类</span>';
        return;
    }
    let cats = state.categories;
    if (state.gender) cats = cats.filter(c => c.gender === state.gender);
    const seen = new Set(); const unique = [];
    for (const cat of cats) { if (!seen.has(cat.name)) { seen.add(cat.name); unique.push(cat); } }
    if (unique.length === 0) { container.innerHTML = '<span class="loading-text">暂无分类</span>'; return; }
    container.innerHTML = unique.map(cat => {
        const isActive = state.selectedCategories.includes(cat.name);
        return `<button class="cat-chip ${isActive ? 'active' : ''}" data-name="${escapeHtml(cat.name)}" onclick="toggleCategory(this)">${escapeHtml(cat.name)}</button>`;
    }).join('');
}

function renderResults(data) {
    const container = document.getElementById('resultsContainer');
    if (!data || data.length === 0) { container.innerHTML = ''; return; }

    // 按来源 -> 分类分组
    const bySource = {};
    for (const item of data) {
        const src = item.source || '未知来源';
        if (!bySource[src]) bySource[src] = {};
        const cat = item.category || '未分类';
        if (!bySource[src][cat]) bySource[src][cat] = [];
        bySource[src][cat].push(item);
    }

    let html = '';
    let delay = 0;

    for (const [source, categories] of Object.entries(bySource)) {
        const sourceCount = Object.values(categories).reduce((s, arr) => s + arr.length, 0);
        if (Object.keys(bySource).length > 1) {
            html += `
            <div class="source-header fade-in" style="animation-delay: ${delay}ms">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" stroke="currentColor" stroke-width="2"/></svg>
                <h2>${escapeHtml(source)}</h2>
                <span class="badge">${sourceCount}本</span>
            </div>`;
            delay += 50;
        }
        for (const [category, novels] of Object.entries(categories)) {
            html += `<div class="category-group fade-in" style="animation-delay: ${delay}ms">
                <div class="category-group-header">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    <h3>${escapeHtml(category)}</h3>
                    <span class="badge">${novels.length}本</span>
                </div><div class="novel-list">`;
            for (const novel of novels) { delay += 20; html += renderNovelCard(novel, delay); }
            html += `</div></div>`;
            delay += 30;
        }
    }
    container.innerHTML = html;
}

function renderNovelCard(novel, delay) {
    const rankClass = novel.rank <= 3 ? `rank-${novel.rank}` : 'rank-other';
    const genderClass = novel.gender === '男频' ? 'tag-gender-male' : 'tag-gender-female';
    const bookUrl = novel.book_url || '#';
    const titleLink = bookUrl !== '#'
        ? `<a href="${escapeHtml(bookUrl)}" target="_blank" rel="noopener">${escapeHtml(novel.title)}</a>`
        : escapeHtml(novel.title);

    return `
    <div class="novel-card glass-card stagger-in" style="animation-delay: ${delay}ms">
        <div class="rank-badge ${rankClass}">${novel.rank}</div>
        <div class="novel-info">
            <div class="novel-title">${titleLink}</div>
            <div class="novel-meta">
                <span class="novel-meta-item">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="7" r="4" stroke="currentColor" stroke-width="2"/></svg>
                    ${escapeHtml(novel.author || '-')}
                </span>
                <span class="novel-meta-item">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><rect x="3" y="3" width="7" height="7" rx="1" stroke="currentColor" stroke-width="2"/><rect x="14" y="3" width="7" height="7" rx="1" stroke="currentColor" stroke-width="2"/><rect x="3" y="14" width="7" height="7" rx="1" stroke="currentColor" stroke-width="2"/><rect x="14" y="14" width="7" height="7" rx="1" stroke="currentColor" stroke-width="2"/></svg>
                    ${escapeHtml(novel.category || '-')}
                </span>
            </div>
            ${novel.latest_chapter ? `<div class="novel-chapter">📖 ${escapeHtml(novel.latest_chapter)}</div>` : ''}
        </div>
        <div class="novel-tags">
            <span class="tag ${genderClass}">${escapeHtml(novel.gender || '-')}</span>
            <span class="tag tag-period">${escapeHtml(novel.period || '-')}</span>
            ${novel.source ? `<span class="tag tag-source">${escapeHtml(novel.source)}</span>` : ''}
        </div>
    </div>`;
}

// ============================================================
// 辅助
// ============================================================
function showSection(name) {
    const sections = { loading: 'loadingSection', results: 'resultsSection', empty: 'emptyState' };
    document.getElementById('statsBar').style.display = name === 'results' ? '' : 'none';
    for (const [key, id] of Object.entries(sections))
        document.getElementById(id).style.display = key === name ? '' : 'none';
}

function updateStats(total, elapsed) {
    document.getElementById('statTotal').textContent = total;
    document.getElementById('statTime').textContent = `${elapsed}s`;
    const cats = new Set(state.results.map(r => r.category));
    document.getElementById('statCategories').textContent = cats.size;
}

function updateLoadingMsg(msg) { document.getElementById('loadingMsg').textContent = msg; }

function showToast(type, message) {
    const container = document.getElementById('toastContainer');
    const icons = {
        success: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M22 4L12 14.01l-3-3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
        error: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><path d="M15 9l-6 6M9 9l6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
        info: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><path d="M12 16v-4M12 8h.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
    };
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `${icons[type] || icons.info} <span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);
    setTimeout(() => { toast.classList.add('toast-exit'); setTimeout(() => toast.remove(), 300); }, 3500);
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
