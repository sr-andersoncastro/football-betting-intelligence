import {mkdir,writeFile,rename,readFile} from 'node:fs/promises';
import {collect as collectOpenLiga} from '../providers/openliga.mjs';
import {collect as collectESPN,leagues} from '../providers/espn.mjs';
import {gzipSync} from 'node:zlib';
const now=new Date();
const current=now.getUTCMonth()>=6?now.getUTCFullYear():now.getUTCFullYear()-1;
const year=now.getUTCFullYear();
await mkdir(new URL('../data/',import.meta.url),{recursive:true});
let failures=0;
async function save(name,jobs){
  const path=new URL(`../data/${name}.json`,import.meta.url);
  let previous=[];
  try{previous=JSON.parse(await readFile(path,'utf8')).captures;}catch(error){if(error.code!=='ENOENT')throw error;}
  const captures=new Map(previous.map(c=>[c.scope??`openliga:bl1:${c.season}`,c]));
  for(const [key,job] of jobs){
    try{
      const {fixtures,raw,...metadata}=await job();
      captures.set(key,{...metadata,scope:key,rawGzip:gzipSync(raw).toString('base64')});
      console.log(`${key}: ${fixtures.length} partidas; SHA-256 ${metadata.sha256}`);
    }catch(error){failures++;console.error(`${key}: ${error.message}; captura anterior preservada`);}
  }
  const temp=new URL(`../data/${name}.json.tmp`,import.meta.url);
  await writeFile(temp,JSON.stringify({schemaVersion:2,captures:[...captures.values()]}));
  await rename(temp,path);
}
await save('openliga',[current-1,current].map(season=>[`openliga:bl1:${season}`,()=>collectOpenLiga(season)]));
await save('espn',leagues.flatMap(league=>[year-1,year].map(y=>[`espn:${league.code}:${y}`,()=>collectESPN(league.code,y)])));
if(failures){console.error(`${failures} consulta(s) falharam`);process.exitCode=1;}
