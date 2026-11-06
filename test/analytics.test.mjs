import test from 'node:test';
import assert from 'node:assert/strict';
import {standings} from '../analytics.mjs';
const match=(home,away,homeGoals,awayGoals,extra={})=>({competition:'Liga',season:2026,home,away,homeGoals,awayGoals,status:'finished',...extra});
test('classificação contabiliza vitórias, empates, derrotas, gols e aproveitamento',()=>{
  const [group]=standings([match('A','B',2,0),match('B','C',1,1),match('C','A',3,1)]);
  assert.equal(group.matches,3);
  assert.deepEqual(group.teams.map(t=>t.name),['C','A','B']);
  assert.deepEqual(group.teams[0],{id:'C',name:'C',played:2,won:1,drawn:1,lost:0,goalsFor:4,goalsAgainst:2,goalDifference:2,points:4,pointsPercentage:100*4/6});
  assert.equal(group.teams.reduce((n,t)=>n+t.goalsFor,0),group.teams.reduce((n,t)=>n+t.goalsAgainst,0));
});
test('classificação separa temporadas e competições e ignora partidas abertas',()=>{
  const groups=standings([match('A','B',2,0),match('A','B',0,0,{season:2025}),match('A','B',0,1,{competition:'Outra'}),match('X','Y',null,null,{status:'scheduled'})]);
  assert.equal(groups.length,3);assert.equal(groups[0].season,2026);
  assert.ok(groups.every(g=>g.matches===1 && g.teams.length===2));
  assert.deepEqual(standings([]),[]);
});
test('desempate usa saldo, gols marcados e nome; identificador preserva renomeações',()=>{
  const [group]=standings([match('A','B',1,0),match('C','D',2,0)]);
  assert.deepEqual(group.teams.map(t=>t.name),['C','A','B','D']);
  const [renamed]=standings([match('A','B',1,0,{homeTeamId:1,awayTeamId:2}),match('A novo','B',0,0,{homeTeamId:1,awayTeamId:2})]);
  assert.equal(renamed.teams.length,2);assert.equal(renamed.teams[0].points,4);
});
