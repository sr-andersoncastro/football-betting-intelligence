import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {normalize,collect} from '../providers/openliga.mjs';
import {Store} from '../store.mjs';
const match={matchID:1,leagueShortcut:'bl1',leagueSeason:2026,matchDateTimeUTC:'2026-10-01T18:00:00Z',team1:{teamId:1,teamName:'A'},team2:{teamId:2,teamName:'B'},matchIsFinished:true,matchResults:[{resultTypeID:2,pointsTeam1:3,pointsTeam2:1},{resultTypeID:1,pointsTeam1:0,pointsTeam2:1}]};
function capture(at='2026-11-06T12:00:00Z',goal=3){const m=structuredClone(match);m.matchResults[0].pointsTeam1=goal;const raw=JSON.stringify([m]);return {source:'OpenLigaDB',url:'https://api.openligadb.de/getmatchdata/bl1/2026',season:2026,collectedAt:at,raw,sha256:createHash('sha256').update(raw).digest('hex')};}
test('seleciona placar final por tipo e não pela ordem do array',()=>{const [r]=normalize([match],2026,'2026-11-06T12:00:00Z');assert.equal(r.homeGoals,3);assert.equal(r.corners,null);assert.equal(r.cards,null);assert.equal(r.kickoff,match.matchDateTimeUTC);});
test('recusa temporada vazia, horário sem fuso e final sem placar',()=>{assert.throws(()=>normalize([],2026,'2026-11-06T12:00:00Z'));assert.throws(()=>normalize([{...match,matchDateTimeUTC:'2026-10-01T18:00:00'}],2026,''));assert.throws(()=>normalize([{...match,matchResults:[]}],2026,''));});
test('não transforma placar parcial em resultado final',()=>{const [r]=normalize([{...match,matchIsFinished:false}],2026,'2026-11-06T12:00:00Z');assert.equal(r.homeGoals,null);assert.equal(r.status,'scheduled');});
test('falha HTTP não vira lista vazia bem-sucedida',async()=>{await assert.rejects(collect(2026,async()=>({ok:false,status:429})),/429/);});
test('auditoria mantém correções e não permite semente antiga sobrescrever estado novo',()=>{const db=new Store();try{db.ingest(capture());db.ingest(capture('2026-11-07T12:00:00Z',4));db.ingest(capture());assert.equal(db.captures().length,2);assert.equal(db.fixtures()[0].homeGoals,4);assert.throws(()=>db.ingest({...capture(),sha256:'inválido'}),/Integridade/);assert.equal(db.fixtures()[0].homeGoals,4);}finally{db.close();}});
test('SQLite preserva histórico e partidas entre aberturas no mesmo disco',async()=>{const directory=await mkdtemp(join(tmpdir(),'football-test-'));try{const file=join(directory,'data.sqlite');const a=new Store(file);a.ingest(capture());a.log('success','coleta');a.close();const b=new Store(file);try{assert.equal(b.fixtures().length,1);assert.equal(b.captures().length,1);assert.equal(b.logs()[0].message,'coleta');}finally{b.close();}}finally{await rm(directory,{recursive:true,force:true});}});
