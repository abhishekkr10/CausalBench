/* Experiment tools extend the existing layout; all results come from the local service. */
let controllerCatalog={}, profiles=[], latestAnalysis=null, latestAnalysisId=null, captureTimer=null, analysisActive=false;
const num=id=>Number(el(id).value);
function candidateConfiguration(){return {version:1,enter_mm:num('enter-mm'),exit_mm:num('exit-mm'),max_age_ms:num('max-age')};}
function experimentSpec(){
 const first=el('reference-policy').value||'baseline-v1', second=el('candidate-policy').value||'guarded-v1';
 const controllers=[first,second];if(first===second)throw Error('Choose two distinct controllers.');
 if(el('include-fusion').checked&&!controllers.includes('fusion-v1'))controllers.push('fusion-v1');
 if(el('include-native').checked&&!controllers.includes('native-guarded-v1'))controllers.push('native-guarded-v1');
 const config=candidateConfiguration(), configs={};for(const identity of controllers)configs[identity]=config;
 configs[first]={version:1,enter_mm:num('reference-enter'),exit_mm:Math.max(num('reference-enter'),120),max_age_ms:300};
 return {scenario:el('scenario').value,seed:num('experiment-seed'),events:num('event-count'),multistream:el('multistream').checked,controllers,configs,
  faults:{delay_ms:num('delay-ms'),delay_rate:num('delay-rate'),drop_rate:num('drop-rate'),duplicate_rate:num('duplicate-rate'),reorder_rate:num('reorder-rate'),invalid_rate:num('invalid-rate'),noise_mm:num('noise-mm'),start_ms:num('fault-start'),duration_ms:num('fault-duration'),disconnect_stream:el('disconnect-stream').value}};
}
function textNode(tag,text,className){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(className)n.className=className;return n;}
function dataTable(headers,rows){const wrap=textNode('div',undefined,'table-wrap'),table=document.createElement('table'),head=document.createElement('thead'),hr=document.createElement('tr');for(const h of headers)hr.append(textNode('th',h));head.append(hr);const body=document.createElement('tbody');for(const row of rows){const tr=document.createElement('tr');for(const v of row)tr.append(textNode('td',v===null||v===undefined?'Unknown':String(v)));body.append(tr);}table.append(head,body);wrap.append(table);return wrap;}
function labRender(run){
 const c=run.bundle.manifest.comparison,t=run.bundle.manifest.trace;
 el('baseline-title').textContent=c.baseline.policy;el('guarded-title').textContent=c.guarded.policy;
 const rows=Object.entries(c.controllers||{[c.baseline.policy]:c.baseline,[c.guarded.policy]:c.guarded}).map(([id,r])=>[id,r.metrics.pulses,r.metrics.unsafe_fixture_pulses,r.metrics.missed_present_events,r.configuration.enter_mm,r.configuration.exit_mm,r.configuration.max_age_ms]);
 el('policy-summary').replaceChildren(dataTable(['Controller','Pulses','Incorrect fixture pulses','Missed-present events','Enter / mm','Exit / mm','Max age / ms'],rows));
 for(const id of ['minimize-run','regression-save','package-export'])el(id).disabled=false;
 el('package-status').textContent='Exact source snapshot retained for this experiment. ZIP imports never execute archived source.';
}
function labFrame(event){
 const rows=[['distance',event.observation?.distance_mm,event.observation?'mm':'—',event.observation?event.time_ms-event.observation.sample_ms:null,event.observation?event.observation.valid!==false:false]];
 for(const [name,obs] of Object.entries(event.streams||{}))rows.push([name,obs?.value,obs?.unit??'—',obs?event.time_ms-obs.sample_ms:null,obs?obs.valid!==false:false]);
 el('stream-view').replaceChildren(dataTable(['Stream','Reading','Units','Age / ms','Valid / available'],rows));
 el('fault-audit').textContent='Fault audit for this event: '+(event.applied_faults?.join(', ')||'No composed faults applied')+'. Fixture truth is excluded from controller inputs.';
}
async function initLab(){
 controllerCatalog=await api('/api/controllers');
 for(const id of ['reference-policy','candidate-policy']){el(id).replaceChildren();for(const [key,value] of Object.entries(controllerCatalog)){const option=document.createElement('option');option.value=key;option.textContent=key;option.title=value.description;el(id).append(option);}}
 el('reference-policy').value='baseline-v1';el('candidate-policy').value='guarded-v1';
 el('include-native').disabled=!controllerCatalog['native-guarded-v1'];
 el('controller-help').textContent=Object.entries(controllerCatalog).map(([id,value])=>id+': '+value.description).join(' · ');
 await Promise.all([refreshProfiles(),refreshRegressions(),refreshAnalyses()]);
 const state=await api('/api/capture');showCapture(state);if(state.state==='recording')pollCapture();
}
async function refreshProfiles(){profiles=await api('/api/profiles');el('profile-select').replaceChildren();const first=document.createElement('option');first.value='';first.textContent='Choose a configuration';el('profile-select').append(first);for(const p of profiles){const option=document.createElement('option');option.value=p.id;option.textContent=p.payload.name+' · '+p.id.slice(0,8);el('profile-select').append(option);}}
function loadConfig(cfg){el('enter-mm').value=cfg.enter_mm;el('exit-mm').value=cfg.exit_mm;el('max-age').value=cfg.max_age_ms;}
el('profile-save').onclick=()=>perform(async()=>{const saved=await api('/api/profiles',{name:el('profile-name').value,configuration:candidateConfiguration()});await refreshProfiles();el('profile-select').value=saved.id;el('status').textContent='Configuration saved in SQLite.';});
el('profile-load').onclick=()=>perform(async()=>{const p=profiles.find(p=>p.id===el('profile-select').value);if(!p)throw Error('Choose a saved configuration.');loadConfig(p.payload.configuration);el('status').textContent='Loaded '+p.payload.name+'. Applies to the next run.';});
el('candidate-policy').onchange=()=>{const cfg=controllerCatalog[el('candidate-policy').value]?.configuration;if(cfg)loadConfig(cfg);};
function listNumbers(id){const parts=el(id).value.split(',').map(s=>s.trim());if(parts.some(s=>s===''))throw Error('Supply comma-separated numbers without empty entries.');const values=parts.map(Number);if(values.some(v=>!Number.isFinite(v)))throw Error('Supply valid comma-separated numbers.');return values;}
async function runAnalysis(kind,body){
 if(analysisActive)throw Error('An analysis is already running in this dashboard.');
 analysisActive=true;openWorkspaceView('results');el('analysis-status').textContent=kind+' analysis running…';
 for(const id of ['batch-run','boundary-run','minimize-run','plant-run'])el(id).disabled=true;
 try{let job=await api('/api/jobs',{kind,...body});while(job.status==='running'){await new Promise(resolve=>setTimeout(resolve,400));job=await api('/api/jobs/'+job.id);}
 if(job.status==='failed')throw Error(job.error);displayAnalysis(job.result,job.artifact_id);await refreshAnalyses();}
 catch(error){el('analysis-status').textContent=error.message;throw error;}
 finally{analysisActive=false;for(const id of ['batch-run','boundary-run','plant-run'])el(id).disabled=false;el('minimize-run').disabled=!current;}
}
el('batch-run').onclick=()=>perform(async()=>{const spec=experimentSpec(),sweep=el('study-sweep').value;let variations;
 if(sweep==='delay')variations=[0,300,600,900].map(delay=>({label:'delay '+delay+' ms',faults:{delay_ms:delay,delay_rate:1}}));
 if(sweep==='freshness')variations=[100,300,600].map(age=>({label:'max age '+age+' ms',configs:{...spec.configs,[spec.controllers[1]]:{...spec.configs[spec.controllers[1]],max_age_ms:age}}}));
 await runAnalysis('batch',{spec,seeds:listNumbers('study-seeds'),variations});});
el('boundary-parameter').onchange=()=>{const p=el('boundary-parameter').value;el('boundary-values').value=p==='delay_ms'?'0,100,200,300,400,500,600,700,800,900,1000,1100,1200':p==='noise_mm'?'0,10,20,30,40,60,80,100':'0,0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1';};
el('boundary-run').onclick=()=>perform(async()=>{const spec=experimentSpec();spec.scenario='normal';spec.faults={...spec.faults,delay_rate:0,drop_rate:0,duplicate_rate:0,reorder_rate:0,invalid_rate:0,noise_mm:0,disconnect_stream:'none'};await runAnalysis('frontier',{spec,parameter:el('boundary-parameter').value,values:listNumbers('boundary-values'),seeds:listNumbers('study-seeds'),predicate:el('boundary-predicate').value});});
el('minimize-run').onclick=()=>perform(async()=>{if(!current)throw Error('Run an experiment first.');await runAnalysis('minimize',{run_id:current.id,predicate:el('minimize-predicate').value,budget:150});});
async function refreshRegressions(){const cases=await api('/api/regressions');el('regression-list').replaceChildren();for(const c of cases){const button=textNode('button',c.payload.name+' · '+c.id.slice(0,8));button.onclick=()=>perform(async()=>{const result=await api('/api/regressions/check',{id:c.id});displayAnalysis(result.payload,result.id);await refreshAnalyses();});el('regression-list').append(button);}if(!cases.length)el('regression-list').textContent='No saved regressions.';}
el('regression-save').onclick=()=>perform(async()=>{if(!current)throw Error('Run an experiment first.');const limits=el('regression-type').value==='commands'?{expected_commands:current.bundle.manifest.comparison.guarded.rows.map(r=>r.command)}:{guarded_max_incorrect:num('regression-limit')};await api('/api/regressions',{run_id:current.id,name:el('regression-name').value,limits});await refreshRegressions();el('status').textContent='Regression saved. Run it to see its current verdict.';});
el('regression-check').onclick=()=>perform(async()=>{const result=await api('/api/regressions/check',{});displayAnalysis(result.payload,result.id);await refreshAnalyses();});
el('plant-run').onclick=()=>perform(async()=>{const spec=experimentSpec();spec.controllers=spec.controllers.filter(p=>controllerCatalog[p]?.kind!=='native').slice(0,3);if(spec.controllers.length<2)throw Error('Select two non-native controllers for feedback simulation. Native adapters are open-loop only.');await runAnalysis('plant',{spec,ticks:num('plant-ticks'),step_ms:num('plant-step'),speed_mm_s:num('plant-speed'),gate_rate_deg_s:num('plant-gate-rate')});});
function displayAnalysis(value,identity){
 openWorkspaceView('results',false);
 latestAnalysis=value;latestAnalysisId=identity;el('analysis-package').disabled=!value.reproduction_input;el('analysis-results').replaceChildren();el('analysis-export').disabled=false;el('analysis-status').textContent='Completed / '+value.kind+' · saved artifact '+identity.slice(0,8);
 if(value.spec)el('analysis-results').append(textNode('p',`Scenario: ${value.spec.scenario??'normal'} / seeds: ${(value.seeds||[]).join(', ')}`,'muted'));if(value.scope)el('analysis-results').append(textNode('p',value.scope,'analysis-note'));
 if(value.kind==='batch'){
 const rows=[];for(const g of value.groups)for(const [p,m] of Object.entries(g.controllers))rows.push([g.label,p,g.runs,g.mean_divergences.toFixed(2),m.mean_incorrect_pulses===null?null:m.mean_incorrect_pulses.toFixed(2),m.runs_with_incorrect_pulse,m.missed_present_events,m.rejections,(100*m.rejection_fraction).toFixed(1)+'%']);
 el('analysis-results').append(dataTable(['Variation','Controller','Runs','Mean divergences','Mean incorrect pulses','Runs with incorrect pulse','Missed-present events','Rejections','Rejection fraction'],rows));
 }else if(value.kind==='frontier'){
 el('analysis-results').append(textNode('p','First observed failure on supplied grid: '+(value.first_observed_failure??'None')+' / '+value.parameter,'analysis-note'),dataTable(['Parameter value','Failed seeds','Tested seeds','Failure observed'],value.points.map(p=>[p.value,p.failed_seeds,p.seeds,p.any_failure])));
 }else if(value.kind==='minimization'){
 el('analysis-results').append(textNode('p',`${value.original_events} → ${value.retained_events} events · ${value.evaluations} evaluations · 1-minimal: ${value.one_minimal?'certified':'not certified within budget'}`,'analysis-note'));
 const button=textNode('button','Inspect reduced trace');button.onclick=()=>perform(async()=>{render(await api('/api/runs/'+value.run_id));await refreshRunHistory();});el('analysis-results').append(button);
 el('analysis-results').append(dataTable(['Retained time / ms','Observation ID'],value.trace.events.map(e=>[e.time_ms,e.observation?.id??'missing'])));
 }else if(value.kind==='regression-check'){
 if(!value.cases.length)el('analysis-results').append(textNode('p','No saved regressions were checked.'));
 const rows=[];for(const c of value.cases)for(const check of c.checks)rows.push([c.name,check.assertion,Array.isArray(check.actual)?check.actual.join(', '):check.actual,Array.isArray(check.limit)?check.limit.join(', '):check.limit,!check.known?'UNKNOWN':check.passed?'PASS':'FAIL']);el('analysis-results').append(dataTable(['Case','Assertion','Actual','Expected / limit','Verdict'],rows));
 }else if(value.kind==='closed-loop'){
 el('analysis-results').append(dataTable(['Controller','Objects passed','Blocked / ms','Open without near object / ms'],Object.entries(value.trajectories).map(([p,t])=>[p,t.metrics.objects_passed,t.metrics.blocked_duration_ms,t.metrics.open_without_near_object_ms])));
 const assumptions=textNode('ul');for(const a of value.assumptions)assumptions.append(textNode('li',a));el('analysis-results').append(assumptions);
 const controls=textNode('div',undefined,'plant-controls'),label=textNode('label','Model timeline'),slider=document.createElement('input');slider.id='plant-scrub';slider.type='range';slider.min=0;slider.max=value.parameters.ticks-1;slider.value=0;label.append(slider);const time=textNode('p'),frames=textNode('div',undefined,'plant-frame');controls.append(label,time,frames);el('analysis-results').append(controls);
 function frame(){const index=Number(slider.value);time.textContent='Decision at '+index*value.parameters.step_ms+' ms · state after '+(index+1)*value.parameters.step_ms+' ms / model step '+(index+1);frames.replaceChildren();for(const [p,t] of Object.entries(value.trajectories)){const s=t.plant_states[index],card=textNode('article',undefined,'plant-card'),lane=textNode('div',undefined,'model-lane'),gate=textNode('div',undefined,'model-gate');gate.style.transform=`rotate(${-s.gate_angle_deg}deg)`;lane.append(gate);if(s.object_position_mm!==null){const object=textNode('div',undefined,'model-object');object.style.left=Math.max(0,Math.min(96,50+s.object_position_mm/500*50))+'%';lane.append(object);}card.append(textNode('h3',p),lane,textNode('p',`${s.command} · ${s.gate_angle_deg}° · object ${s.object_position_mm??'absent'} mm`),textNode('p',s.reason,'muted'));frames.append(card);}}
 slider.oninput=frame;frame();
 }else{const pre=textNode('pre',JSON.stringify(value,null,2));el('analysis-results').append(pre);}
}
async function refreshAnalyses(){const artifacts=await api('/api/artifacts');el('analysis-history').replaceChildren();for(const a of artifacts.filter(a=>!['profile','regression'].includes(a.kind)).slice(0,30)){const button=textNode('button',a.kind+' · '+a.id.slice(0,8));button.onclick=()=>perform(async()=>{const full=await api('/api/artifacts/'+a.id);displayAnalysis(full.payload,a.id);});el('analysis-history').append(button);}if(!el('analysis-history').children.length)el('analysis-history').textContent='No saved analyses.';}
el('analysis-export').onclick=()=>download(JSON.stringify(latestAnalysis,null,2),'causalbench-analysis.json');
function showCapture(state){const live=state.state==='recording';el('capture-start').disabled=live;el('capture-stop').disabled=!live;el('capture-snapshot').disabled=!state.retained;el('capture-status').textContent=`${state.state} · ${state.synthetic?'SYNTHETIC MOCK / not hardware':state.options.adapter==='http'?'HTTP device / unverified measurement truth':'no adapter'} · received ${state.total_received} · retained ${state.retained} / ${state.retained_bytes??0} bytes · evicted ${state.evicted} · sequence gaps ${state.sequence_gaps} · errors ${state.error_events}${state.error?' · '+state.error:''}`;
 if(state.latest){const e=state.latest;el('capture-latest').textContent=`Latest event ${e.time_ms} ms · ${e.observation?.distance_mm??'missing / invalid'} mm · request uncertainty ${e.uncertainty_ms??'unknown'} ms${e.capture_error?' · '+e.capture_error:''}`;}}
function pollCapture(){clearTimeout(captureTimer);captureTimer=setTimeout(()=>perform(async()=>{const state=await api('/api/capture');showCapture(state);if(state.state==='recording')pollCapture();}),500);}
el('capture-start').onclick=()=>perform(async()=>{const state=await api('/api/capture/start',{adapter:el('capture-adapter').value,url:el('capture-url').value,interval_ms:num('capture-interval'),capacity:num('capture-capacity')});showCapture(state);pollCapture();});
el('capture-stop').onclick=()=>perform(async()=>{clearTimeout(captureTimer);const state=await api('/api/capture/stop',{});showCapture(state);if(state.state==='recording')pollCapture();});
el('capture-snapshot').onclick=()=>perform(async()=>{const spec=experimentSpec();render(await api('/api/capture/snapshot',{configs:spec.configs,controllers:spec.controllers}));await refreshRunHistory();el('status').textContent+=' · snapshot stored; capture can continue';});
el('package-export').onclick=()=>perform(async()=>{if(!current)throw Error('Run an experiment first.');const response=await fetch('/api/packages/'+current.id);if(!response.ok){const error=await response.json();throw Error(error.error);}const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');a.href=url;a.download='causalbench-'+current.id.slice(0,8)+'.zip';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);el('package-status').textContent='Archived sources, evidence and offline reproducer downloaded. Run archived code only when you trust its source.';});
el('package-import').onchange=()=>perform(async()=>{const file=el('package-import').files[0];if(!file)return;if(file.size>16000000)throw Error('Package exceeds 16 MB');const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=32768)binary+=String.fromCharCode(...bytes.subarray(i,i+32768));const result=await api('/api/packages/import',{data:btoa(binary)});if(result.run){render(result.run);await refreshRunHistory();}else{displayAnalysis(result.artifact.payload,result.artifact.id);await refreshAnalyses();}openWorkspaceView('library',false);el('package-status').textContent=`Archive verified / ${result.inspection.files} files / Python ${result.inspection.environment.python}. Imported source was not executed; ${result.run?"trace replayed with installed controllers":"analysis retained without claiming a rerun"}.`;});
perform(initLab);

el('analysis-package').onclick=()=>perform(async()=>{const response=await fetch('/api/artifact-packages/'+latestAnalysisId);if(!response.ok){const e=await response.json();throw Error(e.error);}const url=URL.createObjectURL(await response.blob()),a=document.createElement('a');a.href=url;a.download='causalbench-analysis-'+latestAnalysisId.slice(0,8)+'.zip';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
