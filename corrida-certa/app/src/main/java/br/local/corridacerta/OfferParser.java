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
        public final String pickupAddress; // endereço de embarque (pode ser null)
        public final String destination; // endereço da linha logo após o trecho da viagem (pode ser null)

        Offer(double value, double pickupKm, double pickupMin, double tripKm, double tripMin, boolean bundle, String destination, String pickupAddress) {
            this.destination = destination;
            this.pickupAddress = pickupAddress;
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
            "R[$S]\\s*([0-9]{1,3}(?:\\.[0-9]{3})*,[0-9]{2}|[0-9]+,[0-9]{2})(?![0-9,])(?!\\s*/)");
    // "4 min (1.1 km)", "34 minutos (11.2 km)", "10min (1,8km)", "1 h 5 min (30 km)", "2 min (350 m)"
    private static final Pattern LEG = Pattern.compile(
            "(?i)(?:([0-9]+)\\s*h(?:oras?)?\\s*)?([0-9]+)\\s*min(?:utos?)?\\s*[(\\[]\\s*([0-9]+(?:[.,][0-9]+)?)\\s*(km|m)\\s*[)\\]]");
    private static final Pattern HOURS_ONLY = Pattern.compile(
            "(?i)([0-9]+)\\s*h(?:oras?)?\\s*\\(\\s*([0-9]+(?:[.,][0-9]+)?)\\s*(km|m)\\s*\\)");

    public static Offer parse(String text) {
        if (text == null) return null;
        Matcher m = MONEY.matcher(text);
        if (!m.find()) return null;
        double value = Double.parseDouble(m.group(1).replace(".", "").replace(',', '.'));

        List<double[]> legs = new ArrayList<>(); // {min, km}
        Matcher l = LEG.matcher(text);
        int tripEnd = -1, firstEnd = -1, lastStart = -1, nLegs = 0;
        while (l.find()) {
            tripEnd = l.end();
            if (nLegs++ == 0) firstEnd = l.end();
            lastStart = l.start();
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
        return new Offer(value, pickup[1], pickup[0], trip[1], trip[0], bundle, tripEnd < 0 ? null : addressAfter(text, tripEnd),
                nLegs >= 2 ? firstAddress(text.substring(firstEnd, lastStart)) : null);
    }

    private static double km(String n, String unit) {
        double v = Double.parseDouble(n.replace(',', '.'));
        return unit.equalsIgnoreCase("m") ? v / 1000.0 : v;
    }

    private static final Pattern ADDR = Pattern.compile(
            "(?i)^(r\\.?|rua|av\\.?|avenida|tv\\.?|travessa|al\\.?|alameda|estr\\.?|estrada|pra[çc]a|p[çc]a\\.?|rod\\.?|rodovia|largo|beco|servid[ãa]o)\\s+\\S.*|^.*[A-Za-zÀ-ú]\\s*,\\s*[0-9]+.*");

    private static boolean isAddress(String s) {
        return s.length() >= 6 && s.length() <= 140 && !s.contains("R$") && !LEG.matcher(s).find() && ADDR.matcher(s).matches();
    }

    /**
     * Endereço de destino: primeira linha que PARECE endereço depois do trecho da viagem (ignora textos da interface
     * como "Filtro avançado"). Se não houver, usa o último endereço do card quando houver dois. Senão null.
     */
    static String addressAfter(String text, int from) {
        java.util.List<String> lines = new ArrayList<>();
        java.util.List<Integer> starts = new ArrayList<>();
        Matcher m = Pattern.compile("[^\\r\\n]+").matcher(text);
        while (m.find()) { lines.add(m.group().trim()); starts.add(m.start()); }
        // resto da própria linha do trecho ("13 min (4,4 km) Rua X")
        for (int i = 0; i < lines.size(); i++) {
            int end = starts.get(i) + (lines.get(i).isEmpty() ? 0 : text.indexOf(lines.get(i), starts.get(i)) - starts.get(i)) + lines.get(i).length();
            if (starts.get(i) <= from && from <= end + 1) {
                String rem = text.substring(Math.min(from, text.length()), Math.min(end, text.length())).replaceAll("^[\\s,•·-]+", "").trim();
                if (isAddress(rem)) return clean(rem);
                break;
            }
        }
        java.util.List<Integer> cand = new ArrayList<>();
        for (int i = 0; i < lines.size(); i++) if (!lines.get(i).isEmpty() && isAddress(lines.get(i))) cand.add(i);
        for (int i : cand) {
            if (starts.get(i) >= from) return clean(joinWrapped(lines, i));
        }
        if (cand.size() >= 2) return clean(joinWrapped(lines, cand.get(cand.size() - 1)));
        return null;
    }

    /** Junta a linha seguinte quando o endereço termina em vírgula/hífen (quebra de linha do OCR). */
    private static String joinWrapped(java.util.List<String> lines, int i) {
        String a = lines.get(i);
        if ((a.endsWith(",") || a.endsWith("-")) && i + 1 < lines.size() && !lines.get(i + 1).isEmpty()) a = a + " " + lines.get(i + 1);
        return a;
    }

    private static String clean(String a) { return a.replaceAll("[,\\s-]+$", ""); }

    /** Primeiro endereço (linha que parece endereço) dentro de um trecho de texto. */
    static String firstAddress(String segment) {
        java.util.List<String> lines = new ArrayList<>();
        Matcher m = Pattern.compile("[^\\r\\n]+").matcher(segment);
        while (m.find()) lines.add(m.group().trim());
        for (int i = 0; i < lines.size(); i++) if (!lines.get(i).isEmpty() && isAddress(lines.get(i))) return clean(joinWrapped(lines, i));
        return null;
    }

    /** Bairro de um endereço ("Rua X, 12, Nonoai, Porto Alegre" -> "Nonoai"); null se não der para saber. */
    public static String region(String addr) {
        if (addr == null) return null;
        java.util.List<String> ps = new ArrayList<>(java.util.Arrays.asList(addr.trim().split("\\s*,\\s*")));
        while (ps.size() > 1) { // tira cidade/UF/CEP do fim
            String last = ps.get(ps.size() - 1);
            if (last.matches("(?i)porto alegre(\\s*-\\s*rs)?|rs|brasil|[0-9]{5}-?[0-9]{3}.*")) ps.remove(ps.size() - 1); else break;
        }
        String last = ps.get(ps.size() - 1);
        int i = last.lastIndexOf(" - ");
        if (i >= 0) last = last.substring(i + 3);
        last = last.trim();
        if (ps.size() < 2 && i < 0) return null;
        if (last.isEmpty() || Character.isDigit(last.charAt(0)) || last.length() < 3) return null;
        return last;
    }
}
