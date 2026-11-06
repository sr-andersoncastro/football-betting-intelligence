import http from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import {gunzipSync} from 'node:zlib';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { validateFixtures, evaluate } from './lib.mjs';
import { standings } from './analytics.mjs';
import {buildForecast,evaluateRecorded,PILOT_LEAGUES} from './model.mjs';
import {evaluateRecordedMarkets,validateExtraMarkets} from './markets.mjs';
import {Store} from './store.mjs';
import {collect} from './providers/openliga.mjs';
import {collect as collectESPN,leagues} from './providers/espn.mjs';
const root = new URL('./', import.meta.url);
const demo=process.env.DATA_MODE==='demo';
const dataDirectory=process.env.DATA_DIR || fileURLToPath(new URL('runtime/',root));
if(!demo)await mkdir(dataDirectory,{recursive:true});
export const store=new Store(demo?':memory:':join(dataDirectory,'football.sqlite'));
if(!demo){
  for(const file of ['data/openliga.json','data/espn.json']) {
    try {
      const seed=JSON.parse(await readFile(new URL(file,root),'utf8'));
      for(const capture of seed.captures)store.ingest({...capture,raw:gunzipSync(Buffer.from(capture.rawGzip,'base64')).toString('utf8')});
    }catch(error){store.log('error',file+': '+error.message);}
  }
}
const demoFixtures=demo?validateFixtures(JSON.parse(await readFile(new URL('data/demo.json',root),'utf8'))):[];
const getFixtures=()=>demo?demoFixtures:store.fixtures();
let preservedPredictions=[];
if(!demo){
  try{
    const ledger=JSON.parse(await readFile(new URL('data/predictions.json',root),'utf8'));
    preservedPredictions=ledger.predictions.filter(p=>{
      try{validateFixtures([{id:p.fixtureId,home:p.home,away:p.away,competition:'Brasileirão Série A',kickoff:p.kickoff,status:'scheduled',prediction:p}]);if(p.extraMarkets)validateExtraMarkets(p.extraMarkets);return Date.parse(p.createdAt)<=Date.now();}catch{return false;}
    });
  }catch(error){if(error.code!=='ENOENT')store.log('error','Registros de previsão: '+error.message);}
}
let forecastReports=new Map();
function refreshForecast(){
  if(demo)return;
  const now=new Date(),fixtures=getFixtures();
  const reports=PILOT_LEAGUES.map(l=>buildForecast(fixtures,now,l.code));
  store.savePredictions(reports.flatMap(r=>r.forecasts),fixtures,now);
  const archived=[...preservedPredictions,...store.predictions()];
  forecastReports=new Map(reports.map(report=>{
    report.forecasts=report.forecasts.map(p=>archived.find(a=>a.fixtureId===p.fixtureId&&a.version===p.version&&a.kickoff===p.kickoff&&a.dataHash===p.dataHash)??p);
    return [report.competitionCode,{...report,prospectiveEvaluation:evaluateRecorded(archived,fixtures,now,report.competitionCode),prospectiveMarkets:evaluateRecordedMarkets(archived,fixtures,now,report.competitionCode),storage:'Registros locais mais arquivo versionado no GitHub. O workflow preserva previsões periodicamente; registros locais ainda não versionados podem ser perdidos em reinícios.'}];
  }));
}
refreshForecast();
let syncing=false;
export async function sync(){
  if(syncing)return;
  syncing=true;
  try{
    const now=new Date(),year=now.getUTCFullYear();
    const current=now.getUTCMonth()>=6?year:year-1;
    const jobs=[['Bundesliga',()=>collect(current)],...leagues.flatMap(l=>[year-1,year].map(y=>[l.name+' '+y,()=>collectESPN(l.code,y)]))];
    for(const [label,job] of jobs){
      try{const capture=await job();store.ingest(capture);store.log('success',`${label}: ${capture.fixtures.length} partidas coletadas`);}
      catch(error){store.log('error',label+': '+error.message);}
    }
  }finally{try{refreshForecast();}catch(error){store.log('error','Modelo: '+error.message);}syncing=false;}
}
function coverageStatus(){
  const captures=store.coverage();
  return [{code:'bl1',name:'Bundesliga',source:'OpenLigaDB'},...leagues.map(l=>({...l,source:'ESPN'}))].map(league=>{
    const matching=captures.filter(c=>c.scope.startsWith(league.source==='ESPN'?`espn:${league.code}:`:'openliga:bl1:'));
    const latest=matching.map(c=>c.collectedAt).sort((a,b)=>Date.parse(b)-Date.parse(a))[0]??null;
    return {...league,status:latest?'available':'pending',latestCollectedAt:latest,stale:!latest || Date.now()-Date.parse(latest)>24*3600000,calendarYears:matching.map(c=>c.season).sort()};
  });
}
const assets = new Map([['/manifest.webmanifest',['public/manifest.webmanifest','application/manifest+json']],['/sw.js',['public/sw.js','text/javascript; charset=utf-8']],['/icon-192.png',['public/icon-192.png','image/png']],['/icon-512.png',['public/icon-512.png','image/png']],['/', ['public/index.html','text/html; charset=utf-8']],['/analytics.mjs',['analytics.mjs','text/javascript; charset=utf-8']],['/lib.mjs',['lib.mjs','text/javascript; charset=utf-8']],['/app.js',['public/app.js','text/javascript; charset=utf-8']],['/style.css',['public/style.css','text/css; charset=utf-8']]]);
export const server = http.createServer(async (req,res)=>{
  res.setHeader('X-Content-Type-Options','nosniff');
  res.setHeader('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; worker-src 'self'; manifest-src 'self'");
  res.setHeader('Cache-Control','no-store');
  if(req.method !== 'GET') {res.writeHead(405,{'Allow':'GET'});return res.end();}
  const url = new URL(req.url,'http://localhost');
  const json = value => {res.writeHead(200,{'Content-Type':'application/json; charset=utf-8'}); res.end(JSON.stringify(value));};
  if(url.pathname === '/api/v1/health') return json({status:'ok',mode:demo?'demo':'real',version:'0.7.0'});
  if(url.pathname === '/api/v1/predictions'){
    if(demo)return json({status:'unavailable',reason:'Modelos exclusivos para dados reais das ligas do piloto.',forecasts:[]});
    const code=url.searchParams.get('competition')||'bra.1';
    if(!forecastReports.has(code)){res.writeHead(400,{'Content-Type':'application/json; charset=utf-8'});return res.end(JSON.stringify({error:'Competição fora do piloto',available:PILOT_LEAGUES.map(l=>l.code)}));}
    if(forecastReports.get(code).trainingCutoff.slice(0,10)!==new Date().toISOString().slice(0,10))refreshForecast();
    const now=Date.now(),report=forecastReports.get(code);
    return json({...report,pilot:PILOT_LEAGUES,forecasts:report.forecasts.filter(p=>Date.parse(p.kickoff)>now&&now-Date.parse(report.latestDataAt)<=24*3600000)});
  }
  if(url.pathname === '/api/v1/fixtures') return json({source:demo?'synthetic':'OpenLigaDB + ESPN',fixtures:getFixtures()});
  if(url.pathname === '/api/v1/standings') return json({source:demo?'synthetic':'OpenLigaDB + ESPN',groups:standings(getFixtures()),rules:'3 pontos por vitória; desempate por saldo, gols marcados e nome. Sem ajustes disciplinares ou critérios oficiais adicionais.'});
  if(url.pathname === '/api/v1/data-status') {
    const captures=store.captures(),latest=captures[0]?.collectedAt??null,coverage=coverageStatus();
    return json({mode:demo?'demo':'real',source:demo?'synthetic':'OpenLigaDB + ESPN',latestCollectedAt:latest,stale:coverage.some(c=>c.stale),coverage,captures,logs:store.logs(),unavailable:['cards','xG','lineups'],storage:'SQLite local; no Render gratuito, alterações locais são perdidas ao reiniciar ou publicar. A captura versionada no GitHub é preservada.'});
  }
  if(url.pathname === '/api/v1/evaluation') return json({...evaluate(getFixtures()),source:demo?'synthetic':'OpenLigaDB + ESPN',brierConvention:'multiclass sum, range 0–2'});
  const asset = assets.get(url.pathname);
  if(!asset){res.writeHead(404);return res.end('Não encontrado');}
  try {const data=await readFile(new URL(asset[0],root));res.writeHead(200,{'Content-Type':asset[1]});res.end(data);} catch {res.writeHead(500);res.end('Erro ao abrir o painel');}
});
if (process.argv[1] && fileURLToPath(import.meta.url) === fileURLToPath(pathToFileURL(process.argv[1]))) {
  server.listen(Number(process.env.PORT || 3000),'0.0.0.0',()=>console.log('Painel disponível na porta '+(process.env.PORT || 3000)));
  if(!demo){void sync();setInterval(()=>void sync(),6*3600000).unref();}
}

