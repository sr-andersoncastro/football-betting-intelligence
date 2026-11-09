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
        String platform, dest;
        double value, pickupKm, pickupMin, tripKm, tripMin;
        boolean accepted;
        double totalKm() { return pickupKm + tripKm; }
        double totalMin() { return pickupMin + tripMin; }
        double perKm() { return totalKm() > 0 ? value / totalKm() : 0; }
        double perHour() { return totalMin() > 0 ? value / totalMin() * 60.0 : 0; }
        double perMin() { return totalMin() > 0 ? value / totalMin() : 0; }
    }

    Store(Context c) { super(c.getApplicationContext(), "history.db", null, 1); }

    @Override public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE offers(id INTEGER PRIMARY KEY, at INTEGER, platform TEXT, value REAL, pickupKm REAL, pickupMin REAL,"
                + " tripKm REAL, tripMin REAL, dest TEXT, accepted INTEGER DEFAULT 0)");
    }

    @Override public void onUpgrade(SQLiteDatabase db, int o, int n) {}

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
        long id = db.insert("offers", null, v);
        db.execSQL("DELETE FROM offers WHERE id NOT IN (SELECT id FROM offers ORDER BY at DESC LIMIT 500)");
        return id;
    }

    void markAccepted(String dest, long since) {
        getWritableDatabase().execSQL("UPDATE offers SET accepted=1 WHERE id=(SELECT id FROM offers WHERE dest=? AND at>=? ORDER BY at DESC LIMIT 1)",
                new Object[]{dest, since});
    }

    List<Row> list(String platform, int limit) {
        List<Row> out = new ArrayList<>();
        String sql = "SELECT id,at,platform,value,pickupKm,pickupMin,tripKm,tripMin,dest,accepted FROM offers"
                + (platform == null ? "" : " WHERE platform=?") + " ORDER BY at DESC LIMIT " + limit;
        try (Cursor c = getReadableDatabase().rawQuery(sql, platform == null ? null : new String[]{platform})) {
            while (c.moveToNext()) {
                Row r = new Row();
                r.id = c.getLong(0); r.at = c.getLong(1); r.platform = c.getString(2); r.value = c.getDouble(3);
                r.pickupKm = c.getDouble(4); r.pickupMin = c.getDouble(5); r.tripKm = c.getDouble(6); r.tripMin = c.getDouble(7);
                r.dest = c.getString(8); r.accepted = c.getInt(9) == 1;
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
}
