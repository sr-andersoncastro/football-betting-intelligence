import { DatabaseSync } from 'node:sqlite';
import {createHash} from 'node:crypto';
import {normalize} from './providers/openliga.mjs';
import {normalize as normalizeESPN} from './providers/espn.mjs';
export class Store {
  constructor(path=':memory:') {
    this.db=new DatabaseSync(path);
    this.db.exec(`PRAGMA foreign_keys=ON;
      CREATE TABLE IF NOT EXISTS captures(id INTEGER PRIMARY KEY, source TEXT NOT NULL, url TEXT NOT NULL, season INTEGER NOT NULL, collected_at TEXT NOT NULL, sha256 TEXT NOT NULL, raw TEXT NOT NULL, UNIQUE(season,collected_at,sha256));
      CREATE TABLE IF NOT EXISTS fixtures(id TEXT PRIMARY KEY, season INTEGER NOT NULL, kickoff TEXT NOT NULL, capture_id INTEGER NOT NULL REFERENCES captures(id), json TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS sync_logs(id INTEGER PRIMARY KEY, occurred_at TEXT NOT NULL, status TEXT NOT NULL, message TEXT NOT NULL);`);
    if(!this.db.prepare('PRAGMA table_info(captures)').all().some(c=>c.name==='scope')) {
      this.db.exec("ALTER TABLE captures ADD COLUMN scope TEXT NOT NULL DEFAULT ''; UPDATE captures SET scope='openliga:bl1:' || season;");
    }
    if(!this.db.prepare('PRAGMA table_info(fixtures)').all().some(c=>c.name==='scope')) {
      this.db.exec("ALTER TABLE fixtures ADD COLUMN scope TEXT NOT NULL DEFAULT ''; UPDATE fixtures SET scope='openliga:bl1:' || season;");
    }
  }
  ingest(capture) {
    if(createHash('sha256').update(capture.raw).digest('hex')!==capture.sha256)throw new Error('Integridade da captura inválida');
    if(!Number.isFinite(Date.parse(capture.collectedAt)))throw new Error('Horário de coleta inválido');
    // Normalize offsets and fractional seconds before comparing timestamps in SQLite.
    capture={...capture,collectedAt:new Date(capture.collectedAt).toISOString()};
    const scope=capture.source==='ESPN'?`espn:${capture.competitionCode}:${capture.season}`:`openliga:bl1:${capture.season}`;
    if(!['ESPN','OpenLigaDB'].includes(capture.source))throw new Error('Fonte não suportada');
    const fixtures=capture.source==='ESPN'?normalizeESPN(JSON.parse(capture.raw),capture.competitionCode,capture.season,capture.collectedAt):normalize(JSON.parse(capture.raw),capture.season,capture.collectedAt);
    this.db.exec('BEGIN');
    try {
      this.db.prepare('INSERT OR IGNORE INTO captures(source,url,season,collected_at,sha256,raw,scope) VALUES(?,?,?,?,?,?,?)').run(capture.source,capture.url,capture.season,capture.collectedAt,capture.sha256,capture.raw,scope);
      const id=this.db.prepare('SELECT id FROM captures WHERE season=? AND collected_at=? AND sha256=?').get(capture.season,capture.collectedAt,capture.sha256).id;
      // Older seeds must never overwrite a newer collected result.
      const latest=this.db.prepare('SELECT id FROM captures WHERE scope=? ORDER BY julianday(collected_at) DESC,id DESC LIMIT 1').get(scope);
      if(latest.id===id){
        this.db.prepare('DELETE FROM fixtures WHERE scope=?').run(scope);
        const insert=this.db.prepare(`INSERT INTO fixtures(id,season,kickoff,capture_id,json,scope) VALUES(?,?,?,?,?,?)
          ON CONFLICT(id) DO UPDATE SET season=excluded.season,kickoff=excluded.kickoff,capture_id=excluded.capture_id,json=excluded.json,scope=excluded.scope
          WHERE julianday((SELECT collected_at FROM captures WHERE id=excluded.capture_id)) >= julianday((SELECT collected_at FROM captures WHERE id=fixtures.capture_id))`);
        for(const row of fixtures)insert.run(row.id,row.season,row.kickoff,id,JSON.stringify(row),scope);
      }
      this.db.exec('COMMIT');
    }catch(error){this.db.exec('ROLLBACK');throw error;}
    return fixtures.length;
  }
  fixtures(){return this.db.prepare('SELECT json FROM fixtures ORDER BY kickoff,id').all().map(r=>JSON.parse(r.json));}
  captures(){return this.db.prepare('SELECT id,source,url,season,scope,collected_at AS collectedAt,sha256 FROM captures ORDER BY julianday(collected_at) DESC,id DESC LIMIT 40').all();}
  coverage(){return this.db.prepare(`SELECT scope,source,season,collected_at AS collectedAt FROM captures c WHERE id=(SELECT id FROM captures WHERE scope=c.scope ORDER BY julianday(collected_at) DESC,id DESC LIMIT 1)`).all();}
  log(status,message){this.db.prepare('INSERT INTO sync_logs(occurred_at,status,message) VALUES(?,?,?)').run(new Date().toISOString(),status,String(message).slice(0,500));}
  logs(){return this.db.prepare('SELECT occurred_at AS occurredAt,status,message FROM sync_logs ORDER BY id DESC LIMIT 20').all();}
  close(){this.db.close();}
}

