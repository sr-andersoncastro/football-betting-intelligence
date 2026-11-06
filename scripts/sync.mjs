import { mkdir,writeFile,rename } from 'node:fs/promises';
import {collect} from '../providers/openliga.mjs';
import {gzipSync} from 'node:zlib';
const now=new Date();
const current=now.getUTCMonth()>=6?now.getUTCFullYear():now.getUTCFullYear()-1;
const captures=[];
for(const season of [current-1,current]){const capture=await collect(season);captures.push(capture);console.log(`${season}: ${capture.fixtures.length} partidas; SHA-256 ${capture.sha256}`);}
const path=new URL('../data/openliga.json',import.meta.url);
await mkdir(new URL('../data/',import.meta.url),{recursive:true});
await writeFile(new URL('../data/openliga.json.tmp',import.meta.url),JSON.stringify({schemaVersion:1,captures:captures.map(({fixtures,raw,...metadata})=>({...metadata,rawGzip:gzipSync(raw).toString('base64')}))}));
await rename(new URL('../data/openliga.json.tmp',import.meta.url),path);
console.log('Capturas reais e dados normalizados gravados.');
