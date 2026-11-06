import test from 'node:test';
import assert from 'node:assert/strict';
import {buildMarkets,evaluateRecordedMarkets,validateExtraMarkets} from '../markets.mjs';
const now=new Date('2026-11-06T12:00:00Z');
const rows=()=>Array.from({length:220},(_,i)=>({id:'m:'+i,competitionCode:'bra.1',homeTeamId:'A',awayTeamId:'B',status:'finished',kickoff:new Date(Date.UTC(2026,0,1+i,20)).toISOString(),homeGoals:i%4,awayGoals:i%3}));
const next={id:'next',competitionCode:'bra.1',homeTeamId:'A',awayTeamId:'B',status:'scheduled',kickoff:'2026-11-07T20:00:00.000Z'};
test('probabilidades de gols respeitam complementos e ordem dos limites',()=>{
 const r=buildMarkets(rows(),now,'bra.1',[next]),g=r.predictions.get('next').find(g=>g.code==='goals');
 assert.equal(g.status,'experimental');assert.equal(g.markets.length,4);validateExtraMarkets([g]);
 const totals=g.markets.filter(m=>!m.both);assert.ok(totals[0].probability>=totals[1].probability&&totals[1].probability>=totals[2].probability);
 assert.ok(g.markets.every(m=>m.probability>0&&m.probability<1&&Math.abs(m.probability+m.oppositeProbability-1)<1e-12));
 assert.ok(r.evaluation[0].markets.every(m=>m.model.count>0&&Number.isFinite(m.model.brier)));
});
test('outros campeonatos e resultados do próprio dia ou futuros não entram no cálculo',()=>{
 const base=rows(),expected=buildMarkets(base,now,'bra.1',[next]);
 const extra=[...rows().map(r=>({...r,competitionCode:'eng.1',homeGoals:9})),{...next,id:'today',status:'finished',kickoff:'2026-11-06T01:00:00Z',homeGoals:99,awayGoals:99},{...next,id:'tomorrow',status:'finished',homeGoals:99,awayGoals:99}];
 assert.deepEqual(buildMarkets([...base,...extra],now,'bra.1',[next]).predictions.get('next'),expected.predictions.get('next'));
});
test('partidas sem estatística não são preenchidas com zero e equipes novas ficam sem previsão',()=>{
 const missing=rows().map(r=>({...r,homeGoals:null,awayGoals:null}));
 assert.equal(buildMarkets(missing,now,'bra.1',[next]).predictions.get('next')[0].status,'unavailable');
 assert.equal(buildMarkets(rows(),now,'bra.1',[{...next,homeTeamId:'new'}]).predictions.get('next')[0].status,'unavailable');
});
test('avaliação prospectiva usa registros anteriores ao início e conta uma vez por partida',()=>{
 const g=buildMarkets(rows(),now,'bra.1',[next]).predictions.get('next');
 const p={fixtureId:next.id,kickoff:next.kickoff,createdAt:now.toISOString(),extraMarkets:g},finished={...next,status:'finished',homeGoals:2,awayGoals:1};
 const after=new Date('2026-11-08T12:00:00Z');
 const score=evaluateRecordedMarkets([p,p],[finished],after,'bra.1')[0].markets;
 assert.ok(score.every(m=>m.count===1));assert.equal(score.find(m=>m.id==='goals-over-2.5').brier,(1-g[0].markets.find(m=>m.id==='goals-over-2.5').probability)**2);
 assert.ok(evaluateRecordedMarkets([{...p,createdAt:'2026-11-08T01:00:00Z'}],[finished],after,'bra.1')[0].markets.every(m=>m.count===0));
});
test('recusa probabilidades adicionais inválidas',()=>{
 const g=buildMarkets(rows(),now,'bra.1',[next]).predictions.get('next');g[0].markets[0].probability=2;
 assert.throws(()=>validateExtraMarkets(g),/inválida/);
});
