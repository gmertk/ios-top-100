const {test} = require('node:test');
const assert = require('node:assert/strict');
const {DEFAULT_FILTERS,selectMovers,selectDiscoveries} = require('../templates/opportunities.js');
function fixture() {
  const charts = {
    'top-free:6007':{genre:'6007',feed_type:'top-free',label:'Productivity · Top Free'},
    'top-paid:6018':{genre:'6018',feed_type:'top-paid',label:'Books · Top Paid'},
    'top-free:all':{genre:'all',feed_type:'top-free',label:'Overall · Top Free'},
    'top-free:6014':{genre:'6014',feed_type:'top-free',label:'Games · Top Free'}
  };
  const apps={}, candidates=[];
  for(let i=0;i<40;i++) {
    const id=String(i),key=i===39?'top-paid:6018':'top-free:6007';
    apps[id]={id,name:`App ${id}`,artist:`Maker ${id}`,age_days:30,charts:[{key,...charts[key],rank:20}]};
    candidates.push({id,signals:[{key,gain:80-i,rank:20,streak:1}]});
  }
  return {apps,charts,discoveries:['0','39'],windows:[{days:7,candidates}]};
}
const hidden=()=>({apps:{},developers:{}});
test('filters find candidates outside the original top 25',()=>{
  const result=selectMovers(fixture(),7,{...DEFAULT_FILTERS,category:'6018'},hidden());
  assert.equal(result.length,1);assert.equal(result[0].id,'39');
});
test('selects matching chart evidence rather than overall biggest gain',()=>{
  const data=fixture(); data.windows[0].candidates[0].signals.push({key:'top-paid:6018',gain:10,rank:30,streak:0});
  const result=selectMovers(data,7,{...DEFAULT_FILTERS,category:'6018',chartType:'top-paid'},hidden());
  assert.equal(result.find(a=>a.id==='0').signal.key,'top-paid:6018');
  assert.equal(result.find(a=>a.id==='0').signal.gain,10);
  assert.equal(selectMovers(data,7,{...DEFAULT_FILTERS,category:'6018',chartType:'top-free'},hidden()).length,0);
});
test('sustained climbs precede larger isolated jumps',()=>{
  const data=fixture();data.windows[0].candidates[39].signals[0].streak=3;
  assert.equal(selectMovers(data,7,DEFAULT_FILTERS,hidden())[0].id,'39');
  assert.deepEqual(selectMovers(data,7,{...DEFAULT_FILTERS,mode:'sustained'},hidden()).map(a=>a.id),['39']);
});
test('age and minimum gain exclude unknown ages and small rises',()=>{
  const data=fixture();data.apps['0'].age_days=null;data.apps['1'].age_days=181;
  const result=selectMovers(data,7,{...DEFAULT_FILTERS,age:'180',minGain:70},hidden());
  assert.ok(!result.some(a=>['0','1'].includes(a.id)));assert.ok(result.every(a=>a.signal.gain>=70));
});
test('hide games also removes an overall-chart signal',()=>{
  const data=fixture();const app=data.apps['0'];app.charts.push({key:'top-free:6014',...data.charts['top-free:6014'],rank:4});
  data.windows[0].candidates[0].signals[0].key='top-free:all';
  assert.ok(!selectMovers(data,7,{...DEFAULT_FILTERS,hideGames:true},hidden()).some(a=>a.id==='0'));
});
test('hidden developers and apps affect both shortlists and can be restored',()=>{
  const data=fixture(), h=hidden();h.developers['Maker 0']='Maker 0';h.apps['39']='App 39';
  assert.ok(!selectMovers(data,7,DEFAULT_FILTERS,h).some(a=>['0','39'].includes(a.id)));
  assert.equal(selectDiscoveries(data,DEFAULT_FILTERS,h).length,0);
  delete h.developers['Maker 0'];assert.equal(selectDiscoveries(data,DEFAULT_FILTERS,h)[0].id,'0');
});
test('fresh discoveries obey category but ignore momentum-only thresholds',()=>{
  const result=selectDiscoveries(fixture(),{...DEFAULT_FILTERS,category:'6018',minGain:99,mode:'sustained'},hidden());
  assert.equal(result.length,1);assert.equal(result[0].id,'39');assert.equal(result[0].matchingCharts[0].genre,'6018');
});
test('an unavailable window returns no candidates',()=>{
  assert.deepEqual(selectMovers(fixture(),30,DEFAULT_FILTERS,hidden()),[]);
});
