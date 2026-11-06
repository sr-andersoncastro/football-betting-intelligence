import test from 'node:test';
import assert from 'node:assert/strict';
import {scenarios} from '../lib.mjs';
const side=(p,g)=>({lastTen:{points:p,goalsFor:g,goalsAgainst:1},venueLastTen:{points:p,goalsFor:g,goalsAgainst:1}});
const market=(code,name,items)=>({code,name,status:'experimental',trainingMatches:200,markets:items.map(([label,probability])=>({label,probability,oppositeProbability:1-probability}))});
const forecast={home:'A',away:'B',probabilities:[0.5,0.3,0.2],evidence:{home:side(2,1.8),away:side(1,1)},extraMarkets:[
  market('goals','Gols',[['Mais de 1,5 gols',0.75],['Mais de 2,5 gols',0.45],['Ambas as equipes marcam',0.4]]),
  market('corners','Escanteios',[['Mais de 8,5 escanteios',0.6]]),
  market('fouls','Faltas',[['Mais de 24,5 faltas',0.2]])]};
test('retorna no máximo 3 cenários, ordenados por probabilidade, um por categoria',()=>{
  const r=scenarios(forecast);
  assert.equal(r.length,3);
  assert.ok(r.every((s,i)=>i===0||r[i-1].probability>=s.probability));
  assert.equal(new Set(r.map(s=>s.category)).size,3);
  assert.equal(r[0].label,'Menos de 24,5 faltas');assert.equal(r[0].text,'80%');
  assert.ok(r.every(s=>s.explanation.length>10));
});
test('mercados indisponíveis são ignorados e o resultado usa o mais provável',()=>{
  const r=scenarios({...forecast,extraMarkets:[{code:'corners',name:'Escanteios',status:'unavailable',reason:'x'}]});
  assert.equal(r.length,1);assert.equal(r[0].label,'Vitória do A');assert.equal(r[0].text,'50%');
});
