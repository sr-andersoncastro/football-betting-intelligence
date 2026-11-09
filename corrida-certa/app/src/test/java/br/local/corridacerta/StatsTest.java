package br.local.corridacerta;

import static org.junit.Assert.*;
import java.util.ArrayList;
import java.util.Calendar;
import java.util.List;
import org.junit.Test;

public class StatsTest {
    private static long at(int hour) {
        Calendar c = Calendar.getInstance();
        c.set(2026, Calendar.NOVEMBER, 9, hour, 10, 0);
        return c.getTimeInMillis();
    }

    @Test public void rankingPorBairro() {
        List<Stats.Sample> l = new ArrayList<>();
        l.add(new Stats.Sample(at(20), "Uber", 10, 2.0, 30, "Centro"));
        l.add(new Stats.Sample(at(20), "99", 20, 1.0, 40, "centro"));
        l.add(new Stats.Sample(at(21), "99", 8, 1.5, 20, "Azenha"));
        l.add(new Stats.Sample(at(21), "99", 8, 1.5, 20, null));
        List<Stats.RegionStat> r = Stats.regions(l);
        assertEquals(2, r.size());
        assertEquals("Centro", r.get(0).name);
        assertEquals(2, r.get(0).count);
        assertEquals(15, r.get(0).avgValue, 1e-9);
        assertEquals(35, r.get(0).avgPerHour, 1e-9);
    }

    @Test public void melhorHorario() {
        List<Stats.Sample> l = new ArrayList<>();
        l.add(new Stats.Sample(at(20), "Uber", 10, 2.0, 30, "A"));
        l.add(new Stats.Sample(at(20), "Uber", 10, 2.0, 50, "A"));
        l.add(new Stats.Sample(at(22), "Uber", 10, 2.0, 100, "A")); // só 1 oferta: ignorada
        l.add(new Stats.Sample(at(14), "Uber", 10, 2.0, 20, "A"));
        l.add(new Stats.Sample(at(14), "Uber", 10, 2.0, 20, "A"));
        Stats.Hourly h = Stats.hourly(l);
        assertEquals(2, h.count[20]);
        assertEquals(40, h.avgPerHour[20], 1e-9);
        assertEquals(20, Stats.bestHour(h, 2));
        assertEquals(-1, Stats.bestHour(Stats.hourly(new ArrayList<>()), 2));
    }

    @Test public void categoriasPorKm() {
        assertEquals(0, Stats.category(1.29, 1.30, 1.60));
        assertEquals(0, Stats.category(1.294, 1.30, 1.60));
        assertEquals(1, Stats.category(1.30, 1.30, 1.60));
        assertEquals(1, Stats.category(1.59, 1.30, 1.60));
        assertEquals(2, Stats.category(1.60, 1.30, 1.60));
        assertEquals(2, Stats.category(1.596, 1.30, 1.60)); // aparece como R$ 1,60
        assertEquals(2, Stats.category(2.05, 1.30, 1.60));
    }
}
