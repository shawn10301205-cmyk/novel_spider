/**
 * 小说排行榜前端 - Material 3 磨砂玻璃风格
 */

// ============================================================
// 状态管理
// ============================================================
const state = {
    gender: '',
    period: '',
    sort: 'rank',
    selectedCategories: [],
    categories: [],
    results: [],
    loading: false,
};

// ============================================================
// 初始化
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    loadCategories();
    // 恢复主题
    const saved = localStorage.getItem('theme');
    if (saved === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
    }
});

// ============================================================
// API 调用
// ============================================================
const API_BASE = '';

async function api(path, options = {}) {
    const resp = await fetch(`${API_BASE}${path}`, options);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return resp.json();
}

async function loadCategories() {
    try {
        const res = await api('/api/categories');
        state.categories = res.data || [];
        renderCategoryChips();
    } catch (e) {
        console.error('加载分类失败:', e);
        document.getElementById('categoryChips').innerHTML =
            '<span class="loading-text">分类加载失败，请刷新重试</span>';
    }
}

async function doScrape() {
    if (state.loading) return;
    state.loading = true;

    const btn = document.getElementById('btnScrape');
    btn.classList.add('loading');
    btn.disabled = true;
    showSection('loading');
    updateLoadingMsg('正在抓取排行榜数据...');

    const params = new URLSearchParams();
    if (state.gender) params.set('gender', state.gender);
    if (state.period) params.set('period', state.period);
    if (state.sort) params.set('sort', state.sort);
    if (state.selectedCategories.length > 0) {
        params.set('category', state.selectedCategories.join(','));
    }

    const startTime = Date.now();

    try {
        const res = await api(`/api/scrape?${params.toString()}`);
        state.results = res.data || [];
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

        updateStats(state.results.length, elapsed);
        renderResults(state.results);
        showSection('results');
        showToast('success', `成功抓取 ${state.results.length} 条数据`);

        // 启用飞书按钮
        document.getElementById('btnFeishu').disabled = state.results.length === 0;
    } catch (e) {
        console.error('抓取失败:', e);
        showToast('error', `抓取失败: ${e.message}`);
        showSection('empty');
    } finally {
        state.loading = false;
        btn.classList.remove('loading');
        btn.disabled = false;
    }
}

async function pushFeishu() {
    if (state.results.length === 0) {
        showToast('error', '没有可推送的数据');
        return;
    }

    const btn = document.getElementById('btnFeishu');
    btn.classList.add('loading');
    btn.disabled = true;

    try {
        const res = await api('/api/feishu/push', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ data: state.results, clear: true }),
        });

        if (res.code === 0) {
            showToast('success', '已成功推送到飞书多维表格');
        } else {
            showToast('error', res.msg || '推送失败');
        }
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
function selectChip(el, type) {
    // 同组内单选
    const group = el.parentElement;
    group.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
    el.classList.add('active');
    state[type] = el.dataset.value;

    // 频道变化时更新分类显示
    if (type === 'gender') {
        renderCategoryChips();
    }
}

function toggleCategory(el) {
    const name = el.dataset.name;
    el.classList.toggle('active');

    if (el.classList.contains('active')) {
        if (!state.selectedCategories.includes(name)) {
            state.selectedCategories.push(name);
        }
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

// ============================================================
// 渲染
// ============================================================
function renderCategoryChips() {
    const container = document.getElementById('categoryChips');
    let cats = state.categories;

    // 按频道筛选
    if (state.gender) {
        cats = cats.filter(c => c.gender === state.gender);
    }

    // 去重
    const seen = new Set();
    const unique = [];
    for (const cat of cats) {
        if (!seen.has(cat.name)) {
            seen.add(cat.name);
            unique.push(cat);
        }
    }

    if (unique.length === 0) {
        container.innerHTML = '<span class="loading-text">暂无分类</span>';
        return;
    }

    container.innerHTML = unique.map(cat => {
        const isActive = state.selectedCategories.includes(cat.name);
        return `<button class="cat-chip ${isActive ? 'active' : ''}" 
                    data-name="${cat.name}" 
                    onclick="toggleCategory(this)">${cat.name}</button>`;
    }).join('');
}

function renderResults(data) {
    const container = document.getElementById('resultsContainer');

    if (!data || data.length === 0) {
        container.innerHTML = '';
        return;
    }

    // 按分类分组
    const groups = {};
    for (const item of data) {
        const key = item.category || '未分类';
        if (!groups[key]) groups[key] = [];
        groups[key].push(item);
    }

    let html = '';
    let delay = 0;

    for (const [category, novels] of Object.entries(groups)) {
        html += `
        <div class="category-group fade-in" style="animation-delay: ${delay}ms">
            <div class="category-group-header">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                    <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                <h3>${escapeHtml(category)}</h3>
                <span class="badge">${novels.length}本</span>
            </div>
            <div class="novel-list">`;

        for (const novel of novels) {
            delay += 30;
            html += renderNovelCard(novel, delay);
        }

        html += `</div></div>`;
        delay += 50;
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
    const sections = {
        loading: 'loadingSection',
        results: 'resultsSection',
        empty: 'emptyState',
    };

    // 显示统计条
    document.getElementById('statsBar').style.display = name === 'results' ? '' : 'none';

    for (const [key, id] of Object.entries(sections)) {
        document.getElementById(id).style.display = key === name ? '' : 'none';
    }
}

function updateStats(total, elapsed) {
    document.getElementById('statTotal').textContent = total;
    document.getElementById('statTime').textContent = `${elapsed}s`;

    // 计算分类数
    const cats = new Set(state.results.map(r => r.category));
    document.getElementById('statCategories').textContent = cats.size;
}

function updateLoadingMsg(msg) {
    document.getElementById('loadingMsg').textContent = msg;
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

    // 自动移除
    setTimeout(() => {
        toast.classList.add('toast-exit');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
