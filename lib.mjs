// Crests are only accepted from the two hosts the data sources serve them from.
const logoHosts = new Set(['a.espncdn.com', 'upload.wikimedia.org']);
export function safeLogo(value) {
  try { const url = new URL(value); return url.protocol === 'https:' && logoHosts.has(url.hostname) ? url.href : null; } catch { return null; }
}
export function validateFixtures(rows) {
  if (!Array.isArray(rows)) throw new Error('Lista de partidas inválida');
  const ids = new Set();
  for (const row of rows) {
    if (!row.id || ids.has(row.id)) throw new Error('Identificador ausente ou duplicado');
    ids.add(row.id);
    if (![row.home, row.away, row.competition].every(v => typeof v === 'string' && v.trim())) throw new Error('Equipe ou competição inválida');
    if (!Number.isFinite(Date.parse(row.kickoff))) throw new Error('Data inválida');
    if (!['scheduled', 'finished', 'live', 'postponed', 'cancelled', 'suspended'].includes(row.status)) throw new Error('Estado inválido');
    if (row.status === 'finished' && ![row.homeGoals, row.awayGoals].every(v => Number.isInteger(v) && v >= 0)) throw new Error('Estatística inválida');
    if (![row.corners, row.cards, row.homeCorners, row.awayCorners, row.homeFouls, row.awayFouls, row.fouls].every(v => v == null || (Number.isInteger(v) && v >= 0))) throw new Error('Estatística inválida');
    if (row.prediction) {
      const p = row.prediction;
      if (!Array.isArray(p.probabilities) || p.probabilities.length !== 3 || !p.probabilities.every(v => Number.isFinite(v) && v >= 0 && v <= 1) || Math.abs(p.probabilities.reduce((a,b)=>a+b,0)-1)>1e-8) throw new Error('Probabilidades inválidas');
      if (!p.version || !Number.isFinite(Date.parse(p.createdAt)) || Date.parse(p.createdAt) >= Date.parse(row.kickoff)) throw new Error('Previsão deve anteceder a partida');
    }
  }
  return rows;
}
export function evaluate(rows) {
  const finished = rows.filter(r => r.status === 'finished' && r.prediction);
  if (!finished.length) return { count: 0, brier: null, logLoss: null };
  let brier = 0, logLoss = 0;
  for (const r of finished) {
    const outcome = r.homeGoals > r.awayGoals ? 0 : r.homeGoals === r.awayGoals ? 1 : 2;
    brier += r.prediction.probabilities.reduce((sum,p,i)=>sum+(p-(i===outcome?1:0))**2,0);
    logLoss -= Math.log(Math.max(1e-15,r.prediction.probabilities[outcome]));
  }
  return { count: finished.length, brier: brier/finished.length, logLoss: logLoss/finished.length };
}


// Most probable scenarios according to the experimental models. Not a recommendation: no odds, no value.
const flip = label => label.startsWith('Mais de ') ? 'Menos de ' + label.slice(8) : 'Ambas as equipes marcam' === label ? 'Pelo menos uma equipe não marca' : 'Não: ' + label;
export function scenarios(forecast, limit = 5) {
  const {home, away, probabilities: p, evidence: ev} = forecast;
  const valid=x=>Number.isFinite(x)&&x>=0&&x<=1;
  const pct=x=>x>=.995?'>99%':(100*x).toFixed(0)+'%';
  const fixed=(value,digits=2)=>Number.isFinite(value)?value.toFixed(digits):'—';
  const best=[];
  if(Array.isArray(p)&&p.length===3&&p.every(valid)&&Math.abs(p.reduce((a,b)=>a+b,0)-1)<1e-8){
    const i=p.indexOf(Math.max(...p));
    best.push({category:'Resultado',label:i===0?'Vitória do '+home:i===1?'Empate':'Vitória do '+away,probability:p[i],explanation:`Forma recente: ${home} ${fixed(ev?.home?.lastTen?.points)} e ${away} ${fixed(ev?.away?.lastTen?.points)} pontos/jogo; o modelo também considera o mando.`});
  }
  for(const market of forecast.extraMarkets??[]){
    if(market.status!=='experimental'||!['goals','corners','fouls'].includes(market.code))continue;
    const families=new Map();
    for(const m of market.markets??[]){
      if(!valid(m.probability)||!valid(m.oppositeProbability)||Math.abs(m.probability+m.oppositeProbability-1)>1e-8)continue;
      const both=market.code==='goals'&&(m.both||m.id==='both-teams-score'||m.label==='Ambas as equipes marcam');
      const category=both?'Ambas marcam':market.name;
      const pick=m.probability>=m.oppositeProbability?{label:m.label,probability:m.probability}:{label:flip(m.label),probability:m.oppositeProbability};
      const previous=families.get(category);if(!previous||pick.probability>previous.probability)families.set(category,pick);
    }
    for(const [category,pick] of families){
      const explanation=market.code==='goals'?`Gols marcados por jogo: ${home} ${fixed(ev?.home?.lastTen?.goalsFor,1)}; ${away} ${fixed(ev?.away?.lastTen?.goalsFor,1)}.`:`Histórico recente das equipes; ${market.trainingMatches} jogos no treino da liga.`;
      best.push({category,...pick,explanation});
    }
  }
  const count=Number.isInteger(limit)?Math.max(0,Math.min(5,limit)):5;
  return best.sort((a,b)=>b.probability-a.probability).slice(0,count).map(s=>({...s,text:pct(s.probability)}));
}
