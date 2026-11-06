import {readFile,writeFile,rename} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import {normalize} from '../providers/espn.mjs';
import {buildForecast} from '../model.mjs';
const root=new URL('../data/',import.meta.url),now=new Date();
const seed=JSON.parse(await readFile(new URL('espn.json',root),'utf8'));
const fixtures=new Map();
for(const c of seed.captures.filter(c=>c.competitionCode==='bra.1').sort((a,b)=>Date.parse(a.collectedAt)-Date.parse(b.collectedAt))){
 const rows=normalize(JSON.parse(gunzipSync(Buffer.from(c.rawGzip,'base64')).toString('utf8')),c.competitionCode,c.season,c.collectedAt);
 for(const row of rows)fixtures.set(row.id,row);
}
let previous=[];
try{previous=JSON.parse(await readFile(new URL('predictions.json',root),'utf8')).predictions;}catch(error){if(error.code!=='ENOENT')throw error;}
const report=buildForecast([...fixtures.values()],now);
const key=p=>JSON.stringify([p.fixtureId,p.version,p.kickoff,p.dataHash]);
const archive=new Map(previous.map(p=>[key(p),p]));
for(const p of report.forecasts)if(!archive.has(key(p)))archive.set(key(p),p);
await writeFile(new URL('predictions.json.tmp',root),JSON.stringify({schemaVersion:1,predictions:[...archive.values()]}));
await rename(new URL('predictions.json.tmp',root),new URL('predictions.json',root));
console.log(`${report.forecasts.length} previsão(ões) disponível(is); ${archive.size} registros preservados.`);
