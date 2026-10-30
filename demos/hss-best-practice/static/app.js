'use strict';
const $=id=>document.getElementById(id);
let current=null, events=[], toastTimer, refreshing=false;
let scenarios=[],selectedScenario='suid';
const chain=new window.HssAttackChain();
const seenJobs=new Set();
const token=document.querySelector('meta[name="demo-token"]').content;
const labelMap={online:'在线',not_installed:'未安装',offline:'离线',opened:'已开启',closed:'未开启',ACTIVE:'运行中',BUILD:'创建中',SHUTOFF:'已关机'};
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,6000);}
async function json(url,options){const r=await fetch(url,{cache:'no-store',...options});const d=await r.json();if(!r.ok)throw new Error(d.error||`请求失败 ${r.status}`);return d;}
function metric(id,value,good){const el=$(id);el.textContent=labelMap[value]||value||'未上报';el.className=good?'good':'warn';}
function element(tag,text,cls){const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;}
function time(ts){return ts?new Date(Number(ts)).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'—';}
function banner(errors){$('error-banner').hidden=!errors.length;$('error-banner').textContent=errors.join('；');}
function renderStatus(d){
 current=d;
 $('connection').textContent=d.connected?'● 已连接真实云账户':'云账户未连接';
 metric('ecs-status',d.ecs_status,d.ecs_status==='ACTIVE');
 metric('agent-status',d.host.agent_status,d.host.agent_status==='online');
 metric('protect-status',d.host.protect_status,d.host.protect_status==='opened');
 $('protection-version').textContent=d.host.version||'未上报防护版本';
 $('host-name').textContent=d.resources.server_id?d.demo_id:'尚未创建专用测试主机';
 $('demo-id').textContent=d.demo_id;$('public-ip').textContent=d.resources.public_ip||'未分配';
 $('ssh-cidr').textContent=d.plan?.ssh_cidr||'预检后确定';$('flavor').textContent=d.plan?.flavor||'预检后确定';
 $('busy-label').textContent=d.busy?'● 操作执行中，请稍候':'每次仅执行一个操作';
 const checks={...d.checks,install:d.host.agent_status==='online',protect:d.host.protect_status==='opened'};
 document.querySelectorAll('.step').forEach(el=>{const done=!!checks[el.dataset.stage];el.classList.toggle('done',done);el.querySelector('.stage-state').textContent=done?'已完成':'待执行';});
 const prerequisites={provision:!!d.checks.preflight,install:!!d.resources.server_id,protect:d.host.agent_status==='online',exercise:d.host.protect_status==='opened'&&d.host.agent_status==='online'&&!!scenarios.length,prepare_scenarios:!!d.resources.server_id,risks:!!d.resources.server_id,cleanup_artifacts:!!d.resources.server_id,acknowledge:!!d.checks.artifacts_clean,cleanup:Object.keys(d.resources).length>0,preflight:true};
 document.querySelectorAll('button.action').forEach(b=>b.disabled=d.busy||!prerequisites[b.dataset.action]);
 banner(d.errors||[]);renderJobs(d.jobs||[]);renderDetection();
 chain.sync(d.last_exercise,scenarios.find(s=>s.id===(d.last_exercise?.scenario_id||'suid')));
}
function renderJobs(jobs){
 const box=$('job-feed');box.replaceChildren();
 if(!jobs.length&&!current?.journal?.length){box.append(element('div','暂无执行记录。','empty'));return;}
 for(const j of [...jobs].reverse()){
  const row=element('article',undefined,'job'),head=element('div',undefined,'job-head');
  head.append(element('strong',j.label),element('span',{running:'执行中',success:'执行完成',error:'执行失败'}[j.status],j.status==='error'?'bad':j.status==='success'?'good':'warn'));
  row.append(head,element('div',time(j.started_at),'job-time'));
  if(j.result||j.error)row.append(element('pre',j.error||JSON.stringify(j.result,null,2)));
  box.append(row);
  if(j.status==='success'&&!seenJobs.has(j.id)){
   seenJobs.add(j.id);
   if(j.action==='risks')renderRisks(j.result);
  }
 }
 for(const j of current?.journal||[]){const row=element('article',undefined,'job');row.append(element('strong',j.name),element('div',time(j.ts),'job-time'),element('pre',j.detail));box.append(row);}
}
function renderRisks(result){
 const box=$('risk-summary');box.className='risk-content';box.replaceChildren();
 box.append(element('strong',`漏洞报告：${result.vulnerabilities?.length||0} 条（最多显示 20 条）`),element('br'),element('strong',`基线报告：${result.baseline?.length||0} 条（最多显示 20 条）`));
 for(const e of result.errors||[])box.append(element('p',e,'bad'));
 if(!result.baseline?.length)box.append(element('p','基线接口暂未返回条目，可能尚未扫描或无当前标准结果，不等同于基线通过。'));
 if(!result.errors?.length&&!result.vulnerabilities?.length&&!result.baseline?.length)box.append(element('p','本次接口未返回风险条目；首次扫描可能尚未完成，不等于主机没有风险。'));
 for(const item of [...result.vulnerabilities||[],...result.baseline||[]].slice(0,10))box.append(element('p',item.vul_name||item.check_rule_name||item.check_name||item.name||'风险条目：请在云控制台复核'));
}
function renderEvents(d){
 events=d.events||[];$('event-count').textContent=d.total??events.length;
 $('event-hint').textContent='HSS 主机级事件 · 实际查询';$('last-update').textContent='更新于 '+new Date().toLocaleTimeString('zh-CN',{hour12:false});
 const box=$('alert-feed');box.replaceChildren();
 if(!events.length){box.append(element('div','HSS 当前未返回此主机的安全事件。首次演练后请等待云端检测与上报。','empty'));renderDetection();return;}
 const table=element('table'),thead=element('thead'),tr=element('tr');for(const t of ['安全事件','级别','发生时间','云端处置状态'])tr.append(element('th',t));thead.append(tr);table.append(thead);
 const body=element('tbody');for(const e of events){const row=element('tr');row.append(element('td',e.event_name||e.event_class_name||'未命名事件'));const sev=element('td');sev.append(element('span',String(e.severity??'未知'),'severity'));row.append(sev,element('td',time(e.occur_time)),element('td',({handled:'已处理',unhandled:'未处理',ignored:'已忽略'})[e.handle_status]||String(e.handle_status??'未返回')));body.append(row);}table.append(body);box.append(table);renderDetection();
}
function renderDetection(){
 const el=$('detection-status'),run=current?.last_exercise,started=run?.started_at;
 const matching=run?.matched_events?.[0];
 let message='先确认主机与 Agent 均已就绪',tone='';
 if(started){if(matching){message='真实检出：'+(matching.event_name||matching.event_class_name)+'（'+(run.scenario_name||'文件提权')+'，主机/时间/类型匹配）';tone='good';}else if(run.detection_status==='query_error'){message='HSS 查询失败，当前不能判断是否检出';tone='bad';}else if(run.status==='execution_error'){message='动作执行异常，请查看后端记录，不能据此认定 HSS 已阻断';tone='bad';}else{const seconds=Math.floor((Date.now()-started)/1000);message=seconds>180?'暂未检出：超过 180 秒，请检查场景策略、版本和事件延迟。':`等待真实 HSS 检出 · 已等待 ${Math.max(seconds,0)} 秒`;tone='warn';}}
 else if(current?.host.protect_status==='opened'){message='防护已就绪，可以开始受控演练';tone='good';}
 el.className='detection '+tone;el.lastElementChild.textContent=message;
}
async function refresh(){if(refreshing)return;refreshing=true;try{const results=await Promise.allSettled([json('/api/status'),json('/api/events')]);const errors=[];if(results[0].status==='fulfilled')renderStatus(results[0].value);else errors.push('状态查询：'+results[0].reason.message);if(results[1].status==='fulfilled')renderEvents(results[1].value);else{$('event-count').textContent='不可用';errors.push('告警查询：'+results[1].reason.message);}if(errors.length)banner(errors);}finally{refreshing=false;}}
function selectScenario(id){const spec=scenarios.find(s=>s.id===id);if(!spec)return;selectedScenario=id;$('scenario-select').value=id;$('scenario-title').textContent=spec.name;$('scenario-description').textContent=spec.description;$('scenario-policy').textContent='观察项：'+spec.expected+'。策略条件：'+spec.policy;$('scenario-source').href=spec.source;document.querySelectorAll('.scenario-card').forEach(e=>{const selected=e.dataset.scenario===id;e.classList.toggle('selected',selected);e.setAttribute('aria-pressed',selected);});}
async function loadScenarios(){try{scenarios=(await json('/api/scenarios')).scenarios;$('scenario-select').replaceChildren();$('scenario-grid').replaceChildren();for(const [i,s]of scenarios.entries()){const option=element('option',s.name);option.value=s.id;$('scenario-select').append(option);const card=element('button',undefined,'scenario-card');card.dataset.scenario=s.id;card.setAttribute('aria-pressed','false');card.append(element('span',String(i+1).padStart(2,'0')+' / '+s.phase,'scenario-number'),element('strong',s.name),element('p',s.description),element('small',s.tools.length?'依赖：'+s.tools.join(' / '):'无需额外工具'));card.onclick=()=>selectScenario(s.id);$('scenario-grid').append(card);}selectScenario(selectedScenario);if(current)renderStatus(current);}catch(e){toast('场景加载失败：'+e.message);}}
$('scenario-select').addEventListener('change',e=>selectScenario(e.target.value));
async function execute(action){
 const data={id:action};
 if(action==='exercise')data.scenario_id=selectedScenario;
 if(action==='cleanup'){const value=prompt(`将关闭 HSS 并释放本次创建的 ECS、系统盘、EIP 和网络。输入 Demo ID 确认：\n${current.demo_id}`);if(value!==current.demo_id){if(value!==null)toast('Demo ID 不匹配，未执行清理');return;}data.confirmation=value;}
 document.querySelectorAll('button.action').forEach(b=>b.disabled=true);
 try{await json('/api/execute',{method:'POST',headers:{'Content-Type':'application/json','X-Demo-Token':token},body:JSON.stringify(data)});toast('任务已提交，执行结果会显示在“后端执行记录”中');if(action==='exercise'){chain.begin(scenarios.find(s=>s.id===data.scenario_id));$('architecture').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});}await refresh();}catch(e){toast(e.message);await refresh();}
}
document.querySelectorAll('button.action').forEach(b=>b.addEventListener('click',()=>execute(b.dataset.action)));
$('refresh').addEventListener('click',()=>{refresh();toast('正在查询云端状态');});
for(const key of ['alerts','jobs'])$('tab-'+key).addEventListener('click',()=>{for(const k of ['alerts','jobs']){const chosen=k===key;$('tab-'+k).classList.toggle('active',chosen);$('tab-'+k).setAttribute('aria-selected',chosen);$(k==='alerts'?'alert-feed':'job-feed').hidden=!chosen;}});
loadScenarios();refresh();setInterval(refresh,5000);
