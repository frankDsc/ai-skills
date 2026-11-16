'use strict';
let transferPolling=false;
const transferPhases={idle:'等待开始',preparing:'正在生成合成数据',transferring:'正在真实传输',verifying:'正在云端校验',completed:'云端接收与校验通过',failed:'任务失败'};
const mib=1024*1024;
async function refreshTransfer(){
  if(transferPolling)return;transferPolling=true;
  try{
    const s=await json('/api/transfer');
    const running=['preparing','transferring','verifying'].includes(s.phase);
    $('transfer-start').disabled=running||!s.enabled;
    text('transfer-phase',s.enabled?transferPhases[s.phase]:'等待真实 ECS 就绪');
    text('transfer-rate',s.phase==='transferring'?(s.bytes_per_second/mib).toFixed(2):s.phase==='completed'?'已完成':'—');
    text('transfer-average',s.average_bytes_per_second?(s.average_bytes_per_second/mib).toFixed(2):'—');
    text('transfer-bytes',`${(s.sent_bytes/mib).toFixed(1)} / ${(s.total_bytes/mib).toFixed(0)} MiB`);
    const eta=s.bytes_per_second>0?(s.total_bytes-s.sent_bytes)/s.bytes_per_second:null;
    text('transfer-eta',`预计剩余：${s.phase==='completed'?'已完成':eta===null?'—':Math.ceil(eta)+' 秒'}`);
    text('transfer-integrity',s.verified?'SHA-256 一致':s.phase==='failed'?'未验收':s.phase==='verifying'?'校验中':'待校验');
    $('transfer-integrity').className=s.verified?'verified':'';
    text('transfer-time',`传输耗时：${s.elapsed_seconds?s.elapsed_seconds.toFixed(2)+' 秒':'—'}`);
    const percent=s.total_bytes?Math.min(100,100*s.sent_bytes/s.total_bytes):0;
    $('transfer-progress').style.width=percent+'%';text('transfer-progress-label',`${percent.toFixed(1)}% 已发送`);
    text('transfer-sampling',s.error||`${s.samples.length} 个实测采样点 · ${s.target_size_bytes===s.total_bytes?'目标长度已确认':'目标接收长度待确认'}`);
    for(const id of ['transfer-packet','target-packet']){
      $(id).classList.toggle('running',s.phase==='transferring'&&s.bytes_per_second>0);
      $(id).style.setProperty('--packet-duration',`${Math.max(.25,Math.min(3,2/(s.bytes_per_second/mib+0.1)))}s`);
    }
    const samples=s.samples,peak=Math.max(0,...samples.map(p=>p.bytes_per_second));
    text('transfer-peak',`窗口峰值 ${(peak/mib).toFixed(2)} MiB/s`);
    const t0=samples[0]?.seconds||0,t1=samples[samples.length-1]?.seconds||1;
    const points=samples.map(p=>`${1000*(p.seconds-t0)/Math.max(.001,t1-t0)},${95-85*p.bytes_per_second/Math.max(1,peak)}`);
    $('rate-line').setAttribute('points',points.join(' '));
    $('rate-area').setAttribute('d',points.length>1?'M0 105 L'+points.join(' L')+' L1000 105 Z':'');
  }catch(error){text('transfer-phase','速率采样连接异常');}
  finally{transferPolling=false;}
}
$('transfer-start').onclick=async()=>{
  $('transfer-start').disabled=true;
  try{await json('/api/transfer/start',{method:'POST',headers:{'X-Demo-Token':token}});await refreshTransfer();}
  catch(error){toast(error.message);await refreshTransfer();}
};
refreshTransfer();setInterval(refreshTransfer,1000);
