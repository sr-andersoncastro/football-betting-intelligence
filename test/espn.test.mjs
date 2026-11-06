import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {normalize,collect} from '../providers/espn.mjs';
import {Store} from '../store.mjs';
import {standings} from '../analytics.mjs';
const event={id:'123',date:'2026-06-12T20:00Z',season:{year:2026},competitions:[{timeValid:true,status:{type:{name:'STATUS_FULL_TIME',state:'post',completed:true}},competitors:[{homeAway:'away',team:{id:'2',displayName:'Visitante'},score:'1'},{homeAway:'home',team:{id:'1',displayName:'Mandante'},score:'2'}]}]};
const response=(code='bra.1',e=event)=>({leagues:[{slug:code}],events:[e]});
function capture(code='bra.1',at='2026-11-06T10:00:00Z',e=event){const raw=JSON.stringify(response(code,e));return {source:'ESPN',competitionCode:code,season:2026,collectedAt:at,url:'https://site.api.espn.com/',raw,sha256:createHash('sha256').update(raw).digest('hex')};}
test('ESPN identifica mandante por campo, preserva temporada e placar',()=>{
 const [r]=normalize(response(),'bra.1',2026,'2026-11-06T10:00:00Z');
 assert.equal(r.home,'Mandante');assert.equal(r.homeGoals,2);assert.equal(r.awayGoals,1);assert.equal(r.seasonLabel,'2026');assert.equal(r.source,'ESPN');assert.equal(r.corners,null);
 const european=structuredClone(event);european.season.year=2025;
 assert.equal(normalize(response('eng.1',european),'eng.1',2026,'2026-11-06T10:00:00Z')[0].seasonLabel,'2025/2026');
});
test('partidas agendadas, ao vivo e adiadas não ganham placar final',()=>{
 for(const [name,state,expected] of [['STATUS_SCHEDULED','pre','scheduled'],['STATUS_IN_PROGRESS','in','live'],['STATUS_POSTPONED','pre','postponed'],['STATUS_CANCELED','post','cancelled']]){
  const e=structuredClone(event);e.competitions[0].status.type={name,state,completed:false};
  const [r]=normalize(response('bra.1',e),'bra.1',2026,'2026-11-06T10:00:00Z');assert.equal(r.status,expected);assert.equal(r.homeGoals,null);
 }
});
test('copas e placares após prorrogação não viram classificação de liga',()=>{
 const e=structuredClone(event);e.competitions[0].status.type.name='STATUS_FINAL_AET';
 const rows=normalize(response('uefa.champions',e),'uefa.champions',2026,'2026-11-06T10:00:00Z');
 assert.equal(rows[0].status,'finished');assert.deepEqual(standings(rows),[]);
});
test('rejeita resposta truncada, competição divergente e resultado final inválido',()=>{
 assert.throws(()=>normalize({...response(),events:Array(1000).fill(event)},'bra.1',2026,''),/truncada/);
 assert.throws(()=>normalize(response('bra.2'),'bra.1',2026,''),/divergente/);
 const e=structuredClone(event);e.competitions[0].competitors[0].score='';
 assert.throws(()=>normalize(response('bra.1',e),'bra.1',2026,''),/placar/);
});
test('coleta usa ano civil e limite explícito, mantém evidência original e propaga falhas',async()=>{
 const raw=JSON.stringify(response());let called;
 const c=await collect('bra.1',2026,async url=>{called=url;return {ok:true,text:async()=>raw};},new Date('2026-11-06T10:00:00Z'));
 assert.match(called,/dates=2026&limit=1000/);assert.equal(c.raw,raw);assert.equal(c.fixtures.length,1);
 await assert.rejects(collect('bra.1',2026,async()=>({ok:false,status:429})),/429/);
});
test('capturas de ligas diferentes no mesmo ano permanecem isoladas',()=>{
 const db=new Store();try{
  db.ingest(capture());db.ingest(capture('bra.2'));
  const corrected=structuredClone(event);corrected.competitions[0].competitors[1].score='4';
  db.ingest(capture('bra.1','2026-11-07T10:00:00Z',corrected));db.ingest(capture());
  assert.equal(db.fixtures().length,2);
  assert.equal(db.fixtures().find(r=>r.competitionCode==='bra.1').homeGoals,4);
  assert.equal(db.fixtures().find(r=>r.competitionCode==='bra.2').homeGoals,2);
  assert.equal(db.coverage().length,2);
 }finally{db.close();}
});
test('migração adiciona escopo em banco da versão anterior sem perder dados',async()=>{
 const directory=await mkdtemp(join(tmpdir(),'football-migrate-'));
 try{
  const path=join(directory,'old.sqlite'),legacy=new DatabaseSync(path);
  legacy.exec(`CREATE TABLE captures(id INTEGER PRIMARY KEY,source TEXT NOT NULL,url TEXT NOT NULL,season INTEGER NOT NULL,collected_at TEXT NOT NULL,sha256 TEXT NOT NULL,raw TEXT NOT NULL,UNIQUE(season,collected_at,sha256));
  CREATE TABLE fixtures(id TEXT PRIMARY KEY,season INTEGER NOT NULL,kickoff TEXT NOT NULL,capture_id INTEGER NOT NULL REFERENCES captures(id),json TEXT NOT NULL);
  INSERT INTO captures VALUES(1,'OpenLigaDB','https://api.openligadb.de/',2026,'2026-01-01T00:00:00Z','hash','[]');
  INSERT INTO fixtures VALUES('old',2026,'2026-01-01T00:00:00Z',1,'{"id":"old"}');`);legacy.close();
  const db=new Store(path);try{assert.equal(db.fixtures()[0].id,'old');assert.equal(db.coverage()[0].scope,'openliga:bl1:2026');db.ingest(capture());assert.equal(db.fixtures().length,2);}finally{db.close();}
 }finally{await rm(directory,{recursive:true,force:true});}
});
test('escanteios mantêm zero real e não transformam ausência ou parcial em zero',()=>{
 const e=structuredClone(event);e.competitions[0].competitors[0].statistics=[{name:'wonCorners',displayValue:'0'}];e.competitions[0].competitors[1].statistics=[{name:'wonCorners',displayValue:'5'}];
 const read=()=>normalize(response('bra.1',e),'bra.1',2026,'2026-11-06T10:00:00Z')[0];
 assert.equal(read().homeCorners,5);assert.equal(read().awayCorners,0);assert.equal(read().corners,5);
 e.competitions[0].competitors[0].statistics=[];assert.equal(read().awayCorners,null);assert.equal(read().corners,null);
 e.competitions[0].status.type={name:'STATUS_IN_PROGRESS',state:'in',completed:false};assert.equal(read().homeCorners,null);
});
test('nova versão reprocessa evidência ESPN recente sem substituí-la pela semente antiga',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'football-renormalize-'));const path=join(dir,'db.sqlite');
 try{const db=new Store(path);const e=structuredClone(event);for(const t of e.competitions[0].competitors)t.statistics=[{name:'wonCorners',displayValue:'4'}];db.ingest(capture('bra.1','2026-11-07T10:00:00Z',e));
  const stale=JSON.parse(db.db.prepare('SELECT json FROM fixtures').get().json);delete stale.homeCorners;delete stale.awayCorners;stale.corners=null;db.db.prepare('UPDATE fixtures SET json=?').run(JSON.stringify(stale));db.db.exec('PRAGMA user_version=0');db.close();
  const migrated=new Store(path);try{assert.equal(migrated.fixtures()[0].corners,8);assert.equal(migrated.captures().length,1);}finally{migrated.close();}
 }finally{await rm(dir,{recursive:true,force:true});}
});
test('faltas só usam valores explícitos e válidos do jogo encerrado',()=>{
 const e=structuredClone(event);for(const [i,t] of e.competitions[0].competitors.entries())t.statistics=[{name:'foulsCommitted',displayValue:String(12+i)}];
 const read=()=>normalize(response('bra.1',e),'bra.1',2026,'2026-11-06T10:00:00Z')[0];
 assert.equal(read().homeFouls,13);assert.equal(read().awayFouls,12);assert.equal(read().fouls,25);
 e.competitions[0].competitors[0].statistics[0].displayValue='';assert.equal(read().awayFouls,null);assert.equal(read().fouls,null);
 e.competitions[0].competitors[0].statistics[0].displayValue='0';assert.equal(read().awayFouls,0);
 e.competitions[0].competitors[0].statistics.push({name:'foulsCommitted',displayValue:'4'});assert.equal(read().awayFouls,null);
});
