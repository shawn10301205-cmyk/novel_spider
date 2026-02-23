/**
 * 小说排行榜前端 - 市场分析看板 + 排行榜
 * 支持多数据源、按天缓存、一键全量获取
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
    currentTab: 'dashboard',
    dashboard: null,
};

// ============================================================
// 颜色调色板
// ============================================================
const COLORS = [
    '#6750A4', '#7D5260', '#006B5E', '#4758A9', '#8B5000',
    '#6D5F00', '#A93F46', '#00658E', '#6750A4', '#006D3B',
    '#7C5800', '#5B5F72', '#9A4520', '#006874', '#6B5778',
];
const GENDER_COLORS = {
    '男频': '#4758A9',
    '女频': '#A93F46',
    '全部': '#6750A4',
};

// ============================================================
// 初始化
// ============================================================
document.addEventListener('DOMContentLoaded', async () => {
    const saved = localStorage.getItem('theme');
    if (saved === 'dark') document.documentElement.setAttribute('data-theme', 'dark');

    await loadSources();
    loadCategories();
    // 自动加载看板
    checkAndLoadDashboard();
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
    } catch (e) {
        console.error('加载分类失败:', e);
    }
}

// ============================================================
// Tab 切换
// ============================================================
function switchTab(tab) {
    state.currentTab = tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`[data-tab="${tab}"]`).classList.add('active');

    document.getElementById('tabDashboard').style.display = tab === 'dashboard' ? '' : 'none';
    document.getElementById('tabRank').style.display = tab === 'rank' ? '' : 'none';
}

// ============================================================
// 市场看板
// ============================================================
async function checkAndLoadDashboard() {
    const allHaveData = state.sources.length > 0 && state.sources.every(s => s.has_today);
    const anyHasData = state.sources.some(s => s.has_today);

    if (anyHasData) {
        updateFetchStatus('有今日数据', `${state.sources.filter(s => s.has_today).length}/${state.sources.length} 个平台有数据`, true);
        await loadDashboard();
    } else {
        updateFetchStatus('暂无今日数据', '点击「全量获取数据」开始抓取所有平台排行榜', false);
        document.getElementById('dashboardContent').style.display = 'none';
        document.getElementById('dashEmpty').style.display = '';
    }
}

function updateFetchStatus(title, desc, hasData) {
    document.getElementById('fetchTitle').textContent = title;
    document.getElementById('fetchDesc').textContent = desc;
    const icon = document.querySelector('.fetch-icon');
    icon.style.background = hasData ? 'var(--md-primary-container)' : 'var(--md-surface-variant)';
    icon.style.color = hasData ? 'var(--md-on-primary-container)' : 'var(--md-on-surface-variant)';
}

async function fetchAllData(force = false) {
    const btn = document.getElementById('btnFetchAll');
    btn.disabled = true;
    btn.classList.add('loading');
    document.getElementById('dashLoadingSection').style.display = '';
    document.getElementById('dashboardContent').style.display = 'none';
    document.getElementById('dashEmpty').style.display = 'none';

    const forceParam = force ? '?force=1' : '';
    document.getElementById('dashLoadingMsg').textContent = force ? '正在强制刷新所有平台数据...' : '正在获取所有平台排行榜数据...';

    try {
        const res = await api(`/api/fetch-all${forceParam}`, { method: 'POST' });
        const total = res.total || 0;
        const errors = res.errors || [];

        showToast('success', `已获取 ${total} 条数据（${Object.keys(res.data || {}).length} 个平台）`);
        if (errors.length > 0) {
            showToast('error', `部分平台失败: ${errors.join('; ')}`);
        }

        // 刷新数据源状态
        await loadSources();
        await loadDashboard();
        updateFetchStatus('数据已更新', `共 ${total} 条数据，${Object.keys(res.data || {}).length} 个平台`, true);
    } catch (e) {
        showToast('error', `获取失败: ${e.message}`);
        document.getElementById('dashEmpty').style.display = '';
    } finally {
        btn.disabled = false;
        btn.classList.remove('loading');
        document.getElementById('dashLoadingSection').style.display = 'none';
    }
}

async function loadDashboard() {
    try {
        const res = await api('/api/dashboard');
        if (res.code !== 0 || !res.data.has_data) {
            document.getElementById('dashboardContent').style.display = 'none';
            document.getElementById('dashEmpty').style.display = '';
            return;
        }

        state.dashboard = res.data;
        document.getElementById('dashEmpty').style.display = 'none';
        document.getElementById('dashboardContent').style.display = '';
        renderDashboard(res.data);
    } catch (e) {
        console.error('加载看板失败:', e);
        document.getElementById('dashEmpty').style.display = '';
    }
}

function renderDashboard(data) {
    renderSourceStats(data.source_stats, data.total, data.date);
    renderGenderChart(data.gender_stats);
    renderCategoryChart(data.category_stats);
    renderCrossPlatform(data.cross_platform);
}

function renderSourceStats(sourceStats, total, date) {
    const grid = document.getElementById('sourceStatsGrid');
    let html = `
        <div class="dash-stat-card glass-card dash-stat-total">
            <div class="dash-stat-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </div>
            <div class="dash-stat-value">${total}</div>
            <div class="dash-stat-label">总数据量</div>
            <div class="dash-stat-sub">${date}</div>
        </div>`;

    for (const [name, count] of Object.entries(sourceStats)) {
        html += `
        <div class="dash-stat-card glass-card">
            <div class="dash-stat-icon dash-stat-icon-source">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" stroke="currentColor" stroke-width="2"/></svg>
            </div>
            <div class="dash-stat-value">${count}</div>
            <div class="dash-stat-label">${escapeHtml(name)}</div>
        </div>`;
    }

    grid.innerHTML = html;
}

function renderGenderChart(genderStats) {
    const container = document.getElementById('genderChart');
    const entries = Object.entries(genderStats).filter(([k]) => k !== '未知');
    const total = entries.reduce((s, [, v]) => s + v, 0);

    if (total === 0) {
        container.innerHTML = '<div class="chart-empty">暂无数据</div>';
        return;
    }

    // 绘制饼图（用CSS实现）
    let html = '<div class="pie-chart-wrap">';
    html += '<div class="pie-chart">';

    // 用 conic-gradient 实现饼图
    let gradientParts = [];
    let cumPercent = 0;
    for (const [gender, count] of entries) {
        const pct = (count / total) * 100;
        const color = GENDER_COLORS[gender] || '#999';
        gradientParts.push(`${color} ${cumPercent}% ${cumPercent + pct}%`);
        cumPercent += pct;
    }
    html += `<div class="pie" style="background: conic-gradient(${gradientParts.join(', ')});"></div>`;
    html += '</div>';

    html += '<div class="pie-legend">';
    for (const [gender, count] of entries) {
        const pct = ((count / total) * 100).toFixed(1);
        const color = GENDER_COLORS[gender] || '#999';
        html += `<div class="legend-item">
            <span class="legend-dot" style="background:${color}"></span>
            <span class="legend-label">${escapeHtml(gender)}</span>
            <span class="legend-value">${count} (${pct}%)</span>
        </div>`;
    }
    html += '</div></div>';

    container.innerHTML = html;
}

function renderCategoryChart(categoryStats) {
    const container = document.getElementById('categoryChart');
    const entries = Object.entries(categoryStats).sort((a, b) => b[1] - a[1]);

    if (entries.length === 0) {
        container.innerHTML = '<div class="chart-empty">暂无数据</div>';
        return;
    }

    const maxVal = entries[0][1];

    let html = '<div class="bar-chart">';
    entries.forEach(([cat, count], idx) => {
        const pct = (count / maxVal * 100).toFixed(1);
        const color = COLORS[idx % COLORS.length];
        html += `<div class="bar-row bar-row-interactive"
                    data-category="${escapeHtml(cat)}"
                    onclick="openCategoryDetail('${escapeHtml(cat)}')"
                    onmouseenter="showBarTooltip(event, '${escapeHtml(cat)}', ${count})"
                    onmouseleave="hideBarTooltip()">
            <span class="bar-label">${escapeHtml(cat)}</span>
            <div class="bar-track">
                <div class="bar-fill" style="width:${pct}%;background:${color};animation-delay:${idx * 50}ms"></div>
            </div>
            <span class="bar-value">${count} →</span>
        </div>`;
    });
    html += '</div>';

    container.innerHTML = html;
}

// 柱状图悬停提示
let _tooltipTimer = null;
function showBarTooltip(event, category, count) {
    clearTimeout(_tooltipTimer);
    // 延迟显示，避免快速滑过闪烁
    _tooltipTimer = setTimeout(async () => {
        let tooltip = document.getElementById('barTooltip');
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.id = 'barTooltip';
            tooltip.className = 'bar-tooltip glass-card';
            document.body.appendChild(tooltip);
        }

        // 先显示加载中
        tooltip.innerHTML = `<div class="tooltip-title">${escapeHtml(category)} · ${count}本</div><div class="tooltip-loading">加载预览...</div>`;
        tooltip.style.display = 'block';
        positionTooltip(tooltip, event);

        // 获取该分类的书籍列表
        try {
            const res = await api(`/api/category-books?category=${encodeURIComponent(category)}`);
            const books = (res.data || []).slice(0, 8);
            let listHtml = `<div class="tooltip-title">${escapeHtml(category)} · ${res.total}本</div>`;
            listHtml += '<div class="tooltip-books">';
            for (const b of books) {
                listHtml += `<div class="tooltip-book">
                    <span class="tooltip-book-title">${escapeHtml(b.title)}</span>
                    <span class="tooltip-book-meta">${escapeHtml(b.author || '-')} · ${escapeHtml(b.source || '')}</span>
                </div>`;
            }
            if (res.total > 8) listHtml += `<div class="tooltip-more">还有 ${res.total - 8} 本, 点击查看全部...</div>`;
            listHtml += '</div>';
            tooltip.innerHTML = listHtml;
            positionTooltip(tooltip, event);
        } catch (e) {
            tooltip.innerHTML = `<div class="tooltip-title">${escapeHtml(category)}</div><div class="tooltip-loading">加载失败</div>`;
        }
    }, 200);
}

function positionTooltip(tooltip, event) {
    const rect = event.currentTarget.getBoundingClientRect();
    tooltip.style.left = Math.min(rect.right + 10, window.innerWidth - 320) + 'px';
    tooltip.style.top = Math.max(10, rect.top - 20) + 'px';
}

function hideBarTooltip() {
    clearTimeout(_tooltipTimer);
    const tooltip = document.getElementById('barTooltip');
    if (tooltip) tooltip.style.display = 'none';
}

// 分类详情弹窗
async function openCategoryDetail(category) {
    hideBarTooltip();
    const modal = document.getElementById('categoryModal');
    const title = document.getElementById('modalCategoryTitle');
    const body = document.getElementById('modalCategoryBody');

    title.textContent = category;
    body.innerHTML = '<div class="modal-loading"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" class="spin"><path d="M21 12a9 9 0 1 1-6.22-8.56" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg> 加载中...</div>';
    modal.style.display = 'flex';

    try {
        const res = await api(`/api/category-books?category=${encodeURIComponent(category)}`);
        const books = res.data || [];

        if (books.length === 0) {
            body.innerHTML = '<div class="modal-empty">暂无数据</div>';
            return;
        }

        let html = `<div class="modal-stats">共 <strong>${books.length}</strong> 本 · 来自 <strong>${new Set(books.map(b => b.source)).size}</strong> 个平台</div>`;
        html += '<div class="modal-book-list">';

        for (const book of books) {
            const bookLink = book.book_url
                ? `<a href="${escapeHtml(book.book_url)}" target="_blank" rel="noopener">${escapeHtml(book.title)}</a>`
                : escapeHtml(book.title);
            const genderClass = book.gender === '男频' ? 'tag-gender-male' : 'tag-gender-female';

            html += `<div class="modal-book-card glass-card">
                <div class="modal-book-rank">${book.rank || '-'}</div>
                <div class="modal-book-info">
                    <div class="modal-book-title">${bookLink}</div>
                    <div class="modal-book-meta">
                        <span>✍ ${escapeHtml(book.author || '未知作者')}</span>
                        <span>📖 ${escapeHtml(book.latest_chapter || '-')}</span>
                    </div>
                </div>
                <div class="modal-book-tags">
                    <span class="tag ${genderClass}">${escapeHtml(book.gender || '-')}</span>
                    <span class="tag tag-period">${escapeHtml(book.period || '-')}</span>
                    <span class="tag tag-source">${escapeHtml(book.source || '-')}</span>
                </div>
            </div>`;
        }

        html += '</div>';
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<div class="modal-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
}

function closeCategoryModal() {
    document.getElementById('categoryModal').style.display = 'none';
}


function renderCrossPlatform(crossPlatform) {
    const container = document.getElementById('crossPlatformTable');
    document.getElementById('crossCount').textContent = crossPlatform.length;

    if (crossPlatform.length === 0) {
        container.innerHTML = '<div class="chart-empty">暂无跨平台热门作品</div>';
        return;
    }

    let html = '<div class="cross-table">';
    html += `<div class="cross-header">
        <span class="cross-col cross-col-rank">#</span>
        <span class="cross-col cross-col-title">书名</span>
        <span class="cross-col cross-col-author">作者</span>
        <span class="cross-col cross-col-cat">分类</span>
        <span class="cross-col cross-col-sources">上榜平台</span>
    </div>`;

    crossPlatform.forEach((book, idx) => {
        const sourceTags = book.sources.map(s =>
            `<span class="tag tag-source">${escapeHtml(s)}</span>`
        ).join('');

        html += `<div class="cross-row stagger-in" style="animation-delay:${idx * 30}ms">
            <span class="cross-col cross-col-rank">
                <span class="cross-rank ${idx < 3 ? 'cross-rank-top' : ''}">${idx + 1}</span>
            </span>
            <span class="cross-col cross-col-title">${escapeHtml(book.title)}</span>
            <span class="cross-col cross-col-author">${escapeHtml(book.author || '-')}</span>
            <span class="cross-col cross-col-cat">${escapeHtml(book.category || '-')}</span>
            <span class="cross-col cross-col-sources">${sourceTags}</span>
        </div>`;
    });

    html += '</div>';
    container.innerHTML = html;
}

// ============================================================
// 排行榜 Tab 功能
// ============================================================
async function doScrape(force = false) {
    if (state.loading) return;
    state.loading = true;

    const btn = document.getElementById('btnScrape');
    btn.classList.add('loading');
    btn.disabled = true;
    showRankSection('loading');

    const isAllSources = !state.source;
    document.getElementById('loadingMsg').textContent = '正在加载数据...';

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
            url = `/api/scrape?${params.toString()}`;
        }

        const res = await api(url);
        state.results = res.data || [];
        state.cached = res.from_storage || false;
        state.date = res.date || '';

        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        updateStats(state.results.length, state.date || elapsed);
        renderResults(state.results);
        showRankSection('results');

        const msg = state.cached
            ? `已加载 ${state.results.length} 条缓存数据（${state.date}）`
            : `成功加载 ${state.results.length} 条数据`;
        showToast(state.cached ? 'info' : 'success', msg);

        document.getElementById('btnFeishu').disabled = state.results.length === 0;
    } catch (e) {
        showToast('error', `加载失败: ${e.message}`);
        showRankSection('empty');
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
function showRankSection(name) {
    const sections = { loading: 'loadingSection', results: 'resultsSection', empty: 'emptyState' };
    document.getElementById('statsBar').style.display = name === 'results' ? '' : 'none';
    for (const [key, id] of Object.entries(sections))
        document.getElementById(id).style.display = key === name ? '' : 'none';
}

function updateStats(total, date) {
    document.getElementById('statTotal').textContent = total;
    document.getElementById('statTime').textContent = date;
    const cats = new Set(state.results.map(r => r.category));
    document.getElementById('statCategories').textContent = cats.size;
}

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
