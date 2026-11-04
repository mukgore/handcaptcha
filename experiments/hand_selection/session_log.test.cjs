const test=require('node:test'),assert=require('node:assert/strict');
const {SessionLog}=require('./session_log.js');
test('events use monotonic relative time and snapshot cannot mutate history',()=>{
  let now=100;const log=new SessionLog({clock:()=>now});
  log.record('preparation_started');now=130;log.record('selected');now=125;log.record('palm_self_report',{palm_confirmed:true});
  const report=log.snapshot();assert.deepEqual(report.events.map(e=>e.t_ms),[0,30,30]);
  report.events[0].event='changed';assert.equal(log.snapshot().events[0].event,'preparation_started');
  assert.equal(report.palm_assessment,'user_self_report_only');
});
test('private fields and arbitrary errors cannot enter the export',()=>{
  const log=new SessionLog();
  for(const fields of [{landmarks:[]},{filename:'person.mp4'},{reason:'private error text'},
    {score:1},{participant_id:'private'},{ui_condition:'unknown'}])
    assert.throws(()=>log.record('technical_error',fields));
  assert.throws(()=>log.record('raw_frame'));
  assert.equal(log.snapshot().events.length,0);
});
test('bounded event history records truncation',()=>{
  const log=new SessionLog({limit:2});
  log.record('selected');log.record('lost');log.record('reselect');
  assert.equal(log.snapshot().events.length,2);assert.equal(log.snapshot().truncated,true);
});
