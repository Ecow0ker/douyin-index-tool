const $ = id => document.getElementById(id);
let state = {accounts: [], strategy: 'round_robin', rows: [], exports: [], runDir: '', running: false, paused: false};
let toastTimer;
const previewMode = new URLSearchParams(location.search).get('preview') === '1';
const previewApi = previewMode ? {
  bootstrap: async () => ({version:'1.1.0', accounts:[{id:'preview',name:'账号 · PREVIEW',createdAt:'界面预览'}], strategy:'round_robin', demo:true, startDate:'2026-07-18', endDate:'2026-08-18', outputDir:'~/Downloads/抖音指数数据'}),
  query: async config => ({cancelled:false, rows:config.keywords.flatMap((keyword,k) => Array.from({length:8},(_,i) => ({keyword,date:`2026-08-${String(i+1).padStart(2,'0')}`,composite_index:1170000+k*120000+i*19300,search_index:2580000+k*180000+i*27400,composite_marker:i===5?'波峰点':'',search_marker:i===3?'飙升点':''}))), outputs:['~/Downloads/抖音指数数据/预览.csv'], runDir:'~/Downloads/抖音指数数据'}),
  choose_output_directory: async current => ({selected:false,path:current}), toggle_pause:async()=>({paused:!state.paused}), cancel:async()=>({cancelled:true}), open_path:async path=>({opened:path}),
  open_login:async()=>({opened:true,message:'预览模式登录窗口'}), sync_login_cookies:async()=>({detected:true,message:'预览账号已同步',accounts:[{id:'preview',name:'账号 · PREVIEW',createdAt:'界面预览'}]}),
  set_strategy:async strategy=>({strategy}), remove_account:async()=>({accounts:[]}), clear_accounts:async()=>({accounts:[]}), open_url:async url=>({opened:url})
} : null;

function bridge() { return (window.pywebview && window.pywebview.api) || previewApi; }
async function call(name, ...args) {
  const api = bridge();
  if (!api || typeof api[name] !== 'function') throw new Error('桌面接口尚未就绪');
  return api[name](...args);
}
function toast(message, error=false) {
  const el = $('toast'); el.textContent = message; el.className = `toast show${error ? ' error' : ''}`;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.className = 'toast', 3200);
}
function log(text) {
  const item = document.createElement('div'); item.className = 'logItem';
  const time = new Date().toLocaleTimeString('zh-CN', {hour12:false});
  item.innerHTML = `<time>${time}</time><span></span>`; item.querySelector('span').textContent = text;
  $('activityLog').appendChild(item); $('activityLog').scrollTop = $('activityLog').scrollHeight;
}
function switchPage(page) {
  document.querySelectorAll('.navItem').forEach(x => x.classList.toggle('active', x.dataset.page === page));
  document.querySelectorAll('.page').forEach(x => x.classList.toggle('active', x.id === `page-${page}`));
}
function formatNumber(value) { return value === null || value === undefined ? '—' : Number(value).toLocaleString('zh-CN', {maximumFractionDigits:2}); }
function renderRows(rows) {
  state.rows = rows || []; $('rowCount').textContent = state.rows.length;
  $('resultMeta').textContent = state.rows.length ? `共 ${state.rows.length} 条记录` : '暂无数据';
  if (!state.rows.length) { $('tableBody').innerHTML = '<tr><td colspan="5" class="empty">查询结果将在这里显示</td></tr>'; return; }
  $('tableBody').innerHTML = state.rows.slice(0, 2000).map(row => {
    const marks = [row.composite_marker, row.search_marker].filter(Boolean).join(' / ') || '—';
    return `<tr><td>${escapeHtml(row.keyword)}</td><td>${escapeHtml(row.date)}</td><td>${formatNumber(row.composite_index)}</td><td>${formatNumber(row.search_index)}</td><td>${escapeHtml(marks)}</td></tr>`;
  }).join('');
}
function escapeHtml(value) { const span = document.createElement('span'); span.textContent = value == null ? '' : String(value); return span.innerHTML; }
function setRunning(running) {
  state.running = running; $('startBtn').disabled = running; $('pauseBtn').disabled = !running; $('stopBtn').disabled = !running;
  $('statusDot').classList.toggle('running', running); if (!running) state.paused = false;
}
function updateProgress(done, total, label='') {
  const percent = total ? Math.round(done * 100 / total) : 0;
  $('percent').textContent = `${percent}%`; $('progressBar').style.width = `${percent}%`; $('progressText').textContent = `${done} / ${total}`;
  if (label) $('statusDetail').textContent = label;
}
function renderAccounts(accounts=state.accounts) {
  state.accounts = accounts || []; $('accountBadge').textContent = state.accounts.length;
  if (!state.accounts.length) { $('accountList').innerHTML = '<div class="emptyBlock">暂无已保存账号</div>'; return; }
  $('accountList').innerHTML = state.accounts.map((row, i) => `<div class="accountRow"><div class="accountAvatar">${i+1}</div><div class="accountInfo"><strong>${escapeHtml(row.name)}</strong><span>${escapeHtml(row.createdAt || '本机账号')}</span></div><button data-remove="${escapeHtml(row.id)}">移除</button></div>`).join('');
}
function renderExports() {
  if (!state.exports.length) { $('exportList').innerHTML = '<div class="emptyBlock">暂无导出记录</div>'; return; }
  $('exportList').innerHTML = state.exports.map(path => `<div class="exportRow"><code>${escapeHtml(path)}</code><button class="secondary" data-open="${escapeHtml(state.runDir)}">打开目录</button></div>`).join('');
}
async function runQuery() {
  const keywords = $('keywords').value.split(/\r?\n/).map(x => x.trim()).filter(Boolean);
  const channels = [...document.querySelectorAll('input[name=channel]:checked')].map(x => x.value);
  const config = {keywords, startDate:$('startDate').value, endDate:$('endDate').value, period:$('period').value, interval:Number($('interval').value || 0), channels, outputDir:$('outputDir').value};
  if (!keywords.length) return toast('请至少输入一个关键词', true);
  if (!channels.length) return toast('请至少选择一种指数', true);
  renderRows([]); updateProgress(0, keywords.length); setRunning(true); $('statusTitle').textContent = '正在查询'; $('statusDetail').textContent = '准备请求'; log(`任务开始，共 ${keywords.length} 个关键词`);
  try {
    const result = await call('query', config);
    if (result.cancelled) { $('statusTitle').textContent = '任务已停止'; log('任务已停止'); }
    else { renderRows(result.rows); state.exports = result.outputs || []; state.runDir = result.runDir || ''; renderExports(); $('openLatest').disabled = !state.runDir; $('statusTitle').textContent = '查询完成'; $('statusDetail').textContent = `已导出 ${state.rows.length} 条记录`; updateProgress(keywords.length, keywords.length); log(`查询完成，导出 ${state.rows.length} 条记录`); toast('查询和导出已完成'); }
  } catch (error) { $('statusTitle').textContent = '查询失败'; $('statusDetail').textContent = String(error); $('statusDot').classList.add('error'); log(`失败：${error}`); toast(String(error), true); }
  finally { setRunning(false); $('countdownValue').textContent = '0'; }
}

window.__pythonEvent = (name, payload={}) => {
  if (name === 'log') log(payload.text || '');
  if (name === 'progress') updateProgress(payload.done || 0, payload.total || 0, payload.label || '');
  if (name === 'countdown') { $('countdownValue').textContent = payload.seconds || 0; if (payload.label) $('statusDetail').textContent = payload.label; }
  if (name === 'batch') renderRows([...state.rows, ...(payload.rows || [])]);
};

function bindEvents() {
  document.querySelectorAll('.navItem').forEach(x => x.addEventListener('click', () => switchPage(x.dataset.page)));
  $('goAccounts').onclick = () => switchPage('accounts'); $('startBtn').onclick = runQuery;
  $('resetBtn').onclick = () => { $('keywords').value = '华为'; $('period').value = 'daily'; $('interval').value = '3'; document.querySelectorAll('input[name=channel]').forEach(x => x.checked = true); };
  $('clearLog').onclick = () => { $('activityLog').innerHTML = ''; log('日志已清空'); };
  $('chooseDir').onclick = async () => { try { const r = await call('choose_output_directory', $('outputDir').value); $('outputDir').value = r.path; } catch(e) { toast(String(e), true); } };
  $('pauseBtn').onclick = async () => { const r = await call('toggle_pause'); state.paused = r.paused; $('pauseBtn').textContent = r.paused ? '继续' : '暂停'; $('statusTitle').textContent = r.paused ? '已暂停' : '正在查询'; log(r.paused ? '任务已暂停' : '任务继续'); };
  $('stopBtn').onclick = async () => { await call('cancel'); $('statusTitle').textContent = '正在停止'; };
  $('openLatest').onclick = () => state.runDir && call('open_path', state.runDir);
  $('openLogin').onclick = async () => { const r = await call('open_login'); $('accountMessage').textContent = r.message; if (!r.opened) toast(r.message, true); };
  $('syncLogin').onclick = async () => { $('accountMessage').textContent = '正在读取登录状态…'; const r = await call('sync_login_cookies'); $('accountMessage').textContent = r.message; if (r.accounts) renderAccounts(r.accounts); toast(r.message, !r.detected); };
  $('strategy').onchange = async () => { state.strategy = $('strategy').value; await call('set_strategy', state.strategy); };
  $('accountList').onclick = async event => { const id = event.target.dataset.remove; if (!id || !confirm('确定移除此账号？')) return; const r = await call('remove_account', id); renderAccounts(r.accounts); };
  $('clearAccounts').onclick = async () => { if (!state.accounts.length || !confirm('确定清空本机保存的全部账号？')) return; await call('clear_accounts'); renderAccounts([]); };
  $('exportList').onclick = event => { const path = event.target.dataset.open; if (path) call('open_path', path); };
  const closeAbout = () => $('aboutModal').classList.add('hidden');
  $('aboutButton').onclick = () => $('aboutModal').classList.remove('hidden');
  $('closeAbout').onclick = closeAbout;
  $('aboutModal').onclick = event => { if (event.target === $('aboutModal')) closeAbout(); };
  $('aboutGithub').onclick = () => call('open_url', 'https://github.com/Ecow0ker/douyin-index-tool');
  document.addEventListener('keydown', event => { if (event.key === 'Escape') closeAbout(); });
}

let initialized = false;
async function init() {
  if (initialized) return; initialized = true;
  bindEvents(); log('界面已就绪');
  try {
    const data = await call('bootstrap'); $('version').textContent = `v${data.version}`; $('aboutVersion').textContent = `版本：v${data.version}`; $('startDate').value = data.startDate; $('endDate').value = data.endDate; $('outputDir').value = data.outputDir; $('strategy').value = data.strategy; state.strategy = data.strategy; renderAccounts(data.accounts); if (data.demo) { $('keywords').value = '华为'; log('当前为演示模式'); }
  } catch (error) { toast(String(error), true); }
  window.__appReady = true;
}

window.addEventListener('pywebviewready', init, {once:true});
if (previewMode) window.addEventListener('DOMContentLoaded', init, {once:true});
