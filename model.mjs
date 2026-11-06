import {createHash} from 'node:crypto';
import {buildMarkets,MARKET_GROUPS} from './markets.mjs';

export const MODEL_VERSION='br-a-softmax-v1';
export const PILOT_LEAGUES=[
  {code:'bra.1',name:'Brasileirão Série A',version:MODEL_VERSION},
  {code:'eng.1',name:'Premier League',version:'eng-1-softmax-v1'},
  {code:'esp.1',name:'La Liga',version:'esp-1-softmax-v1'},
  {code:'bl1',name:'Bundesliga',version:'bl1-softmax-v1'}
];
function leagueFor(code){const league=PILOT_LEAGUES.find(l=>l.code===code);if(!league)throw new Error('Competição fora do piloto');return league;}
const MIN_TRAINING=160, MIN_TEAM_MATCHES=8;
export const FEATURE_NAMES=['intercepto / mando','diferença de pontos recentes','diferença de gols marcados','diferença de gols sofridos','desempenho casa / fora','diferença Elo'];
const key=(r,side)=>String(r[side+'TeamId']??r[side]);
const outcome=r=>r.homeGoals>r.awayGoals?0:r.homeGoals===r.awayGoals?1:2;
const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
function probabilities(weights,x){const z=weights.map(w=>dot(w,x)),max=Math.max(...z),exps=z.map(v=>Math.exp(v-max)),sum=exps.reduce((a,b)=>a+b,0);return exps.map(v=>v/sum);}
function stats(matches){
  let weight=4,points=4*1.3,gf=4*1.2,ga=4*1.2;
  matches.slice(-10).reverse().forEach((m,i)=>{const w=.85**i;weight+=w;points+=w*m.points;gf+=w*m.gf;ga+=w*m.ga;});
  return {points:points/weight,goalsFor:gf/weight,goalsAgainst:ga/weight};
}
function createState(){return {teams:new Map(),weights:Array.from({length:3},()=>Array(6).fill(0)),counts:[1,1,1],trained:0};}
function team(state,id){if(!state.teams.has(id))state.teams.set(id,{elo:1500,matches:[],home:[],away:[]});return state.teams.get(id);}
function features(state,row){
  const h=team(state,key(row,'home')),a=team(state,key(row,'away')),hs=stats(h.matches),as=stats(a.matches),home=stats(h.home),away=stats(a.away);
  return {x:[1,(hs.points-as.points)/3,(hs.goalsFor-as.goalsFor)/3,(hs.goalsAgainst-as.goalsAgainst)/3,(home.points-away.points)/3,(h.elo-a.elo)/400],
    evidence:{home:{matches:h.matches.length,lastTen:hs,venueMatches:h.home.length,venueLastTen:home,elo:h.elo},away:{matches:a.matches.length,lastTen:as,venueMatches:a.away.length,venueLastTen:away,elo:a.elo}},
    sufficient:state.trained>=MIN_TRAINING&&h.matches.length>=MIN_TEAM_MATCHES&&a.matches.length>=MIN_TEAM_MATCHES};
}
function observe(state,row,input){
  const y=outcome(row),p=probabilities(state.weights,input);
  for(let k=0;k<3;k++)for(let j=0;j<input.length;j++)state.weights[k][j]-=.035*((p[k]-(k===y?1:0))*input[j]+(j===0?0:.003*state.weights[k][j]));
  state.counts[y]++;state.trained++;
  const h=team(state,key(row,'home')),a=team(state,key(row,'away'));
  const expected=1/(1+10**((a.elo-h.elo-60)/400)),change=20*((y===0?1:y===1?.5:0)-expected);
  h.elo+=change;a.elo-=change;
  const home={points:y===0?3:y===1?1:0,gf:row.homeGoals,ga:row.awayGoals};
  const away={points:y===2?3:y===1?1:0,gf:row.awayGoals,ga:row.homeGoals};
  h.matches.push(home);h.home.push(home);a.matches.push(away);a.away.push(away);
}
function metrics(records,field){
  if(!records.length)return {count:0,brier:null,logLoss:null,accuracy:null,calibration:[]};
  let brier=0,logLoss=0,hits=0;
  const bins=Array.from({length:5},(_,i)=>({from:i/5,to:(i+1)/5,count:0,predictedSum:0,hits:0}));
  for(const r of records){const p=r[field],winner=p.indexOf(Math.max(...p));brier+=p.reduce((s,v,i)=>s+(v-(i===r.outcome?1:0))**2,0);logLoss-=Math.log(Math.max(1e-15,p[r.outcome]));hits+=winner===r.outcome?1:0;const bin=bins[Math.min(4,Math.floor(p[winner]*5))];bin.count++;bin.predictedSum+=p[winner];bin.hits+=winner===r.outcome?1:0;}
  return {count:records.length,brier:brier/records.length,logLoss:logLoss/records.length,accuracy:hits/records.length,calibration:bins.map(b=>({from:b.from,to:b.to,count:b.count,meanProbability:b.count?b.predictedSum/b.count:null,observedFrequency:b.count?b.hits/b.count:null}))};
}
export function evaluateRecorded(predictions,fixtures,now=new Date(),competitionCode='bra.1'){
  const league=leagueFor(competitionCode);
  const rows=new Map(fixtures.filter(r=>r.competitionCode===competitionCode&&r.status==='finished'&&Date.parse(r.kickoff)<now.getTime()).map(r=>[r.id,r]));
  const latest=new Map();
  for(const p of predictions){const r=rows.get(p.fixtureId);if(!r||p.kickoff!==r.kickoff||Date.parse(p.createdAt)>=Date.parse(r.kickoff)||p.version!==league.version)continue;const previous=latest.get(r.id);if(!previous||Date.parse(p.createdAt)>Date.parse(previous.createdAt))latest.set(r.id,p);}
  return metrics([...latest.values()].map(p=>({probabilities:p.probabilities,outcome:outcome(rows.get(p.fixtureId))})),'probabilities');
}
export function buildForecast(fixtures,now=new Date(),competitionCode='bra.1'){
  const league=leagueFor(competitionCode);
  const createdAt=now.toISOString(),cutoff=createdAt.slice(0,10)+'T00:00:00.000Z';
  // Use completed prior UTC days only. Same-day outcomes never enter features or training.
  const history=fixtures.filter(r=>r.competitionCode===competitionCode&&r.status==='finished'&&Date.parse(r.kickoff)+6*3600000<Date.parse(cutoff)).sort((a,b)=>Date.parse(a.kickoff)-Date.parse(b.kickoff)||a.id.localeCompare(b.id));
  const state=createState(),records=[];let pending=[];
  for(let i=0;i<history.length;){
    const day=history[i].kickoff.slice(0,10),batch=[],dayStart=Date.parse(day+'T00:00:00Z');
    const ready=pending.filter(({r})=>Date.parse(r.kickoff)+6*3600000<dayStart);
    pending=pending.filter(({r})=>Date.parse(r.kickoff)+6*3600000>=dayStart);
    for(const {r,f} of ready)observe(state,r,f.x);
    while(i<history.length&&history[i].kickoff.slice(0,10)===day){const r=history[i++],f=features(state,r);batch.push({r,f});if(f.sufficient)records.push({fixtureId:r.id,kickoff:r.kickoff,probabilities:probabilities(state.weights,f.x),baseline:state.counts.map(c=>c/state.counts.reduce((a,b)=>a+b,0)),outcome:outcome(r)});}
    pending.push(...batch);
  }
  for(const {r,f} of pending)observe(state,r,f.x);
  const model=metrics(records,'probabilities'),baseline=metrics(records,'baseline');
  const dataHash=createHash('sha256').update(MARKET_GROUPS.map(g=>g.version).join('|')).update(JSON.stringify(history.map(r=>[r.id,r.kickoff,r.homeTeamId??r.home,r.awayTeamId??r.away,r.homeGoals,r.awayGoals,r.homeCorners??null,r.awayCorners??null,r.homeFouls??null,r.awayFouls??null,r.collectedAt]))).digest('hex');
  const latestDataAt=fixtures.filter(r=>r.competitionCode===competitionCode).map(r=>r.collectedAt).filter(v=>Number.isFinite(Date.parse(v))).sort((a,b)=>Date.parse(b)-Date.parse(a))[0]??null;
  const dataStale=!latestDataAt||now.getTime()-Date.parse(latestDataAt)>24*3600000||Date.parse(latestDataAt)>now.getTime();
  const forecasts=[],unavailable=[];
  for(const row of fixtures.filter(r=>r.competitionCode===competitionCode&&r.status==='scheduled'&&r.kickoffConfirmed!==false&&Date.parse(r.kickoff)>now.getTime()&&Date.parse(r.kickoff)<=now.getTime()+7*86400000)){
    const f=features(state,row);
    if(dataStale){unavailable.push({fixtureId:row.id,reason:'Coleta da competição ausente ou com mais de 24 horas.'});continue;}
    if(!f.sufficient){unavailable.push({fixtureId:row.id,reason:'Histórico insuficiente: exige 160 jogos de treino e 8 jogos anteriores por equipe.'});continue;}
    forecasts.push({fixtureId:row.id,home:row.home,away:row.away,kickoff:row.kickoff,version:league.version,competitionCode,createdAt,trainingCutoff:cutoff,trainingMatches:history.length,dataHash,probabilities:probabilities(state.weights,f.x),evidence:f.evidence,status:'experimental'});
  }
  const extra=buildMarkets(fixtures,now,competitionCode,forecasts.map(p=>fixtures.find(r=>r.id===p.fixtureId)));
  for(const p of forecasts)p.extraMarkets=extra.predictions.get(p.fixtureId)??[];
  return {version:league.version,competitionCode,competition:league.name,status:'experimental',createdAt,trainingCutoff:cutoff,latestDataAt,dataStale,trainingMatches:history.length,dataHash,featureNames:FEATURE_NAMES,weights:state.weights,
    forecasts,unavailable,marketEvaluation:extra.evaluation,walkForward:{records,method:'Treino sequencial por dia UTC, sem resultados do mesmo dia ou de dias futuros; margem de 6 horas após o início antes de incorporar um resultado. Dados retrospectivos sujeitos às correções atuais da fonte; não equivale a previsões registradas no passado.',model,baseline,betterThanBaseline:model.count>=200&&model.brier<baseline.brier&&model.logLoss<baseline.logLoss},
    limitations:['Somente resultados, forma recente, mando e Elo; sem lesões, suspensões ou escalações.','Histórico recente de até 10 jogos com suavização; a amostra disponível limita a aprendizagem.','Probabilidades experimentais, sem garantia de acerto ou ganho.']};
}
