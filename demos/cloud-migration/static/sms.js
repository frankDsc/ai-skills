'use strict';
let smsPolling=false;
async function refreshSms(){
  if(smsPolling)return;smsPolling=true;
  try{
    const s=await json('/api/sms');
    if(!s.enabled){$('sms-panel').hidden=true;return;}
    $('sms-panel').hidden=false;
    text('sms-mode',s.continuous_sync===false?'源端停写后全量迁移；持续同步未通过':'持续同步测试');
    text('sms-deadline',s.auto_release_at?new Date(s.auto_release_at).toLocaleTimeString()+' 主机到期；随后自动清理':'未配置资源到期时间');
    text('sms-source',s.released?'已释放':s.source_ip||'准备中');text('sms-target',s.released?'已释放':s.target_ip||'准备中');
    const t=s.task||{},subs=t.sub_tasks||[];
    const current=subs.find(x=>t.subtask_info?.startsWith(x.name+'-'))||[...subs].reverse().find(x=>x.start_date&&!x.end_date);
    const rate=typeof t.migrate_speed==='number'?t.migrate_speed:null;
    text('sms-rate',rate===null?'—':rate.toFixed(2));
    const states={READY:'等待开始',RUNNING:'迁移进行中',SYNCING:'持续同步中',MIGRATE_SUCCESS:'SMS 主机迁移完成',SYNC_SUCCESS:'同步完成',MIGRATE_FAIL:'SMS 迁移失败',SYNC_FAIL:'同步失败',ABORT:'任务中止',DELETING:'任务清理中'};
    text('sms-phase',s.released?'云资源已释放':states[t.state]||t.state||'准备源端应用与 SMS Agent');
    text('sms-progress-value',current?.progress===undefined?'—':current.progress+'%');
    text('sms-subtask',current?.name||t.subtask_info||'等待 Agent 注册');
    $('sms-progress').style.width=Math.max(0,Math.min(100,current?.progress||0))+'%';
    const failed=['MIGRATE_FAIL','SYNC_FAIL','ABORT'].includes(t.state);
    text('sms-remaining',t.state==='MIGRATE_SUCCESS'?'已完成':!failed&&t.remain_seconds>0?Math.ceil(t.remain_seconds)+' 秒':'—');
    const last=s.samples?.[s.samples.length-1];
    const age=last?(Date.now()/1000-last.time):null;
    text('sms-update',last?(t.state==='MIGRATE_SUCCESS'?'最终上报 ':'最近上报 ')+new Date(last.time*1000).toLocaleTimeString()+(age>30&&['RUNNING','SYNCING'].includes(t.state)?' · 采样已过期':''):'等待首个 SMS 样本');
    const taskId=s.task_id||t.id;
    text('sms-task',taskId?(s.released?'历史任务 ':'任务 ')+taskId:'尚未创建 SMS 任务');
    const samples=(s.samples||[]).filter(x=>typeof x.migrate_speed_mbps==='number'&&(!t.create_date||x.time>=t.create_date/1000));
    const peak=Math.max(0,...samples.map(x=>x.migrate_speed_mbps));
    text('sms-peak','本任务峰值 '+peak.toFixed(2)+' Mbit/s');
    const volume=s.source_progress?.totalsize>0?` · SMS 已复制 ${(s.source_progress.replicatesize/1024**3).toFixed(2)} / ${(s.source_progress.totalsize/1024**3).toFixed(2)} GiB`:'';
    text('sms-count',samples.length+' 个实际采样点'+volume);
    const t0=samples[0]?.time||0,t1=samples[samples.length-1]?.time||1;
    $('sms-line').setAttribute('points',samples.map(x=>`${1000*(x.time-t0)/Math.max(1,t1-t0)},${95-85*x.migrate_speed_mbps/Math.max(1,peak)}`).join(' '));
    const running=age!==null&&age<30&&rate>0&&!s.released;
    for(const id of ['sms-packet','sms-target-packet'])$(id).classList.toggle('running',running);
    if($('sms-flow'))$('sms-flow').style.display=running?'block':'none';
    text('sms-check',s.validation?.passed?'验收通过':s.validation?'验收未通过':'待迁移');
    $('sms-route-target').disabled=!s.validation?.passed||s.released;
    $('sms-route-source').disabled=!!s.released;
    $('sms-load-orders').disabled=!!s.released;
    text('sms-active',s.released?'云资源已释放 · 保留历史验收':s.active_side==='target'?'当前访问目标 ECS':'当前访问源 ECS');
    if(s.validation?.passed)$('sms-check').className='verified';
    if(s.target_health)text('sms-orders',`${s.target_health.orders.toLocaleString()} 笔订单 · 目标应用运行中`);
    const feed=$('sms-events');feed.replaceChildren();
    for(const event of (s.events||[]).slice(-6).reverse()){
      const p=document.createElement('p');p.textContent=new Date(event.time*1000).toLocaleTimeString()+'  '+event.message;feed.append(p);
    }
    if(s.error){const p=document.createElement('p');p.textContent=s.error;feed.prepend(p);}
    if(t.error_json){const p=document.createElement('p');p.textContent='SMS 原始错误：'+t.error_json;feed.prepend(p);}
  }catch(error){text('sms-phase','SMS 状态读取失败');}
  finally{smsPolling=false;}
}
refreshSms();setInterval(refreshSms,5000);
function showSmsOrders(data){
  const output=$('sms-order-output');output.replaceChildren();
  const caption=document.createElement('p');caption.textContent=`实际响应：${data.side} ECS / ${data.ip}:8080 · 最新 5 笔合成订单`;output.append(caption);
  const table=document.createElement('table');
  for(const values of [['订单号','虚构客户','商品','金额','状态'],...data.orders.slice(0,5).map(x=>[x.id,x.customer,x.product,'¥'+(x.amount_cents/100).toFixed(2),x.status])]){
    const row=document.createElement('tr');for(const value of values){const cell=document.createElement('td');cell.textContent=value;row.append(cell);}table.append(row);
  }
  output.append(table);
}
$('sms-load-orders').onclick=async()=>{try{showSmsOrders(await json('/api/sms/orders'));}catch(error){toast(error.message);}};
for(const side of ['source','target'])$('sms-route-'+side).onclick=async()=>{
  try{showSmsOrders(await json('/api/sms/route',{method:'POST',headers:{'Content-Type':'application/json','X-Demo-Token':token},body:JSON.stringify({side})}));await refreshSms();}
  catch(error){toast(error.message);}
};
$('sms-export').onclick=async()=>{
  try{
    const evidence=await json('/api/sms');const url=URL.createObjectURL(new Blob([JSON.stringify(evidence,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='sms-migration-evidence.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(error){toast(error.message);}
};
