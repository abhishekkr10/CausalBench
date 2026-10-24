const el=id=>document.getElementById(id);
let current=null,timer=null;
async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const v=await r.json();if(!r.ok)throw Error(v.error||'Request failed');return v;}
async function perform(fn){try{await fn();}catch(e){el('status').textContent=e.message;}}
function stop(){clearTimeout(timer);timer=null;el('play').textContent='Play replay';}
function showFrame(){if(!current)return;const m=current.bundle.manifest,i=Number(el('scrub').value),e=m.trace.events[i];el('time').textContent=`${e.time_ms} ms · event ${i+1}/${m.trace.events.length}`;for(const n of ['baseline','guarded']){const r=m.comparison[n].rows[i];el(n+'-actuator').textContent=r.command;el(n+'-actuator').classList.toggle('pulse',r.command==='PULSE');el(n+'-reason').textContent=`${r.state_before??'unknown'} → ${r.state_after??'unknown'} · age ${r.sample_age_ms??'unknown'} ms · ${r.reason}`;}el('observation').textContent=e.observation?`Input: ${e.observation.distance_mm??'invalid'} mm · sampled ${e.observation.sample_ms} ms · fixture presence: ${e.fixture_present??'unknown'}`:'Input: missing observation';if(typeof labFrame==='function')labFrame(e);}
function render(run){stop();current=run;const m=run.bundle.manifest,c=m.comparison;el('mode').value=m.trace.mode;el('metrics').replaceChildren();for(const [label,value] of [['Events',m.trace.events.length],[c.baseline.policy+' incorrect fixture pulses',c.baseline.metrics.unsafe_fixture_pulses],[c.guarded.policy+' incorrect fixture pulses',c.guarded.metrics.unsafe_fixture_pulses],['Command divergences',c.divergence_times_ms.length]]){const a=document.createElement('article'),b=document.createElement('strong'),s=document.createElement('span');a.className='card';b.textContent=value??'Unknown';s.textContent=label;a.append(b,s);el('metrics').append(a);}el('ledger').replaceChildren();c.baseline.rows.forEach((a,i)=>{const b=c.guarded.rows[i],tr=document.createElement('tr');tr.classList.toggle('different',a.command!==b.command);for(const v of [a.time_ms+' ms',a.observation_id??'missing',a.sample_age_ms===null?'—':a.sample_age_ms+' ms',a.command,b.command,b.reason]){const td=document.createElement('td');td.textContent=v;tr.append(td);}el('ledger').append(tr);});el('scrub').max=m.trace.events.length-1;el('scrub').value=0;for(const id of ['scrub','export','trace','report','step','divergence','play','verify','tamper'])el(id).disabled=false;el('integrity').textContent='Manifest SHA-256: '+run.bundle.manifest_digest;el('status').textContent=`Experiment ${run.id.slice(0,8)} · ${m.trace.mode} · ${m.trace.scenario??'imported'}`;if(typeof labRender==='function')labRender(run);showFrame();}
async function history(){const runs=await api('/api/runs');el('history').replaceChildren();if(!runs.length)el('history').textContent='No experiments yet. Run a scenario to begin.';for(const r of runs){const b=document.createElement('button');b.textContent=r.scenario+' · '+r.id.slice(0,8);b.onclick=()=>perform(async()=>render(await api('/api/runs/'+r.id)));el('history').append(b);}}
el('run').onclick=()=>perform(async()=>{el('run').disabled=true;el('status').textContent='Running experiment…';try{if(el('mode').value==='captured-input')throw Error('Use Live sensor recording below and snapshot its buffer, or import a captured trace.');render(await api('/api/runs',typeof experimentSpec==='function'?experimentSpec():{scenario:el('scenario').value}));await history();}finally{el('run').disabled=false;}});
el('scrub').oninput=()=>{stop();showFrame();};
function advance(){const i=Number(el('scrub').value),events=current.bundle.manifest.trace.events;if(i>=events.length-1){stop();return;}timer=setTimeout(()=>{el('scrub').value=i+1;showFrame();advance();},Math.min(events[i+1].time_ms-events[i].time_ms,2000));}
el('play').onclick=()=>{if(timer){stop();return;}if(Number(el('scrub').value)===Number(el('scrub').max))el('scrub').value=0;showFrame();el('play').textContent='Pause replay';advance();};
el('step').onclick=()=>{stop();el('scrub').value=Math.min(Number(el('scrub').value)+1,Number(el('scrub').max));showFrame();};
el('divergence').onclick=()=>{stop();const m=current.bundle.manifest,t=m.comparison.divergence_times_ms[0];if(t===undefined){el('status').textContent='No command divergence';return;}el('scrub').value=m.trace.events.findIndex(e=>e.time_ms===t);showFrame();};
function download(value,name,type='application/json'){const u=URL.createObjectURL(new Blob([value],{type})),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
el('export').onclick=()=>download(JSON.stringify(current.bundle,null,2),'causalbench-evidence.json');
el('trace').onclick=()=>download(JSON.stringify(current.bundle.manifest.trace,null,2),'causalbench-trace.json');
el('report').onclick=()=>perform(async()=>{if(!(await api('/api/verify',current.bundle)).valid)throw Error('Evidence verification failed');const m=current.bundle.manifest;download('# CausalBench comparison report\n\n'+m.comparison.scope+'\n\nManifest digest: '+current.bundle.manifest_digest+'\n\n```json\n'+JSON.stringify(m.comparison,null,2)+'\n```\n','causalbench-report.md','text/markdown');});
el('verify').onclick=()=>perform(async()=>{const r=await api('/api/verify',current.bundle);el('integrity').textContent='Verification: '+(r.valid?'VALID':'INVALID')+' · '+current.bundle.manifest_digest;});
el('tamper').onclick=()=>perform(async()=>{const c=structuredClone(current.bundle);c.manifest.trace.events[0].time_ms+=1;const r=await api('/api/verify',c);el('integrity').textContent='Modified-copy verification: '+(r.valid?'unexpectedly valid':'INVALID — change detected')+'. Stored experiment preserved.';});
el('import').onchange=()=>perform(async()=>{const f=el('import').files[0];if(!f)return;if(f.size>32000000)throw Error('Evidence file exceeds 32 MB; traces are limited to 2 MB.');const v=JSON.parse(await f.text());if(v.manifest&&!(await api('/api/verify',v)).valid)throw Error('Imported bundle invalid');render(await api('/api/runs',{trace:v.manifest?v.manifest.trace:v}));await history();});
perform(history);
// Workspace motion and the event sequence use the current recorded evidence.
const originalRender=render,originalFrame=showFrame;
render=function(run){originalRender(run);const m=run.bundle.manifest;el('event-timeline').replaceChildren();m.trace.events.forEach((event,i)=>{const b=document.createElement('button');b.textContent=i+1;b.title=`Event ${i+1} at ${event.time_ms} ms`;b.setAttribute('aria-label',b.title);b.classList.toggle('diverged',m.comparison.baseline.rows[i].command!==m.comparison.guarded.rows[i].command);b.onclick=()=>{stop();el('scrub').value=i;showFrame();};el('event-timeline').append(b);});showFrame();};
showFrame=function(){originalFrame();const index=Number(el('scrub').value);document.querySelectorAll('#event-timeline button').forEach((b,i)=>{b.classList.toggle('selected',i===index);b.setAttribute('aria-pressed',String(i===index));});document.querySelectorAll('#ledger tr').forEach((row,i)=>row.classList.toggle('active-event',i===index));};
const revealObserver=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){e.target.classList.add('reveal');revealObserver.unobserve(e.target);}},{threshold:.06});document.querySelectorAll('.panel,.cards,header').forEach(n=>revealObserver.observe(n));
const workspaceLinks=[...document.querySelectorAll('nav a')];function syncNavigation(){let active=workspaceLinks[0];const offset=innerWidth<=800?160:90;for(const link of workspaceLinks){const target=document.querySelector(link.getAttribute('href'));if(target&&target.getBoundingClientRect().top<=offset)active=link;}for(const link of workspaceLinks){link.classList.toggle('active',link===active);if(link===active)link.setAttribute('aria-current','location');else link.removeAttribute('aria-current');}}addEventListener('scroll',syncNavigation,{passive:true});syncNavigation();
// Keep the workspace comfortable for both animated and reduced-motion use.
const motionPreference=matchMedia('(prefers-reduced-motion: reduce)');
let reduceWorkspaceMotion=false;
try { reduceWorkspaceMotion=localStorage.getItem('causalbench-reduce-motion')==='true'; } catch (_) {}
function updateWorkspaceMotion(){
 const reduced=reduceWorkspaceMotion||motionPreference.matches;
 document.documentElement.dataset.motion=reduced?'off':'on';
 const button=el('motion-toggle');
 button.setAttribute('aria-pressed',String(reduced));
 button.textContent=motionPreference.matches?'System: reduced motion':reduced?'Reduced motion on':'Reduce motion';
 button.disabled=motionPreference.matches;
 button.title=motionPreference.matches?'Your system preference disables interface animations.':'Toggle interface animations. Replay controls remain available.';
}
el('motion-toggle').onclick=()=>{reduceWorkspaceMotion=!reduceWorkspaceMotion;try { localStorage.setItem('causalbench-reduce-motion',String(reduceWorkspaceMotion)); } catch (_) {}updateWorkspaceMotion();};
motionPreference.addEventListener('change',updateWorkspaceMotion);
updateWorkspaceMotion();
// Follow the system until the user explicitly chooses a theme.
const systemTheme=matchMedia('(prefers-color-scheme: dark)');
let savedTheme=null;
try { const value=localStorage.getItem('causalbench-theme');if(value==='light'||value==='dark')savedTheme=value; } catch (_) {}
function updateTheme(){
 const dark=(savedTheme||(systemTheme.matches?'dark':'light'))==='dark';
 document.documentElement.dataset.theme=dark?'dark':'light';
 const button=el('theme-toggle');button.setAttribute('aria-pressed',String(dark));button.textContent=dark?'Light theme':'Dark theme';button.setAttribute('aria-label',dark?'Switch to light theme':'Switch to dark theme');
}
el('theme-toggle').onclick=()=>{savedTheme=document.documentElement.dataset.theme==='dark'?'light':'dark';try { localStorage.setItem('causalbench-theme',savedTheme); } catch (_) {}updateTheme();};
systemTheme.addEventListener('change',()=>{if(!savedTheme)updateTheme();});updateTheme();
