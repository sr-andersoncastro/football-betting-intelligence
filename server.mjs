import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { validateFixtures, evaluate } from './lib.mjs';
const root = new URL('./', import.meta.url);
const fixtures = validateFixtures(JSON.parse(await readFile(new URL('data/demo.json',root),'utf8')));
const assets = new Map([['/', ['public/index.html','text/html; charset=utf-8']],['/lib.mjs',['lib.mjs','text/javascript; charset=utf-8']],['/app.js',['public/app.js','text/javascript; charset=utf-8']],['/style.css',['public/style.css','text/css; charset=utf-8']]]);
export const server = http.createServer(async (req,res)=>{
  res.setHeader('X-Content-Type-Options','nosniff');
  res.setHeader('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'");
  res.setHeader('Cache-Control','no-store');
  if(req.method !== 'GET') {res.writeHead(405,{'Allow':'GET'});return res.end();}
  const url = new URL(req.url,'http://localhost');
  const json = value => {res.writeHead(200,{'Content-Type':'application/json; charset=utf-8'}); res.end(JSON.stringify(value));};
  if(url.pathname === '/api/v1/health') return json({status:'ok',mode:'demo',version:'0.1.0'});
  if(url.pathname === '/api/v1/fixtures') return json({source:'synthetic',fixtures});
  if(url.pathname === '/api/v1/evaluation') return json({...evaluate(fixtures),source:'synthetic',brierConvention:'multiclass sum, range 0–2'});
  const asset = assets.get(url.pathname);
  if(!asset){res.writeHead(404);return res.end('Não encontrado');}
  try {const data=await readFile(new URL(asset[0],root));res.writeHead(200,{'Content-Type':asset[1]});res.end(data);} catch {res.writeHead(500);res.end('Erro ao abrir o painel');}
});
if (process.argv[1] && fileURLToPath(import.meta.url) === fileURLToPath(pathToFileURL(process.argv[1]))) server.listen(Number(process.env.PORT || 3000),'0.0.0.0',()=>console.log('Painel disponível na porta '+(process.env.PORT || 3000)));
