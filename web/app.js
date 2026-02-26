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
    sort: 'heat',
    selectedCategories: [],
    categories: [],
    sources: [],
    results: [],
    loading: false,
    cached: false,
    date: '',
    currentTab: 'dashboard',
    dashboard: null,
    _cache: {},  // 浏览器端 API 缓存
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

    // 排序切换 - 立即客户端重排不重新请求
    const sortSel = document.getElementById('sortSelect');
    if (sortSel) {
        sortSel.value = state.sort; // 默认按热度
        sortSel.addEventListener('change', () => {
            state.sort = sortSel.value;
            if (state.results.length > 0) {
                renderResults(state.results);
            }
        });
    }

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

    if (tab === 'rank') {
        document.getElementById('dataDisplaySection').style.display = '';
        document.getElementById('emptyState').style.display = 'none';
        // 有缓存直接渲染，不重新请求
        loadCategoryRankInline();
        if (state.results.length === 0) {
            switchDataView('category');
        }
    }
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

        // 显示飞书群通知结果
        if (res.notified) {
            showToast('success', '已自动通知飞书群');
        }
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
    renderHeatRank(data.heat_rank_male || [], data.heat_rank_female || []);
    renderCrossPlatform(data.cross_platform);
}

function renderHeatRank(maleBooks, femaleBooks) {
    renderHeatCol('heatRankMale', maleBooks);
    renderHeatCol('heatRankFemale', femaleBooks);
}

function renderHeatCol(containerId, books) {
    const el = document.getElementById(containerId);
    if (!el) return;
    if (books.length === 0) {
        el.innerHTML = '<div class="heat-empty">暂无热度数据</div>';
        return;
    }
    let html = '';
    books.forEach((b, idx) => {
        const rankClass = idx < 3 ? `heat-rank-top heat-rank-${idx + 1}` : '';
        const titleLink = b.book_url
            ? `<a href="${escapeHtml(b.book_url)}" target="_blank" rel="noopener">${escapeHtml(b.title)}</a>`
            : escapeHtml(b.title);
        const heatText = [];
        if (b.heat) heatText.push(`🔥 ${escapeHtml(b.heat)}`);
        if (b.word_count) heatText.push(`📝 ${escapeHtml(b.word_count)}`);

        html += `<div class="heat-rank-item ${rankClass}" style="animation-delay:${idx * 30}ms">
            <span class="heat-rank-num">${idx + 1}</span>
            <div class="heat-rank-info">
                <div class="heat-rank-title">${titleLink}</div>
                <div class="heat-rank-meta">${escapeHtml(b.author || '-')}${b.word_count ? ` · 📝 ${escapeHtml(b.word_count)}` : ''}</div>
            </div>
            <div class="heat-rank-heat">${b.heat ? `🔥 ${escapeHtml(b.heat.startsWith('在读') ? b.heat : '在读：' + b.heat)}` : ''}</div>
            <span class="heat-rank-tag">${escapeHtml(b.category || '-')}</span>
            <span class="tag tag-source heat-rank-source">${escapeHtml(b.source || '')}</span>
        </div>`;
    });
    el.innerHTML = html;
}

function renderSourceStats(sourceStats, total, date) {
    const grid = document.getElementById('sourceStatsGrid');
    let html = `
        <div class="dash-stat-card glass-card dash-stat-total" onclick="goToAllRank()" title="点击查看全部排行">
            <div class="dash-stat-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </div>
            <div class="dash-stat-value">${total}</div>
            <div class="dash-stat-label">总数据量</div>
            <div class="dash-stat-sub">${date}</div>
        </div>`;

    for (const [name, count] of Object.entries(sourceStats)) {
        // 根据 name 反查 source id
        const srcId = getSourceIdByName(name);
        html += `
        <div class="dash-stat-card glass-card dash-stat-clickable" onclick="goToSourceRank('${srcId}')" title="点击查看 ${escapeHtml(name)} 排行榜">
            <div class="dash-stat-icon dash-stat-icon-source">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" stroke="currentColor" stroke-width="2"/></svg>
            </div>
            <div class="dash-stat-value">${count}</div>
            <div class="dash-stat-label">${escapeHtml(name)}</div>
            <div class="dash-stat-sub">点击查看排行 →</div>
        </div>`;
    }

    grid.innerHTML = html;
}

function getSourceIdByName(name) {
    const src = state.sources.find(s => s.name === name);
    return src ? src.id : '';
}

// 跳转到排行榜 Tab 并加载指定数据源
function goToSourceRank(sourceId) {
    switchTab('rank');
    // 选中对应的数据源 chip
    state.source = sourceId;
    const chips = document.querySelectorAll('#sourceChips .chip');
    chips.forEach(c => {
        c.classList.toggle('active', c.dataset.value === sourceId);
    });
    doScrape();
}

function goToAllRank() {
    switchTab('rank');
    state.source = '';
    const chips = document.querySelectorAll('#sourceChips .chip');
    chips.forEach(c => {
        c.classList.toggle('active', c.dataset.value === '');
    });
    doScrape();
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

// 分类详情弹窗 — 按在读/热度排行前10
async function openCategoryDetail(category) {
    hideBarTooltip();
    const modal = document.getElementById('categoryModal');
    const title = document.getElementById('modalCategoryTitle');
    const body = document.getElementById('modalCategoryBody');

    title.textContent = `${category} · 在读排行`;
    body.innerHTML = '<div class="modal-loading"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" class="spin"><path d="M21 12a9 9 0 1 1-6.22-8.56" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg> 加载中...</div>';
    modal.style.display = 'flex';

    try {
        const res = await api(`/api/category-books?category=${encodeURIComponent(category)}&sort=heat&limit=10`);
        const books = res.data || [];
        const total = res.total || 0;

        if (books.length === 0) {
            body.innerHTML = '<div class="modal-empty">暂无数据</div>';
            return;
        }

        let html = `<div class="modal-stats">共 <strong>${total}</strong> 本 · 展示热度 Top <strong>${books.length}</strong> · 来自 <strong>${new Set(books.map(b => b.source)).size}</strong> 个平台</div>`;
        html += '<div class="modal-heat-rank-list">';

        books.forEach((b, idx) => {
            const rankClass = idx < 3 ? `heat-rank-top heat-rank-${idx + 1}` : '';
            const titleLink = b.book_url
                ? `<a href="${escapeHtml(b.book_url)}" target="_blank" rel="noopener">${escapeHtml(b.title)}</a>`
                : escapeHtml(b.title);

            const extra = b.extra || {};
            const heatDisplay = extra.heat
                ? `🔥 ${escapeHtml(extra.heat.startsWith('在读') ? extra.heat : '在读：' + extra.heat)}`
                : '';
            const genderClass = b.gender === '男频' ? 'tag-gender-male' : 'tag-gender-female';

            html += `<div class="heat-rank-item ${rankClass}" style="animation-delay:${idx * 40}ms">
                <span class="heat-rank-num">${idx + 1}</span>
                <div class="heat-rank-info">
                    <div class="heat-rank-title">${titleLink}</div>
                    <div class="heat-rank-meta">${escapeHtml(b.author || '-')}${extra.word_count ? ` · 📝 ${escapeHtml(extra.word_count)}` : ''}</div>
                </div>
                <div class="heat-rank-heat">${heatDisplay}</div>
                <span class="tag ${genderClass}" style="margin-right:4px">${escapeHtml(b.gender || '-')}</span>
                <span class="tag tag-source heat-rank-source">${escapeHtml(b.source || '')}</span>
            </div>`;
        });

        html += '</div>';

        // 如果总数超过10，添加"查看全部"按钮
        if (total > 10) {
            html += `<div class="modal-show-all">
                <button class="btn btn-outline btn-sm" onclick="openCategoryAll('${escapeHtml(category)}')">
                    查看全部 ${total} 本 →
                </button>
            </div>`;
        }

        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<div class="modal-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
}

// 查看某分类全部书籍（按热度排序）
async function openCategoryAll(category) {
    const title = document.getElementById('modalCategoryTitle');
    const body = document.getElementById('modalCategoryBody');

    title.textContent = `${category} · 全部书籍`;
    body.innerHTML = '<div class="modal-loading"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" class="spin"><path d="M21 12a9 9 0 1 1-6.22-8.56" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg> 加载中...</div>';

    try {
        const res = await api(`/api/category-books?category=${encodeURIComponent(category)}&sort=heat`);
        const books = res.data || [];

        if (books.length === 0) {
            body.innerHTML = '<div class="modal-empty">暂无数据</div>';
            return;
        }

        let html = `<div class="modal-stats">共 <strong>${books.length}</strong> 本 · 来自 <strong>${new Set(books.map(b => b.source)).size}</strong> 个平台 · 按在读热度排序</div>`;
        html += `<div class="modal-back-btn"><button class="btn btn-outline btn-sm" onclick="openCategoryDetail('${escapeHtml(category)}')">← 返回 Top 10</button></div>`;
        html += '<div class="modal-book-list">';

        for (const [idx, book] of books.entries()) {
            const bookLink = book.book_url
                ? `<a href="${escapeHtml(book.book_url)}" target="_blank" rel="noopener">${escapeHtml(book.title)}</a>`
                : escapeHtml(book.title);
            const genderClass = book.gender === '男频' ? 'tag-gender-male' : 'tag-gender-female';
            const extra = book.extra || {};
            const extraParts = [];
            if (extra.heat) extraParts.push(`🔥 ${escapeHtml(extra.heat)}`);
            if (extra.word_count) extraParts.push(`📝 ${escapeHtml(extra.word_count)}`);
            if (extra.status) extraParts.push(escapeHtml(extra.status));
            const extraLine = extraParts.length ? `<div class="novel-extra">${extraParts.join(' · ')}</div>` : '';

            html += `<div class="modal-book-card glass-card">
                <div class="modal-book-rank">${idx + 1}</div>
                <div class="modal-book-info">
                    <div class="modal-book-title">${bookLink}</div>
                    <div class="modal-book-meta">
                        <span>✍ ${escapeHtml(book.author || '未知作者')}</span>
                    </div>
                    ${extraLine}
                </div>
                <div class="modal-book-tags">
                    <span class="tag ${genderClass}">${escapeHtml(book.gender || '-')}</span>
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

// 分类排行弹窗 — 按各分类在读前10累加倒排
async function openCategoryRankModal() {
    const modal = document.getElementById('categoryModal');
    const title = document.getElementById('modalCategoryTitle');
    const body = document.getElementById('modalCategoryBody');

    title.textContent = '分类热度排行';
    body.innerHTML = '<div class="modal-loading"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" class="spin"><path d="M21 12a9 9 0 1 1-6.22-8.56" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg> 计算中...</div>';
    modal.style.display = 'flex';

    try {
        const res = await api('/api/category-rank');
        const categories = res.data || [];

        if (categories.length === 0) {
            body.innerHTML = '<div class="modal-empty">暂无数据</div>';
            return;
        }

        const maxHeat = categories[0].total_heat || 1;

        let html = `<div class="modal-stats">共 <strong>${categories.length}</strong> 个分类 · 按在读 Top10 累加热度排序</div>`;
        html += '<div class="cat-rank-list">';

        categories.forEach((cat, idx) => {
            const pct = (cat.total_heat / maxHeat * 100).toFixed(1);
            const rankClass = idx < 3 ? `cat-rank-top cat-rank-${idx + 1}` : '';
            const heatDisplay = cat.total_heat >= 10000
                ? (cat.total_heat / 10000).toFixed(1) + '万'
                : Math.round(cat.total_heat).toLocaleString();

            // Top10 书籍预览
            let booksHtml = '';
            if (cat.top10 && cat.top10.length > 0) {
                booksHtml = '<div class="cat-rank-books" style="display:none">';
                cat.top10.forEach((b, bi) => {
                    const heatVal = b.heat || '';
                    const titleLink = b.book_url
                        ? `<a href="${escapeHtml(b.book_url)}" target="_blank" rel="noopener">${escapeHtml(b.title)}</a>`
                        : escapeHtml(b.title);
                    booksHtml += `<div class="cat-rank-book-item">
                        <span class="cat-rank-book-idx">${bi + 1}</span>
                        <span class="cat-rank-book-title">${titleLink}</span>
                        <span class="cat-rank-book-author">${escapeHtml(b.author || '')}</span>
                        <span class="cat-rank-book-heat">${heatVal ? '🔥' + escapeHtml(heatVal) : ''}</span>
                        <span class="tag tag-source" style="font-size:0.65rem">${escapeHtml(b.source || '')}</span>
                    </div>`;
                });
                booksHtml += '</div>';
            }

            html += `<div class="cat-rank-item ${rankClass}" style="animation-delay:${idx * 30}ms">
                <div class="cat-rank-header" onclick="toggleCatBooks(this)">
                    <span class="cat-rank-num">${idx + 1}</span>
                    <div class="cat-rank-info">
                        <div class="cat-rank-name">${escapeHtml(cat.category)}</div>
                        <div class="cat-rank-bar-track">
                            <div class="cat-rank-bar-fill" style="width:${pct}%"></div>
                        </div>
                    </div>
                    <div class="cat-rank-meta">
                        <span class="cat-rank-heat">🔥 ${heatDisplay}</span>
                        <span class="cat-rank-count">${cat.book_count}本</span>
                    </div>
                    <span class="cat-rank-expand">▸</span>
                </div>
                ${booksHtml}
            </div>`;
        });

        html += '</div>';
        body.innerHTML = html;
    } catch (e) {
        body.innerHTML = `<div class="modal-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
}

// 分类排行 — 内联加载到页面（带缓存）
async function loadCategoryRankInline() {
    const section = document.getElementById('categoryRankInline');
    const content = document.getElementById('categoryRankContent');

    section.style.display = 'block';

    // 有缓存直接渲染，不重新请求
    if (state._cache.categoryRank) {
        _renderCategoryRank(state._cache.categoryRank);
        return;
    }

    content.innerHTML = '<div class="modal-loading"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" class="spin"><path d="M21 12a9 9 0 1 1-6.22-8.56" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg> 计算中...</div>';

    try {
        const res = await api('/api/category-rank');
        const categories = res.data || [];

        if (categories.length === 0) {
            content.innerHTML = '<div class="modal-empty">暂无数据</div>';
            return;
        }

        state._cache.categoryRank = categories;
        _renderCategoryRank(categories);
    } catch (e) {
        content.innerHTML = `<div class="modal-empty">加载失败: ${escapeHtml(e.message)}</div>`;
    }
}

// 渲染分类排行列表
function _renderCategoryRank(categories) {
    const content = document.getElementById('categoryRankContent');
    const badge = document.getElementById('catRankBadge');
    const statCat = document.getElementById('statCategories');

    if (badge) badge.textContent = categories.length;
    if (statCat) statCat.textContent = categories.length;
    const maxHeat = categories[0].total_heat || 1;

    let html = '<div class="cat-rank-list">';

    categories.forEach((cat, idx) => {
        const pct = (cat.total_heat / maxHeat * 100).toFixed(1);
        const rankClass = idx < 3 ? `cat-rank-top cat-rank-${idx + 1}` : '';
        const heatDisplay = cat.total_heat >= 10000
            ? (cat.total_heat / 10000).toFixed(1) + '万'
            : Math.round(cat.total_heat).toLocaleString();

        let booksHtml = '';
        if (cat.top10 && cat.top10.length > 0) {
            booksHtml = '<div class="cat-rank-books" style="display:none">';
            cat.top10.forEach((b, bi) => {
                if (!b.title) return; // 跳过空标题
                const heatVal = b.heat || '';
                const safeTitle = escapeHtml(b.title).replace(/'/g, "\\'");
                const safeSource = escapeHtml(b.source || '').replace(/'/g, "\\'");
                booksHtml += `<div class="cat-rank-book-item" style="cursor:pointer" onclick="openNovelTrend('${safeTitle}', '${safeSource}')">
                    <span class="cat-rank-book-idx">${bi + 1}</span>
                    <span class="cat-rank-book-title">${escapeHtml(b.title)}</span>
                    <span class="cat-rank-book-author">${escapeHtml(b.author || '')}</span>
                    <span class="cat-rank-book-heat">${heatVal ? '🔥' + escapeHtml(heatVal) : ''}</span>
                    <span class="tag tag-source" style="font-size:0.65rem">${escapeHtml(b.source || '')}</span>
                </div>`;
            });
            booksHtml += '</div>';
        }

        html += `<div class="cat-rank-item ${rankClass} stagger-in" style="animation-delay:${idx * 30}ms">
            <div class="cat-rank-header" onclick="toggleCatBooks(this)">
                <span class="cat-rank-num">${idx + 1}</span>
                <div class="cat-rank-info">
                    <div class="cat-rank-name">${escapeHtml(cat.category)}</div>
                    <div class="cat-rank-bar-track">
                        <div class="cat-rank-bar-fill" style="width:${pct}%"></div>
                    </div>
                </div>
                <div class="cat-rank-meta">
                    <span class="cat-rank-heat">🔥 ${heatDisplay}</span>
                    <span class="cat-rank-count">${cat.book_count}本</span>
                </div>
                <span class="cat-rank-expand">▸</span>
            </div>
            ${booksHtml}
        </div>`;
    });

    html += '</div>';
    content.innerHTML = html;
}

// 展开/收起分类下的书籍列表
function toggleCatBooks(headerEl) {
    const item = headerEl.closest('.cat-rank-item');
    const books = item.querySelector('.cat-rank-books');
    const arrow = item.querySelector('.cat-rank-expand');
    if (!books) return;
    if (books.style.display === 'none') {
        books.style.display = 'block';
        arrow.textContent = '▾';
        item.classList.add('cat-rank-expanded');
    } else {
        books.style.display = 'none';
        arrow.textContent = '▸';
        item.classList.remove('cat-rank-expanded');
    }
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

        const titleLink = book.book_url
            ? `<a href="${escapeHtml(book.book_url)}" target="_blank" rel="noopener">${escapeHtml(book.title)}</a>`
            : escapeHtml(book.title);

        html += `<div class="cross-row stagger-in" style="animation-delay:${idx * 30}ms">
            <span class="cross-col cross-col-rank">
                <span class="cross-rank ${idx < 3 ? 'cross-rank-top' : ''}">${idx + 1}</span>
            </span>
            <span class="cross-col cross-col-title">${titleLink}</span>
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
    state._cache = {}; // 清除缓存，拉取新数据后重新计算

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

        // 切换到热度视图
        switchDataView('heat');
        loadCategoryRankInline();

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

async function notifyFeishuGroup() {
    const btn = document.getElementById('btnNotifyFeishu');
    btn.classList.add('loading');
    btn.disabled = true;
    try {
        const res = await api('/api/notify', { method: 'POST' });
        showToast(res.code === 0 ? 'success' : 'error', res.msg || '操作完成');
    } catch (e) {
        showToast('error', `通知失败: ${e.message}`);
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

// ============================================================
// 设置弹窗
// ============================================================
async function openSettingsModal() {
    const modal = document.getElementById('settingsModal');
    modal.style.display = 'flex';

    try {
        const res = await api('/api/settings');
        const data = res.data || {};
        document.getElementById('settingsEnabled').checked = data.enabled || false;
        document.getElementById('settingsSyncTime').value = data.sync_time || '08:00';

        // 显示上次同步信息
        const lastSync = data.last_sync || {};
        const lastSyncRow = document.getElementById('settingsLastSync');
        if (lastSync.time) {
            lastSyncRow.style.display = 'flex';
            const statusIcon = lastSync.status === 'success' ? '✅' : '⚠️';
            document.getElementById('settingsLastSyncText').textContent =
                `${statusIcon} ${lastSync.time} · ${lastSync.total || 0}条`;
        } else {
            lastSyncRow.style.display = 'none';
        }
    } catch (e) {
        console.error('加载设置失败', e);
    }
}

function closeSettingsModal() {
    document.getElementById('settingsModal').style.display = 'none';
}

async function saveSettings() {
    const enabled = document.getElementById('settingsEnabled').checked;
    const syncTime = document.getElementById('settingsSyncTime').value;

    try {
        const res = await api('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled, sync_time: syncTime }),
        });

        if (res.code === 0) {
            showToast('success', enabled
                ? `定时同步已开启，每天 ${syncTime} 自动拉取数据`
                : '定时同步已关闭');
            closeSettingsModal();
        } else {
            showToast('error', res.msg || '保存失败');
        }
    } catch (e) {
        showToast('error', '保存失败: ' + e.message);
    }
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

    // 按热度排序时，分页显示
    if (state.sort === 'heat') {
        if (!state._heatSorted || state._heatSortedSource !== data) {
            state._heatSorted = [...data].sort((a, b) => parseHeatValue(b) - parseHeatValue(a));
            state._heatSortedSource = data;
            state.page = 1;
        }
        const sorted = state._heatSorted;
        const pageSize = 50;
        const totalPages = Math.ceil(sorted.length / pageSize);
        const page = Math.min(state.page || 1, totalPages);
        const start = (page - 1) * pageSize;
        const pageData = sorted.slice(start, start + pageSize);

        let html = '<div class="category-group fade-in"><div class="category-group-header"><svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M12 2c.5 4-3 6-3 10a5 5 0 0 0 10 0c0-4-3-6-3-10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg><h3>按热度排序</h3><span class="badge">' + sorted.length + '本</span></div>';

        // 顶部分页
        html += renderPagination(page, totalPages, sorted.length, pageSize);

        html += '<div class="novel-list">';
        pageData.forEach((novel, idx) => {
            html += renderNovelCard(novel, idx * 15, start + idx + 1);
        });
        html += '</div>';

        // 底部分页
        html += renderPagination(page, totalPages, sorted.length, pageSize);

        html += '</div>';
        container.innerHTML = html;
        // 滚动到顶部
        if (state.page > 1) container.scrollIntoView({ behavior: 'smooth', block: 'start' });
        return;
    }

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
    let globalIdx = 0;

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
            for (const novel of novels) { globalIdx++; delay += 20; html += renderNovelCard(novel, delay, globalIdx); }
            html += `</div></div>`;
            delay += 30;
        }
    }
    container.innerHTML = html;
}

// 渲染分页条
function renderPagination(page, totalPages, total, pageSize) {
    if (totalPages <= 1) return '';

    const start = (page - 1) * pageSize + 1;
    const end = Math.min(page * pageSize, total);

    let html = '<div class="pagination">';
    html += `<span class="pagination-info">第 ${start}-${end} 条，共 ${total} 条</span>`;
    html += '<div class="pagination-btns">';

    // 上一页
    html += `<button class="btn btn-outline btn-sm" ${page <= 1 ? 'disabled' : ''} onclick="goPage(${page - 1})">← 上一页</button>`;

    // 页码
    const range = getPageRange(page, totalPages);
    for (const p of range) {
        if (p === '...') {
            html += '<span class="pagination-dot">…</span>';
        } else {
            html += `<button class="btn btn-sm ${p === page ? 'btn-primary' : 'btn-outline'}" onclick="goPage(${p})">${p}</button>`;
        }
    }

    // 下一页
    html += `<button class="btn btn-outline btn-sm" ${page >= totalPages ? 'disabled' : ''} onclick="goPage(${page + 1})">下一页 →</button>`;

    html += '</div></div>';
    return html;
}

// 计算显示哪些页码（1 ... 4 5 6 ... 20）
function getPageRange(current, total) {
    if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
    const pages = [];
    pages.push(1);
    if (current > 3) pages.push('...');
    for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
        pages.push(i);
    }
    if (current < total - 2) pages.push('...');
    pages.push(total);
    return pages;
}

// 翻页
function goPage(p) {
    state.page = p;
    renderResults(state.results);
}

// 解析热度值为数字，用于排序
function parseHeatValue(novel) {
    const extra = novel.extra || {};
    const heat = extra.heat || '';
    if (!heat) return 0;
    // 格式: "169.4万", "在读：3.2万", "在读：6388"
    const cleaned = heat.replace(/^[^0-9.]*/, ''); // 去掉开头非数字
    const match = cleaned.match(/([\d.]+)\s*(万)?/);
    if (!match) return 0;
    let val = parseFloat(match[1]) || 0;
    if (match[2] === '万') val *= 10000;
    return val;
}

function renderNovelCard(novel, delay, globalRank) {
    const displayRank = globalRank || novel.rank;
    const rankClass = displayRank <= 3 ? `rank-${displayRank}` : 'rank-other';
    const genderClass = novel.gender === '男频' ? 'tag-gender-male' : 'tag-gender-female';
    const bookUrl = novel.book_url || '#';
    const titleLink = bookUrl !== '#'
        ? `<a href="${escapeHtml(bookUrl)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${escapeHtml(novel.title)}</a>`
        : escapeHtml(novel.title);

    const extra = novel.extra || {};

    // 在读热度 — 突出显示
    let heatHtml = '';
    if (extra.heat) {
        heatHtml = `<span class="novel-heat-badge">🔥 在读 ${escapeHtml(extra.heat)}</span>`;
    }

    // 辅助信息 — 弱化
    let subParts = [];
    if (extra.word_count) subParts.push(`📝 ${escapeHtml(extra.word_count)}`);
    if (extra.status) subParts.push(escapeHtml(extra.status));
    const subHtml = subParts.length > 0 ? `<span class="novel-extra-sub">${subParts.join(' · ')}</span>` : '';

    const safeTitle = escapeHtml(novel.title).replace(/'/g, "\\'");
    const safeSource = escapeHtml(novel.source || '').replace(/'/g, "\\'");

    return `
    <div class="novel-card glass-card stagger-in" style="animation-delay: ${delay}ms" onclick="openNovelTrend('${safeTitle}', '${safeSource}')">
        <div class="rank-badge ${rankClass}">${displayRank}</div>
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
                ${subHtml}
            </div>
            ${heatHtml}
            <div class="trend-hint">📈 点击查看热度趋势</div>
        </div>
        <div class="novel-tags">
            <span class="tag ${genderClass}">${escapeHtml(novel.gender || '-')}</span>
            ${novel.source ? `<span class="tag tag-source">${escapeHtml(novel.source)}</span>` : ''}
        </div>
    </div>`;
}

// ============================================================
// 辅助
// ============================================================
function showRankSection(name) {
    const sections = { loading: 'loadingSection', results: 'dataDisplaySection', empty: 'emptyState' };
    document.getElementById('statsBar').style.display = name === 'results' ? '' : 'none';
    for (const [key, id] of Object.entries(sections))
        document.getElementById(id).style.display = key === name ? '' : 'none';
}

function switchDataView(view) {
    const catView = document.getElementById('categoryRankInline');
    const heatView = document.getElementById('resultsSection');
    const catChip = document.getElementById('chipCategoryRank');

    if (view === 'category') {
        catView.style.display = '';
        heatView.style.display = 'none';
        if (catChip) catChip.classList.add('active');
    } else {
        catView.style.display = 'none';
        heatView.style.display = '';
        if (catChip) catChip.classList.remove('active');
    }
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

// ============================================================
// 热度趋势弹窗
// ============================================================
async function openNovelTrend(title, sourceName) {
    const modal = document.getElementById('trendModal');
    const modalTitle = document.getElementById('trendModalTitle');
    const body = document.getElementById('trendModalBody');

    // 保存当前打开的小说信息
    window._trendNovelTitle = title;
    window._trendNovelSource = sourceName;

    modalTitle.textContent = `${title} · 热度趋势`;
    body.innerHTML = '<div class="modal-loading"><svg width="32" height="32" viewBox="0 0 24 24" fill="none" class="spin"><path d="M21 12a9 9 0 1 1-6.22-8.56" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg> 加载中...</div>';
    modal.style.display = 'flex';

    try {
        const res = await api(`/api/novel/trend?title=${encodeURIComponent(title)}&limit=30`);
        const data = res.data || [];

        if (data.length === 0) {
            body.innerHTML = `<div class="trend-no-data">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none"><path d="M23 6l-9.5 9.5-5-5L1 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
                <p>暂无历史数据，请先拉取数据</p>
            </div>`;
            return;
        }

        // 按日期正序
        const sorted = [...data].reverse();

        // 汇总信息
        const latestHeat = sorted[sorted.length - 1];
        const firstHeat = sorted[0];
        const maxHeatValue = Math.max(...sorted.map(d => d.heat_value));
        const minHeatValue = Math.min(...sorted.filter(d => d.heat_value > 0).map(d => d.heat_value));

        const formatHeat = (v) => v >= 10000 ? (v / 10000).toFixed(1) + '万' : Math.round(v).toLocaleString();

        let html = `<div class="trend-summary">`;
        html += `<div class="trend-summary-item"><span class="trend-summary-label">最新热度</span><span class="trend-summary-value">🔥 ${escapeHtml(latestHeat.heat || '-')}</span></div>`;
        html += `<div class="trend-summary-item"><span class="trend-summary-label">数据天数</span><span class="trend-summary-value">${sorted.length} 天</span></div>`;
        html += `<div class="trend-summary-item"><span class="trend-summary-label">最高热度</span><span class="trend-summary-value">${formatHeat(maxHeatValue)}</span></div>`;
        if (sorted.length > 1) {
            const diff = latestHeat.heat_value - firstHeat.heat_value;
            const arrow = diff >= 0 ? '↑' : '↓';
            const color = diff >= 0 ? '#22C55E' : '#EF4444';
            html += `<div class="trend-summary-item"><span class="trend-summary-label">变化</span><span class="trend-summary-value" style="color:${color}">${arrow} ${formatHeat(Math.abs(diff))}</span></div>`;
        }
        html += `<div class="trend-summary-item"><span class="trend-summary-label">分类</span><span class="trend-summary-value">${escapeHtml(latestHeat.category || '-')}</span></div>`;
        html += `</div>`;

        // 查找书籍链接（从最新数据中取）
        let bookUrl = '';
        for (const d of data) {
            // 尝试从 raw 数据获取 book_url
            if (d.book_url) { bookUrl = d.book_url; break; }
        }

        // 查看书本按钮
        if (bookUrl) {
            html = `<div class="trend-action-bar"><a href="${escapeHtml(bookUrl)}" target="_blank" rel="noopener" class="btn btn-primary btn-sm">📖 查看书本</a></div>` + html;
        }

        // 图表容器
        html += `<div class="trend-chart-wrap"><canvas id="trendCanvas" width="660" height="280"></canvas></div>`;

        // 数据表格
        html += `<div style="max-height:240px;overflow-y:auto">`;
        html += `<table class="trend-data-table"><thead><tr><th>日期</th><th>热度</th><th>排名</th><th>平台</th><th>频道</th></tr></thead><tbody>`;
        for (const d of [...sorted].reverse()) {
            html += `<tr>
                <td>${escapeHtml(d.date)}</td>
                <td class="heat-cell">${escapeHtml(d.heat || '-')}</td>
                <td class="rank-cell">#${d.rank}</td>
                <td>${escapeHtml(d.source_name || d.source)}</td>
                <td>${escapeHtml(d.gender || '-')}</td>
            </tr>`;
        }
        html += `</tbody></table></div>`;

        body.innerHTML = html;

        // 绘制图表
        requestAnimationFrame(() => drawTrendChart(sorted));
    } catch (e) {
        body.innerHTML = `<div class="trend-no-data">加载失败: ${escapeHtml(e.message)}</div>`;
    }
}

function closeTrendModal() {
    document.getElementById('trendModal').style.display = 'none';
}

function drawTrendChart(data) {
    const canvas = document.getElementById('trendCanvas');
    if (!canvas) return;

    const dpr = window.devicePixelRatio || 1;
    const displayWidth = 660;
    const displayHeight = 280;
    canvas.width = displayWidth * dpr;
    canvas.height = displayHeight * dpr;
    canvas.style.width = displayWidth + 'px';
    canvas.style.height = displayHeight + 'px';

    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);

    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const textColor = isDark ? '#CAC4D0' : '#49454F';
    const gridColor = isDark ? 'rgba(202,196,208,0.15)' : 'rgba(0,0,0,0.06)';
    const lineColor = '#6750A4';
    const fillColor = isDark ? 'rgba(208,188,255,0.15)' : 'rgba(103,80,164,0.1)';
    const dotColor = '#6750A4';
    const dotHoverColor = '#D0BCFF';

    // 边距
    const pad = { top: 20, right: 20, bottom: 40, left: 60 };
    const w = displayWidth - pad.left - pad.right;
    const h = displayHeight - pad.top - pad.bottom;

    const values = data.map(d => d.heat_value);
    const maxVal = Math.max(...values) * 1.1 || 1;
    const minVal = Math.min(...values.filter(v => v > 0)) * 0.9;
    const range = maxVal - minVal || 1;

    // 清空
    ctx.clearRect(0, 0, displayWidth, displayHeight);

    // 网格线
    ctx.strokeStyle = gridColor;
    ctx.lineWidth = 1;
    const gridLines = 5;
    for (let i = 0; i <= gridLines; i++) {
        const y = pad.top + (h / gridLines) * i;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(pad.left + w, y);
        ctx.stroke();

        // Y轴标签
        const val = maxVal - (range / gridLines) * i;
        ctx.fillStyle = textColor;
        ctx.font = '11px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'middle';
        const label = val >= 10000 ? (val / 10000).toFixed(1) + '万' : Math.round(val).toString();
        ctx.fillText(label, pad.left - 8, y);
    }

    if (data.length < 2) {
        // 只有1天数据，画单点
        const x = pad.left + w / 2;
        const y = pad.top + h / 2;
        ctx.beginPath();
        ctx.arc(x, y, 6, 0, Math.PI * 2);
        ctx.fillStyle = dotColor;
        ctx.fill();

        ctx.fillStyle = textColor;
        ctx.font = '12px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(data[0].date, x, displayHeight - 10);
        return;
    }

    // 计算坐标点
    const points = data.map((d, i) => ({
        x: pad.left + (w / (data.length - 1)) * i,
        y: pad.top + h - ((d.heat_value - minVal) / range) * h,
        label: d.date,
        heat: d.heat,
        value: d.heat_value,
    }));

    // 填充区域
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
        const prev = points[i - 1];
        const curr = points[i];
        const cpx = (prev.x + curr.x) / 2;
        ctx.bezierCurveTo(cpx, prev.y, cpx, curr.y, curr.x, curr.y);
    }
    ctx.lineTo(points[points.length - 1].x, pad.top + h);
    ctx.lineTo(points[0].x, pad.top + h);
    ctx.closePath();
    ctx.fillStyle = fillColor;
    ctx.fill();

    // 线条
    ctx.beginPath();
    ctx.moveTo(points[0].x, points[0].y);
    for (let i = 1; i < points.length; i++) {
        const prev = points[i - 1];
        const curr = points[i];
        const cpx = (prev.x + curr.x) / 2;
        ctx.bezierCurveTo(cpx, prev.y, cpx, curr.y, curr.x, curr.y);
    }
    ctx.strokeStyle = lineColor;
    ctx.lineWidth = 2.5;
    ctx.stroke();

    // 数据点
    for (const p of points) {
        ctx.beginPath();
        ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
        ctx.fillStyle = '#fff';
        ctx.fill();
        ctx.strokeStyle = dotColor;
        ctx.lineWidth = 2;
        ctx.stroke();
    }

    // X轴日期标签（显示部分）
    ctx.fillStyle = textColor;
    ctx.font = '10px "Noto Sans SC", sans-serif';
    ctx.textAlign = 'center';
    const step = Math.max(1, Math.floor(points.length / 8));
    for (let i = 0; i < points.length; i += step) {
        const dateStr = points[i].label.slice(5); // MM-DD
        ctx.fillText(dateStr, points[i].x, displayHeight - 10);
    }
    // 始终显示最后一天
    if ((points.length - 1) % step !== 0) {
        const last = points[points.length - 1];
        ctx.fillText(last.label.slice(5), last.x, displayHeight - 10);
    }
}
