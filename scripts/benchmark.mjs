import {performance} from 'node:perf_hooks';
import {buildForecast,PILOT_LEAGUES} from '../model.mjs';
const start=performance.now();
const {store}=await import('../server.mjs');
const startupToReadyMs=performance.now()-start,rows=store.fixtures(),now=new Date();
const round=v=>Math.round(v*100)/100;
function measure(leagues){
 global.gc?.();const times=[];
 for(let i=0;i<10;i++){
  const begin=performance.now();for(const league of leagues)buildForecast(rows,now,league.code);times.push(performance.now()-begin);
 }
 const sorted=times.toSorted((a,b)=>a-b);
 global.gc?.();return {leagues:leagues.length,runs:times.length,medianMs:round((sorted[4]+sorted[5])/2),maxMs:round(sorted.at(-1)),rssMB:round(process.memoryUsage().rss/1048576)};
}
try{
 const oneLeague=measure(PILOT_LEAGUES.slice(0,1)),fourLeagues=measure(PILOT_LEAGUES);
 console.log(JSON.stringify({environment:'Local, processo Node; não mede memória nem CPU do Render',node:process.version,measuredAt:now.toISOString(),fixtures:rows.length,startupToReadyMs:round(startupToReadyMs),oneLeague,fourLeagues,peakRssMB:round(process.resourceUsage().maxRSS/1024),note:'O cálculo ocorre na atualização e é mantido em memória. Consultas não treinam o modelo novamente, exceto na virada do dia UTC.'},null,2));
}finally{store.close();}
