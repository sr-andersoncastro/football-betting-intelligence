package br.local.corridacerta;

import java.util.ArrayList;
import java.util.Calendar;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** Estatísticas do histórico: bairros mais movimentados e tendência por horário. Java puro (testável). */
final class Stats {
    private Stats() {}

    static final class Sample {
        final long at; final String platform; final double value, perKm, perHour; final String region;
        Sample(long at, String platform, double value, double perKm, double perHour, String region) {
            this.at = at; this.platform = platform; this.value = value; this.perKm = perKm; this.perHour = perHour; this.region = region;
        }
    }

    static final class RegionStat {
        String name; int count; double avgValue, avgPerKm, avgPerHour;
    }

    /** Bairros ordenados por nº de ofertas (empate: maior R$/h). Ofertas sem bairro ficam de fora. */
    static List<RegionStat> regions(List<Sample> in) {
        Map<String, RegionStat> m = new HashMap<>();
        Map<String, double[]> sum = new HashMap<>();
        for (Sample s : in) {
            if (s.region == null || s.region.isEmpty()) continue;
            String k = s.region.toLowerCase(Locale.ROOT);
            RegionStat r = m.get(k);
            if (r == null) { r = new RegionStat(); r.name = s.region; m.put(k, r); sum.put(k, new double[3]); }
            r.count++;
            double[] a = sum.get(k);
            a[0] += s.value; a[1] += s.perKm; a[2] += s.perHour;
        }
        List<RegionStat> out = new ArrayList<>();
        for (Map.Entry<String, RegionStat> e : m.entrySet()) {
            RegionStat r = e.getValue(); double[] a = sum.get(e.getKey());
            r.avgValue = a[0] / r.count; r.avgPerKm = a[1] / r.count; r.avgPerHour = a[2] / r.count;
            out.add(r);
        }
        out.sort(Comparator.<RegionStat>comparingInt(r -> -r.count).thenComparingDouble(r -> -r.avgPerHour));
        return out;
    }

    static final class Hourly {
        final int[] count = new int[24];
        final double[] avgValue = new double[24], avgPerHour = new double[24];
    }

    static Hourly hourly(List<Sample> in) {
        Hourly h = new Hourly();
        Calendar c = Calendar.getInstance();
        for (Sample s : in) {
            c.setTimeInMillis(s.at);
            int hr = c.get(Calendar.HOUR_OF_DAY);
            h.count[hr]++; h.avgValue[hr] += s.value; h.avgPerHour[hr] += s.perHour;
        }
        for (int i = 0; i < 24; i++) if (h.count[i] > 0) { h.avgValue[i] /= h.count[i]; h.avgPerHour[i] /= h.count[i]; }
        return h;
    }

    /** Hora (0-23) com maior R$/h médio, exigindo ao menos minCount ofertas; -1 se não houver. */
    static int bestHour(Hourly h, int minCount) {
        int best = -1;
        for (int i = 0; i < 24; i++) if (h.count[i] >= minCount && (best < 0 || h.avgPerHour[i] > h.avgPerHour[best])) best = i;
        return best;
    }

    /** Categoria pelo R$/km já arredondado a centavos (como aparece na tela): 0 = ruim, 1 = média, 2 = boa. */
    static int category(double perKm, double badBelow, double goodFrom) {
        long v = Math.round(perKm * 100), bad = Math.round(badBelow * 100), good = Math.round(goodFrom * 100);
        return v < bad ? 0 : (v < good ? 1 : 2);
    }
}
