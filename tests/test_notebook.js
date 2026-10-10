const {test} = require('node:test');
const assert = require('node:assert/strict');
const {parse,serialize,merge,observe} = require('../templates/notebook.js');
const entry = (overrides={}) => ({id:'123',country:'us',name:'Example',artist:'Maker',url:'https://example.com',
  reportDate:'2026-10-09',savedAt:'2026-10-09T10:00:00.000Z',charts:[{key:'top-free:6018',rank:30,label:'Books · Top Free'}],
  notes:{why:'Worth researching',audience:'Readers',problem:'',angle:'',experiment:''},...overrides});
test('backup roundtrip preserves notes and saved rank evidence',()=>{
  const entries=[entry()];assert.deepEqual(parse(serialize(entries)),entries);
});
test('imports preserve local notes and merge by app and country',()=>{
  const local=entry(), incoming=entry({notes:{...local.notes,why:'Older note'}});
  const result=merge([local],[incoming,entry({id:'456'}),entry({country:'gb'})]);
  assert.equal(result.added,2);assert.equal(result.kept,1);assert.equal(result.entries[0].notes.why,'Worth researching');
  assert.equal(result.entries.length,3);
});
test('invalid entries reject the whole import and unsafe links are rejected',()=>{
  for(const bad of [entry({url:'javascript:alert(1)'}),entry({reportDate:'2026-02-30'}),entry({notes:{}}),entry({charts:[{key:'top-free:6018',rank:101,label:'Books'}]})]) {
    assert.throws(()=>parse(JSON.stringify({format:'ios-app-radar-notebook',version:1,entries:[entry(),bad]})));
  }
  assert.throws(()=>parse('not json'));
  assert.throws(()=>parse(JSON.stringify({format:'ios-app-radar-notebook',version:2,entries:[]})));
});
test('duplicate identities and oversized notebooks are rejected',()=>{
  assert.throws(()=>serialize([entry(),entry()]));
  assert.throws(()=>merge(Array.from({length:200},(_,i)=>entry({id:String(i)})),[entry({id:'999'})]));
  assert.throws(()=>parse(' '.repeat(5*1024*1024+1)));
});
test('tracking includes apps outside candidates and compares only matching later charts',()=>{
  const data={country:'us',date:'2026-10-10',apps:{},tracking:{'123':{charts:[
    {key:'top-free:6018',rank:10,label:'Books'},{key:'top-paid:6018',rank:5,label:'Paid books'}]}}};
  const current=observe(entry(),data);
  assert.equal(current.state,'present');assert.equal(current.charts[0].gain,20);assert.equal(current.charts[1].gain,null);
  assert.equal(observe(entry(),{...data,date:'2026-10-09'}).charts[0].gain,null);
  assert.equal(observe(entry(),{...data,date:'2026-10-08'}).charts[0].gain,null);
  data.tracking['123'].charts[0].rank=50;assert.equal(observe(entry(),data).charts[0].gain,-20);
});
test('missing charts and other countries do not invent rank changes',()=>{
  assert.deepEqual(observe(entry(),{country:'us',tracking:{}}),{state:'absent',charts:[]});
  assert.deepEqual(observe(entry(),{country:'gb',tracking:{}}),{state:'other-country',charts:[]});
});
