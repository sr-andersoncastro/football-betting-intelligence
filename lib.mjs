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
export function scenarios(forecast, limit = 3) {
  const {home, away, probabilities: p, evidence: ev} = forecast;
  const pct = x => (100 * x).toFixed(0) + '%';
  const best = [];
  const outcomes = [
    {label: 'Vitória do ' + home, probability: p[0], explanation: `${home} faz ${ev.home.venueLastTen.points.toFixed(2)} pontos/jogo em casa nos últimos 10 jogos suavizados; ${away} faz ${ev.away.venueLastTen.points.toFixed(2)} fora.`},
    {label: 'Empate', probability: p[1], explanation: `Forma recente próxima: ${home} com ${ev.home.lastTen.points.toFixed(2)} e ${away} com ${ev.away.lastTen.points.toFixed(2)} pontos/jogo.`},
    {label: 'Vitória do ' + away, probability: p[2], explanation: `${away} faz ${ev.away.venueLastTen.points.toFixed(2)} pontos/jogo fora nos últimos 10 jogos suavizados; ${home} faz ${ev.home.venueLastTen.points.toFixed(2)} em casa.`}
  ].sort((a, b) => b.probability - a.probability)[0];
  best.push({category: 'Resultado', ...outcomes});
  for (const market of forecast.extraMarkets ?? []) {
    if (market.status === 'unavailable' || !market.markets?.length) continue;
    const picks = market.markets.map(m => m.probability >= m.oppositeProbability ? {label: m.label, probability: m.probability} : {label: flip(m.label), probability: m.oppositeProbability});
    const top = picks.sort((a, b) => b.probability - a.probability)[0];
    const explanation = market.code === 'goals'
      ? `Média recente de gols marcados por jogo: ${home} ${ev.home.lastTen.goalsFor.toFixed(1)} e ${away} ${ev.away.lastTen.goalsFor.toFixed(1)}; sofridos: ${ev.home.lastTen.goalsAgainst.toFixed(1)} e ${ev.away.lastTen.goalsAgainst.toFixed(1)}.`
      : `Estimativa de ${market.name.toLowerCase()} a partir do histórico recente das duas equipes (modelo treinado com ${market.trainingMatches} jogos da liga).`;
    best.push({category: market.name, ...top, explanation});
  }
  return best.sort((a, b) => b.probability - a.probability).slice(0, limit).map(s => ({...s, text: pct(s.probability)}));
}
