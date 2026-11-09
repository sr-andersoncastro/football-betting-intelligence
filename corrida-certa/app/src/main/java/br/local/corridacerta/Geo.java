package br.local.corridacerta;

import android.content.Context;
import android.os.Handler;
import android.os.Looper;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.List;

/**
 * Descobre a posição aproximada de um BAIRRO de Porto Alegre pelo nome (Nominatim/OpenStreetMap) e guarda no aparelho.
 * Só o nome do bairro vai para a internet: nenhum endereço completo, valor ou dado de passageiro.
 * Respeita a política do serviço: 1 consulta por segundo, User-Agent identificado e cache.
 */
final class Geo {
    private Geo() {}
    private static boolean running;

    static synchronized void resolve(Context c, List<String> keys, Runnable done) {
        if (running || keys.isEmpty()) return;
        Context app = c.getApplicationContext();
        Store st = new Store(app);
        List<String> todo = new ArrayList<>();
        for (String k : keys) {
            double[] g = st.geoRow(k);
            if (g == null || (g[0] > 900 && System.currentTimeMillis() - g[2] > 86400000L)) todo.add(k);
        }
        if (todo.isEmpty()) return;
        running = true;
        new Thread(() -> {
            boolean any = false;
            try {
                for (String k : todo) {
                    URL u = new URL("https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=br&bounded=1"
                            + "&viewbox=-51.31,-29.92,-51.07,-30.28&q=" + URLEncoder.encode(k + ", Porto Alegre, RS, Brasil", "UTF-8"));
                    HttpURLConnection h = (HttpURLConnection) u.openConnection();
                    h.setRequestProperty("User-Agent", "CorridaCerta/0.8 (app pessoal de motorista)");
                    h.setConnectTimeout(8000);
                    h.setReadTimeout(8000);
                    int code = h.getResponseCode();
                    if (code == 429 || code >= 500) break; // limite do serviço: tenta de novo depois
                    if (code == 200) {
                        StringBuilder sb = new StringBuilder();
                        try (BufferedReader r = new BufferedReader(new InputStreamReader(h.getInputStream(), "UTF-8"))) {
                            String line;
                            while ((line = r.readLine()) != null) sb.append(line);
                        }
                        org.json.JSONArray a = new org.json.JSONArray(sb.toString());
                        if (a.length() > 0) {
                            org.json.JSONObject o = a.getJSONObject(0);
                            st.putGeo(k, Double.parseDouble(o.getString("lat")), Double.parseDouble(o.getString("lon")));
                        } else {
                            st.putGeo(k, 999, 999);
                        }
                        any = true;
                    }
                    Thread.sleep(1100);
                }
            } catch (Exception ignored) {
                // sem internet ou erro: nada é gravado como "não encontrado"; tenta de novo na próxima abertura
            } finally {
                synchronized (Geo.class) { running = false; }
                if (any) new Handler(Looper.getMainLooper()).post(done);
            }
        }).start();
    }
}
