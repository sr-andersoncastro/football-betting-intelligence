import {createHash} from 'node:crypto';
import {validateFixtures} from '../lib.mjs';

export const leagues = [
  {code:'bra.1',name:'Brasileirão Série A',calendar:true},
  {code:'bra.2',name:'Brasileirão Série B',calendar:true},
  {code:'eng.1',name:'Premier League'},
  {code:'esp.1',name:'La Liga'},
  {code:'ita.1',name:'Serie A italiana'},
  {code:'fra.1',name:'Ligue 1'},
  {code:'por.1',name:'Liga Portugal'},
  {code:'ned.1',name:'Eredivisie'},
  {code:'uefa.champions',name:'Champions League',cup:true},
  {code:'conmebol.libertadores',name:'Copa Libertadores',calendar:true,cup:true}
];
function statistic(team,name,finished){
  if(!finished||!Array.isArray(team.statistics))return null;
  const values=team.statistics.filter(s=>s.name===name);
  if(values.length!==1||!/^\d+$/.test(String(values[0].displayValue??'')))return null;
  const n=Number(values[0].displayValue);return Number.isSafeInteger(n)?n:null;
}
const finals=new Set(['STATUS_FULL_TIME','STATUS_FINAL_AET','STATUS_FINAL_PEN']);
export function normalize(raw, code, calendarYear, collectedAt) {
  const league=leagues.find(l=>l.code===code);
  if(!league || !Number.isInteger(calendarYear))throw new Error('Competição ou ano inválido');
  if(!raw || !Array.isArray(raw.events) || !raw.events.length)throw new Error('Fonte retornou período vazio ou inválido');
  if(raw.leagues?.[0]?.slug!==code)throw new Error('Competição da resposta divergente');
  // ESPN defaults to 100 records. Reject a response at the requested cap instead of claiming completeness.
  if(raw.events.length>=1000)throw new Error('Resposta possivelmente truncada');
  return validateFixtures(raw.events.map(event=>{
    const match=event.competitions?.[0];
    const competitors=match?.competitors;
    const home=competitors?.find(t=>t.homeAway==='home');
    const away=competitors?.find(t=>t.homeAway==='away');
    const state=match?.status?.type ?? event.status?.type;
    if(!/^\d+$/.test(event.id??'') || !home?.team?.id || !away?.team?.id || competitors.length!==2 || !Number.isInteger(event.season?.year))throw new Error('Identidade da partida inválida');
    if(!/Z$/.test(event.date??'') || !Number.isFinite(Date.parse(event.date)) || typeof state?.completed!=='boolean')throw new Error('Estado ou horário inválido');
    let status;
    if(state.completed && finals.has(state.name))status='finished';
    else if(/POSTPONED|DELAYED/.test(state.name))status='postponed';
    else if(/CANCEL|ABANDON/.test(state.name))status='cancelled';
    else if(/SUSPEND/.test(state.name))status='suspended';
    else if(state.state==='in')status='live';
    else if(state.state==='pre')status='scheduled';
    else throw new Error('Estado da fonte não reconhecido: '+state.name);
    const score=team=>{
      if(status!=='finished')return null;
      if(!/^\d+$/.test(String(team.score??'')))throw new Error('Partida encerrada sem placar válido');
      return Number(team.score);
    };
    const season=event.season.year;
    const homeCorners=statistic(home,'wonCorners',status==='finished'),awayCorners=statistic(away,'wonCorners',status==='finished');
    const homeFouls=statistic(home,'foulsCommitted',status==='finished'),awayFouls=statistic(away,'foulsCommitted',status==='finished');
    return {
      id:`espn:${code}:${event.id}`,providerId:event.id,competition:league.name,competitionCode:code,
      season,seasonLabel:league.calendar?String(season):`${season}/${season+1}`,calendarYear,
      home:home.team.displayName,away:away.team.displayName,
      homeTeamId:`espn:${home.team.id}`,awayTeamId:`espn:${away.team.id}`,
      kickoff:new Date(event.date).toISOString(),kickoffConfirmed:match.timeValid!==false,
      status,homeGoals:score(home),awayGoals:score(away),
      homeFouls,awayFouls,fouls:homeFouls===null||awayFouls===null?null:homeFouls+awayFouls,
      homeCorners,awayCorners,corners:homeCorners===null||awayCorners===null?null:homeCorners+awayCorners,cards:null,source:'ESPN',collectedAt,tableEligible:!league.cup,
      resultType:state.name,venue:match.venue?.fullName??null
    };
  }));
}
export async function collect(code, calendarYear, fetcher=fetch, now=new Date()) {
  if(!leagues.some(l=>l.code===code) || !Number.isInteger(calendarYear))throw new Error('Competição ou ano inválido');
  const url=`https://site.api.espn.com/apis/site/v2/sports/soccer/${code}/scoreboard?dates=${calendarYear}&limit=1000`;
  const response=await fetcher(url,{signal:AbortSignal.timeout(30000),headers:{Accept:'application/json'}});
  if(!response.ok)throw new Error(`ESPN ${code} HTTP ${response.status}`);
  const raw=await response.text();
  if(Buffer.byteLength(raw)>20_000_000)throw new Error('Resposta da fonte excedeu o limite');
  const collectedAt=now.toISOString();
  return {source:'ESPN',competitionCode:code,scope:`espn:${code}:${calendarYear}`,url,season:calendarYear,collectedAt,
    sha256:createHash('sha256').update(raw).digest('hex'),raw,
    fixtures:normalize(JSON.parse(raw),code,calendarYear,collectedAt)};
}
