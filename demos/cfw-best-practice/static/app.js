'use strict';
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="demo-token"]').content;
let scenarios = [], selected = 'ingress', frame = null, elapsed = 0, previous = null, paused = false;
let mode = 'preview', live = null;
const expandedRuns = new Set();
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
  $('walk-status').textContent = '方案推演已就绪；以上为预期步骤，实际执行结果请查看实测区。';
}
function renderAccount(a) {
  $('resource-count').textContent = '0'; $('resource-detail').textContent = 'CFW / ECS / EIP 均未创建';
  $('cost-value').textContent = '¥0'; $('cost-label').textContent = '本轮新增费用';
  $('cost-detail').textContent = '未创建收费资源；非账户总账单';
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
    const d = await json('/api/status'); mode = d.mode;
    if (mode === 'live') renderLive(d); else renderAccount(d.account);
    if (!scenarios.length) {
      scenarios = d.plan.scenarios;
      scenarios.forEach((s, i) => {
        const o = element('option', s.name); o.value = s.id; $('scenario-select').append(o);
        const b = element('button', '', 'scenario-card'); b.dataset.scenario = s.id; b.type = 'button';
        b.append(element('span', String(i + 1).padStart(2, '0') + ' / ' + s.tag, 'scenario-number'), element('strong', s.name), element('p', s.description));
        b.onclick = () => select(s.id); $('scenario-grid').append(b);
      }); select(selected);
    }
    $('local-update').textContent = '本地页面刷新：' + new Date().toLocaleTimeString('zh-CN', {hour12: false}) + '；云端核验时间单独显示。';
  } catch (e) { toast(e.message); }
}
function tick(now) {
  if (previous !== null) elapsed += Math.min(now - previous, 100) * Number($('speed').value);
  previous = now;
  const stage = Math.min(3, Math.floor(elapsed / 2200));
  const spec = scenarios.find(s => s.id === selected);
  document.querySelectorAll('.walk-step').forEach((e, i) => e.classList.toggle('active', i === stage));
  document.querySelectorAll('.node').forEach(e => e.classList.toggle('active', e.id === (stage === 2 ? 'node-logs' : 'node-cfw')));
  $('walk-status').textContent = '方案推演 ' + (stage + 1) + '/4 · ' + spec.stages[stage] + '（方案预期）';
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
    $('walk-status').textContent = '方案推演结束。本次动画不产生云端测试数据；真实结果请查看实测区。'; return;
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
  if (mode === 'live') { await executeLive('refresh'); return; }
  $('refresh').disabled = true; $('refresh').textContent = '正在只读核验…';
  try { const d = await json('/api/preflight', {method: 'POST', headers: {'X-Demo-Token': token}}); renderAccount(d.account); toast('云端核验已更新；未创建资源。'); }
  catch (e) { toast(e.message); }
  finally { $('refresh').disabled = false; $('refresh').textContent = '↻ 重新核验按需资格'; }
};

function date(ms) { return ms ? new Date(ms).toLocaleString('zh-CN', {timeZone:'Asia/Shanghai',hour12:false}) : '待查询'; }
function renderLive(d) {
  live = d; const c = d.cloud || {}, checks = d.checks || {}, runs = d.runs || [];
  const passed = runs.filter(r => r.status === 'passed').length;
  const active = runs.findLast ? runs.findLast(r => r.status === 'running') : [...runs].reverse().find(r => r.status === 'running');
  $('real-results').hidden = false;
  $('mode-label').textContent = d.released ? '真实环境已释放 · 保留证据' : '真实云端演练 · 中国香港';
  $('resource-count').textContent = d.resources_created;
  $('resource-detail').textContent = ['probe','business'].map(k => `${k==='probe'?'探测':'业务'} ECS: ${c.ecs?.[k] || '待核验'}`).join(' / ');
  if(d.released)$('resource-detail').textContent='CFW / ECS / 盘 / EIP 等均已释放';
  $('protection-label').textContent = '业务 EIP 的 CFW 防护';
  const protectedNow = c.eip?.status === 0 && checks.protected && !d.released;
  $('eligibility').textContent = d.released ? '已释放' : protectedNow ? '已保护' : '待接入';
  $('eligibility').className = protectedNow ? 'good' : 'warn';
  $('checked-at').textContent = '云端核验：' + date(c.checked_at);
  $('real-status').textContent = `${passed} / ${runs.length}`;
  $('event-detail').textContent = `已通过 / 已运行 · ${d.logs.length} 条匹配原生日志`;
  $('cost-label').textContent = '本轮预算'; $('cost-value').textContent = '¥10';
  const left = Math.max(0, Math.ceil((d.cleanup_due_at-Date.now())/60000));
  $('cost-detail').textContent = d.released ? '资源已释放；账单可能延后入账' : `约 ${left} 分钟后清理 · 非平台硬限额`;
  if(d.billing_summary?.currency==='CNY'){
    $('cost-label').textContent='本轮已出账';$('cost-value').textContent='¥'+Number(d.billing_summary.amount).toFixed(2);
    $('cost-detail').textContent=`预算 ¥10 · 已核对 ${d.billing_summary.record_count} 条消费记录`;
  }
  $('blocker-title').textContent = d.released ? '本轮真实资源已释放，实测证据保留' : checks.bootstrap && protectedNow ? '真实 CFW 与双 ECS 已接通' : '真实云资源已创建，正在完成服务接入';
  $('blocker-detail').textContent = `中国香港 ${d.region} · CFW ${c.firewall_status===2?'运行中':'等待核验'} · ${c.charge_mode===1?'按需计费已确认':'计费模式待核验'}。${c.error || '请求结果与日志分别验收，未命中不会显示通过。'}`;
  if(d.released)$('blocker-detail').textContent=`中国香港 ${d.region} · 本轮资源已释放。下方保留真实请求与日志，实测按钮已关闭。`;
  $('demo-id').textContent = d.demo_id; $('cleanup-time').textContent = d.released ? '已完成释放' : date(d.cleanup_due_at)+' 左右';
  $('native-update').textContent = '云端查询：' + date(c.checked_at);
  const proof=d.release_verification;
  if(d.released)$('native-update').textContent=proof?.checked_at?'释放核验：'+date(proof.checked_at):'资源已释放 · 历史实测记录';
  const phase = {baseline:'基线请求',deny:'临时拒绝与请求验证',restore:'删除演练规则并验证恢复',completed:'完成请求，关联日志'};
  $('live-state').textContent = active ? `正在执行：${active.scenario} · ${phase[active.phase] || active.phase}` : d.released ? '资源已释放；下方为本轮真实记录。' : checks.bootstrap && protectedNow ? '服务与防护已就绪，可执行固定实测。每阶段结果将实时写入。' : '资源已运行；等待合成服务部署及防护接入完成，实测入口暂不开放。';
  $('api-result').textContent = `region=${d.region}; charge_mode=${c.charge_mode ?? '未知'}; CFW status=${c.firewall_status ?? '未知'}; EIP protection=${c.eip?.status ?? '未知'}`;
  $('account-note').textContent = '只查询本轮资源。云端约每 15 秒刷新；页面每 5 秒读取最新执行状态。';
  if(d.released){
    $('checked-at').textContent=proof?.checked_at?'释放核验：'+date(proof.checked_at):'资源已释放';
    const verifiedEmpty=['cfw_matching','ecs_matching','evs_matching','eip_matching','bandwidth_matching','vpc_matching','subnet_matching','security_group_matching'].every(k=>proof?.direct_checks?.[k]===0);
    $('api-result').textContent=verifiedEmpty?'云端复查：本轮 CFW、ECS、EVS、EIP、带宽与专属网络均为 0':'已释放；云端直接复查尚无完整结果';
    $('account-note').textContent='历史运行快照不代表资源仍在线；释放后不再执行云端测试。';
    document.querySelector('.cost-panel strong').textContent='本轮资源已释放，历史实测与账单核验已保留';
    document.querySelector('.cost-panel p').textContent='自动清理任务已结束。真实执行入口关闭，导出功能继续可用。';
  }
  $('workflow-status').textContent = d.released ? '已释放；证据保留' : '真实运行 · 按计划自动释放';
  document.querySelectorAll('[data-live-stage]').forEach(e => {
    const k=e.dataset.liveStage, done=d.released || (k==='preflight' ? c.charge_mode===1 : k==='cleanup' ? d.released : !!checks[k]);
    e.classList.toggle('done',done);e.querySelector('.stage-state').textContent=d.released?(k==='cleanup'?'已释放':'历史已完成'):done?'已完成':k==='cleanup'&&d.cleanup_scheduled?'已安排':'进行中';
  });
  const ready = checks.bootstrap && protectedNow && !d.busy && !active && !d.released && left>0 && runs.length<20;
  document.querySelectorAll('[data-real-scenario]').forEach(b => b.disabled=!ready);
  $('real-test').disabled=!ready || selected==='ips';
  $('real-test').textContent = selected==='ips' ? 'IPS 可选场景 · 未接入实际执行器' : ready ? '▷ 执行当前选定场景' : '等待真实服务和防护就绪';
  $('restore').disabled=d.busy || d.released || !checks.protected;
  $('cleanup').disabled=d.busy || d.released || !d.resources_created;
  renderRuns(runs); renderLogs(d.logs);
  $('real-jobs').textContent = (d.jobs || []).slice(-3).map(j => `${j.action}${j.scenario?' / '+j.scenario:''}：${({running:'执行中',success:'执行结束',error:'未完成'})[j.status]}${j.error?' · '+j.error:''}`).join('；');
}
function renderRuns(runs) {
  const feed=$('real-run-feed');feed.replaceChildren();
  if(!runs.length){feed.append(element('div','尚未执行云端实测。下面的策略推演不是实测结果。','empty'));return;}
  for(const r of [...runs].reverse().slice(0,5)){
    const card=element('article','','real-run');
    const head=element('div','','real-run-head');
    head.append(element('strong',({ingress:'入站访问控制',egress:'出站访问控制',priority:'规则优先级'})[r.scenario]||r.scenario),element('span',({running:'执行中',awaiting_logs:'请求验证通过 · 等待日志',passed:'请求 + 原生日志通过',failed:'存在未通过项',error:'执行异常'})[r.status]||r.status,r.status==='passed'?'good':'warn'));
    card.append(head,element('small',date(r.started_at)+' · '+r.id,'muted'));
    const strip=element('div','','phase-results');
    for(const [k,label] of [['baseline','基线'],['deny','拒绝'],['restored','恢复']]){
      const ms=r.measurements?.[k]||[], ok=ms.filter(m=>m.http_status===200).length;
      strip.append(element('span',`${label}：${ms.length?(k==='deny'?`${ms.length-ok}/${ms.length} 请求失败`:`${ok}/${ms.length} HTTP 200`):'待执行'}`));
    }
    card.append(strip);
    const measurements=Object.entries(r.measurements||{}).flatMap(([phase,ms])=>ms.map(m=>({...m,phase})));
    if(measurements.length){
      const chart=document.createElementNS('http://www.w3.org/2000/svg','svg');chart.setAttribute('viewBox','0 0 600 90');chart.setAttribute('role','img');chart.setAttribute('aria-label','实际 HTTP 请求耗时；绿色为200，橙色为失败');chart.classList.add('latency-chart');
      const max=Math.max(1,...measurements.map(m=>m.elapsed_ms));
      measurements.forEach((m,i)=>{const h=56*m.elapsed_ms/max;const rect=document.createElementNS(chart.namespaceURI,'rect');rect.setAttribute('x',10+i*580/measurements.length);rect.setAttribute('y',66-h);rect.setAttribute('width',Math.max(4,480/measurements.length));rect.setAttribute('height',Math.max(2,h));rect.setAttribute('fill',m.http_status===200?'#259675':'#d58a38');const title=document.createElementNS(chart.namespaceURI,'title');title.textContent=`${m.phase} · ${m.elapsed_ms}ms · HTTP ${m.http_status??m.error}`;rect.append(title);chart.append(rect);});
      card.append(chart,element('small','实际请求耗时（毫秒） · 绿：HTTP 200 / 橙：请求失败，需另查 CFW 日志','muted'));
      const details=document.createElement('details');details.open=expandedRuns.has(r.id);details.append(element('summary',`查看 ${measurements.length} 条真实请求与五元组`));
      details.ontoggle=()=>{if(details.open)expandedRuns.add(r.id);else expandedRuns.delete(r.id);};
      const table=document.createElement('table');const tr=document.createElement('tr');['阶段','请求结果','耗时 ms','源 → 目的'].forEach(x=>tr.append(element('th',x)));table.append(tr);
      measurements.forEach(m=>{const row=document.createElement('tr');[m.phase,m.http_status??m.error,m.elapsed_ms,`${m.src_ip}:${m.src_port} → ${m.dst_ip}:${m.dst_port}`].forEach(x=>row.append(element('td',String(x))));table.append(row);});
      const wrap=element('div','','table-wrap');wrap.append(table);details.append(wrap);card.append(details);
    }
    if(r.error||r.restore_errors||r.logs_error)card.append(element('p',[r.error,...(r.restore_errors||[]),r.logs_error].filter(Boolean).join('；'),'bad'));
    card.append(element('p',`网络行为：${r.network_behavior_passed?'通过':'尚未通过'}；已关联拒绝请求 ${r.matched_request_count??'待核验'}/3；原生日志 ${r.matched_logs?.length||0} 条（含 TCP 重传）。`,'helper'));feed.append(card);
  }
}
function renderLogs(logs){
  const feed=$('real-log-feed');feed.replaceChildren();
  if(!logs.length){feed.append(element('div','尚无精确匹配的原生拒绝日志；不会用请求失败代替日志证据。','empty'));return;}
  const table=document.createElement('table'),head=document.createElement('tr');['云端时间','动作 / 规则','源 → 目的'].forEach(x=>head.append(element('th',x)));table.append(head);
  const seen=new Set();for(const l of logs){const id=[l.rule_id,l.log_id,l.hit_time,l.src_port].join('|');if(seen.has(id))continue;seen.add(id);const row=document.createElement('tr');[date(l.hit_time),`${l.action} / ${l.rule_name||l.rule_id}`,`${l.src_ip}:${l.src_port} → ${l.dst_ip}:${l.dst_port}`].forEach(x=>row.append(element('td',String(x))));table.append(row);}feed.append(table);
}
async function executeLive(id,scenario){
  const data={id,scenario_id:scenario};
  if(id==='cleanup'){
    const answer=prompt(`将删除本轮 CFW、双 ECS、盘、EIP 与专属网络。请输入完整 Demo ID：${live.demo_id}`);
    if(answer!==live.demo_id){if(answer!==null)toast('Demo ID 不匹配，未释放');return;}data.confirmation=answer;
  }
  try{await json('/api/execute',{method:'POST',headers:{'Content-Type':'application/json','X-Demo-Token':token},body:JSON.stringify(data)});toast('固定动作已提交，实际状态会持续更新。');await refresh();}
  catch(e){toast(e.message);}
}
document.querySelectorAll('[data-real-scenario]').forEach(b=>b.onclick=()=>executeLive('exercise',b.dataset.realScenario));
$('real-test').onclick=()=>executeLive('exercise',selected);
$('restore').onclick=()=>executeLive('restore');
$('cleanup').onclick=()=>executeLive('cleanup');
refresh(); setInterval(refresh, 5000);
