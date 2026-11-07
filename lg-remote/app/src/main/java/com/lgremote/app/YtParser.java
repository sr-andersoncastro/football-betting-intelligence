package com.lgremote.app;

import java.util.ArrayList;
import java.util.List;

/** Extrai (id, título) dos vídeos da página de resultados do YouTube. Java puro, sem dependências do Android. */
public final class YtParser {
    private YtParser() { }

    public static List<String[]> parse(String html, int max) {
        List<String[]> out = new ArrayList<String[]>();
        String marker = "\"videoRenderer\":{\"videoId\":\"";
        int from = 0;
        while (out.size() < max) {
            int i = html.indexOf(marker, from);
            if (i < 0) break;
            int s = i + marker.length();
            from = s;
            if (s + 11 > html.length()) break;
            String id = html.substring(s, s + 11);
            if (!id.matches("[A-Za-z0-9_-]{11}")) continue;
            boolean dup = false;
            for (String[] o : out) if (o[0].equals(id)) dup = true;
            if (dup) continue;
            String tmark = "\"title\":{\"runs\":[{\"text\":\"";
            int t = html.indexOf(tmark, s);
            String title = id;
            if (t >= 0 && t - s < 4000) title = readJsonString(html, t + tmark.length());
            out.add(new String[] { id, title });
        }
        return out;
    }

    /** Lê uma string JSON a partir de start (logo após a aspa de abertura) e a desescapa. */
    static String readJsonString(String s, int start) {
        StringBuilder b = new StringBuilder();
        for (int i = start; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"') break;
            if (c == '\\' && i + 1 < s.length()) {
                char n = s.charAt(++i);
                switch (n) {
                    case 'n': b.append(' '); break;
                    case 't': b.append(' '); break;
                    case 'u':
                        if (i + 4 < s.length()) {
                            try { b.append((char) Integer.parseInt(s.substring(i + 1, i + 5), 16)); } catch (NumberFormatException e) { }
                            i += 4;
                        }
                        break;
                    default: b.append(n);
                }
            } else b.append(c);
        }
        return b.toString();
    }

    /** Lista [{id,title}] como literal JSON seguro para colar em JavaScript. */
    public static String toJson(List<String[]> list) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < list.size(); i++) {
            if (i > 0) sb.append(',');
            sb.append("{\"id\":\"").append(list.get(i)[0]).append("\",\"title\":\"").append(esc(list.get(i)[1])).append("\"}");
        }
        return sb.append(']').toString();
    }

    private static String esc(String s) {
        StringBuilder b = new StringBuilder();
        for (char c : s.toCharArray()) {
            if (c == '"' || c == '\\') b.append('\\').append(c);
            else if (c < 0x20 || c == ' ' || c == ' ') b.append(' ');
            else b.append(c);
        }
        return b.toString();
    }
}
