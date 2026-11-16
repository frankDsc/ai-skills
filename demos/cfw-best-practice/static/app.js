'use strict';
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="demo-token"]').content;
let scenarios = [], selected = 'ingress', frame = null, elapsed = 0, previous = null, paused = false;
let timer;
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

function element(tag, text, cls) {
  const e = document.createElement(tag); e.textContent = text;
  if (cls) e.className = cls;
  return e;
}
function toast(message) {
  $('toast').textContent = message; $('toast').hidden = false;
  clearTimeout(timer); timer = setTimeout(() => { $('toast').hidden = true; }, 6000);
}
async function json(url, options = {}) {
  const r = await fetch(url, {cache: 'no-store', ...options});
  const d = await r.json(); if (!r.ok) throw new Error(d.error || '请求失败'); return d;
}
function stop() {
  cancelAnimationFrame(frame); frame = null; previous = null; elapsed = 0; paused = false;
  $('flow-dot').setAttribute('visibility', 'hidden');
  $('pause').disabled = true; $('pause').textContent = '暂停';
  document.querySelectorAll('.walk-step,.node').forEach(e => e.classList.remove('active'));
}
function select(id) {
  stop(); selected = id; const s = scenarios.find(x => x.id === id);
  if (!s) return;
  $('scenario-select').value = id; $('scenario-title').textContent = s.name;
  $('scenario-description').textContent = s.description; $('acceptance').textContent = '真实验收条件：' + s.acceptance;
  $('walk-steps').replaceChildren();
  s.stages.forEach((text, i) => {
    const row = element('article', '', 'walk-step');
    row.append(element('span', String(i + 1).padStart(2, '0')), element('p', text)); $('walk-steps').append(row);
  });
  document.querySelectorAll('.scenario-card').forEach(e => {
    const active = e.dataset.scenario === id; e.classList.toggle('selected', active); e.setAttribute('aria-pressed', String(active));
  });
  $('walk-status').textContent = '方案推演已就绪；以上均为预期行为，尚未实测。';
}
function renderAccount(a) {
  const supported = a.connected && a.postpaid_supported === true;
  $('eligibility').textContent = !a.connected ? '未核验' : supported ? '已支持' : a.postpaid_supported === false ? '不支持' : '未知';
  $('eligibility').className = supported ? 'good' : 'warn';
  const checked = a.checked_at ? new Date(a.checked_at).toLocaleString('zh-CN', {hour12: false}) : '尚无';
  $('checked-at').textContent = '云端核验：' + checked;
  $('blocker-title').textContent = supported ? '资格已支持；当前仍为未部署预览' : '当前账号不支持按需购买，真实环境尚未创建';
  $('blocker-detail').textContent = supported ? '只读核验已支持按需。需重新确认实时价格、接入真实执行器和自动清理后才能部署。' : a.connected && a.postpaid_supported === false ? 'CFW 官方 API 返回 is_support_postpaid=false；购买页也仅提供包年/包月。未提交订单或创建收费资源。' : '当前无法确定按需资格，请重新核验；历史购买页面仅提供包年/包月。';
  $('api-result').textContent = a.connected ? `is_support_postpaid=${String(a.postpaid_supported)}; firewall_count=${a.firewall_count ?? '未知'}` : '暂无成功的账号核验';
  $('account-note').textContent = `核验时间：${checked}。CFW 实例数为北京四项目查询值；本轮创建数始终为 0。`;
  $('real-test').textContent = supported ? '真实演练不可用 · 尚未部署' : '真实演练不可用 · 按需资格受限';
}
async function refresh() {
  try {
    const d = await json('/api/status'); renderAccount(d.account);
    if (!scenarios.length) {
      scenarios = d.plan.scenarios;
      scenarios.forEach((s, i) => {
        const o = element('option', s.name); o.value = s.id; $('scenario-select').append(o);
        const b = element('button', '', 'scenario-card'); b.dataset.scenario = s.id; b.type = 'button';
        b.append(element('span', String(i + 1).padStart(2, '0') + ' / ' + s.tag, 'scenario-number'), element('strong', s.name), element('p', s.description));
        b.onclick = () => select(s.id); $('scenario-grid').append(b);
      }); select(selected);
    }
    $('local-update').textContent = '本地页面刷新：' + new Date().toLocaleTimeString('zh-CN', {hour12: false}) + '；云端核验时间见上方。真实访问日志：未采集。';
  } catch (e) { toast(e.message); }
}
function tick(now) {
  if (previous !== null) elapsed += Math.min(now - previous, 100) * Number($('speed').value);
  previous = now;
  const stage = Math.min(3, Math.floor(elapsed / 2200));
  const spec = scenarios.find(s => s.id === selected);
  document.querySelectorAll('.walk-step').forEach((e, i) => e.classList.toggle('active', i === stage));
  document.querySelectorAll('.node').forEach(e => e.classList.toggle('active', e.id === (stage === 2 ? 'node-logs' : 'node-cfw')));
  $('walk-status').textContent = '方案推演 ' + (stage + 1) + '/4 · ' + spec.stages[stage] + '（未实测）';
  const outbound = selected === 'egress';
  let t = (elapsed % 2200) / 2200;
  const blocked = stage === 1 && selected !== 'ips';
  let path = outbound ? 'b' : 'a';
  if (!blocked) {
    path = t < 0.5 ? (outbound ? 'b' : 'a') : (outbound ? 'a' : 'b');
    t = (t * 2) % 1;
  }
  const edge = $('edge-ingress-' + path);
  if (outbound) t = 1 - t;
  const point = edge.getPointAtLength(edge.getTotalLength() * t);
  $('flow-dot').setAttribute('cx', point.x); $('flow-dot').setAttribute('cy', point.y);
  $('flow-dot').setAttribute('visibility', stage === 2 || reducedMotion ? 'hidden' : 'visible');
  if (elapsed >= 8800) {
    $('flow-dot').setAttribute('visibility', 'hidden'); $('pause').disabled = true; frame = null;
    $('walk-status').textContent = '方案推演结束。当前仍未部署、未实测；真实验收需完成请求与云端日志关联。'; return;
  }
  frame = requestAnimationFrame(tick);
}
$('play').onclick = () => {
  if (!scenarios.length) return;
  stop(); $('pause').disabled = false;
  if (reducedMotion) toast('已遵循减少动态效果设置：展示步骤，不播放流量点。');
  frame = requestAnimationFrame(tick);
};
$('pause').onclick = () => {
  paused = !paused; $('pause').textContent = paused ? '继续' : '暂停';
  if (paused) { cancelAnimationFrame(frame); previous = null; }
  else frame = requestAnimationFrame(tick);
};
$('scenario-select').onchange = e => select(e.target.value);
$('refresh').onclick = async () => {
  $('refresh').disabled = true; $('refresh').textContent = '正在只读核验…';
  try { const d = await json('/api/preflight', {method: 'POST', headers: {'X-Demo-Token': token}}); renderAccount(d.account); toast('云端核验已更新；未创建资源。'); }
  catch (e) { toast(e.message); }
  finally { $('refresh').disabled = false; $('refresh').textContent = '↻ 重新核验按需资格'; }
};
refresh(); setInterval(refresh, 5000);
