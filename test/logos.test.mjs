import test from 'node:test';
import assert from 'node:assert/strict';
import {safeLogo} from '../lib.mjs';
import {normalize} from '../providers/espn.mjs';
import {normalize as normalizeOpenLiga} from '../providers/openliga.mjs';
test('escudos só são aceitos por HTTPS e dos hosts das fontes',()=>{
  assert.equal(safeLogo('https://a.espncdn.com/i/teamlogos/soccer/500/337.png'),'https://a.espncdn.com/i/teamlogos/soccer/500/337.png');
  assert.ok(safeLogo('https://upload.wikimedia.org/wikipedia/commons/1/1f/x.svg'));
  for(const bad of ['http://a.espncdn.com/x.png','https://evil.example/x.png','javascript:alert(1)','https://a.espncdn.com.evil.example/x.png','',null,undefined])assert.equal(safeLogo(bad),null);
});
const team=(id,homeAway,logo)=>({homeAway,score:'1',team:{id,displayName:'T'+id,logo}});
test('ESPN e OpenLigaDB preservam o escudo e ignoram endereços inválidos',()=>{
  const event={id:'1',date:'2026-11-08T20:00Z',season:{year:2026},competitions:[{timeValid:true,status:{type:{name:'STATUS_SCHEDULED',state:'pre',completed:false}},competitors:[team('10','home','https://a.espncdn.com/i/teamlogos/soccer/500/10.png'),team('20','away','https://evil.example/20.png')]}]};
  const [e]=normalize({leagues:[{slug:'eng.1'}],events:[event]},'eng.1',2026,'2026-11-06T10:00:00Z');
  assert.equal(e.homeLogo,'https://a.espncdn.com/i/teamlogos/soccer/500/10.png');assert.equal(e.awayLogo,null);
  const match={leagueShortcut:'bl1',leagueSeason:2026,matchID:5,matchIsFinished:false,matchDateTimeUTC:'2026-11-08T20:00:00Z',team1:{teamId:1,teamName:'A',teamIconUrl:'https://upload.wikimedia.org/a.svg'},team2:{teamId:2,teamName:'B',teamIconUrl:'http://x/b.svg'}};
  const [o]=normalizeOpenLiga([match],2026,'2026-11-06T10:00:00Z');
  assert.equal(o.homeLogo,'https://upload.wikimedia.org/a.svg');assert.equal(o.awayLogo,null);
});
