import http from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import {gunzipSync} from 'node:zlib';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { validateFixtures, evaluate } from './lib.mjs';
import {Store} from './store.mjs';
import {collect,coverage} from './providers/openliga.mjs';
const root = new URL('./', import.meta.url);
const demo=process.env.DATA_MODE==='demo';
const dataDirectory=process.env.DATA_DIR || fileURLToPath(new URL('runtime/',root));
if(!demo)await mkdir(dataDirectory,{recursive:true});
export const store=new Store(demo?':memory:':join(dataDirectory,'football.sqlite'));
if(!demo){
  const seed=JSON.parse(await readFile(new URL('data/openliga.json',root),'utf8'));
  for(const capture of seed.captures)store.ingest({...capture,raw:gunzipSync(Buffer.from(capture.rawGzip,'base64')).toString('utf8')});
}
const demoFixtures=demo?validateFixtures(JSON.parse(await readFile(new URL('data/demo.json',root),'utf8'))):[];
const getFixtures=()=>demo?demoFixtures:store.fixtures();
export async function sync(){
  const current=new Date().getUTCMonth()>=6?new Date().getUTCFullYear():new Date().getUTCFullYear()-1;
  try{const capture=await collect(current);store.ingest(capture);store.log('success',`${capture.fixtures.length} partidas de ${current} coletadas`);}catch(error){store.log('error',error.message);}
}
const assets = new Map([['/', ['public/index.html','text/html; charset=utf-8']],['/lib.mjs',['lib.mjs','text/javascript; charset=utf-8']],['/app.js',['public/app.js','text/javascript; charset=utf-8']],['/style.css',['public/style.css','text/css; charset=utf-8']]]);
export const server = http.createServer(async (req,res)=>{
  res.setHeader('X-Content-Type-Options','nosniff');
  res.setHeader('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'");
  res.setHeader('Cache-Control','no-store');
  if(req.method !== 'GET') {res.writeHead(405,{'Allow':'GET'});return res.end();}
  const url = new URL(req.url,'http://localhost');
  const json = value => {res.writeHead(200,{'Content-Type':'application/json; charset=utf-8'}); res.end(JSON.stringify(value));};
  if(url.pathname === '/api/v1/health') return json({status:'ok',mode:demo?'demo':'real',version:'0.2.0'});
  if(url.pathname === '/api/v1/fixtures') return json({source:demo?'synthetic':'OpenLigaDB',fixtures:getFixtures()});
  if(url.pathname === '/api/v1/data-status') {
    const captures=store.captures(),latest=captures[0]?.collectedAt??null;
    return json({mode:demo?'demo':'real',source:demo?'synthetic':'OpenLigaDB',latestCollectedAt:latest,stale:latest?Date.now()-Date.parse(latest)>24*3600000:true,coverage,captures,logs:store.logs(),unavailable:['corners','cards','xG','lineups'],storage:'SQLite local; no Render gratuito, alterações locais são perdidas ao reiniciar ou publicar. A captura versionada no GitHub é preservada.'});
  }
  if(url.pathname === '/api/v1/evaluation') return json({...evaluate(getFixtures()),source:demo?'synthetic':'OpenLigaDB',brierConvention:'multiclass sum, range 0–2'});
  const asset = assets.get(url.pathname);
  if(!asset){res.writeHead(404);return res.end('Não encontrado');}
  try {const data=await readFile(new URL(asset[0],root));res.writeHead(200,{'Content-Type':asset[1]});res.end(data);} catch {res.writeHead(500);res.end('Erro ao abrir o painel');}
});
if (process.argv[1] && fileURLToPath(import.meta.url) === fileURLToPath(pathToFileURL(process.argv[1]))) {
  server.listen(Number(process.env.PORT || 3000),'0.0.0.0',()=>console.log('Painel disponível na porta '+(process.env.PORT || 3000)));
  if(!demo){void sync();setInterval(()=>void sync(),6*3600000).unref();}
}
