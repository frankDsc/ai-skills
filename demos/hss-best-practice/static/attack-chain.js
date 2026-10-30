'use strict';
// Visualization consumes actual run state; it never creates a security event.
window.HssAttackChain=class {
 constructor(){this.generation=0;this.paused=false;this.speed=1;this.runKey=null;this.detected=new Set();this.currentRun=null;this.spec=null;this.playing=null;this.submittedAt=0;
  document.getElementById('chain-speed').onchange=e=>this.speed=Number(e.target.value);
  document.getElementById('chain-pause').onclick=()=>{this.paused=!this.paused;document.getElementById('arch').classList.toggle('motion-paused',this.paused);document.getElementById('chain-pause').textContent=this.paused?'继续动画':'暂停动画';document.getElementById('chain-motion-note').textContent=this.paused?'仅动画暂停，真实任务与告警查询仍在进行':'';};
  document.getElementById('chain-replay').onclick=()=>this.replay();
 }
 phase(n,text,tone=''){document.getElementById('chain-state').textContent=text;document.getElementById('chain-state').className='chain-state '+tone;document.querySelectorAll('.chain-step').forEach((e,i)=>{e.classList.toggle('done',i<n);e.classList.toggle('current',i===n);});}
 reset(){this.generation++;this.playing=null;for(const e of document.querySelectorAll('#arch .node'))e.classList.remove('active','hit','awaiting','detected');for(const e of document.querySelectorAll('#arch path.chain-edge')){e.classList.remove('chain-edge');e.style.removeProperty('marker-end');}for(const id of ['flow-dot','flow-halo'])document.getElementById(id)?.setAttribute('visibility','hidden');}
 hit(id,color){const n=document.getElementById('node-'+id);if(!n)return;n.style.setProperty('--chain-color',color);n.classList.add('active','hit');setTimeout(()=>n.classList.remove('hit'),650);}
 async play(paths,color,epoch){
  if(matchMedia('(prefers-reduced-motion: reduce)').matches){for(const id of paths)this.hit(id.split('-').at(-1),color);return;}
  const dot=document.getElementById('flow-dot'),halo=document.getElementById('flow-halo');
  for(const id of paths){
   if(epoch!==this.generation)return;
   const path=document.getElementById('edge-'+id);if(!path)continue;
   path.style.setProperty('--chain-color',color);path.style.markerEnd=color==='#177c57'?'url(#ad)':'url(#ar)';path.classList.add('chain-edge');
   for(const e of [dot,halo]){e?.setAttribute('fill',color);e?.setAttribute('visibility','visible');}
   await new Promise(resolve=>{let distance=0,previous=null;const length=path.getTotalLength();const tick=t=>{
    if(epoch!==this.generation){resolve();return;}
    if(previous!==null&&!this.paused)distance+=(t-previous)*this.speed/1400;
    previous=t;const p=path.getPointAtLength(Math.min(distance,1)*length);
    for(const e of [dot,halo]){e?.setAttribute('cx',p.x);e?.setAttribute('cy',p.y);}
    if(distance<1)requestAnimationFrame(tick);else resolve();
   };requestAnimationFrame(tick);});
   if(epoch!==this.generation)return;this.hit(id.split('-').at(-1),color);
  }
  if(epoch===this.generation)for(const e of [dot,halo])e?.setAttribute('visibility','hidden');
 }
 begin(spec){this.reset();this.spec=spec;this.submittedAt=Date.now();this.currentRun=null;this.runKey=null;this.phase(0,'演练指令下发 · '+spec.name);this.hit('operator','#c7000b');const epoch=this.generation;
  this.playing=this.play(spec.flow,'#c7000b',epoch).then(()=>{if(epoch===this.generation){this.playing=null;this.afterAttack();}});
 }
 sync(run,spec){if(!run)return;
  if(this.submittedAt&&Number(run.started_at)<this.submittedAt-1500)return;
  this.currentRun=run;
  this.spec=spec||this.spec;if(!this.spec)return;
  const key=run.marker||String(run.started_at);
  if(key!==this.runKey){this.runKey=key;if(!this.submittedAt){this.reset();this.phase(1,'演练状态 · '+this.spec.name);}this.submittedAt=0;}
  if(!this.playing)this.afterAttack();
 }
 afterAttack(){const run=this.currentRun;if(!run||!this.spec)return;for(const n of document.querySelectorAll('#arch .awaiting'))n.classList.remove('awaiting');
  if(run.detection_status==='detected'){
   if(!this.detected.has(this.runKey)){this.detected.add(this.runKey);this.phase(3,'收到真实 HSS 告警 · '+this.spec.name,'good');const epoch=this.generation;
    this.playing=this.play(this.spec.detection_flow,'#177c57',epoch).then(()=>{if(epoch===this.generation){this.playing=null;document.getElementById('node-alerts')?.classList.add('detected');this.phase(3,'真实检出 · '+(run.matched_events?.[0]?.event_name||this.spec.expected),'good');}});
   }else this.phase(3,'真实检出 · '+(run.matched_events?.[0]?.event_name||this.spec.expected),'good');
   return;
  }
  if(run.detection_status==='query_error'){this.phase(2,'告警查询失败，不能判断是否检出','bad');return;}
  if(run.status==='execution_error'){this.phase(1,'动作执行异常，请查看后端记录；未确认阻断','bad');return;}
  if(run.status==='executing'){this.phase(1,'主机正在执行 · '+this.spec.name);document.getElementById('node-ecs')?.classList.add('awaiting');return;}
  document.getElementById('node-hss')?.classList.add('awaiting');
  const seconds=Math.max(0,Math.floor((Date.now()-Number(run.started_at))/1000));
  this.phase(2,(seconds>180?'尚未检出 · 请检查场景策略与版本':'等待真实 HSS 告警 · '+seconds+' 秒')+' · '+this.spec.name,'warn');
 }
 replay(){if(!this.spec){return;}this.reset();this.paused=false;document.getElementById('arch').classList.remove('motion-paused');document.getElementById('chain-pause').textContent='暂停动画';document.getElementById('chain-motion-note').textContent='链路重播仅播放已有演示状态，不执行新攻击';this.phase(0,'链路重播 · '+this.spec.name);const epoch=this.generation;
  this.playing=this.play(this.spec.flow,'#c7000b',epoch).then(async()=>{if(epoch!==this.generation)return;if(this.currentRun?.detection_status==='detected')await this.play(this.spec.detection_flow,'#177c57',epoch);if(epoch===this.generation){this.playing=null;this.afterAttack();}});
 }
};
