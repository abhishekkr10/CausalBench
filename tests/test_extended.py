import copy
import io
import json
import unittest
from unittest.mock import patch
from causalbench.cli import capture
from causalbench.engine import make_trace, compare, replay, seal, verify, canonical, validate_trace
from causalbench.actuators import SimulatedActuator, PhysicalActuator

class ExtendedTests(unittest.TestCase):
    def test_out_of_order(self):
        c=compare(make_trace('out-of-order'))
        self.assertEqual(c['divergence_times_ms'], [1200])
        self.assertEqual(c['guarded']['metrics']['rejected_out_of_order'],1)
    def test_invalid(self):
        c=compare(make_trace('invalid'))
        self.assertEqual(c['guarded']['metrics']['rejected_invalid'],1)
        self.assertEqual(c['guarded']['rows'][6]['command'],'HOLD')
    def test_noise_seed(self):
        self.assertEqual(make_trace('noise',17),make_trace('noise',17))
        self.assertNotEqual(make_trace('noise',17),make_trace('noise',18))
    def test_hysteresis_boundary(self):
        t=make_trace('normal');t['events']=[{'time_ms':i*100,'observation':{'id':str(i),'sample_ms':i*100,'distance_mm':v}} for i,v in enumerate([100,99,119,120])]
        self.assertEqual([r['command'] for r in replay(t,'guarded-v1')['rows']],['HOLD','PULSE','PULSE','HOLD'])
    def test_missing_duration(self):
        self.assertEqual(compare(make_trace('disconnect'))['guarded']['metrics']['missing_observation_duration_ms'],600)
    def test_roundtrip(self):
        t=make_trace('noise');b=seal(t,compare(t));self.assertTrue(verify(json.loads(canonical(b))))
    def test_rehashed_wrong_decision(self):
        from causalbench.engine import digest
        t=make_trace('stale');b=seal(t,compare(t));b['manifest']['comparison']['guarded']['rows'][0]['command']='PULSE';b['manifest_digest']=digest(b['manifest']);self.assertFalse(verify(b))
    def test_unit_validation(self):
        t=make_trace('normal');t['events'][0]['observation']['units']='cm'
        with self.assertRaises(ValueError):validate_trace(t)
    def test_capture_metadata(self):
        raw={'valid':True,'distance_mm':70,'sequence':3,'boot_id':'abc','uptime_ms':123}
        with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(raw).encode())),patch('time.sleep'):
            t=capture('http://mock/reading',1,200)
        self.assertEqual(t['events'][0]['observation']['source_timestamp_ms'],123)
        self.assertNotIn('fixture_present',t['events'][0])
    def test_capture_disconnect_recovers(self):
        raw={'valid':True,'distance_mm':70,'sequence':3,'boot_id':'abc'}
        with patch('urllib.request.urlopen',side_effect=[OSError('offline'),io.BytesIO(json.dumps(raw).encode())]),patch('time.sleep'):
            t=capture('http://mock/reading',2,200)
        self.assertIsNone(t['events'][0]['observation']);self.assertIsNotNone(t['events'][1]['observation'])
    def test_capture_partial_preserved(self):
        with patch('urllib.request.urlopen',return_value=io.BytesIO(b'{"valid":false,"distance_mm":null}')),patch('time.sleep'):
            t=capture('http://mock/reading',1,200)
        self.assertFalse(t['events'][0]['raw_observation']['valid'])
    def test_actuator_safety(self):
        self.assertTrue(SimulatedActuator().command('PULSE',100)['simulated'])
        with self.assertRaises(RuntimeError):PhysicalActuator()
        with self.assertRaises(NotImplementedError):PhysicalActuator(enabled=True)

    def test_configuration_changes_replay(self):
        t=make_trace('stale');t['controller_config']={'version':1,'enter_mm':100,'exit_mm':120,'max_age_ms':700}
        # Still rejected by ordering, even when freshness allows the sample.
        self.assertEqual(compare(t)['guarded']['metrics']['rejected_out_of_order'],1)
        t=make_trace('normal');t['controller_config']={'version':1,'enter_mm':50,'exit_mm':60,'max_age_ms':300}
        self.assertEqual(compare(t)['guarded']['metrics']['pulses'],0)
    def test_bad_configuration(self):
        t=make_trace('normal');t['controller_config']={'version':1,'enter_mm':100,'exit_mm':50,'max_age_ms':300}
        with self.assertRaises(ValueError):validate_trace(t)
    def test_boolean_schema_rejected(self):
        t=make_trace('normal');t['schema_version']=True
        with self.assertRaises(ValueError):validate_trace(t)
    def test_device_nonobject(self):
        with patch('urllib.request.urlopen',return_value=io.BytesIO(b'[]')),patch('time.sleep'):
            t=capture('http://mock/reading',1,200)
        self.assertIsNone(t['events'][0]['observation'])
