package br.local.corridacerta;

import android.content.ContentValues;
import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.database.sqlite.SQLiteOpenHelper;

import java.util.ArrayList;
import java.util.List;

/** Histórico de ofertas lidas. Fica só no aparelho (SQLite local); o app não tem permissão de internet. */
final class Store extends SQLiteOpenHelper {
    static final class Row {
        long id, at;
        String platform, dest, pickupAddr, pickupRegion, destRegion;
        double value, pickupKm, pickupMin, tripKm, tripMin;
        boolean accepted;
        double totalKm() { return pickupKm + tripKm; }
        double totalMin() { return pickupMin + tripMin; }
        double perKm() { return totalKm() > 0 ? value / totalKm() : 0; }
        double perHour() { return totalMin() > 0 ? value / totalMin() * 60.0 : 0; }
        double perMin() { return totalMin() > 0 ? value / totalMin() : 0; }
    }

    Store(Context c) { super(c.getApplicationContext(), "history.db", null, 3); }

    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE offers(id INTEGER PRIMARY KEY, at INTEGER, platform TEXT, value REAL, pickupKm REAL, pickupMin REAL,"
                + " tripKm REAL, tripMin REAL, dest TEXT, accepted INTEGER DEFAULT 0, pickupAddr TEXT, pickupRegion TEXT, destRegion TEXT)");
        db.execSQL("CREATE TABLE IF NOT EXISTS geo(name TEXT PRIMARY KEY, lat REAL, lon REAL, ts INTEGER)");
    }

    @Override public void onUpgrade(SQLiteDatabase db, int o, int n) {
        if (o < 2) {
            db.execSQL("ALTER TABLE offers ADD COLUMN pickupAddr TEXT");
            db.execSQL("ALTER TABLE offers ADD COLUMN pickupRegion TEXT");
            db.execSQL("ALTER TABLE offers ADD COLUMN destRegion TEXT");
        }
        db.execSQL("CREATE TABLE IF NOT EXISTS geo(name TEXT PRIMARY KEY, lat REAL, lon REAL, ts INTEGER)");
    }

    /** Grava a oferta, ignorando repetição da mesma oferta nos últimos 10 minutos (o card é lido várias vezes). */
    /** @return id da nova linha, ou -1 se for repetição. */
    long add(String platform, OfferParser.Offer o, long at) {
        SQLiteDatabase db = getWritableDatabase();
        try (Cursor c = db.rawQuery("SELECT id FROM offers WHERE platform=? AND value=? AND pickupKm=? AND tripKm=? AND at>? LIMIT 1",
                new String[]{platform, String.valueOf(o.value), String.valueOf(o.pickupKm), String.valueOf(o.tripKm), String.valueOf(at - 600000)})) {
            if (c.moveToFirst()) return -1;
        }
        ContentValues v = new ContentValues();
        v.put("at", at); v.put("platform", platform); v.put("value", o.value);
        v.put("pickupKm", o.pickupKm); v.put("pickupMin", o.pickupMin);
        v.put("tripKm", o.tripKm); v.put("tripMin", o.tripMin);
        v.put("dest", o.destination == null ? "" : o.destination);
        v.put("pickupAddr", o.pickupAddress == null ? "" : o.pickupAddress);
        v.put("pickupRegion", OfferParser.region(o.pickupAddress));
        v.put("destRegion", OfferParser.region(o.destination));
        long id = db.insert("offers", null, v);
        db.execSQL("DELETE FROM offers WHERE id NOT IN (SELECT id FROM offers ORDER BY at DESC LIMIT 20000)");
        return id;
    }

    void markAccepted(String dest, long since) {
        getWritableDatabase().execSQL("UPDATE offers SET accepted=1 WHERE id=(SELECT id FROM offers WHERE dest=? AND at>=? ORDER BY at DESC LIMIT 1)",
                new Object[]{dest, since});
    }

    List<Row> list(String platform, int limit) { return list(platform, 0, limit); }

    List<Row> list(String platform, long since, int limit) {
        List<Row> out = new ArrayList<>();
        String sql = "SELECT id,at,platform,value,pickupKm,pickupMin,tripKm,tripMin,dest,accepted,pickupAddr,pickupRegion,destRegion FROM offers"
                + " WHERE at>=" + since + (platform == null ? "" : " AND platform=?") + " ORDER BY at DESC LIMIT " + limit;
        try (Cursor c = getReadableDatabase().rawQuery(sql, platform == null ? null : new String[]{platform})) {
            while (c.moveToNext()) {
                Row r = new Row();
                r.id = c.getLong(0); r.at = c.getLong(1); r.platform = c.getString(2); r.value = c.getDouble(3);
                r.pickupKm = c.getDouble(4); r.pickupMin = c.getDouble(5); r.tripKm = c.getDouble(6); r.tripMin = c.getDouble(7);
                r.dest = c.getString(8); r.accepted = c.getInt(9) == 1;
                r.pickupAddr = c.getString(10); r.pickupRegion = c.getString(11); r.destRegion = c.getString(12);
                out.add(r);
            }
        }
        return out;
    }

    void clear() { getWritableDatabase().execSQL("DELETE FROM offers"); }

    // ---- prints das ofertas (JPEG reduzido, em armazenamento privado do app; só os 100 mais recentes) ----
    static java.io.File printFile(Context c, long id) { return new java.io.File(new java.io.File(c.getFilesDir(), "prints"), id + ".jpg"); }

    void cleanupPrints(Context c) {
        java.io.File[] files = new java.io.File(c.getFilesDir(), "prints").listFiles();
        if (files == null) return;
        java.util.Set<String> keep = new java.util.HashSet<>();
        for (Row r : list(null, 100)) keep.add(r.id + ".jpg");
        for (java.io.File f : files) if (!keep.contains(f.getName())) f.delete();
    }

    static void deleteAllPrints(Context c) {
        java.io.File[] files = new java.io.File(c.getFilesDir(), "prints").listFiles();
        if (files != null) for (java.io.File f : files) f.delete();
    }

    // ---- posição aproximada dos bairros (cache; só o NOME do bairro é consultado online) ----
    /** @return {lat, lon, ts} (lat > 900 = não encontrado) ou null se nunca consultado. */
    double[] geoRow(String key) {
        try (Cursor c = getReadableDatabase().rawQuery("SELECT lat,lon,ts FROM geo WHERE name=?", new String[]{key})) {
            return c.moveToFirst() ? new double[]{c.getDouble(0), c.getDouble(1), c.getLong(2)} : null;
        }
    }

    void putGeo(String key, double lat, double lon) {
        getWritableDatabase().execSQL("INSERT OR REPLACE INTO geo(name,lat,lon,ts) VALUES(?,?,?,?)", new Object[]{key, lat, lon, System.currentTimeMillis()});
    }
}
