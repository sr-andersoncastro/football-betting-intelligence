import test from 'node:test';
import assert from 'node:assert/strict';
import {scenarios} from '../lib.mjs';
const side=(p,g)=>({lastTen:{points:p,goalsFor:g,goalsAgainst:1},venueLastTen:{points:p,goalsFor:g,goalsAgainst:1}});
const market=(code,name,items)=>({code,name,status:'experimental',trainingMatches:200,markets:items.map(([label,probability])=>({label,probability,oppositeProbability:1-probability}))});
const forecast={home:'A',away:'B',probabilities:[0.5,0.3,0.2],evidence:{home:side(2,1.8),away:side(1,1)},extraMarkets:[
  market('goals','Gols',[['Mais de 1,5 gols',0.75],['Mais de 2,5 gols',0.45],['Ambas as equipes marcam',0.4]]),
  market('corners','Escanteios',[['Mais de 8,5 escanteios',0.6]]),
  market('fouls','Faltas',[['Mais de 24,5 faltas',0.2]])]};
test('retorna no máximo 5 cenários, ordenados por probabilidade, um por categoria',()=>{
  const r=scenarios(forecast);
  assert.equal(r.length,5);
  assert.ok(r.every((s,i)=>i===0||r[i-1].probability>=s.probability));
  assert.equal(new Set(r.map(s=>s.category)).size,5);
  assert.equal(r[0].label,'Menos de 24,5 faltas');assert.equal(r[0].text,'80%');
  assert.ok(r.every(s=>s.explanation.length>10));
});
test('mercados indisponíveis são ignorados e o resultado usa o mais provável',()=>{
  const r=scenarios({...forecast,extraMarkets:[{code:'corners',name:'Escanteios',status:'unavailable',reason:'x'}]});
  assert.equal(r.length,1);assert.equal(r[0].label,'Vitória do A');assert.equal(r[0].text,'50%');
});

test('ambas marcam é uma categoria própria sem duplicar totais aninhados',()=>{
  const r=scenarios(forecast);assert.ok(r.some(s=>s.category==='Ambas marcam'));assert.equal(r.filter(s=>s.category==='Gols').length,1);assert.equal(scenarios(forecast,99).length,5);
});
test('complemento de ambas marcam e limites incompletos não viram certezas',()=>{
  const r=scenarios({...forecast,extraMarkets:[market('goals','Gols',[['Ambas as equipes marcam',0.005]])]});
  assert.equal(r[0].label,'Pelo menos uma equipe não marca');assert.equal(r[0].text,'>99%');
  assert.equal(scenarios({...forecast,probabilities:[.9,.9,.9],extraMarkets:[]}).length,0);
  assert.equal(scenarios(forecast,0).length,0);
});
test('probabilidades inválidas são ignoradas e o cálculo não altera as entradas',()=>{
  const copy=structuredClone(forecast);scenarios(forecast);assert.deepEqual(forecast,copy);
  const invalid=structuredClone(forecast);for(const g of invalid.extraMarkets)for(const m of g.markets)m.probability=NaN;
  const r=scenarios(invalid);assert.equal(r.length,1);assert.equal(r[0].category,'Resultado');
});
