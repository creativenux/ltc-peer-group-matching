/* Peer group matching: web interface.
   Talks only to the FastAPI backend (/api/...), which reads and writes /output/. */

const METHODS = {
  weighted_gower: 'Weighted Gower',
  unweighted_gower: 'Unweighted Gower',
  single_age_band: 'Age band only',
  single_primary_support_goal: 'Support goal only',
  random: 'Random',
};
const REFERENCE = 'weighted_gower';
const ATTRIBUTES = {
  primary_condition_subtype: 'Condition sub-type',
  primary_support_goal: 'Support goal',
  support_orientation: 'Support orientation',
  age_band: 'Age band',
  condition_duration_band: 'Time lived with the condition',
  psychosocial_isolation_score: 'Isolation level',
  gender: 'Gender',
  engagement_level: 'Engagement level',
};
const PROFILE_FIELDS = [
  ['profile_id', 'Profile'], ['age_band', 'Age band'], ['gender', 'Gender'],
  ['communication_language', 'Language'], ['primary_condition_category', 'Condition category'],
  ['primary_condition_subtype', 'Condition sub-type'], ['comorbidities', 'Other conditions'],
  ['condition_duration_band', 'Years with condition'], ['primary_support_goal', 'Support goal'],
  ['support_orientation', 'Support orientation'], ['engagement_level', 'Engagement'],
  ['psychosocial_isolation_score', 'Isolation score'], ['lives_alone', 'Lives alone'],
  ['imd_quintile', 'Deprivation quintile'],
];
const TEAL = '#0F6E6E', OCHRE = '#B7791F', INK = '#17212B';
const MATCH_LIMIT = 10000;

const state = { datasets: [], runs: [], evaluations: [], readOnly: false, current: null, charts: [], poll: null };
const $ = (sel, root = document) => root.querySelector(sel);
const view = () => $('#view');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
const fmt = (x, d = 3) => (x === null || x === undefined || Number.isNaN(x)) ? 'n/a' : Number(x).toFixed(d);
const pText = p => (p < 0.001 ? '< 0.001' : p.toFixed(3));
const label = s => String(s).replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase());

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' }, ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map(d => d.msg).join('; ') : data.detail;
    throw new Error(detail || `Request failed (${res.status}).`);
  }
  return data;
}

function notice(message, kind = 'ok') {
  const cls = { ok: 'pill-ok', warn: 'pill-warn', bad: 'pill-bad' }[kind];
  $('#notice').innerHTML = message ? `<p class="mb-4"><span class="pill ${cls}">${esc(message)}</span></p>` : '';
}

function destroyCharts() {
  state.charts.forEach(c => c.destroy());
  state.charts = [];
}

const isMatched = () => state.current && state.runs.some(r => r.n === state.current.n && r.seed === state.current.seed);
const key = d => `${d.n}:${d.seed}`;
const cur = () => state.current;

function header(title, lede) {
  return `<h2 class="section-title">${esc(title)}</h2><p class="lede">${lede}</p>`;
}

function emptyState(message, actionLabel, actionId) {
  return `<div class="block"><p class="mb-3">${message}</p>${actionLabel ? `<button id="${actionId}" class="btn btn-primary">${esc(actionLabel)}</button>` : ''}</div>`;
}

// ---------------------------------------------------------------------------
// State and top bar
// ---------------------------------------------------------------------------

async function loadState(preferred) {
  const s = await api('/api/state');
  Object.assign(state, { datasets: s.datasets, runs: s.matching_runs, evaluations: s.evaluations, readOnly: s.read_only });
  applyReadOnly();
  const select = $('#dataset-select');
  if (!state.datasets.length) {
    select.innerHTML = '<option value="">No datasets yet</option>';
    state.current = null;
  } else {
    select.innerHTML = state.datasets.map(d =>
      `<option value="${key(d)}">${d.n.toLocaleString()} profiles, seed ${d.seed}</option>`).join('');
    const wanted = preferred || state.current || state.datasets.find(d => d.n === 3000 && d.seed === 42) || state.datasets[0];
    const found = state.datasets.find(d => key(d) === key(wanted)) || state.datasets[0];
    state.current = { n: found.n, seed: found.seed };
    select.value = key(found);
  }
  updateMatchStatus();
}

// View-only version (online): hide every control that generates data or runs anything.
function applyReadOnly() {
  $('#new-dataset').classList.toggle('hidden', state.readOnly);
  $('#read-only-note').classList.toggle('hidden', !state.readOnly);
}

function updateMatchStatus() {
  const status = $('#match-status'), button = $('#run-matching');
  if (!cur()) { status.textContent = ''; button.classList.add('hidden'); return; }
  if (state.readOnly) {
    status.innerHTML = isMatched() ? '<span class="pill pill-ok">Matched</span>' : '';
    button.classList.add('hidden');
    return;
  }
  if (isMatched()) {
    status.innerHTML = '<span class="pill pill-ok">Matched</span>';
    button.classList.remove('hidden');
    button.textContent = 'Run matching again';
    button.classList.remove('btn-primary');
  } else {
    status.innerHTML = '<span class="pill pill-warn">Not matched yet</span>';
    button.classList.remove('hidden');
    button.textContent = 'Run matching';
    button.classList.add('btn-primary');
  }
  button.disabled = cur().n > MATCH_LIMIT;
  button.title = cur().n > MATCH_LIMIT ? `Matching runs on datasets of up to ${MATCH_LIMIT.toLocaleString()} profiles.` : '';
}

async function runMatching() {
  const button = $('#run-matching');
  button.disabled = true;
  const seconds = Math.max(5, Math.round(cur().n / 3000 * 30));
  $('#match-status').innerHTML = `<span class="pill pill-warn">Matching, about ${seconds} s</span>`;
  try {
    await api('/api/matching', { method: 'POST', body: cur() });
    await loadState(cur());
    notice(`Matched ${cur().n.toLocaleString()} profiles with all five methods.`);
    render();
  } catch (e) {
    notice(e.message, 'bad');
    updateMatchStatus();
  }
}

async function generateDataset(event) {
  event.preventDefault();
  const form = $('#dataset-form');
  if (event.submitter && event.submitter.value === 'cancel') { $('#dataset-dialog').close(); return; }
  const body = { n: Number(form.n.value), seed: Number(form.seed.value) };
  const submit = $('#dataset-submit');
  submit.disabled = true; submit.textContent = 'Generating…';
  $('#dataset-error').textContent = '';
  try {
    await api('/api/datasets', { method: 'POST', body });
    $('#dataset-dialog').close();
    await loadState(body);
    notice(`Generated ${body.n.toLocaleString()} profiles with seed ${body.seed}.`);
    location.hash = '#dataset';
    render();
  } catch (e) {
    $('#dataset-error').textContent = e.message;
  } finally {
    submit.disabled = false; submit.textContent = 'Generate dataset';
  }
}

// ---------------------------------------------------------------------------
// Profile drawer
// ---------------------------------------------------------------------------

async function openProfile(pid) {
  const drawer = $('#drawer');
  $('#drawer-title').textContent = pid;
  $('#drawer-body').innerHTML = '<p class="text-muted">Loading…</p>';
  drawer.classList.add('open'); drawer.setAttribute('aria-hidden', 'false'); drawer.inert = false;
  $('#drawer-close').focus();
  try {
    let attributes, methods = null;
    if (isMatched()) {
      const p = await api(`/api/matching/${cur().n}/${cur().seed}/profiles/${encodeURIComponent(pid)}`);
      attributes = p.attributes; methods = p.methods;
    } else {
      const r = await api(`/api/datasets/${cur().n}/${cur().seed}/profiles?search=${encodeURIComponent(pid)}&page_size=1`);
      attributes = r.rows[0];
    }
    const rows = PROFILE_FIELDS.map(([k, l]) =>
      `<tr><th class="w-44">${esc(l)}</th><td>${esc(k === 'lives_alone' ? (attributes[k] ? 'Yes' : 'No') : (attributes[k] || '—'))}</td></tr>`).join('');
    let groups = '<p class="text-muted mt-4">Run matching to see which group this person joins under each method.</p>';
    if (methods) {
      groups = Object.entries(METHODS).map(([m, name]) => {
        const g = methods[m];
        if (!g.group_id) return `<div class="py-3 border-t border-rule"><h4 class="font-bold">${esc(name)}</h4><p class="text-danger">${esc(g.reason)}</p></div>`;
        const others = g.members.filter(x => x !== pid).map(x => `<button class="underline text-teal" data-pid="${esc(x)}">${esc(x)}</button>`).join(', ');
        return `<div class="py-3 border-t border-rule"><h4 class="font-bold">${esc(name)}</h4>
          <p class="text-sm">${esc(g.explanation.summary)}</p>
          <p class="text-sm text-muted mt-1">Group of ${g.members.length} · score ${fmt(g.score)}. With: ${others}</p></div>`;
      }).join('');
      groups = `<h3 class="font-bold mt-6 mb-1">Group under each method</h3>${groups}`;
    }
    $('#drawer-body').innerHTML = `<table class="data-table">${rows}</table>${groups}`;
  } catch (e) {
    $('#drawer-body').innerHTML = `<p class="text-danger">${esc(e.message)}</p>`;
  }
}

function closeDrawer() {
  const drawer = $('#drawer');
  drawer.classList.remove('open'); drawer.setAttribute('aria-hidden', 'true'); drawer.inert = true;
}

// ---------------------------------------------------------------------------
// 1. Dataset
// ---------------------------------------------------------------------------

async function renderDataset() {
  if (!cur()) {
    view().innerHTML = header('Dataset', 'Synthetic profiles of UK adults living with long-term conditions.') +
      (state.readOnly ? emptyState('No dataset is available in this version.')
                      : emptyState('There is no dataset yet. Generate one to start.', 'New dataset', 'empty-new'));
    const d = $('#empty-new'); if (d) d.onclick = () => $('#dataset-dialog').showModal();
    return;
  }
  const v = await api(`/api/datasets/${cur().n}/${cur().seed}/validation`);
  const checks = Object.entries(v.consistency).filter(([k]) => k !== 'TOTAL').map(([k, c]) =>
    `<tr><td>${esc(label(k))}</td><td class="r">${c}</td><td>${c === 0 ? '<span class="pill pill-ok">Pass</span>' : '<span class="pill pill-bad">Fail</span>'}</td></tr>`).join('');
  const chi = v.chi_square.map(c => {
    const col = c.attribute;
    const rows = c.rows.map(r => `<tr><td>${esc(r[col])}</td><td class="r">${fmt(r.target * 100, 1)}%</td><td class="r">${fmt(r.generated * 100, 1)}%</td><td class="r">${r.difference >= 0 ? '+' : ''}${fmt(r.difference * 100, 2)}</td></tr>`).join('');
    const ok = c.p_value >= 0.05;
    return `<div class="block"><h3>${esc(label(col))}</h3>
      <p class="text-sm text-muted mb-2">Target: ${esc(c.source)}</p>
      <table class="data-table"><thead><tr><th>Category</th><th class="r">Target</th><th class="r">Generated</th><th class="r">Difference (points)</th></tr></thead><tbody>${rows}</tbody></table>
      <p class="text-sm mt-3">Chi-square ${fmt(c.statistic, 2)}, p = ${fmt(c.p_value, 4)}
      <span class="pill ${ok ? 'pill-ok' : 'pill-warn'} ml-1">${ok ? 'Matches target' : 'Differs at p < 0.05'}</span></p></div>`;
  }).join('');
  const figures = v.figures.map(f =>
    `<figure class="block p-3"><img src="${esc(f.url)}" alt="${esc(f.label)}" loading="lazy" class="w-full h-auto"><figcaption class="text-sm text-muted mt-2">${esc(f.label)}</figcaption></figure>`).join('');
  view().innerHTML = header('Dataset', `${v.n.toLocaleString()} synthetic profiles (seed ${v.seed}), calibrated to published UK figures.
      These checks confirm the data is logically consistent and matches its targets before any matching runs.
      <a class="underline text-teal" href="${esc(v.report_url)}" target="_blank" rel="noopener">Open the full validation report</a>.`) + `
    <div class="grid lg:grid-cols-[minmax(0,22rem)_1fr] gap-6 mb-6">
      <div class="block self-start"><h3>Logical consistency</h3>
        <p class="text-sm text-muted mb-2">Each count should be zero.</p>
        <table class="data-table"><tbody>${checks}</tbody></table></div>
      <div class="grid gap-6">${chi}</div>
    </div>
    <h3 class="font-bold text-lg mb-3">Distributions</h3>
    <div class="grid md:grid-cols-2 gap-4">${figures}</div>`;
}

// ---------------------------------------------------------------------------
// 2. Hard rules
// ---------------------------------------------------------------------------

function needsMatching(title, lede) {
  if (state.readOnly) {
    view().innerHTML = header(title, lede) + emptyState('Matching results are not available for this dataset in this version.');
    return;
  }
  const tooBig = cur() && cur().n > MATCH_LIMIT;
  view().innerHTML = header(title, lede) + (cur()
    ? emptyState(tooBig ? `Matching runs on datasets of up to ${MATCH_LIMIT.toLocaleString()} profiles. Choose or generate a smaller dataset.`
                        : 'This dataset has not been matched yet.', tooBig ? '' : 'Run matching', 'empty-match')
    : emptyState('Generate a dataset first.', 'New dataset', 'empty-new'));
  const m = $('#empty-match'); if (m) m.onclick = runMatching;
  const d = $('#empty-new'); if (d) d.onclick = () => $('#dataset-dialog').showModal();
}

async function renderRules() {
  const lede = 'Before any similarity is measured, people are split into pools that share a condition category and a language. Groups are only formed inside a pool, and every group has six to eight members.';
  if (!isMatched()) return needsMatching('Hard rules', lede);
  const [s, unmatched] = await Promise.all([
    api(`/api/matching/${cur().n}/${cur().seed}`),
    api(`/api/matching/${cur().n}/${cur().seed}/unmatched?method=${REFERENCE}`),
  ]);
  const rules = s.rules.map(r => `<tr><td>${esc(label(r.rule))}</td><td class="r">${r.checked.toLocaleString()}</td><td class="r">${r.excluded.toLocaleString()}</td><td class="text-muted">${esc(r.note)}</td></tr>`).join('');
  const methods = Object.entries(METHODS).map(([m, name]) => {
    const x = s.methods[m];
    return `<tr><td>${esc(name)}</td><td class="r">${x.n_groups}</td><td class="r">${x.n_unmatched}</td><td class="r">${fmt(x.mean_score)}</td><td class="r">${fmt(x.seconds, 1)} s</td></tr>`;
  }).join('');
  const pools = [...s.pools].sort((a, b) => b.size - a.size).map(p =>
    `<tr><td>${esc(p.category)}</td><td>${esc(p.language)}</td><td class="r">${p.size}</td><td class="r">${p.n_groups}</td><td>${p.viable ? '<span class="pill pill-ok">Grouped</span>' : '<span class="pill pill-warn">Too small</span>'}</td></tr>`).join('');
  const un = unmatched.map(u => `<tr class="clickable" data-pid="${esc(u.profile_id)}"><td>${esc(u.profile_id)}</td><td>${esc(u.plain_language)}</td></tr>`).join('');
  view().innerHTML = header('Hard rules', lede) + `
    <div class="block mb-6 overflow-x-auto"><h3>Rules applied</h3>
      <table class="data-table"><thead><tr><th>Rule</th><th class="r">Checked</th><th class="r">Excluded</th><th>Note</th></tr></thead><tbody>${rules}</tbody></table></div>
    <div class="block mb-6 overflow-x-auto"><h3>Methods on this dataset</h3>
      <p class="text-sm text-muted mb-2">All methods use the same pools and group sizes, so the number of groups and unmatched people is the same for each. Score is the mean group score under the default weights.</p>
      <table class="data-table"><thead><tr><th>Method</th><th class="r">Groups</th><th class="r">Unmatched</th><th class="r">Mean score</th><th class="r">Time</th></tr></thead><tbody>${methods}</tbody></table></div>
    <div class="grid xl:grid-cols-2 gap-6">
      <div class="block overflow-x-auto"><h3>Pools (${s.pools.length})</h3>
        <table class="data-table"><thead><tr><th>Condition category</th><th>Language</th><th class="r">People</th><th class="r">Groups</th><th>Status</th></tr></thead><tbody>${pools}</tbody></table></div>
      <div class="block overflow-x-auto"><h3>Not grouped (${unmatched.length})</h3>
        <p class="text-sm text-muted mb-2">Select a person to see their profile.</p>
        <table class="data-table"><tbody>${un || '<tr><td>Everyone was placed in a group.</td></tr>'}</tbody></table></div>
    </div>`;
}

// ---------------------------------------------------------------------------
// 3. Groups and the group map
// ---------------------------------------------------------------------------

const groupsState = { pool: null, method: REFERENCE, cache: {} };

async function renderGroups() {
  const lede = 'Each dot is one person in the selected pool, placed so that people with similar attributes sit close together. Lines join each member to the centre of their group: short lines mean a close group, long lines a loose one. Switch method to compare.';
  if (!isMatched()) return needsMatching('Groups', lede);
  const s = await api(`/api/matching/${cur().n}/${cur().seed}`);
  const pools = s.pools.filter(p => p.n_groups >= 1).sort((a, b) => b.size - a.size);
  const poolKey = p => `${p.category}|${p.language}`;
  if (!groupsState.pool || !pools.some(p => poolKey(p) === groupsState.pool)) groupsState.pool = poolKey(pools[0]);
  const [category, language] = groupsState.pool.split('|');

  view().innerHTML = header('Groups', lede) + `
    <div class="flex flex-wrap items-end gap-4 mb-4">
      <label class="text-sm max-w-full">Pool<br><select id="pool-select" class="field mt-1 w-full">${pools.map(p =>
        `<option value="${esc(poolKey(p))}">${esc(p.category)}, ${esc(p.language)} (${p.size} people, ${p.n_groups} groups)</option>`).join('')}</select></label>
      <div><span class="text-sm">Method</span><br><div class="seg mt-1" role="group" aria-label="Method">${Object.entries(METHODS).map(([m, name]) =>
        `<button data-method="${m}" aria-pressed="${m === groupsState.method}">${esc(name)}</button>`).join('')}</div></div>
    </div>
    <div class="grid xl:grid-cols-[1fr_20rem] gap-6 mb-6">
      <div class="map-wrap"><div id="map" class="map"></div><div id="map-tip" class="map-tip hidden"></div>
        <p class="text-xs text-muted mt-2">Positions come from classical multidimensional scaling of the weighted Gower distances (Torgerson, 1952). The map is for display only: it plays no part in forming groups, and flattening to two dimensions distorts some distances. Hollow dots are people not placed in a group.</p></div>
      <div class="block"><h3>This pool, by method</h3>
        <p class="text-sm text-muted mb-2">Mean distance between members of the same group (weighted Gower; lower is closer).</p>
        <table class="data-table" id="pool-compare"><tbody><tr><td>Loading…</td></tr></tbody></table></div>
    </div>
    <h3 class="font-bold text-lg mb-3" id="group-list-title"></h3>
    <div id="group-list" class="grid gap-3"></div>`;
  $('#pool-select').value = groupsState.pool;
  $('#pool-select').onchange = e => { groupsState.pool = e.target.value; renderGroups(); };
  view().querySelectorAll('[data-method]').forEach(b => b.onclick = () => {
    groupsState.method = b.dataset.method;
    view().querySelectorAll('[data-method]').forEach(x => x.setAttribute('aria-pressed', x === b));
    drawGroups(category, language);
  });

  const base = `/api/matching/${cur().n}/${cur().seed}`;
  const q = `category=${encodeURIComponent(category)}&language=${encodeURIComponent(language)}`;
  const cacheKey = `${key(cur())}|${groupsState.pool}`;
  if (!groupsState.cache[cacheKey]) {
    const [map, ...lists] = await Promise.all([api(`${base}/map?${q}`),
      ...Object.keys(METHODS).map(m => api(`${base}/groups?method=${m}&${q}`))]);
    groupsState.cache = { [cacheKey]: { map, groups: Object.fromEntries(Object.keys(METHODS).map((m, i) => [m, lists[i]])) } };
  }
  const data = groupsState.cache[cacheKey];
  $('#pool-compare tbody').innerHTML = Object.entries(METHODS).map(([m, name]) => {
    const gs = data.groups[m];
    const mean = gs.reduce((a, g) => a + g.details.mean_distance, 0) / Math.max(gs.length, 1);
    return `<tr><td>${m === REFERENCE ? '<strong>' + esc(name) + '</strong>' : esc(name)}</td><td class="r">${fmt(mean)}</td></tr>`;
  }).join('');
  drawGroups(category, language);
}

function drawGroups(category, language) {
  const data = groupsState.cache[`${key(cur())}|${groupsState.pool}`];
  const method = groupsState.method;
  drawMap(data.map.points, method);
  const groups = data.groups[method];
  $('#group-list-title').textContent = `${groups.length} groups under ${METHODS[method]}`;
  $('#group-list').innerHTML = groups.map((g, i) => {
    const e = g.explanation;
    const members = g.members.map(p => `<button class="underline text-teal" data-pid="${esc(p)}">${esc(p)}</button>`).join(' ');
    const balance = Object.values(e.balance).map(b => esc(b)).join('; ');
    return `<article class="block" data-group="${esc(g.group_id)}">
      <div class="flex flex-wrap items-baseline justify-between gap-2"><h4 class="font-bold">Group ${i + 1} <span class="font-normal text-muted">· ${g.members.length} people</span></h4>
      <span class="text-sm text-muted">Score ${fmt(g.score)} · mean distance ${fmt(g.details.mean_distance)}</span></div>
      <p class="mt-1">${esc(e.summary)}</p>
      <p class="text-sm text-muted mt-1">${balance.charAt(0).toUpperCase() + balance.slice(1)}. ${esc(e.weakest_link)}</p>
      <p class="text-sm mt-2">${members}</p></article>`;
  }).join('');
}

function drawMap(points, method) {
  const W = 820, H = 520, pad = 18;
  const xs = points.map(p => p.x), ys = points.map(p => p.y);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const sx = x => pad + (x - x0) / ((x1 - x0) || 1) * (W - 2 * pad);
  const sy = y => H - pad - (y - y0) / ((y1 - y0) || 1) * (H - 2 * pad);
  const groups = {};
  points.forEach(p => { const g = p.group[method]; if (g) (groups[g] ||= []).push(p); });
  const centre = {};
  Object.entries(groups).forEach(([g, ms]) => {
    centre[g] = [ms.reduce((a, p) => a + sx(p.x), 0) / ms.length, ms.reduce((a, p) => a + sy(p.y), 0) / ms.length];
  });
  const spokes = points.filter(p => p.group[method]).map(p => {
    const [cx, cy] = centre[p.group[method]];
    return `<line class="spoke" data-g="${esc(p.group[method])}" x1="${sx(p.x).toFixed(1)}" y1="${sy(p.y).toFixed(1)}" x2="${cx.toFixed(1)}" y2="${cy.toFixed(1)}"/>`;
  }).join('');
  const dots = points.map(p => {
    const g = p.group[method];
    return `<circle class="pt${g ? '' : ' unmatched'}" data-g="${esc(g || '')}" data-pid="${esc(p.profile_id)}" cx="${sx(p.x).toFixed(1)}" cy="${sy(p.y).toFixed(1)}" r="3.2" tabindex="-1"><title>${esc(p.profile_id)}</title></circle>`;
  }).join('');
  const host = $('#map');
  host.className = `map${method === REFERENCE || method === 'unweighted_gower' ? '' : ' baseline'}`;
  host.innerHTML = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Map of ${points.length} people in this pool, joined to their group centres under ${esc(METHODS[method])}">${spokes}${dots}</svg>`;
  const tip = $('#map-tip');
  host.querySelectorAll('.pt').forEach(c => {
    c.addEventListener('mouseenter', () => {
      const g = c.dataset.g;
      if (g) {
        host.classList.add('focus');
        host.querySelectorAll(`[data-g="${CSS.escape(g)}"]`).forEach(el => el.classList.add('on'));
      }
      const box = host.getBoundingClientRect(), r = c.getBoundingClientRect();
      tip.style.left = `${r.left - box.left + r.width / 2}px`;
      tip.style.top = `${r.top - box.top}px`;
      tip.textContent = g ? `${c.dataset.pid}: group ${g.split('|').pop()}` : `${c.dataset.pid}: not grouped`;
      tip.classList.remove('hidden');
    });
    c.addEventListener('mouseleave', () => {
      host.classList.remove('focus');
      host.querySelectorAll('.on').forEach(el => el.classList.remove('on'));
      tip.classList.add('hidden');
    });
  });
}

// ---------------------------------------------------------------------------
// 4. Profiles
// ---------------------------------------------------------------------------

const profileFilters = { search: '', page: 1 };
const FILTERS = [['primary_condition_category', 'Condition category'], ['communication_language', 'Language'],
  ['age_band', 'Age band'], ['gender', 'Gender'], ['primary_support_goal', 'Support goal']];

async function renderProfiles() {
  const lede = 'Every generated profile. Filter or search, then select a person to see all their attributes and the group they join under each method.';
  if (!cur()) return needsMatching('Profiles', lede);
  const params = new URLSearchParams({ page: profileFilters.page, page_size: 50 });
  if (profileFilters.search) params.set('search', profileFilters.search);
  FILTERS.forEach(([k]) => { if (profileFilters[k]) params.set(k, profileFilters[k]); });
  const r = await api(`/api/datasets/${cur().n}/${cur().seed}/profiles?${params}`);
  const pages = Math.max(1, Math.ceil(r.total / r.page_size));
  const selects = FILTERS.map(([k, l]) => `<label class="text-sm">${esc(l)}<br><select data-filter="${k}" class="field mt-1"><option value="">All</option>${r.facets[k].map(v =>
    `<option ${profileFilters[k] === v ? 'selected' : ''}>${esc(v)}</option>`).join('')}</select></label>`).join('');
  const cols = [['profile_id', 'Profile'], ['age_band', 'Age'], ['gender', 'Gender'], ['communication_language', 'Language'],
    ['primary_condition_subtype', 'Condition'], ['primary_support_goal', 'Goal'], ['support_orientation', 'Orientation'], ['psychosocial_isolation_score', 'Isolation']];
  const rows = r.rows.map(p => `<tr class="clickable" data-pid="${esc(p.profile_id)}">${cols.map(([k]) =>
    `<td${k === 'psychosocial_isolation_score' ? ' class="r"' : ''}>${esc(k === 'primary_support_goal' ? label(p[k]) : p[k])}</td>`).join('')}</tr>`).join('');
  view().innerHTML = header('Profiles', lede) + `
    <div class="flex flex-wrap items-end gap-3 mb-4">
      <label class="text-sm">Search by profile<br><input id="profile-search" class="field mt-1" placeholder="e.g. P000123" value="${esc(profileFilters.search)}"></label>
      ${selects}
    </div>
    <div class="block overflow-x-auto">
      <table class="data-table"><thead><tr>${cols.map(([k, l]) => `<th${k === 'psychosocial_isolation_score' ? ' class="r"' : ''}>${esc(l)}</th>`).join('')}</tr></thead>
      <tbody>${rows || `<tr><td colspan="${cols.length}">No profiles match these filters.</td></tr>`}</tbody></table>
      <div class="flex items-center justify-between mt-3 text-sm">
        <span class="text-muted">${r.total.toLocaleString()} profiles · page ${r.page} of ${pages}</span>
        <span class="flex gap-2"><button class="btn" id="prev" ${r.page <= 1 ? 'disabled' : ''}>Previous</button><button class="btn" id="next" ${r.page >= pages ? 'disabled' : ''}>Next</button></span>
      </div>
    </div>`;
  let timer;
  $('#profile-search').oninput = e => { clearTimeout(timer); timer = setTimeout(() => { profileFilters.search = e.target.value; profileFilters.page = 1; renderProfiles().then(() => { const s = $('#profile-search'); s.focus(); s.setSelectionRange(s.value.length, s.value.length); }); }, 300); };
  view().querySelectorAll('[data-filter]').forEach(s => s.onchange = () => { profileFilters[s.dataset.filter] = s.value; profileFilters.page = 1; renderProfiles(); });
  $('#prev').onclick = () => { profileFilters.page -= 1; renderProfiles(); };
  $('#next').onclick = () => { profileFilters.page += 1; renderProfiles(); };
}

// ---------------------------------------------------------------------------
// 5. Evaluation
// ---------------------------------------------------------------------------

const METRIC_INFO = {
  silhouette_weighted: ['Silhouette, weighted Gower matrix', 'Higher is more cohesive. Established measure (Rousseeuw, 1987).'],
  silhouette_unweighted: ['Silhouette, unweighted Gower matrix', 'The same on a distance the weighted method does not optimise.'],
  within_group_distance: ['Within-group distance', 'Mean weighted Gower distance between members of the same group. Lower is more cohesive.'],
  cohesion_index: ['Cohesion index', 'Mean group score under the default weights. Specific to this project.'],
};

function evaluationForm(defaults) {
  if (state.readOnly) {
    return `<div class="block"><h3>Run the evaluation</h3><p class="text-sm text-muted">Running the evaluation is turned off in this view-only version. The results above were produced with <code>run_evaluation.py</code>.</p></div>`;
  }
  return `<div class="block"><h3>Run the evaluation</h3>
    <p class="text-sm text-muted mb-3">Generates any missing replicate datasets, runs every method on each, then runs the statistical tests and the weight sensitivity analysis. About 6 minutes for 20 replicates of 3,000 profiles.</p>
    <form id="eval-form" class="flex flex-wrap items-end gap-3">
      <label class="text-sm">Profiles<br><input name="n" type="number" min="300" max="5000" value="${defaults.n}" class="field mt-1 w-28"></label>
      <label class="text-sm">First seed<br><input name="seed" type="number" min="0" value="${defaults.seed}" class="field mt-1 w-24"></label>
      <label class="text-sm">Replicates<br><input name="replicates" type="number" min="5" max="30" value="20" class="field mt-1 w-24"></label>
      <button class="btn btn-primary" id="eval-run">Run evaluation</button>
    </form>
    <p id="eval-error" class="text-sm text-danger mt-2" role="alert"></p>
    <div id="job" class="mt-3"></div></div>`;
}

function bindEvaluationForm() {
  if (state.readOnly) return;
  $('#eval-form').onsubmit = async e => {
    e.preventDefault();
    const f = e.target;
    try {
      await api('/api/evaluation/run', { method: 'POST', body: { n: Number(f.n.value), seed: Number(f.seed.value), replicates: Number(f.replicates.value) } });
      $('#eval-error').textContent = '';
      pollJob();
    } catch (err) { $('#eval-error').textContent = err.message; }
  };
  pollJob(true);
}

async function pollJob(once = false) {
  clearTimeout(state.poll);
  const job = await api('/api/jobs/current');
  const host = $('#job');
  if (!host) return;
  if (job.status === 'idle') { host.innerHTML = ''; return; }
  const badge = { running: 'pill-warn', done: 'pill-ok', failed: 'pill-bad' }[job.status];
  const text = { running: 'Running', done: 'Finished', failed: 'Failed' }[job.status];
  host.innerHTML = `<p class="mb-2"><span class="pill ${badge}">${text}</span> <span class="text-sm text-muted">n = ${job.params.n}, seeds ${job.params.seed} to ${job.params.seed + job.params.replicates - 1}</span></p><div class="log">${esc(job.log.join('\n'))}</div>`;
  const log = host.querySelector('.log'); log.scrollTop = log.scrollHeight;
  $('#eval-run').disabled = job.status === 'running';
  if (job.status === 'running') state.poll = setTimeout(() => pollJob(), 2000);
  else if (!once && job.status === 'done') { await loadState(cur()); notice('Evaluation finished.'); render(); }
}

function evaluationN() {
  if (!state.evaluations.length) return null;
  return cur() && state.evaluations.includes(cur().n) ? cur().n : state.evaluations[0];
}

async function renderEvaluation() {
  const lede = 'Does weighted multi-attribute matching form more cohesive groups than random assignment and single-attribute matching? Every method runs on the same replicate datasets, and the differences are tested with paired non-parametric tests.';
  const n = evaluationN();
  if (!n) {
    view().innerHTML = header('Evaluation', lede) + evaluationForm({ n: cur()?.n && cur().n <= 5000 ? cur().n : 3000, seed: 42 });
    return bindEvaluationForm();
  }
  const { results: r, report } = await api(`/api/evaluation/${n}`);
  const methods = Object.keys(METHODS);
  const charts = Object.entries(METRIC_INFO).map(([m, [title, note]]) =>
    `<div class="block"><h3>${esc(title)}</h3><p class="text-sm text-muted mb-2">${esc(note)}</p><div class="h-56"><canvas id="c-${m}"></canvas></div></div>`).join('');
  const tests = Object.entries(METRIC_INFO).map(([m, [title]]) => {
    const t = r.tests[m];
    if (!t.friedman) return '';
    const rows = t.pairwise.map(p => `<tr><td>${esc(METHODS[p.baseline])}</td><td class="r">${p.median_difference >= 0 ? '+' : ''}${fmt(p.median_difference, 4)}</td><td class="r">${pText(p.p_holm)}</td><td class="r">${fmt(p.rank_biserial, 2)}</td><td>${esc(p.effect_size)}</td></tr>`).join('');
    return `<div class="block overflow-x-auto"><h3>${esc(title)}</h3><p class="text-sm mb-2">${esc(t.friedman.interpretation)}</p>
      ${rows ? `<table class="data-table"><thead><tr><th>Weighted Gower vs</th><th class="r">Median difference</th><th class="r">Holm p</th><th class="r">Rank-biserial r</th><th>Effect</th></tr></thead><tbody>${rows}</tbody></table>` : ''}</div>`;
  }).join('');
  const other = state.evaluations.length > 1 ? `Showing n = ${n.toLocaleString()}. Also available: ${state.evaluations.filter(x => x !== n).join(', ')}.` : '';
  view().innerHTML = header('Evaluation', lede) + `
    <p class="text-sm text-muted -mt-3 mb-5">${r.seeds.length} replicate datasets of ${r.n.toLocaleString()} profiles (seeds ${r.seeds[0]} to ${r.seeds[r.seeds.length - 1]}). Bars show the mean; hover for the standard deviation and the test against weighted Gower. An asterisk marks a significant difference from weighted Gower (Holm-adjusted p &lt; 0.05). ${esc(other)}</p>
    <div class="grid lg:grid-cols-2 gap-6 mb-8">${charts}</div>
    <h3 class="font-bold text-lg mb-3">Statistical tests</h3>
    <p class="text-sm text-muted mb-3">Friedman test across all five methods, Kendall's W as effect size; then Wilcoxon signed-rank tests of weighted Gower against each baseline, Holm-corrected, with the matched-pairs rank-biserial correlation r.</p>
    <div class="grid xl:grid-cols-2 gap-6 mb-8">${tests}</div>
    <details class="block mb-8"><summary class="font-bold cursor-pointer">Full evaluation report</summary><div class="report mt-4">${marked.parse(report || '')}</div></details>
    ${evaluationForm({ n, seed: r.seeds[0] })}`;

  destroyCharts();
  Object.keys(METRIC_INFO).forEach(m => {
    const pair = Object.fromEntries((r.tests[m].pairwise || []).map(p => [p.baseline, p]));
    const labels = methods.map(x => METHODS[x] + (pair[x] && pair[x].p_holm < 0.05 ? ' *' : ''));
    state.charts.push(new Chart($(`#c-${m}`), {
      type: 'bar',
      data: { labels, datasets: [{ data: methods.map(x => r.summary[m][x].mean),
        backgroundColor: methods.map(x => x === REFERENCE ? TEAL : (x === 'unweighted_gower' ? '#5E9C9C' : OCHRE)), borderRadius: 3 }] },
      options: {
        indexAxis: 'y', maintainAspectRatio: false, animation: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: {
          label: c => {
            const x = methods[c.dataIndex], s = r.summary[m][x], p = pair[x];
            const lines = [`Mean ${fmt(s.mean, 4)} (SD ${fmt(s.sd, 4)})`];
            if (p) lines.push(`vs weighted Gower: Holm p ${pText(p.p_holm)}, r = ${fmt(p.rank_biserial, 2)} (${p.effect_size})`);
            return lines;
          } } } },
        scales: { x: { grid: { color: '#E6EAED' } }, y: { grid: { display: false }, ticks: { font: { size: 13 } } } },
      },
    }));
  });
  bindEvaluationForm();
}

// ---------------------------------------------------------------------------
// 6. Sensitivity
// ---------------------------------------------------------------------------

async function renderSensitivity() {
  const lede = 'The attribute weights come from the literature, not from patient data. Each weight is moved up and down by 10% and the groups are formed again on the same dataset, to see how much the result depends on the exact values.';
  const n = evaluationN();
  if (!n) {
    view().innerHTML = header('Sensitivity', lede) + emptyState('The sensitivity analysis runs as part of the evaluation.', 'Go to evaluation', 'go-eval');
    $('#go-eval').onclick = () => { location.hash = '#evaluation'; };
    return;
  }
  const { results } = await api(`/api/evaluation/${n}`);
  const s = results.sensitivity;
  const wgd = Object.fromEntries(s.perturbations.map(p => [`${p.attribute}${p.direction}`, p.within_group_distance]));
  const rows = s.ranking.map(x => `<tr><td>${esc(ATTRIBUTES[x.attribute])}</td><td class="r">${fmt(x.original_weight, 4)}</td><td class="r">${fmt(x.ari_plus)}</td><td class="r">${fmt(x.ari_minus)}</td><td class="r">${fmt(wgd[x.attribute + '+10%'], 4)}</td><td class="r">${fmt(wgd[x.attribute + '-10%'], 4)}</td></tr>`).join('');
  const all = Object.values(wgd);
  view().innerHTML = header('Sensitivity', lede) + `
    <div class="grid md:grid-cols-3 gap-4 mb-6">
      <div class="block"><p class="text-sm text-muted">Membership kept after a weight change</p><p class="stat text-2xl font-bold">${fmt(Math.min(...s.ranking.map(x => Math.min(x.ari_plus, x.ari_minus))), 2)} to ${fmt(Math.max(...s.ranking.map(x => Math.max(x.ari_plus, x.ari_minus))), 2)}</p><p class="text-sm text-muted">Adjusted Rand Index (1 = identical groups)</p></div>
      <div class="block"><p class="text-sm text-muted">Membership kept after changing only the seed</p><p class="stat text-2xl font-bold">${fmt(s.seed_reference_ari, 2)}</p><p class="text-sm text-muted">The same comparison, weights unchanged</p></div>
      <div class="block"><p class="text-sm text-muted">Group quality across all changes</p><p class="stat text-2xl font-bold">${fmt(Math.min(...all), 3)} to ${fmt(Math.max(...all), 3)}</p><p class="text-sm text-muted">Within-group distance; original ${fmt(s.base_within_group_distance, 3)}, random ${fmt(results.summary.within_group_distance.random.mean, 3)}</p></div>
    </div>
    <div class="block mb-6"><h3>Adjusted Rand Index after each change</h3>
      <p class="text-sm text-muted mb-2">Lower means the change moved more people into different groups. The dashed line is the seed-only reference.</p>
      <div class="h-80"><canvas id="c-sens"></canvas></div></div>
    <div class="block overflow-x-auto"><h3>All sixteen changes</h3>
      <table class="data-table"><thead><tr><th>Attribute</th><th class="r">Weight</th><th class="r">ARI +10%</th><th class="r">ARI −10%</th><th class="r">Distance +10%</th><th class="r">Distance −10%</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  destroyCharts();
  const labels = s.ranking.map(x => ATTRIBUTES[x.attribute].split(' ').reduce((lines, w) => {
    const last = lines[lines.length - 1];
    if (last && (last + ' ' + w).length <= 14) lines[lines.length - 1] = last + ' ' + w; else lines.push(w);
    return lines;
  }, []));
  state.charts.push(new Chart($('#c-sens'), {
    type: 'bar',
    data: { labels, datasets: [
      { label: 'Weight +10%', data: s.ranking.map(x => x.ari_plus), backgroundColor: TEAL, borderRadius: 3 },
      { label: 'Weight −10%', data: s.ranking.map(x => x.ari_minus), backgroundColor: '#7FB8B8', borderRadius: 3 },
      { type: 'line', label: `Seed only (${fmt(s.seed_reference_ari, 2)})`, data: labels.map(() => s.seed_reference_ari), borderColor: OCHRE, borderDash: [6, 4], pointRadius: 0, borderWidth: 2 },
    ] },
    options: {
      maintainAspectRatio: false, animation: false,
      scales: { y: { min: 0, max: 1, title: { display: true, text: 'Adjusted Rand Index' } }, x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: false } } },
    },
  }));
}

// ---------------------------------------------------------------------------
// Routing
// ---------------------------------------------------------------------------

const VIEWS = { dataset: renderDataset, rules: renderRules, groups: renderGroups, profiles: renderProfiles, evaluation: renderEvaluation, sensitivity: renderSensitivity };

async function render() {
  const name = (location.hash || '#dataset').slice(1);
  const fn = VIEWS[name] || renderDataset;
  document.querySelectorAll('#stages a').forEach(a => { if (a.dataset.view === name) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  destroyCharts();
  clearTimeout(state.poll);
  view().innerHTML = '<p class="text-muted">Loading…</p>';
  try { await fn(); } catch (e) { view().innerHTML = `<div class="block"><p class="text-danger">${esc(e.message)}</p></div>`; }
}

document.addEventListener('click', e => {
  const target = e.target.closest('[data-pid]');
  if (target && !target.closest('#map')) openProfile(target.dataset.pid);
  else if (target && target.tagName === 'circle') openProfile(target.dataset.pid);
});
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });
$('#drawer-close').onclick = closeDrawer;
$('#new-dataset').onclick = () => { $('#dataset-error').textContent = ''; $('#dataset-dialog').showModal(); };
$('#dataset-form').addEventListener('submit', generateDataset);
$('#run-matching').onclick = runMatching;
$('#dataset-select').onchange = e => {
  const [n, seed] = e.target.value.split(':').map(Number);
  state.current = { n, seed };
  groupsState.cache = {}; profileFilters.page = 1;
  updateMatchStatus(); notice('');
  render();
};
window.addEventListener('hashchange', () => { notice(''); render(); });

// Charts measure their labels when drawn, so wait for the web font first.
Chart.defaults.font.family = '"Atkinson Hyperlegible", system-ui, sans-serif';
Chart.defaults.color = INK;
document.fonts.ready.then(loadState).then(render).catch(e => { view().innerHTML = `<p class="text-danger">${esc(e.message)}</p>`; });
