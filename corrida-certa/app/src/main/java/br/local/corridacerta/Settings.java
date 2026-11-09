package br.local.corridacerta;

import android.content.Context;
import android.content.SharedPreferences;

final class Settings {
    private final SharedPreferences p;
    Settings(Context c) { p = c.getApplicationContext().getSharedPreferences("settings", Context.MODE_PRIVATE); }
    double minPerKm() { return Double.longBitsToDouble(p.getLong("minKm", Double.doubleToLongBits(1.80))); }
    double minPerHour() { return Double.longBitsToDouble(p.getLong("minHour", Double.doubleToLongBits(30.0))); }
    void save(double perKm, double perHour) {
        p.edit().putLong("minKm", Double.doubleToLongBits(perKm)).putLong("minHour", Double.doubleToLongBits(perHour)).apply();
    }
    boolean enabled() { return p.getBoolean("enabled", true); }
    void setEnabled(boolean v) { p.edit().putBoolean("enabled", v).apply(); }
    /** Último texto lido da Uber/99, para diagnóstico quando o parser não reconhece o card. */
    String lastRaw() { return p.getString("lastRaw", ""); }
    void setLastRaw(String t) { p.edit().putString("lastRaw", t).apply(); }
    String lastResult() { return p.getString("lastResult", "Nenhuma corrida lida ainda."); }
    void setLastResult(String t) { p.edit().putString("lastResult", t).apply(); }
}
