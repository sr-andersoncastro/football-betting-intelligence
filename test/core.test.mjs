import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {validateFixtures,evaluate} from '../lib.mjs';
import {server,store} from '../server.mjs';
const data=JSON.parse(await readFile(new URL('../data/demo.json',import.meta.url),'utf8'));
test('dados demonstrativos íntegros',()=>assert.equal(validateFixtures(data).length,6));
test('rejeita previsão posterior ao início',()=>{const rows=structuredClone(data);rows[0].prediction.createdAt=rows[0].kickoff;assert.throws(()=>validateFixtures(rows),/anteceder/);});
test('rejeita probabilidades que não somam um',()=>{const rows=structuredClone(data);rows[0].prediction.probabilities=[0.9,0.9,0.9];assert.throws(()=>validateFixtures(rows),/Probabilidades/);});
test('rejeita resultados negativos e IDs duplicados',()=>{const rows=structuredClone(data);rows[0].cards=-1;assert.throws(()=>validateFixtures(rows));assert.throws(()=>validateFixtures([data[0],data[0]]));});
test('previsão perfeita tem perdas zero',()=>{const rows=structuredClone(data.slice(0,1));rows[0].prediction.probabilities=[1,0,0];assert.deepEqual(evaluate(rows),{count:1,brier:0,logLoss:0});});
test('confere Brier e log loss contra resultado conhecido',()=>{const result=evaluate(data.slice(0,1));assert.ok(Math.abs(result.brier-0.3768)<1e-10);assert.ok(Math.abs(result.logLoss-Math.log(2))<1e-10);});
test('amostra vazia não apresenta desempenho inventado',()=>assert.deepEqual(evaluate([]),{count:0,brier:null,logLoss:null}));
test('servidor entrega painel, dados e erros seguros',async()=>{
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 try{
  const base='http://127.0.0.1:'+server.address().port;
  const health=await fetch(base+'/api/v1/health');assert.equal((await health.json()).mode,'real');
  const fixtures=await fetch(base+'/api/v1/fixtures');const payload=await fixtures.json();assert.equal(payload.source,'OpenLigaDB + ESPN');assert.ok(payload.fixtures.length>0);assert.ok(payload.fixtures.every(r=>['OpenLigaDB','ESPN'].includes(r.source) && !r.prediction));
  const html=await fetch(base+'/');assert.match(await html.text(),/Partidas reais/);assert.match(html.headers.get('content-security-policy'),/frame-ancestors 'none'/);
  for(const path of ['/app.js','/style.css','/lib.mjs','/analytics.mjs','/sw.js','/manifest.webmanifest','/icon-192.png','/icon-512.png'])assert.equal((await fetch(base+path)).status,200);
  const table=await fetch(base+'/api/v1/standings').then(r=>r.json());
  assert.equal(table.source,'OpenLigaDB + ESPN');assert.ok(table.groups.length>0);
  assert.ok(table.groups.every(g=>g.teams.every(t=>t.played===t.won+t.drawn+t.lost && t.points===3*t.won+t.drawn)));
  assert.equal((await fetch(base+'/api/v1/evaluation').then(r=>r.json())).count,0);
  const prediction=await fetch(base+'/api/v1/predictions').then(r=>r.json());
  assert.equal(prediction.competitionCode,'bra.1');assert.equal(prediction.status,'experimental');assert.ok(prediction.trainingMatches>160);assert.ok(prediction.walkForward.model.count>0);
  assert.ok(prediction.forecasts.every(p=>p.probabilities.length===3 && Date.parse(p.createdAt)<Date.parse(p.kickoff)));
  const audit=await fetch(base+'/api/v1/data-status').then(r=>r.json());assert.ok(audit.captures.length>=2);assert.ok(audit.coverage.some(c=>c.code==='bra.1' && c.status==='available'));
  const manifest=await fetch(base+'/manifest.webmanifest').then(r=>r.json());assert.equal(manifest.display,'standalone');assert.equal(manifest.icons.length,2);
  assert.equal(audit.coverage.length,11);assert.ok(payload.fixtures.some(r=>r.competitionCode==='bra.2'));
  assert.equal((await fetch(base+'/.env')).status,404);
  assert.equal((await fetch(base+'/api/v1/fixtures',{method:'POST'})).status,405);
 }finally{await new Promise(resolve=>server.close(resolve));store.close();}
});

