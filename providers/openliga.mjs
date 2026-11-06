import { createHash } from 'node:crypto';
import { validateFixtures } from '../lib.mjs';
export const coverage = [
  {code:'bl1', name:'Bundesliga', status:'available'},
  {code:'BR-A', name:'Brasileirão Série A', status:'pending'},
  {code:'BR-B', name:'Brasileirão Série B', status:'pending'},
  {code:'PL', name:'Premier League', status:'pending'},
  {code:'ES', name:'La Liga', status:'pending'},
  {code:'CL', name:'Champions League', status:'pending'},
];
export function normalize(raw, season, collectedAt) {
  if(!Array.isArray(raw) || !raw.length) throw new Error('Fonte retornou temporada vazia ou inválida');
  const fixtures=raw.map(match=>{
    if(match.leagueShortcut !== 'bl1' || Number(match.leagueSeason) !== season || !Number.isInteger(match.matchID)) throw new Error('Identidade da partida inválida');
    if(typeof match.matchIsFinished !== 'boolean' || !/Z$/.test(match.matchDateTimeUTC??'')) throw new Error('Estado ou horário UTC inválido');
    const result=match.matchResults?.find(r=>r.resultTypeID===2);
    if(match.matchIsFinished && !result) throw new Error('Partida encerrada sem placar final');
    return {
      id:`openliga:${match.matchID}`,providerId:match.matchID,competition:'Bundesliga',competitionCode:'bl1',season,
      home:match.team1?.teamName,away:match.team2?.teamName,
      homeTeamId:match.team1?.teamId,awayTeamId:match.team2?.teamId,
      kickoff:match.matchDateTimeUTC,round:match.group?.groupOrderID??null,
      status:match.matchIsFinished?'finished':'scheduled',
      homeGoals:match.matchIsFinished?result.pointsTeam1:null,awayGoals:match.matchIsFinished?result.pointsTeam2:null,
      corners:null,cards:null,source:'OpenLigaDB',collectedAt,
      sourceUpdatedAt:match.lastUpdateDateTime??null
    };
  });
  return validateFixtures(fixtures);
}
export async function collect(season, fetcher=fetch, now=new Date()) {
  const url=`https://api.openligadb.de/getmatchdata/bl1/${season}`;
  const response=await fetcher(url,{signal:AbortSignal.timeout(20000),headers:{Accept:'application/json'}});
  if(!response.ok) throw new Error(`OpenLigaDB HTTP ${response.status}`);
  const raw=await response.text();
  if(raw.length>10_000_000) throw new Error('Resposta da fonte excedeu o limite');
  const collectedAt=now.toISOString();
  return {source:'OpenLigaDB',url,season,collectedAt,sha256:createHash('sha256').update(raw).digest('hex'),fixtures:normalize(JSON.parse(raw),season,collectedAt),raw};
}

