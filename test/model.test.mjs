import test from 'node:test';
import assert from 'node:assert/strict';
import {buildForecast,evaluateRecorded,MODEL_VERSION} from '../model.mjs';
import {Store} from '../store.mjs';
const now=new Date('2026-11-06T12:00:00Z');
function history(){
 return Array.from({length:240},(_,i)=>({id:'past:'+i,competition:'Brasileirão Série A',competitionCode:'bra.1',season:2026,home:'A',away:'B',homeTeamId:'A',awayTeamId:'B',kickoff:new Date(Date.UTC(2026,0,1+i,20)).toISOString(),status:'finished',homeGoals:i%3===0?0:2,awayGoals:i%3===0?1:i%3===1?2:0,collectedAt:now.toISOString()}));
}
const future={id:'next',competition:'Brasileirão Série A',competitionCode:'bra.1',season:2026,home:'A',away:'B',homeTeamId:'A',awayTeamId:'B',kickoff:'2026-11-07T20:00:00.000Z',kickoffConfirmed:true,status:'scheduled',homeGoals:null,awayGoals:null,collectedAt:now.toISOString()};
test('modelo aprende pesos e entrega probabilidades válidas com amostra explícita',()=>{
 const r=buildForecast([...history(),future],now);
 assert.equal(r.trainingMatches,240);assert.equal(r.forecasts.length,1);assert.ok(r.walkForward.model.count>0);
 const p=r.forecasts[0];assert.equal(p.version,MODEL_VERSION);assert.equal(p.evidence.home.matches,240);
 assert.ok(Math.abs(p.probabilities.reduce((a,b)=>a+b,0)-1)<1e-12);assert.ok(p.probabilities.every(v=>v>0&&v<1));
 assert.ok(r.weights.flat().some(v=>v!==0));assert.equal(r.status,'experimental');
});
test('resultados posteriores ao corte não alteram o treino ou a previsão',()=>{
 const rows=[...history(),future],baseline=buildForecast(rows,now);
 const leaked={...future,id:'future-finished',kickoff:'2026-11-08T20:00:00.000Z',status:'finished',homeGoals:99,awayGoals:0};
 const sameDay={...leaked,id:'today-finished',kickoff:'2026-11-06T01:00:00.000Z'};
 const recent={...leaked,id:'late-yesterday',kickoff:'2026-11-05T23:00:00.000Z'};
 const altered=buildForecast([...rows,leaked,sameDay,recent],now);
 assert.deepEqual(altered.forecasts[0].probabilities,baseline.forecasts[0].probabilities);assert.equal(altered.dataHash,baseline.dataHash);
});
test('teste histórico nunca usa o resultado do próprio dia para prever outra partida',()=>{
 const rows=history(),same={...rows[200],id:'same-day',kickoff:rows[200].kickoff};
 const a=buildForecast([...rows,same],now);same.homeGoals=30;
 const b=buildForecast([...rows,same],now);
 const earlyA=a.walkForward.records.filter(r=>Date.parse(r.kickoff)<=Date.parse(same.kickoff));
 const earlyB=b.walkForward.records.filter(r=>Date.parse(r.kickoff)<=Date.parse(same.kickoff));
 assert.deepEqual(earlyA.map(r=>r.probabilities),earlyB.map(r=>r.probabilities));
 assert.notDeepEqual(a.weights,b.weights);
 const reordered=buildForecast([...history()].reverse(),now);
 assert.deepEqual(reordered.forecasts,buildForecast(history(),now).forecasts);
 assert.deepEqual(reordered.weights,buildForecast(history(),now).weights);
});
test('recusa previsões com coleta antiga, pouca história, outra liga ou horário indefinido',()=>{
 assert.equal(buildForecast([future],now).forecasts.length,0);
 const stale=[...history(),future].map(r=>({...r,collectedAt:'2026-11-01T12:00:00Z'}));
 assert.equal(buildForecast(stale,now).forecasts.length,0);
 assert.equal(buildForecast([...history(),{...future,competitionCode:'bra.2'}],now).forecasts.length,0);
 assert.equal(buildForecast([...history(),{...future,kickoffConfirmed:false}],now).forecasts.length,0);
 assert.equal(buildForecast([...history(),{...future,homeTeamId:'unknown'}],now).forecasts.length,0);
});
test('registro é imutável para o mesmo conjunto de dados e aceita nova versão de dados',()=>{
 const fixtures=[...history(),future],r=buildForecast(fixtures,now),db=new Store();
 try{
  db.savePredictions(r.forecasts,fixtures,now);
  const next=structuredClone(r.forecasts);next[0].createdAt='2026-11-06T13:00:00.000Z';next[0].probabilities=[.2,.3,.5];
  db.savePredictions(next,fixtures,new Date('2026-11-06T13:00:00Z'));
  assert.equal(db.predictions().length,1);assert.deepEqual(db.predictions()[0].probabilities,r.forecasts[0].probabilities);
  next[0].dataHash='new-data';db.savePredictions(next,fixtures,new Date('2026-11-06T13:00:00Z'));assert.equal(db.predictions().length,2);
  assert.throws(()=>db.savePredictions(next,fixtures,new Date('2026-11-08T13:00:00Z')),/inválido/);
 }finally{db.close();}
});
test('avaliação prospectiva separa previsões registradas de simulações e evita contagem duplicada',()=>{
 const fixtures=[...history(),future],p=buildForecast(fixtures,now).forecasts[0],finished={...future,status:'finished',homeGoals:2,awayGoals:0};
 assert.equal(evaluateRecorded([p],[future],now).count,0);
 const at=new Date('2026-11-08T12:00:00Z');
 assert.equal(evaluateRecorded([p,p],[finished],at).count,1);
 assert.equal(evaluateRecorded([{...p,createdAt:'2026-11-08T00:00:00Z'}],[finished],at).count,0);
 assert.equal(evaluateRecorded([p],[{...finished,kickoff:'2026-11-08T20:00:00Z'}],at).count,0);
});
test('cada liga treina somente com seu histórico mesmo com IDs de equipes iguais',()=>{
 const local=history(),foreign=history().map(r=>({...r,id:'eng:'+r.id,competitionCode:'eng.1',competition:'Premier League',homeGoals:0,awayGoals:5}));
 const brazil=buildForecast([...local,...foreign,future],now,'bra.1');
 assert.deepEqual(brazil.weights,buildForecast([...local,future],now).weights);
 const england=buildForecast([...local,...foreign,{...future,id:'eng:next',competitionCode:'eng.1'}],now,'eng.1');
 assert.equal(england.trainingMatches,240);assert.equal(england.forecasts.length,1);assert.equal(england.version,'eng-1-softmax-v1');
 assert.notDeepEqual(england.weights,brazil.weights);
 assert.throws(()=>buildForecast(local,now,'bra.2'),/fora do piloto/);
});
test('registro e avaliação permanecem separados por liga e versão',()=>{
 const rows=history().map(r=>({...r,competitionCode:'eng.1'})),match={...future,competitionCode:'eng.1'},fixtures=[...rows,match];
 const p=buildForecast(fixtures,now,'eng.1').forecasts[0],db=new Store();
 try{
  db.savePredictions([p],fixtures,now);assert.equal(db.predictions().length,1);
  assert.throws(()=>db.savePredictions([{...p,version:MODEL_VERSION}],fixtures,now),/inválido/);
  const finished={...match,status:'finished',homeGoals:1,awayGoals:0},after=new Date('2026-11-08T12:00:00Z');
  assert.equal(evaluateRecorded([p],[finished],after,'eng.1').count,1);
  assert.equal(evaluateRecorded([p],[finished],after,'bra.1').count,0);
 }finally{db.close();}
});
