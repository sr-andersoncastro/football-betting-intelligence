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
    if (![row.corners, row.cards].every(v => v == null || (Number.isInteger(v) && v >= 0))) throw new Error('Estatística inválida');
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

