package br.local.corridacerta;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Lê o texto bruto do card da Uber/99 e calcula R$/km e R$/hora. Java puro (testável sem Android). */
public final class OfferParser {
    private OfferParser() {}

    public static final class Offer {
        public final double value, pickupKm, tripKm, pickupMin, tripMin;
        public final boolean bundle;

        Offer(double value, double pickupKm, double pickupMin, double tripKm, double tripMin, boolean bundle) {
            this.value = value; this.pickupKm = pickupKm; this.pickupMin = pickupMin;
            this.tripKm = tripKm; this.tripMin = tripMin; this.bundle = bundle;
        }
        public double totalKm() { return pickupKm + tripKm; }
        public double totalMin() { return pickupMin + tripMin; }
        public double perKm() { return totalKm() > 0 ? value / totalKm() : 0; }
        public double perHour() { return totalMin() > 0 ? value / totalMin() * 60.0 : 0; }
    }

    // R$ 20,08 | R$14,80 | R$ 1.234,56 — ignora "R$2,21/km" e "R$30,62/hr" (valores já calculados por outros apps)
    private static final Pattern MONEY = Pattern.compile(
            "R\\$\\s*([0-9]{1,3}(?:\\.[0-9]{3})*,[0-9]{2}|[0-9]+,[0-9]{2})(?![0-9,])(?!\\s*/)");
    // "4 min (1.1 km)", "34 minutos (11.2 km)", "10min (1,8km)", "1 h 5 min (30 km)", "2 min (350 m)"
    private static final Pattern LEG = Pattern.compile(
            "(?i)(?:([0-9]+)\\s*h(?:oras?)?\\s*)?([0-9]+)\\s*min(?:utos?)?\\s*\\(\\s*([0-9]+(?:[.,][0-9]+)?)\\s*(km|m)\\s*\\)");
    private static final Pattern HOURS_ONLY = Pattern.compile(
            "(?i)([0-9]+)\\s*h(?:oras?)?\\s*\\(\\s*([0-9]+(?:[.,][0-9]+)?)\\s*(km|m)\\s*\\)");

    public static Offer parse(String text) {
        if (text == null) return null;
        Matcher m = MONEY.matcher(text);
        if (!m.find()) return null;
        double value = Double.parseDouble(m.group(1).replace(".", "").replace(',', '.'));

        List<double[]> legs = new ArrayList<>(); // {min, km}
        Matcher l = LEG.matcher(text);
        while (l.find()) {
            double min = Double.parseDouble(l.group(2)) + (l.group(1) != null ? Double.parseDouble(l.group(1)) * 60 : 0);
            legs.add(new double[]{min, km(l.group(3), l.group(4))});
        }
        if (legs.isEmpty()) {
            Matcher h = HOURS_ONLY.matcher(text);
            while (h.find()) legs.add(new double[]{Double.parseDouble(h.group(1)) * 60, km(h.group(2), h.group(3))});
        }
        if (legs.isEmpty()) return null;

        boolean bundle = text.toLowerCase().contains("pacote de viagens")
                || text.matches("(?s).*Aceitar\\s+[2-9]\\s+viagens.*");
        double[] trip = legs.get(legs.size() - 1);
        double[] pickup = legs.size() >= 2 ? legs.get(0) : new double[]{0, 0};
        return new Offer(value, pickup[1], pickup[0], trip[1], trip[0], bundle);
    }

    private static double km(String n, String unit) {
        double v = Double.parseDouble(n.replace(',', '.'));
        return unit.equalsIgnoreCase("m") ? v / 1000.0 : v;
    }
}
