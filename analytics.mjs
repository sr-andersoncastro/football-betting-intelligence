// Statistical summaries of observed results; no forecasts or betting signals.
export function standings(fixtures) {
  const groups = new Map();
  for (const fixture of fixtures) {
    if (fixture.status !== 'finished' || fixture.tableEligible === false) continue;
    const key = JSON.stringify([fixture.competition, fixture.season ?? null]);
    if (!groups.has(key)) groups.set(key, {
      competition: fixture.competition, season: fixture.season ?? null, seasonLabel: fixture.seasonLabel ?? `${fixture.season}/${fixture.season+1}`, teams: new Map(), matches: 0
    });
    const group = groups.get(key);
    const team = (side) => {
      const id = fixture[side + 'TeamId'] ?? fixture[side];
      if (!group.teams.has(id)) group.teams.set(id, {
        id, name: fixture[side], played: 0, won: 0, drawn: 0, lost: 0,
        goalsFor: 0, goalsAgainst: 0, goalDifference: 0, points: 0
      });
      return group.teams.get(id);
    };
    const home = team('home'), away = team('away');
    home.played++; away.played++; group.matches++;
    home.goalsFor += fixture.homeGoals; home.goalsAgainst += fixture.awayGoals;
    away.goalsFor += fixture.awayGoals; away.goalsAgainst += fixture.homeGoals;
    if (fixture.homeGoals === fixture.awayGoals) {
      home.drawn++; away.drawn++; home.points++; away.points++;
    } else {
      const [winner, loser] = fixture.homeGoals > fixture.awayGoals ? [home, away] : [away, home];
      winner.won++; winner.points += 3; loser.lost++;
    }
  }
  return [...groups.values()].map(group => ({
    competition: group.competition, season: group.season, seasonLabel: group.seasonLabel, matches: group.matches,
    teams: [...group.teams.values()].map(team => ({
      ...team, goalDifference: team.goalsFor - team.goalsAgainst,
      pointsPercentage: 100 * team.points / (3 * team.played)
    })).sort((a,b) => b.points - a.points || b.goalDifference - a.goalDifference ||
      b.goalsFor - a.goalsFor || a.name.localeCompare(b.name, 'pt-BR'))
  })).sort((a,b) => a.competition.localeCompare(b.competition, 'pt-BR') || (b.season ?? 0) - (a.season ?? 0));
}
