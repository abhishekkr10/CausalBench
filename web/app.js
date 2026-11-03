const el=id=>document.getElementById(id);
let current=null,timer=null;
async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const v=await r.json();if(!r.ok)throw Error(v.error||'Request failed');return v;}
async function perform(fn){try{await fn();}catch(e){el('status').textContent=e.message;setExperimentState('failed',e.message);}}
function stop(){clearTimeout(timer);timer=null;el('play').textContent='Play replay';}
function showFrame(){if(!current)return;const m=current.bundle.manifest,i=Number(el('scrub').value),e=m.trace.events[i];el('time').textContent=`${e.time_ms} ms · event ${i+1}/${m.trace.events.length}`;for(const n of ['baseline','guarded']){const r=m.comparison[n].rows[i];el(n+'-actuator').textContent=r.command;el(n+'-actuator').classList.toggle('pulse',r.command==='PULSE');el(n+'-reason').textContent=`${r.state_before??'unknown'} → ${r.state_after??'unknown'} · age ${r.sample_age_ms??'unknown'} ms · ${r.reason}`;}el('observation').textContent=e.observation?`Input: ${e.observation.distance_mm??'invalid'} mm · sampled ${e.observation.sample_ms} ms · fixture presence: ${e.fixture_present??'unknown'}`:'Input: missing observation';if(typeof labFrame==='function')labFrame(e);updateEventInspector(e);}
function render(run){stop();setExperimentState('completed');document.querySelector('[data-view=experiment]').dataset.hasResult='true';if(el('trace-dialog').open)el('trace-dialog').close();current=run;if(typeof openWorkspaceView==='function')openWorkspaceView('experiment',false);const m=run.bundle.manifest,c=m.comparison;el('mode').value=m.trace.mode;el('metrics').replaceChildren();for(const [label,value] of [['Recorded events',m.trace.events.length],['Reference incorrect pulses',c.baseline.metrics.unsafe_fixture_pulses],['Candidate incorrect pulses',c.guarded.metrics.unsafe_fixture_pulses],['Command disagreements',c.divergence_times_ms.length]]){const a=document.createElement('article'),b=document.createElement('strong'),s=document.createElement('span');a.className='card';b.textContent=value??'Unknown';s.textContent=label;a.append(b,s);el('metrics').append(a);}el('ledger').replaceChildren();c.baseline.rows.forEach((a,i)=>{const b=c.guarded.rows[i],tr=document.createElement('tr');tr.classList.toggle('different',a.command!==b.command);for(const v of [a.time_ms+' ms',a.observation_id??'missing',a.sample_age_ms===null?'—':a.sample_age_ms+' ms',a.command,b.command,b.reason]){const td=document.createElement('td');td.textContent=v;tr.append(td);}el('ledger').append(tr);});el('scrub').max=m.trace.events.length-1;el('scrub').value=0;for(const id of ['scrub','export','trace','report','step','divergence','play','verify','tamper'])el(id).disabled=false;el('integrity').textContent='Manifest SHA-256: '+run.bundle.manifest_digest;el('status').textContent=`Experiment ${run.id.slice(0,8)} · ${m.trace.mode} · ${m.trace.scenario??'imported'}`;if(typeof labRender==='function')labRender(run);showFrame();}
async function refreshRunHistory(){const runs=await api('/api/runs');el('history').replaceChildren();if(typeof updateRunChoices==='function')updateRunChoices(runs);if(!runs.length)el('history').textContent='No experiments yet. Run a scenario to begin.';for(const r of runs){const b=document.createElement('button');b.textContent=r.scenario+' · '+r.id.slice(0,8);b.onclick=()=>perform(async()=>render(await api('/api/runs/'+r.id)));el('history').append(b);}}
el('run').onclick=()=>perform(async()=>{el('run').disabled=true;openWorkspaceView('experiment',false);setExperimentState('loading');el('status').textContent='Running experiment…';try{if(el('mode').value==='captured-input')throw Error('Use Live sensor recording below and snapshot its buffer, or import a captured trace.');render(await api('/api/runs',typeof experimentSpec==='function'?experimentSpec():{scenario:el('scenario').value}));await refreshRunHistory();}finally{el('run').disabled=false;}});
el('scrub').oninput=()=>{stop();showFrame();};
function advance(){const i=Number(el('scrub').value),events=current.bundle.manifest.trace.events;if(i>=events.length-1){stop();return;}timer=setTimeout(()=>{el('scrub').value=i+1;showFrame();advance();},Math.min(events[i+1].time_ms-events[i].time_ms,2000));}
el('play').onclick=()=>{if(timer){stop();return;}if(Number(el('scrub').value)===Number(el('scrub').max))el('scrub').value=0;showFrame();el('play').textContent='Pause replay';advance();};
el('step').onclick=()=>{stop();el('scrub').value=Math.min(Number(el('scrub').value)+1,Number(el('scrub').max));showFrame();};
el('divergence').onclick=()=>{stop();const m=current.bundle.manifest,t=m.comparison.divergence_times_ms[0];if(t===undefined){el('status').textContent='No command divergence';return;}el('scrub').value=m.trace.events.findIndex(e=>e.time_ms===t);showFrame();};
function download(value,name,type='application/json'){const u=URL.createObjectURL(new Blob([value],{type})),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);}
el('export').onclick=()=>perform(async()=>download(await exactEvidence(),'causalbench-evidence.json'));
el('trace').onclick=()=>download(JSON.stringify(current.bundle.manifest.trace,null,2),'causalbench-trace.json');
el('report').onclick=()=>perform(async()=>{if(!(await verifyEvidence(await exactEvidence())).valid)throw Error('Evidence verification failed');const m=current.bundle.manifest;download('# CausalBench comparison report\n\n'+m.comparison.scope+'\n\nManifest digest: '+current.bundle.manifest_digest+'\n\n```json\n'+JSON.stringify(m.comparison,null,2)+'\n```\n','causalbench-report.md','text/markdown');});
el('verify').onclick=()=>perform(async()=>{const r=await verifyEvidence(await exactEvidence());el('integrity').textContent='Verification: '+(r.valid?'VALID':'INVALID')+' · '+current.bundle.manifest_digest;});
el('tamper').onclick=()=>perform(async()=>{const c=structuredClone(current.bundle);c.manifest.trace.events[0].time_ms+=1;const r=await api('/api/verify',c);el('integrity').textContent='Modified-copy verification: '+(r.valid?'unexpectedly valid':'INVALID — change detected')+'. Stored experiment preserved.';});
el('import').onchange=()=>perform(async()=>{const f=el('import').files[0];if(!f)return;if(f.size>32000000)throw Error('Evidence file exceeds 32 MB; traces are limited to 2 MB.');setExperimentState('loading','Reading and validating the selected trace…');const raw=await f.text(),v=JSON.parse(raw);if(v.manifest&&!(await verifyEvidence(raw)).valid)throw Error('Imported bundle invalid');render(await api('/api/runs',{trace:v.manifest?v.manifest.trace:v}));await refreshRunHistory();});
perform(refreshRunHistory);
// Workspace motion and the event sequence use the current recorded evidence.
const originalRender=render,originalFrame=showFrame;
render=function(run){originalRender(run);const m=run.bundle.manifest;el('event-timeline').replaceChildren();m.trace.events.forEach((event,i)=>{const b=document.createElement('button');b.textContent=i+1;b.title=`Event ${i+1} at ${event.time_ms} ms`;b.setAttribute('aria-label',b.title);b.classList.toggle('diverged',m.comparison.baseline.rows[i].command!==m.comparison.guarded.rows[i].command);b.onclick=()=>{stop();el('scrub').value=i;showFrame();};el('event-timeline').append(b);});showFrame();};
showFrame=function(){originalFrame();const index=Number(el('scrub').value);document.querySelectorAll('#event-timeline button').forEach((b,i)=>{b.classList.toggle('selected',i===index);b.setAttribute('aria-pressed',String(i===index));});document.querySelectorAll('#ledger tr').forEach((row,i)=>row.classList.toggle('active-event',i===index));};
// Keep the workspace comfortable for both animated and reduced-motion use.
const motionPreference=matchMedia('(prefers-reduced-motion: reduce)');
let reduceWorkspaceMotion=false;
try { reduceWorkspaceMotion=localStorage.getItem('causalbench-reduce-motion')==='true'; } catch (_) {}
function updateWorkspaceMotion(){
 const reduced=reduceWorkspaceMotion||motionPreference.matches;
 document.documentElement.dataset.motion=reduced?'off':'on';
 const button=el('motion-toggle');
 button.setAttribute('aria-pressed',String(reduced));button.setAttribute('aria-label',motionPreference.matches?'System: reduced motion':reduced?'Enable animations':'Disable animations');
 button.textContent=motionPreference.matches?'System: reduced motion':reduced?'Enable animations':'Animations on';
 button.disabled=motionPreference.matches;
 button.title=motionPreference.matches?'Your system preference disables interface animations.':reduced?'Enable hover zoom, highlighting and scroll blur effects.':'Animations enabled. Click to reduce motion.';
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
/* Recorded trace visualization and guided investigation. */
const svgNS='http://www.w3.org/2000/svg';
function svgNode(name,attrs={},text){const n=document.createElementNS(svgNS,name);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);if(text!==undefined)n.textContent=text;return n;}
function selectRecordedEvent(index){stop();el('scrub').value=index;showFrame();}
function drawTrace(){
 const host=el('trace-chart');host.replaceChildren();if(!current)return;setChartZoom(1);for(const id of ['chart-zoom-in','chart-zoom-out','chart-zoom-reset','chart-expand'])el(id).disabled=false;
 const m=current.bundle.manifest,events=m.trace.events,c=m.comparison,W=900,H=400,L=100,R=870;
 const first=events[0].time_ms,last=events.at(-1).time_ms;
 const x=t=>last===first?(L+R)/2:L+(t-first)/(last-first)*(R-L);
 const valid=e=>e.observation&&e.observation.valid!==false&&Number.isFinite(e.observation.distance_mm);
 const distances=events.map(e=>valid(e)?e.observation.distance_mm:null);
 const ages=events.map(e=>valid(e)&&Number.isFinite(e.observation.sample_ms)?e.time_ms-e.observation.sample_ms:null);
 const svg=svgNode('svg',{viewBox:`0 0 ${W} ${H}`,role:'group','aria-label':'Recorded distance, observation age and controller commands'});
 svg.append(svgNode('title',{},'Sensor trace and controller decisions at recorded event times'));
 function series(values,top,height,label,color){const numbers=values.filter(v=>v!==null),lo=Math.min(0,...numbers),hi=Math.max(1,...numbers);const y=v=>top+height-(v-lo)/(hi-lo)*height;
 svg.append(svgNode('text',{x:4,y:top+14},label),svgNode('text',{x:4,y:top+33},`${lo} … ${hi}`),svgNode('line',{x1:L,x2:R,y1:top+height,y2:top+height,class:'chart-axis'}));
 let points=[];const flush=()=>{if(points.length)svg.append(svgNode('polyline',{points:points.join(' '),fill:'none',stroke:color,'stroke-width':2}));points=[];};values.forEach((v,i)=>{if(v===null){flush();return;}points.push(`${x(events[i].time_ms)},${y(v)}`);svg.append(svgNode('circle',{cx:x(events[i].time_ms),cy:y(v),r:2,fill:color,'data-event-index':i}));});flush();}
 series(distances,15,85,'Distance / mm','var(--text)');series(ages,125,80,'Age / ms','var(--cyan)');
 for(const [key,top] of [['baseline',245],['guarded',315]]){svg.append(svgNode('text',{x:4,y:top-8},key==='baseline'?'Reference':'Candidate'),svgNode('text',{x:4,y:top+10},'PULSE / HOLD'));const points=[];c[key].rows.forEach((r,i)=>{const y=top+(r.command==='PULSE'?0:28),px=x(events[i].time_ms);if(i)points.push(`${px},${top+(c[key].rows[i-1].command==='PULSE'?0:28)}`);points.push(`${px},${y}`);});svg.append(svgNode('polyline',{points:points.join(' '),fill:'none',stroke:key==='baseline'?'var(--accent)':'var(--cyan)','stroke-width':2}));}
 events.forEach((e,i)=>{if(c.baseline.rows[i].command!==c.guarded.rows[i].command)svg.append(svgNode('line',{x1:x(e.time_ms),x2:x(e.time_ms),y1:10,y2:355,stroke:'var(--orange)','stroke-opacity':.3}));});
 svg.append(svgNode('line',{id:'chart-cursor',y1:5,y2:355,stroke:'var(--text)','stroke-width':2}),svgNode('text',{x:L,y:385},`${first} ms`),svgNode('text',{x:R,y:385,'text-anchor':'end'},`${last} ms`));
 const interaction=svgNode('rect',{x:L,y:0,width:R-L,height:360,fill:'transparent',tabindex:0,role:'slider','aria-label':'Selected recorded event','aria-valuemin':1,'aria-valuemax':events.length,id:'chart-selection'});
 interaction.addEventListener('pointerdown',event=>{const point=svg.createSVGPoint();point.x=event.clientX;point.y=event.clientY;const px=point.matrixTransform(svg.getScreenCTM().inverse()).x;let best=0;events.forEach((e,i)=>{if(Math.abs(x(e.time_ms)-px)<Math.abs(x(events[best].time_ms)-px))best=i;});selectRecordedEvent(best);interaction.focus();});
 interaction.addEventListener('keydown',event=>{let i=Number(el('scrub').value);if(['ArrowRight','ArrowUp'].includes(event.key))i++;else if(['ArrowLeft','ArrowDown'].includes(event.key))i--;else if(event.key==='Home')i=0;else if(event.key==='End')i=events.length-1;else return;event.preventDefault();selectRecordedEvent(Math.max(0,Math.min(events.length-1,i)));});
 const hoverGuide=svgNode('line',{id:'chart-hover-guide',y1:5,y2:355,stroke:'var(--accent)','stroke-width':1.5,'stroke-dasharray':'4 4',opacity:0});svg.append(hoverGuide);
 let hovered=-1;
 interaction.addEventListener('pointermove',event=>{
  if(event.pointerType==='touch')return;
  const point=svg.createSVGPoint();point.x=event.clientX;point.y=event.clientY;const px=point.matrixTransform(svg.getScreenCTM().inverse()).x;
  let nearest=0;events.forEach((e,i)=>{if(Math.abs(x(e.time_ms)-px)<Math.abs(x(events[nearest].time_ms)-px))nearest=i;});
  if(Number(el('scrub').value)!==nearest)selectRecordedEvent(nearest);
  if(document.documentElement.dataset.motion!=='on')return;
  if(nearest!==hovered){svg.querySelectorAll('.trace-hover-point').forEach(n=>n.classList.remove('trace-hover-point'));svg.querySelectorAll(`[data-event-index="${nearest}"]`).forEach(n=>n.classList.add('trace-hover-point'));hovered=nearest;}
  hoverGuide.setAttribute('x1',x(events[nearest].time_ms));hoverGuide.setAttribute('x2',x(events[nearest].time_ms));hoverGuide.setAttribute('opacity',1);
  const bounds=host.getBoundingClientRect();host.style.setProperty('--pointer-x',(event.clientX-bounds.left+host.scrollLeft)+'px');host.style.setProperty('--pointer-y',(event.clientY-bounds.top)+'px');host.classList.add('chart-pointer-active');
 });
 interaction.addEventListener('pointerleave',()=>{hoverGuide.setAttribute('opacity',0);svg.querySelectorAll('.trace-hover-point').forEach(n=>n.classList.remove('trace-hover-point'));host.classList.remove('chart-pointer-active');hovered=-1;});
 svg.append(interaction);host.append(svg);host.dataset.first=first;host.dataset.last=last;
}
function updateTraceSelection(){if(!current||!el('chart-cursor'))return;const events=current.bundle.manifest.trace.events,i=Number(el('scrub').value),first=events[0].time_ms,last=events.at(-1).time_ms;const px=last===first?485:100+(events[i].time_ms-first)/(last-first)*770;el('chart-cursor').setAttribute('x1',px);el('chart-cursor').setAttribute('x2',px);el('chart-selection').setAttribute('aria-valuenow',i+1);el('chart-selection').setAttribute('aria-valuetext',`Event ${i+1}: ${el('time').textContent}. ${el('observation').textContent}. Reference ${current.bundle.manifest.comparison.baseline.rows[i].command}, candidate ${current.bundle.manifest.comparison.guarded.rows[i].command}`);}
let tour={active:false,step:0,runId:null,busy:false,epoch:0};
function tourMessage(message,label){el('tour-status').textContent=message;el('tour-next').textContent=label;}
function resetTour(){tour.epoch++;tour.active=true;tour.step=0;tour.runId=null;el('tour-body').hidden=false;el('tour-next').disabled=false;tourMessage('Step 1 of 4: choose a labelled fault, then run the example.','Run labelled example');el('tour-scenario').disabled=false;el('tour-status').focus();}
el('tour-start').onclick=resetTour;
el('tour-exit').onclick=()=>{tour.epoch++;tour.active=false;el('tour-body').hidden=true;el('tour-start').focus();};
el('tour-scenario').onchange=resetTour;
el('tour-next').onclick=async()=>{if(tour.busy)return;const epoch=tour.epoch;tour.busy=true;el('tour-next').disabled=true;
 try{if(tour.step===0){tourMessage('Running labelled example…','Running…');const run=await api('/api/runs',{scenario:el('tour-scenario').value,seed:42,events:12,controllers:['baseline-v1','guarded-v1']});if(epoch!==tour.epoch)return;tour.runId=run.id;render(run);tour.step=1;el('tour-scenario').disabled=true;tourMessage('Step 2 of 4: the example is saved. Find its first command disagreement.','Find first disagreement');await refreshRunHistory();}
 else{if(!current||current.id!==tour.runId)throw Error('The selected experiment changed. Restart the walkthrough.');const m=current.bundle.manifest;
 if(tour.step===1){const t=m.comparison.divergence_times_ms[0];selectRecordedEvent(t===undefined?0:m.trace.events.findIndex(e=>e.time_ms===t));tour.step=2;tourMessage(t===undefined?'Step 3 of 4: this example has no command disagreement. Inspect the selected recorded event; agreement alone does not prove correctness.':'Step 3 of 4: inspect the selected event, observation age and both decision explanations. A disagreement alone is not failure.','Explain selected event');}
 else if(tour.step===2){const i=Number(el('scrub').value),a=m.comparison.baseline.rows[i],b=m.comparison.guarded.rows[i],e=m.trace.events[i];tour.step=3;tourMessage(`Step 4 of 4: event ${i+1} at ${e.time_ms} ms. Reference ${a.command}: ${a.reason}. Candidate ${b.command}: ${b.reason}. Fixture presence: ${e.fixture_present??'Unknown'}. Export this run to preserve the evidence.`,'Verify & export evidence');}
 else{tourMessage('Verifying saved evidence…','Verifying…');const raw=await exactEvidence(),result=await verifyEvidence(raw);if(epoch!==tour.epoch||current.id!==tour.runId)return;if(!result.valid)throw Error('Evidence verification failed. Retry or restart.');download(raw,'causalbench-first-experiment.json');tourMessage('Complete: evidence verified and download requested. You can restart or exit this walkthrough.','Export evidence again');}}
 }catch(error){if(epoch===tour.epoch)tourMessage(error.message,'Retry step');}finally{tour.busy=false;if(epoch===tour.epoch)el('tour-next').disabled=false;}
};
const traceRender=render,traceFrame=showFrame;
render=function(run){traceRender(run);drawTrace();updateTraceSelection();if(tour.active&&tour.runId&&tour.runId!==run.id){tour.step=0;tour.runId=null;el('tour-scenario').disabled=false;tourMessage('Another experiment was selected. Run the labelled example again to restart.','Run labelled example');}};
showFrame=function(){traceFrame();updateTraceSelection();};

/* Compare independently saved evidence without claiming controller causality. */
let savedComparison=null,comparisonEpoch=0;
function stableJSON(value){if(Array.isArray(value))return '['+value.map(stableJSON).join(',')+']';if(value&&typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+stableJSON(value[k])).join(',')+'}';return JSON.stringify(value);}
function updateRunChoices(runs){for(const id of ['compare-a','compare-b']){const select=el(id),previous=select.value;select.replaceChildren();runs.forEach(r=>{const o=document.createElement('option');o.value=r.id;o.textContent=`${r.scenario} · ${r.id.slice(0,8)}`;select.append(o);});if(runs.some(r=>r.id===previous))select.value=previous;else if(id==='compare-b'&&runs.length>1)select.selectedIndex=1;}invalidateComparison();}
function invalidateComparison(){comparisonEpoch++;savedComparison=null;el('compare-export').disabled=true;el('compare-results').replaceChildren();el('compare-status').textContent='Choose two saved experiments.';}
for(const id of ['compare-a','compare-b'])el(id).onchange=invalidateComparison;
el('compare-runs').onclick=async()=>{const epoch=++comparisonEpoch;el('compare-export').disabled=true;savedComparison=null;el('compare-results').replaceChildren();el('compare-status').textContent='Loading saved evidence…';try{const a=el('compare-a').value,b=el('compare-b').value;if(!a||!b||a===b)throw Error('Choose two different saved experiments.');const runs=await Promise.all([api('/api/runs/'+a),api('/api/runs/'+b)]);if(epoch!==comparisonEpoch)return;const manifests=runs.map(r=>r.bundle.manifest),traces=manifests.map(m=>m.trace);
 // Only configuration fields are excluded: event values, truth, streams and timing must match.
 const inputs=traces.map(t=>{const copy=structuredClone(t);delete copy.controller_config;delete copy.controller_configs;delete copy.controllers;return copy;});
 const identical=stableJSON(inputs[0])===stableJSON(inputs[1]);
 const scope=identical?'Identical recorded inputs and trace metadata. Compare controller configurations and metrics below.':'Inputs or trace metadata differ. Outcome changes cannot be attributed solely to controller changes.';
 const summarize=m=>({events:m.trace.events.length,scenario:m.trace.scenario??'imported',controllers:Object.fromEntries(Object.entries(m.comparison.controllers||{[m.comparison.baseline.policy]:m.comparison.baseline,[m.comparison.guarded.policy]:m.comparison.guarded}).map(([id,r])=>[id,{configuration:r.configuration,metrics:r.metrics}]))});
 savedComparison={kind:'saved-run-comparison',run_ids:[a,b],identical_inputs:identical,scope,runs:manifests.map(summarize),manifest_digests:runs.map(r=>r.bundle.manifest_digest)};el('compare-status').textContent=scope;
 const rows=[['Event count',...savedComparison.runs.map(r=>r.events)],['Scenario',...savedComparison.runs.map(r=>r.scenario)]];
 const ids=new Set(savedComparison.runs.flatMap(r=>Object.keys(r.controllers)));for(const id of ids){rows.push([id+' configuration',...savedComparison.runs.map(r=>r.controllers[id]?stableJSON(r.controllers[id].configuration):'Not selected')]);const metrics=new Set(savedComparison.runs.flatMap(r=>Object.keys(r.controllers[id]?.metrics||{})));for(const key of metrics)rows.push([id+' / '+key,...savedComparison.runs.map(r=>r.controllers[id]?r.controllers[id].metrics[key]??'Unknown':'Not selected')]);}
 el('compare-results').append(dataTable(['Property','First experiment','Second experiment'],rows));el('compare-export').disabled=false;
 }catch(error){if(epoch===comparisonEpoch)el('compare-status').textContent=error.message;}};
el('compare-export').onclick=()=>{if(savedComparison)download(JSON.stringify(savedComparison,null,2),'causalbench-run-comparison.json');};

async function exactEvidence(){const response=await fetch('/api/evidence/'+current.id);if(!response.ok)throw Error('Could not load exact stored evidence.');return response.text();}
async function verifyEvidence(raw){const response=await fetch('/api/verify',{method:'POST',headers:{'Content-Type':'application/json'},body:raw});const value=await response.json();if(!response.ok)throw Error(value.error||'Evidence verification failed');return value;}

// Views share one recorded experiment and the existing API-backed controls.
const workspaceViews={
 experiment:['Experiment','REPLAY & COMPARE','Run a scenario. Inspect the decisions behind each command.'],
 configuration:['Configuration','CONTROLLERS & FAULTS','Tune the next run. Saved experiment inputs remain unchanged.'],
 studies:['Studies','TEST & REDUCE','Sweep faults, find boundaries, and preserve regression cases.'],
 recording:['Recording','SENSOR INPUT','Record synthetic or HTTP observations. Actuation stays simulated.'],
 model:['Feedback model','CLOSED-LOOP SIMULATION','Explore how controller actions change later observations.'],
 results:['Analysis results','SAVED RESEARCH','Inspect study outcomes and export reproducible evidence.'],
 library:['Runs & evidence','LOCAL ARCHIVE','Reopen experiments, compare runs, and preserve their implementation.']
};
const workspaceAliases={overview:'experiment',replay:'experiment','experiment-builder':'configuration',capture:'recording',plant:'model','analysis-panel':'results',evidence:'library',walkthrough:'experiment'};
function openWorkspaceView(name,focus=true){
 name=workspaceAliases[name]||name;if(!workspaceViews[name])name='experiment';
 for(const view of document.querySelectorAll('[data-view]'))view.hidden=view.dataset.view!==name;
 for(const link of document.querySelectorAll('[data-view-link]')){const active=link.dataset.viewLink===name;link.classList.toggle('active',active);if(active)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');}
 const [title,kicker,description]=workspaceViews[name];el('view-title').textContent=title;el('view-breadcrumb').textContent=title;el('view-kicker').textContent=kicker;el('view-description').textContent=description;document.title='CausalBench | '+title;
 if(location.hash!=='#'+name)historyForWorkspace(name);
 if(focus){stop();el('workspace').focus({preventScroll:true});window.scrollTo({top:0,behavior:'instant'});}
}
function historyForWorkspace(name){window.history.pushState(null,'','#'+name);}
function followWorkspaceHash(){const key=location.hash.slice(1)||'experiment';openWorkspaceView(workspaceAliases[key]||key,false);if(key==='walkthrough')el('walkthrough').scrollIntoView({block:'center'});}
document.addEventListener('click',event=>{const link=event.target.closest('a[href^="#"]');if(!link)return;const key=link.getAttribute('href').slice(1);if(key==='workspace')return;if(workspaceViews[key]||workspaceAliases[key]){event.preventDefault();openWorkspaceView(workspaceAliases[key]||key);if(key==='walkthrough')el('walkthrough').scrollIntoView({block:'center'});}});
addEventListener('popstate',followWorkspaceHash);addEventListener('hashchange',followWorkspaceHash);followWorkspaceHash();

function updateEventInspector(event){
 el('inspector-time').textContent=event.time_ms+' ms';const o=event.observation;
 const fields=[['Sample timestamp',o?o.sample_ms+' ms':'Missing'],['Observation age',o?(event.time_ms-o.sample_ms)+' ms':'Unknown'],['Distance',o&&o.valid!==false&&Number.isFinite(o.distance_mm)?o.distance_mm+' mm':'Missing / invalid'],['Reading validity',!o?'Missing':o.valid===false?'Invalid':'Valid'],['Fixture truth',event.fixture_present===undefined?'Unknown':event.fixture_present?'Present':'Absent']];
 el('event-readings').replaceChildren();for(const [label,value] of fields){const row=document.createElement('div'),dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;row.append(dt,dd);el('event-readings').append(row);}
}
let chartZoom=1;
function setChartZoom(value){chartZoom=Math.max(1,Math.min(4,value));el('trace-inspection-surface').style.setProperty('--chart-zoom',chartZoom);el('chart-zoom-level').textContent=Math.round(chartZoom*100)+'%';}
el('chart-zoom-in').onclick=()=>setChartZoom(chartZoom+.5);
el('chart-zoom-out').onclick=()=>setChartZoom(chartZoom-.5);
el('chart-zoom-reset').onclick=()=>{setChartZoom(1);el('trace-chart').scrollLeft=0;};
const chartHome=document.createComment('Recorded trace original position');el('trace-inspection-surface').before(chartHome);
el('chart-expand').onclick=()=>{el('trace-dialog-chart').append(el('trace-inspection-surface'));el('trace-dialog').showModal();el('trace-dialog-close').focus();};
el('trace-dialog-close').onclick=()=>el('trace-dialog').close();
el('trace-dialog').addEventListener('close',()=>{chartHome.after(el('trace-inspection-surface'));el('chart-expand').focus({preventScroll:true});});

// Figma refinement: operation states are driven by actual API outcomes.
function setExperimentState(state,message){
 const panel=el('run-state-panel');if(!panel)return;
 const busy=state==='loading';el('workspace').setAttribute('aria-busy',String(busy));
 panel.dataset.state=state;panel.hidden=state==='completed';
 const states={empty:['NO ACTIVE EXPERIMENT','Prepare a trace to begin','Generate or import a recorded trace.'],loading:['RUNNING LOCALLY','Evaluating controller decisions','Waiting for the local experiment service. Actuation remains simulated.'],failed:['OPERATION FAILED','The operation could not be completed','Review the error and try again.']};
 const copy=states[state];if(copy){el('run-state-kicker').textContent=copy[0];el('run-state-title').textContent=copy[1];el('run-state-message').textContent=message||copy[2];}
 el('run-state-retry').hidden=state!=='failed';
 el('run-state-retry').textContent=el('mode').value==='captured-input'?'Import another trace':'Run experiment again';
}
el('run-state-retry').onclick=()=>{if(el('mode').value==='captured-input'){openWorkspaceView('library');el('import').click();}else el('run').click();};
const workspaceNavigation=document.querySelector('nav[aria-label="Workspace navigation"]');
const navigationHome=document.createComment('Workspace navigation home');workspaceNavigation.before(navigationHome);
el('mobile-menu').onclick=()=>{el('navigation-dialog-content').append(workspaceNavigation);el('navigation-dialog').showModal();el('navigation-close').focus();};
el('navigation-close').onclick=()=>el('navigation-dialog').close();
el('navigation-dialog').addEventListener('close',()=>{navigationHome.after(workspaceNavigation);el('mobile-menu').focus({preventScroll:true});});
workspaceNavigation.addEventListener('click',event=>{if(event.target.closest('a')&&el('navigation-dialog').open)el('navigation-dialog').close();});
addEventListener('resize',()=>{if(innerWidth>760&&el('navigation-dialog').open)el('navigation-dialog').close();});

// Scroll entrances replay when a section leaves and re-enters the viewport.
// Recorded chart values and table rows remain sharp and are never interpolated.
const scrollEntrances=new Map();
const scrollRevealObserver=new IntersectionObserver(entries=>{
 for(const entry of entries){
  if(!entry.isIntersecting){scrollEntrances.get(entry.target)?.cancel();scrollEntrances.delete(entry.target);continue;}
  if(document.documentElement.dataset.motion!=='on'||entry.target.closest('[hidden]'))continue;
  // Avoid animating containers while the user is editing or selecting data.
  if(entry.target.contains(document.activeElement))continue;
  const animation=entry.target.animate([
   {opacity:.55,filter:'blur(5px)',transform:'translateY(12px) scale(.985)'},
   {opacity:1,filter:'blur(0px)',transform:'translateY(0) scale(1)'}
  ],{duration:480,easing:'cubic-bezier(.16,1,.3,1)'});
  scrollEntrances.set(entry.target,animation);
  animation.onfinish=()=>{if(scrollEntrances.get(entry.target)===animation)scrollEntrances.delete(entry.target);};
 }
},{threshold:.08});
const revealTargets=new Set();
function refreshScrollEntrances(){
 for(const target of revealTargets)if(!target.isConnected){scrollRevealObserver.unobserve(target);revealTargets.delete(target);scrollEntrances.get(target)?.cancel();scrollEntrances.delete(target);}
 for(const target of document.querySelectorAll('.workspace-view > .panel,.workspace-view > .ledger-details,#metrics .card,.event-inspector,.actuators article')){
  if(revealTargets.has(target))continue;revealTargets.add(target);scrollRevealObserver.observe(target);
 }
}
let revealRefresh=null;
new MutationObserver(()=>{if(revealRefresh===null)revealRefresh=requestAnimationFrame(()=>{revealRefresh=null;refreshScrollEntrances();});}).observe(el('workspace'),{childList:true,subtree:true});
new MutationObserver(()=>{if(document.documentElement.dataset.motion==='off'){for(const animation of scrollEntrances.values())animation.cancel();scrollEntrances.clear();}}).observe(document.documentElement,{attributes:true,attributeFilter:['data-motion']});
refreshScrollEntrances();
