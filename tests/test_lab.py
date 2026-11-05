import copy
import io
import json
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch
import test_server as helpers
from causalbench.engine import compare, digest, verify, seal, validate_trace
from causalbench.faults import generate, settings, configuration
from causalbench.controllers import evaluate, registry
from causalbench.studies import batch, minimize, frontier, regression, check_regression
from causalbench.plant import simulate
from causalbench.capture import Recorder, read_http
from causalbench import packages


class LabEngineTests(unittest.TestCase):
    def test_composed_faults_repeatable_and_unchanged(self):
        f={'delay_rate':.4,'drop_rate':.2,'duplicate_rate':.3,'invalid_rate':.1,'noise_mm':20}
        t=generate('normal',42,f,36,True,policies=['baseline-v1','guarded-v1','fusion-v1'])
        self.assertEqual(t,generate('normal',42,f,36,True,policies=['baseline-v1','guarded-v1','fusion-v1']))
        before=copy.deepcopy(t)
        self.assertEqual(compare(t),compare(t))
        self.assertEqual(t,before)

    def test_zero_delay_uses_current_value(self):
        t=generate('normal',faults={'delay_ms':0,'delay_rate':1})
        self.assertEqual(compare(t)['divergence_times_ms'],[])
        self.assertEqual(t['events'][6]['observation']['distance_mm'],250)

    def test_delay_uses_real_old_sample(self):
        t=generate('normal',faults={'delay_ms':600,'delay_rate':1})
        o=t['events'][6]['observation']
        self.assertEqual((o['sample_ms'],o['distance_mm']),(600,70))
        self.assertIn('delay',t['events'][6]['applied_faults'])

    def test_probability_and_config_validation(self):
        for f in ({'drop_rate':True},{'drop_rate':float('nan')},{'unknown':1},{'delay_ms':-1}):
            with self.assertRaises(ValueError):settings(f)
        with self.assertRaises(ValueError):configuration({'version':True})
        with self.assertRaises(ValueError):configuration({'exit_mm':50})

    def test_stream_validation(self):
        t=generate(multistream=True)
        t['events'][0]['streams']['temperature']['unit']='degrees'
        with self.assertRaises(ValueError):validate_trace(t)

    def test_fusion_missing_corroboration(self):
        t=generate('normal',multistream=False,policies=['guarded-v1','fusion-v1'])
        c=compare(t)
        self.assertGreater(c['guarded']['metrics']['rejected_sensor_disagreement'],0)
        self.assertEqual(c['guarded']['metrics']['pulses'],0)

    def test_fusion_imu_veto(self):
        t=generate('normal',multistream=True,policies=['guarded-v1','fusion-v1'])
        t['events'][3]['streams']['imu']['value']=2000
        c=compare(t)
        self.assertEqual(c['guarded']['rows'][3]['command'],'HOLD')
        self.assertIn('IMU',c['guarded']['rows'][3]['reason'])

    def test_fixture_truth_separation_all_plugins(self):
        t=generate('stale',multistream=True,policies=['baseline-v1','guarded-v1','fusion-v1','native-guarded-v1'])
        a=compare(t)
        for e in t['events']:e['fixture_present']=not e['fixture_present']
        b=compare(t)
        for p in a['controllers']:
            self.assertEqual([r['command'] for r in a['controllers'][p]['rows']],[r['command'] for r in b['controllers'][p]['rows']])

    def test_native_matches_python_fault_cases(self):
        self.assertIn('native-guarded-v1',registry())
        for scenario in ('normal','stale','duplicate','disconnect','out-of-order','noise','invalid'):
            t=generate(scenario,policies=['guarded-v1','native-guarded-v1'])
            self.assertEqual(compare(t)['divergence_times_ms'],[],scenario)

    def test_native_bad_output_rejected(self):
        t=generate()
        with patch('subprocess.run',return_value=subprocess.CompletedProcess([],0,'OPEN nope\n','')):
            with self.assertRaises(ValueError):evaluate(t,'native-guarded-v1')

    def test_native_nondeterminism_rejected(self):
        with patch('subprocess.run',side_effect=[subprocess.CompletedProcess([],0,'HOLD missing\n',''),subprocess.CompletedProcess([],0,'PULSE accepted\n','')]):
            with self.assertRaises(ValueError):evaluate(generate(),'native-guarded-v1')

    def test_batch_is_paired_and_seeded(self):
        spec={'scenario':'normal','faults':{'drop_rate':.3},'controllers':['baseline-v1','guarded-v1']}
        variants=[{'label':'small noise','faults':{'noise_mm':10}},{'label':'larger noise','faults':{'noise_mm':30}}]
        a=batch(spec,[1,2,3],variants)
        self.assertEqual(a,batch(spec,[1,2,3],variants))
        self.assertEqual(len(a['records']),6)
        self.assertEqual([r['seed'] for r in a['records']],[1,2,3,1,2,3])

    def test_minimizer_preserves_time_and_failure(self):
        t=generate(policies=['baseline-v1','guarded-v1'])
        before=copy.deepcopy(t)
        r=minimize(t)
        self.assertEqual(r['retained_events'],1)
        self.assertTrue(r['one_minimal'])
        self.assertEqual(r['trace']['events'][0]['time_ms'],1200)
        self.assertTrue(r['comparison']['divergence_times_ms'])
        self.assertEqual(t,before)

    def test_minimizer_rejects_nonfailure(self):
        with self.assertRaises(ValueError):minimize(generate('normal'))

    def test_regression_pass_fail_unknown(self):
        t=generate()
        self.assertTrue(check_regression(regression(t,'guarded'))['passed'])
        self.assertFalse(check_regression(regression(t,'baseline',{'baseline_max_incorrect':0}))['passed'])
        for e in t['events']:e.pop('fixture_present')
        result=check_regression(regression(t,'unknown'))
        self.assertFalse(result['passed'])
        self.assertFalse(result['checks'][0]['known'])

    def test_command_regression_detects_changed_config(self):
        t=generate('normal',policies=['baseline-v1','guarded-v1'])
        commands=[r['command'] for r in compare(t)['guarded']['rows']]
        case=regression(t,'commands',{'expected_commands':commands})
        self.assertTrue(check_regression(case)['passed'])
        case['trace']['controller_configs']={'guarded-v1':{'version':1,'enter_mm':50,'exit_mm':60,'max_age_ms':300}}
        case['trace_digest']=digest(case['trace'])
        self.assertFalse(check_regression(case)['passed'])

    def test_frontier_scans_actual_grid(self):
        result=frontier({'scenario':'normal'},values=[0,100,600],seeds=[42,43])
        self.assertEqual(result['first_observed_failure'],100)
        self.assertEqual([p['failed_seeds'] for p in result['points']],[0,2,2])

    def test_plant_deterministic_and_feedback(self):
        spec={'controllers':['baseline-v1','guarded-v1'], 'faults':{'delay_rate':1,'delay_ms':600,'start_ms':0,'duration_ms':12000}}
        a=simulate(spec,30)
        self.assertEqual(a,simulate(spec,30))
        self.assertNotEqual(a['trajectories']['baseline-v1']['plant_states'],a['trajectories']['guarded-v1']['plant_states'])
        self.assertIn('Independent',a['scope'])

    def test_plant_never_accepts_native_without_adapter(self):
        with self.assertRaises(ValueError):simulate({'controllers':['baseline-v1','native-guarded-v1']})

    def test_capture_ring_and_no_truth(self):
        recorder=Recorder()
        try:
            recorder.start({'adapter':'mock','interval_ms':20,'capacity':10})
            deadline=time.monotonic()+2
            while recorder.snapshot()['total_received']<12 and time.monotonic()<deadline:time.sleep(.01)
            recorder.stop()
            state=recorder.snapshot()
            self.assertEqual(state['retained'],10)
            self.assertGreaterEqual(state['evicted'],2)
            t=recorder.trace()
            self.assertNotIn('fixture_present',t['events'][0])
            self.assertEqual(t['source_kind'],'synthetic-mock')
        finally:recorder.stop()

    def test_http_capture_clock_domains_and_streams(self):
        raw={'valid':True,'distance_mm':70,'sequence':4,'boot_id':'device','uptime_ms':99999,
            'streams':{'temperature':{'sample_ms':99999,'value':24000,'unit':'milliC'}}}
        with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(raw).encode())):
            e=read_http('http://device',time.monotonic_ns(),0)
        self.assertEqual(e['observation']['source_timestamp_ms'],99999)
        self.assertEqual(e['streams']['temperature']['source_sample_ms'],99999)
        self.assertLessEqual(e['streams']['temperature']['sample_ms'],e['time_ms'])

    def test_http_errors_explicit(self):
        with patch('urllib.request.urlopen',side_effect=OSError('disconnected')):
            e=read_http('http://device',time.monotonic_ns(),0)
        self.assertIsNone(e['observation'])
        self.assertIn('disconnected',e['capture_error'])

    def test_portable_package_reproduces(self):
        t=generate(multistream=True,policies=['baseline-v1','guarded-v1','fusion-v1','native-guarded-v1'])
        b=seal(t,compare(t))
        _,source=packages.source_snapshot()
        archive=packages.build(b,source)
        self.assertTrue(packages.inspect(archive)['valid'])
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with zipfile.ZipFile(io.BytesIO(archive)) as z:z.extractall(root)
            process=subprocess.run([sys.executable,str(root/'reproduce.py')],cwd=root,capture_output=True,text=True,timeout=20)
            self.assertEqual(process.returncode,0,process.stdout+process.stderr)
            self.assertIn('REPRODUCED',process.stdout)

    def test_modified_package_rejected(self):
        t=generate();_,source=packages.source_snapshot();archive=packages.build(seal(t,compare(t)),source)
        out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(archive)) as original,zipfile.ZipFile(out,'w') as modified:
            for n in original.namelist():modified.writestr(n,b'{}' if n=='trace.json' else original.read(n))
        with self.assertRaises(ValueError):packages.inspect(out.getvalue())

    def test_package_path_traversal_rejected(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:z.writestr('../escape.py','malicious')
        with self.assertRaises(ValueError):packages.inspect(out.getvalue())


class LabAPITests(unittest.TestCase):
    def test_foreign_host_rejected(self):
        import urllib.request
        request=urllib.request.Request(self.url+'/api/runs',headers={'Host':'foreign.example'})
        with self.assertRaises(urllib.error.HTTPError) as raised:urllib.request.urlopen(request)
        self.assertEqual(raised.exception.code,403)

    def test_large_export_can_verify_through_api(self):
        trace=generate('normal',events=1000,multistream=True,policies=['baseline-v1','guarded-v1'])
        for event in trace['events']:event['capture_note']='x'*500
        run=self.store.create(trace)
        from causalbench.engine import canonical
        self.assertGreater(len(canonical(run['bundle']).encode()),2000000)
        self.assertTrue(self.request('/api/verify',run['bundle'])['valid'])

    setUp=helpers.ServerTests.setUp
    request=helpers.ServerTests.request

    def tearDown(self):
        self.server.RequestHandlerClass.recorder.stop()
        helpers.ServerTests.tearDown(self)

    def test_controller_and_lab_static(self):
        self.assertIn('fusion-v1',self.request('/api/controllers'))
        import urllib.request
        with urllib.request.urlopen(self.url+'/lab.js') as r:self.assertIn(b'experimentSpec',r.read())

    def test_profile_persistence_and_validation(self):
        saved=self.request('/api/profiles',{'name':'bench','configuration':{'enter_mm':90,'exit_mm':110,'max_age_ms':250}})
        self.assertEqual(self.request('/api/profiles')[0]['id'],saved['id'])
        from causalbench.server import Store
        self.assertEqual(Store(self.path).artifact(saved['id']),saved)
        with self.assertRaises(urllib.error.HTTPError):self.request('/api/profiles',{'name':'bad','configuration':{'exit_mm':1}})

    def test_regression_workflow(self):
        run=self.request('/api/runs',{'scenario':'stale','controllers':['baseline-v1','guarded-v1'],'multistream':True})
        case=self.request('/api/regressions',{'run_id':run['id'],'name':'stale guard'})
        checked=self.request('/api/regressions/check',{'id':case['id']})
        self.assertTrue(checked['payload']['cases'][0]['passed'])

    def test_job_persists_minimized_experiment(self):
        run=self.request('/api/runs',{'scenario':'stale'})
        job=self.request('/api/jobs',{'kind':'minimize','run_id':run['id']})
        deadline=time.monotonic()+5
        while job['status']=='running' and time.monotonic()<deadline:
            time.sleep(.02);job=self.request('/api/jobs/'+job['id'])
        self.assertEqual(job['status'],'complete',job)
        self.assertEqual(job['result']['retained_events'],1)
        self.assertEqual(self.request('/api/artifacts/'+job['artifact_id'])['payload'],job['result'])

    def test_capture_api_snapshot_and_stop(self):
        self.request('/api/capture/start',{'adapter':'mock','interval_ms':20,'capacity':10})
        deadline=time.monotonic()+2
        while self.request('/api/capture')['retained']<2 and time.monotonic()<deadline:time.sleep(.01)
        run=self.request('/api/capture/snapshot',{})
        self.assertEqual(run['bundle']['manifest']['trace']['source_kind'],'synthetic-mock')
        self.assertIsNone(run['bundle']['manifest']['comparison']['guarded']['metrics']['unsafe_fixture_pulses'])
        self.assertEqual(self.request('/api/capture/stop',{})['state'],'stopped')

    def test_artifact_tamper_detected(self):
        from causalbench.server import connection
        a=self.store.save_artifact('batch',{'kind':'batch','test':1})
        with connection(self.path) as db:db.execute('UPDATE artifacts SET payload=? WHERE id=?',('{"test":2}',a['id']))
        with self.assertRaises(ValueError):self.store.artifact(a['id'])

    def test_package_route_and_import(self):
        import urllib.request
        import base64
        run=self.request('/api/runs',{'scenario':'stale','controllers':['baseline-v1','guarded-v1']})
        with urllib.request.urlopen(self.url+'/api/packages/'+run['id']) as response:archive=response.read()
        result=self.request('/api/packages/import',{'data':base64.b64encode(archive).decode()})
        self.assertTrue(result['inspection']['valid'])
        self.assertNotEqual(result['run']['id'],run['id'])

    def test_analysis_package_reproduces_and_reimports(self):
        import base64
        body={'spec':{'scenario':'normal'},'parameter':'delay_ms','values':[0,100,600],'seeds':[42]}
        payload=frontier(**body)
        payload['reproduction_input']=body
        saved=self.store.save_artifact('frontier',payload)
        archive=self.store.artifact_package(saved['id'])
        self.assertEqual(packages.inspect(archive)['kind'],'analysis')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            with zipfile.ZipFile(io.BytesIO(archive)) as z:z.extractall(root)
            run=subprocess.run([sys.executable,str(root/'reproduce.py')],cwd=root,capture_output=True,text=True,timeout=20)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        imported=self.request('/api/packages/import',{'data':base64.b64encode(archive).decode()})
        self.assertEqual(imported['artifact']['payload'],payload)
        self.assertTrue(packages.inspect(self.store.artifact_package(imported['artifact']['id']))['valid'])

    def test_failed_job_reports_error(self):
        job=self.request('/api/jobs',{'kind':'batch','seeds':[-1]})
        deadline=time.monotonic()+3
        while job['status']=='running' and time.monotonic()<deadline:
            time.sleep(.02);job=self.request('/api/jobs/'+job['id'])
        self.assertEqual(job['status'],'failed')
        self.assertIn('seed',job['error'])


class AdditionalLabTests(unittest.TestCase):
    def test_http_device_end_to_end_and_sequence_gaps(self):
        import threading
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        class Device(BaseHTTPRequestHandler):
            counter=0
            def do_GET(self):
                index=Device.counter;Device.counter+=1
                sequence=[1,3,2,4][index] if index<4 else index+1
                payload=json.dumps({'valid':True,'distance_mm':70,'sequence':sequence,'boot_id':'stub','uptime_ms':1000+index,
                    'streams':{'temperature':{'value':24000,'unit':'milliC'}}}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Device)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        recorder=Recorder()
        try:
            recorder.start({'adapter':'http','url':f'http://127.0.0.1:{server.server_port}/reading','interval_ms':20,'capacity':10})
            deadline=time.monotonic()+3
            while recorder.snapshot()['total_received']<4 and time.monotonic()<deadline:time.sleep(.01)
            recorder.stop()
            self.assertEqual(recorder.snapshot()['sequence_gaps'],1)
            trace=recorder.trace()
            self.assertEqual(trace['events'][0]['observation']['distance_mm'],70)
            self.assertEqual(trace['events'][0]['streams']['temperature']['value'],24000)
        finally:
            recorder.stop();server.shutdown();server.server_close();thread.join()

    def test_installed_custom_native_controller(self):
        import shutil
        import causalbench.controllers as controllers
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'controllers').mkdir();(root/'causalbench').mkdir()
            executable='custom.exe' if sys.platform=='win32' else 'custom.bin'
            shutil.copy2(controllers.ROOT/'controllers'/controllers.NATIVE_NAME,root/'controllers'/executable)
            shutil.copyfile(controllers.ROOT/'controllers'/'native_guarded.cpp',root/'controllers'/'custom.cpp')
            shutil.copyfile(controllers.ROOT/'causalbench'/'engine.py',root/'causalbench'/'engine.py')
            descriptor={'schema_version':1,'id':'custom-native','kind':'native','executable':executable,'source':'custom.cpp','description':'Installed native test',
                'configuration':{'version':1,'enter_mm':50,'exit_mm':60,'max_age_ms':300}}
            (root/'controllers'/'custom.controller.json').write_text(json.dumps(descriptor),encoding='utf-8')
            with patch('causalbench.controllers.ROOT',root):
                trace=generate('normal',policies=['guarded-v1','custom-native'])
                result=compare(trace)
                self.assertEqual(result['guarded']['policy'],'custom-native')
                self.assertEqual(result['guarded']['metrics']['pulses'],0)
                self.assertTrue(result['divergence_times_ms'])

    def test_capture_byte_budget_keeps_snapshot_valid(self):
        recorder=Recorder()
        def reading(url,origin,index):
            if index == 119:
                recorder.stop_event.set()
            return {'time_ms':index*20,'observation':{'id':str(index),'sample_ms':index*20,'distance_mm':250,'sequence':index,'session_id':'mock-http'},
                    'raw_observation':{'padding':'x'*14000},'capture_error':None}
        try:
            # Exercise byte eviction with a fixed input count, independent of
            # runner scheduling speed. Thread startup has separate coverage.
            recorder.options={'adapter':'http','url':'http://mock','interval_ms':20,'capacity':1000}
            with patch('causalbench.capture.read_http',side_effect=reading), patch.object(recorder.stop_event,'wait',return_value=False):
                recorder._run()
            state=recorder.snapshot()
            self.assertGreater(state['evicted'],0)
            self.assertLessEqual(state['retained_bytes'],1500000)
            validate_trace(recorder.trace())
        finally:recorder.stop()

    def test_nonfinite_device_response_preserved_as_text(self):
        with patch('urllib.request.urlopen',return_value=io.BytesIO(b'{"valid":true,"distance_mm":NaN}')):
            event=read_http('http://device',time.monotonic_ns(),0)
        self.assertIsNone(event['observation'])
        self.assertIn('NaN',event['raw_observation']['invalid_json_text'])
        from causalbench.engine import canonical
        canonical(event)

    def test_loaded_source_is_not_relabelled_after_edit(self):
        from causalbench.provenance import register_source, loaded_source
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'module.py'
            path.write_bytes(b'old implementation')
            register_source(path)
            path.write_bytes(b'new implementation')
            self.assertEqual(loaded_source(path),b'old implementation')
            register_source(path)
            self.assertEqual(loaded_source(path),b'new implementation')

    def test_all_analysis_archives_reproduce(self):
        trace=generate(policies=['baseline-v1','guarded-v1'])
        requests=[
            (batch({'scenario':'normal'},[1,2]),{'spec':{'scenario':'normal'},'seeds':[1,2]}),
            (minimize(trace),{'trace':trace,'predicate':'divergence','budget':150}),
            (simulate({'controllers':['baseline-v1','guarded-v1']},10),{'spec':{'controllers':['baseline-v1','guarded-v1']},'ticks':10}),
        ]
        case=regression(trace,'saved')
        requests.append(({'kind':'regression-check','cases':[check_regression(case)]},{'cases':[case]}))
        _,source=packages.source_snapshot()
        for payload,body in requests:
            payload['reproduction_input']=body
            archive=packages.build_analysis(payload,source)
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                with zipfile.ZipFile(io.BytesIO(archive)) as z:z.extractall(root)
                process=subprocess.run([sys.executable,str(root/'reproduce.py')],cwd=root,capture_output=True,text=True,timeout=20)
                self.assertEqual(process.returncode,0,payload['kind']+process.stdout+process.stderr)

    def test_cli_regression_exit_codes(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'cases.json'
            for expected,key in ((0,'guarded_max_incorrect'),(1,'baseline_max_incorrect')):
                path.write_text(json.dumps({'cases':[regression(generate(),'case',{key:0})]}),encoding='utf-8')
                run=subprocess.run([sys.executable,'-m','causalbench.lab_cli','regressions','--input',str(path)],cwd=packages.ROOT,capture_output=True,text=True,timeout=10)
                self.assertEqual(run.returncode,expected,run.stderr)

    def test_independent_sensor_does_not_copy_fault(self):
        trace=generate('stale',multistream=True)
        event=trace['events'][6]
        self.assertEqual(event['observation']['distance_mm'],70)
        self.assertFalse(event['streams']['proximity']['value'])

    def test_archived_evidence_survives_installed_plugin_change(self):
        trace=generate(policies=['baseline-v1','guarded-v1'])
        bundle=seal(trace,compare(trace))
        with patch('causalbench.controllers.implementation_digest',return_value='different build'):
            self.assertTrue(verify(bundle))

    def test_baseline_effective_configuration(self):
        result=compare(generate(policies=['baseline-v1','guarded-v1']))
        self.assertEqual(result['baseline']['configuration']['exit_mm'],100)

    def test_three_controller_plant_results(self):
        result=simulate({'controllers':['baseline-v1','guarded-v1','fusion-v1']},15)
        self.assertEqual(len(result['trajectories']),3)
        for t in result['trajectories'].values():
            self.assertEqual(len(t['plant_states']),15)
            self.assertTrue(all(0<=s['gate_angle_deg']<=90 for s in t['plant_states']))
