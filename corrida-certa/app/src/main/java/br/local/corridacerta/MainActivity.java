package br.local.corridacerta;

import android.app.Activity;
import android.content.ComponentName;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import java.util.Locale;

public class MainActivity extends Activity {
    private static final int BG = Color.parseColor("#0F1419");
    private static final int CARD = Color.parseColor("#1A2129");
    private static final int FIELD = Color.parseColor("#252F3A");
    private static final int GREEN = Color.parseColor("#22C55E");
    private static final int RED = Color.parseColor("#EF4444");
    private static final int AMBER = Color.parseColor("#F59E0B");
    private static final int TEXT = Color.parseColor("#F3F4F6");
    private static final int MUTED = Color.parseColor("#9CA3AF");

    private Settings s;
    private LinearLayout statusCard;
    private TextView statusTitle, statusSub, lastResult, lastRaw, diagText;
    private android.widget.FrameLayout content;
    private ScrollView homeView, historyView;
    private LinearLayout historyList;
    private Button tabDash, tabHistory, tabTools;
    private ScrollView dashView;
    private LinearLayout dashBox;
    private int period = 0, dashPlat = 0, curTab = 0;
    private org.osmdroid.views.MapView mapView;
    private String filter = null; // null = todos
    private long expandedId = -1;
    private Button activate;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        s = new Settings(this);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);

        ScrollView sv = new ScrollView(this);
        sv.setBackgroundColor(BG);
        sv.setFillViewport(true);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(18), dp(36), dp(18), dp(28));
        sv.addView(root);

        // Cabeçalho
        String ver = "?";
        try { ver = getPackageManager().getPackageInfo(getPackageName(), 0).versionName; } catch (Exception ignored) {}
        root.addView(label("Corrida Certa  v" + ver, 28, TEXT, true));
        root.addView(label("Veja R$/km e R$/hora de cada corrida da Uber e da 99, antes de aceitar.", 14, MUTED, false));
        space(root, 18);

        // Status do serviço
        statusCard = card(root);
        statusTitle = label("", 20, TEXT, true);
        statusSub = label("", 14, MUTED, false);
        statusCard.addView(statusTitle);
        statusCard.addView(statusSub);
        activate = button("Ativar agora", GREEN, Color.parseColor("#06260F"));
        activate.setOnClickListener(v -> startActivity(new Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        statusCard.addView(activate, lp(12));
        statusCard.addView(label("Em Acessibilidade > Apps instalados > Corrida Certa > Ligar.\nSe estiver bloqueado: Info do app > ⋮ > Permitir configurações restritas.", 12, MUTED, false), lp(10));
        space(root, 14);

        LinearLayout dataCard = card(root);
        dataCard.addView(label("Seus dados", 18, TEXT, true));
        dataCard.addView(label("Histórico, prints e endereços ficam só neste aparelho. A internet é usada apenas para as imagens do mapa e para achar a posição do NOME do bairro; endereços completos, valores e dados de passageiros nunca saem do celular.", 12, MUTED, false));
        Button clear = button("Apagar dados capturados", FIELD, TEXT);
        clear.setOnClickListener(v -> { s.clearTrips(); new Store(this).clear(); Store.deleteAllPrints(this); onResume(); Toast.makeText(this, "Dados apagados", Toast.LENGTH_SHORT).show(); });
        dataCard.addView(clear, lp(12));
        space(root, 14);
        // Metas
        LinearLayout goals = card(root);
        goals.addView(label("Suas metas", 18, TEXT, true));
        goals.addView(label("Corrida boa (verde), média (laranja) ou ruim (vermelha), pelo R$/km.", 12, MUTED, false));
        Switch sw = new Switch(this);
        sw.setText("Mostrar cartão sobre as corridas");
        sw.setTextColor(TEXT);
        sw.setChecked(s.enabled());
        sw.setThumbTintList(ColorStateList.valueOf(GREEN));
        sw.setTrackTintList(ColorStateList.valueOf(Color.parseColor("#3B4856")));
        sw.setOnCheckedChangeListener((v, on) -> s.setEnabled(on));
        goals.addView(sw, lp(14));
        Switch sb = new Switch(this);
        sb.setText("Botões de atalho: aceitar / recusar");
        sb.setTextColor(TEXT);
        sb.setChecked(s.buttons());
        sb.setThumbTintList(ColorStateList.valueOf(GREEN));
        sb.setTrackTintList(ColorStateList.valueOf(Color.parseColor("#3B4856")));
        sb.setOnCheckedChangeListener((v, on) -> s.setButtons(on));
        goals.addView(sb, lp(10));

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        EditText bad = field(String.format(Locale.US, "%.2f", s.badBelowKm()));
        EditText good = field(String.format(Locale.US, "%.2f", s.goodFromKm()));
        row.addView(fieldBox("Ruim: abaixo de R$/km", bad), new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        space(row, 12, true);
        row.addView(fieldBox("Boa: a partir de R$/km", good), new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        goals.addView(row, lp(14));
        goals.addView(label("Entre os dois valores a corrida é média (laranja).", 12, MUTED, false), lp(6));
        EditText hr = field(String.format(Locale.US, "%.2f", s.minPerHour()));
        goals.addView(fieldBox("Meta R$/hora (usada no gráfico por horário)", hr), lp(12));

        Button save = button("Salvar metas", GREEN, Color.parseColor("#06260F"));
        save.setOnClickListener(v -> {
            try {
                double b = Double.parseDouble(bad.getText().toString().replace(',', '.'));
                double g = Double.parseDouble(good.getText().toString().replace(',', '.'));
                if (b > g) { Toast.makeText(this, "O valor de \"ruim\" deve ser menor que o de \"boa\"", Toast.LENGTH_LONG).show(); return; }
                s.save(b, g, Double.parseDouble(hr.getText().toString().replace(',', '.')));
                Toast.makeText(this, "Metas salvas", Toast.LENGTH_SHORT).show();
            } catch (NumberFormatException e) {
                Toast.makeText(this, "Valor inválido", Toast.LENGTH_SHORT).show();
            }
        });
        goals.addView(save, lp(16));
        space(root, 14);

        space(root, 14);
        // Diagnóstico: escondido por padrão, expande ao tocar
        LinearLayout dg = card(root);
        Button dgToggle = button("Diagnóstico (avançado)  ▾", FIELD, TEXT);
        dg.addView(dgToggle);
        LinearLayout dgBody = new LinearLayout(this);
        dgBody.setOrientation(LinearLayout.VERTICAL);
        dgBody.setVisibility(View.GONE);
        dg.addView(dgBody);
        dgToggle.setOnClickListener(v -> {
            boolean open = dgBody.getVisibility() == View.GONE;
            dgBody.setVisibility(open ? View.VISIBLE : View.GONE);
            dgToggle.setText(open ? "Diagnóstico (avançado)  ▴" : "Diagnóstico (avançado)  ▾");
        });
        diagText = label("", 11, MUTED, false);
        dgBody.addView(diagText, lp(12));
        Button copy = button("Copiar diagnóstico", FIELD, TEXT);
        copy.setOnClickListener(v -> {
            android.content.ClipboardManager cm = (android.content.ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            cm.setPrimaryClip(android.content.ClipData.newPlainText("diagnostico", diagText.getText()));
            Toast.makeText(this, "Copiado. Cole na conversa.", Toast.LENGTH_SHORT).show();
        });
        dgBody.addView(copy, lp(12));
        dgBody.addView(label("Última corrida lida", 15, TEXT, true), lp(14));
        lastResult = label("", 14, TEXT, false);
        dgBody.addView(lastResult, lp(4));
        Button toggle = button("Ver texto capturado", FIELD, TEXT);
        lastRaw = label("", 11, MUTED, false);
        lastRaw.setVisibility(View.GONE);
        toggle.setOnClickListener(v -> lastRaw.setVisibility(lastRaw.getVisibility() == View.GONE ? View.VISIBLE : View.GONE));
        dgBody.addView(toggle, lp(10));
        dgBody.addView(lastRaw, lp(8));
        space(root, 14);

        homeView = sv; // aba Ferramentas
        buildHistory();
        buildDash();

        LinearLayout outer = new LinearLayout(this);
        outer.setOrientation(LinearLayout.VERTICAL);
        outer.setBackgroundColor(BG);
        content = new android.widget.FrameLayout(this);
        outer.addView(content, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        LinearLayout nav = new LinearLayout(this);
        nav.setOrientation(LinearLayout.HORIZONTAL);
        nav.setBackgroundColor(CARD);
        nav.setPadding(dp(10), dp(8), dp(10), dp(8));
        tabDash = tab("Início", 0);
        tabHistory = tab("Histórico", 1);
        tabTools = tab("Ferramentas", 2);
        for (Button x : new Button[]{tabDash, tabHistory, tabTools}) {
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1);
            lp.rightMargin = dp(4);
            nav.addView(x, lp);
        }
        outer.addView(nav);
        setContentView(outer);
        showTab(0);
    }

    private Button tab(String name, int idx) {
        Button b = button(name, CARD, MUTED);
        b.setMinHeight(dp(44));
        b.setTextSize(14);
        b.setOnClickListener(v -> showTab(idx));
        return b;
    }

    private void showTab(int idx) {
        curTab = idx;
        content.removeAllViews();
        content.addView(idx == 0 ? dashView : idx == 1 ? historyView : homeView);
        Button[] all = {tabDash, tabHistory, tabTools};
        for (int i = 0; i < 3; i++) {
            all[i].setBackground(rounded(i == idx ? FIELD : CARD, 14, 0));
            all[i].setTextColor(i == idx ? GREEN : MUTED);
        }
        if (idx == 0) refreshDash();
        if (idx == 1) refreshHistory();
    }

    // ---- Início: painel de regiões e horários ----
    private void buildDash() {
        dashView = new ScrollView(this);
        dashView.setBackgroundColor(BG);
        dashBox = new LinearLayout(this);
        dashBox.setOrientation(LinearLayout.VERTICAL);
        dashBox.setPadding(dp(18), dp(36), dp(18), dp(18));
        dashView.addView(dashBox);
    }

    private LinearLayout chips(String[] names, int sel, java.util.function.IntConsumer on) {
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        for (int i = 0; i < names.length; i++) {
            Button c = button(names[i], i == sel ? GREEN : FIELD, i == sel ? Color.parseColor("#06260F") : TEXT);
            c.setMinHeight(dp(40));
            c.setTextSize(14);
            final int idx = i;
            c.setOnClickListener(v -> on.accept(idx));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1);
            lp.rightMargin = dp(8);
            row.addView(c, lp);
        }
        return row;
    }

    private void refreshDash() {
        dashBox.removeAllViews();
        dashBox.addView(label("Porto Alegre", 26, TEXT, true));
        dashBox.addView(label("Ofertas lidas pelo Corrida Certa (aceitas ou não): onde e quando mais aparecem corridas.", 13, MUTED, false));

        // Destino do passageiro
        String dest = currentDest();
        LinearLayout dc = card(dashBox);
        ((LinearLayout.LayoutParams) dc.getLayoutParams()).topMargin = dp(14);
        boolean hasAcc = !s.acceptedDest().isEmpty() && s.acceptedAt() >= s.lastOfferAt() - 120000;
        dc.addView(label(hasAcc ? "Destino do passageiro (corrida aceita)" : "Destino da última oferta vista", 15, TEXT, true));
        dc.addView(label(dest.isEmpty() ? "Nenhuma corrida lida ainda." : dest, 14, MUTED, false), lp(4));
        if (!dest.isEmpty()) {
            Button mb = button("Abrir no Google Maps", GREEN, Color.parseColor("#06260F"));
            mb.setOnClickListener(v -> openMaps());
            dc.addView(mb, lp(10));
        }

        dashBox.addView(chips(new String[]{"Hoje", "7 dias", "30 dias"}, period, i -> { period = i; refreshDash(); }), lp(14));
        dashBox.addView(chips(new String[]{"Todos", "99", "Uber"}, dashPlat, i -> { dashPlat = i; refreshDash(); }), lp(8));

        long now = System.currentTimeMillis();
        long since;
        if (period == 0) {
            java.util.Calendar c = java.util.Calendar.getInstance();
            c.set(java.util.Calendar.HOUR_OF_DAY, 0); c.set(java.util.Calendar.MINUTE, 0); c.set(java.util.Calendar.SECOND, 0); c.set(java.util.Calendar.MILLISECOND, 0);
            since = c.getTimeInMillis();
        } else since = now - (period == 1 ? 7L : 30L) * 86400000L;
        String plat = dashPlat == 0 ? null : dashPlat == 1 ? "99" : "Uber";
        java.util.List<Store.Row> rows = new Store(this).list(plat, since, 20000);
        java.util.List<Stats.Sample> samples = new java.util.ArrayList<>();
        double sv = 0, sk = 0, sh = 0;
        for (Store.Row r : rows) {
            samples.add(new Stats.Sample(r.at, r.platform, r.value, r.perKm(), r.perHour(), r.pickupRegion));
            sv += r.value; sk += r.perKm(); sh += r.perHour();
        }
        int n = rows.size();

        // resumo
        LinearLayout tiles = new LinearLayout(this);
        tiles.setOrientation(LinearLayout.HORIZONTAL);
        String[][] tl = {{String.valueOf(n), "ofertas"}, {n == 0 ? "-" : money(sv / n), "valor médio"}, {n == 0 ? "-" : money(sh / n), "R$/h médio"}, {n == 0 ? "-" : money(sk / n), "R$/km médio"}};
        for (String[] x : tl) {
            LinearLayout b = new LinearLayout(this);
            b.setOrientation(LinearLayout.VERTICAL);
            b.setGravity(Gravity.CENTER);
            b.setPadding(dp(4), dp(10), dp(4), dp(10));
            b.setBackground(rounded(CARD, 12, 0));
            b.addView(label(x[0], 17, TEXT, true));
            b.addView(label(x[1], 11, MUTED, false));
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1);
            lp.rightMargin = dp(6);
            tiles.addView(b, lp);
        }
        dashBox.addView(tiles, lp(14));

        if (n == 0) {
            dashBox.addView(label("Ainda não há ofertas neste período. Elas aparecem aqui quando chegarem na Uber ou na 99.", 14, MUTED, false), lp(16));
            return;
        }

        // regiões mais movimentadas (bairro de embarque)
        java.util.List<Stats.RegionStat> regs = Stats.regions(samples);

        // mapa de calor por bairro
        LinearLayout mc = card(dashBox);
        ((LinearLayout.LayoutParams) mc.getLayoutParams()).topMargin = dp(14);
        mc.addView(label("Mapa de calor", 18, TEXT, true));
        mc.addView(label("Bolhas maiores e mais quentes (azul > laranja > vermelho) = mais ofertas no bairro de embarque. Posição aproximada pelo nome do bairro.", 12, MUTED, false));
        buildMap(mc, regs);
        LinearLayout rc = card(dashBox);
        ((LinearLayout.LayoutParams) rc.getLayoutParams()).topMargin = dp(14);
        rc.addView(label("Regiões mais movimentadas", 18, TEXT, true));
        rc.addView(label("Bairro de onde sai a corrida (embarque). Cor pelo R$/km médio: verde = boa, laranja = média, vermelha = ruim.", 12, MUTED, false));
        if (regs.isEmpty()) rc.addView(label("Os endereços de embarque ainda não foram lidos nestas ofertas.", 13, MUTED, false), lp(8));
        int max = regs.isEmpty() ? 1 : regs.get(0).count;
        for (int i = 0; i < Math.min(10, regs.size()); i++) {
            Stats.RegionStat r = regs.get(i);
            int rc2 = s.category(r.avgPerKm);
            int col = rc2 == 2 ? GREEN : (rc2 == 1 ? AMBER : RED);
            rc.addView(label((i + 1) + ". " + r.name + "  ·  " + r.count + (r.count == 1 ? " oferta" : " ofertas"), 14, TEXT, true), lp(12));
            LinearLayout bar = new LinearLayout(this);
            bar.setOrientation(LinearLayout.HORIZONTAL);
            View fill = new View(this);
            fill.setBackground(rounded(col, 6, 0));
            View rest = new View(this);
            bar.addView(fill, new LinearLayout.LayoutParams(0, dp(8), Math.max(1, r.count * 100f / max)));
            bar.addView(rest, new LinearLayout.LayoutParams(0, dp(8), Math.max(0, 100f - r.count * 100f / max)));
            rc.addView(bar, lp(4));
            rc.addView(label(money(r.avgValue) + " por oferta · " + money(r.avgPerKm) + "/km · " + money(r.avgPerHour) + "/h", 12, MUTED, false), lp(2));
        }

        // tendência por horário
        Stats.Hourly h = Stats.hourly(samples);
        LinearLayout hc = card(dashBox);
        ((LinearLayout.LayoutParams) hc.getLayoutParams()).topMargin = dp(14);
        hc.addView(label("Tendência por horário", 18, TEXT, true));
        hc.addView(label("Altura = quantidade de ofertas. Verde = R$/h acima da meta; laranja = perto.", 12, MUTED, false));
        int best = Stats.bestHour(h, 2);
        if (best >= 0) {
            TextView bt = label(String.format(Locale.US, "Melhor horário: das %02d:00 às %02d:00 (R$ %.2f/h médio)", best, (best + 1) % 24, h.avgPerHour[best]).replace('.', ','), 14, GREEN, true);
            hc.addView(bt, lp(8));
        }
        int curH = java.util.Calendar.getInstance().get(java.util.Calendar.HOUR_OF_DAY);
        int maxC = 1;
        for (int i = 0; i < 24; i++) maxC = Math.max(maxC, h.count[i]);
        android.widget.HorizontalScrollView hs = new android.widget.HorizontalScrollView(this);
        hs.setHorizontalScrollBarEnabled(false);
        LinearLayout cols = new LinearLayout(this);
        cols.setOrientation(LinearLayout.HORIZONTAL);
        for (int i = 0; i < 24; i++) {
            LinearLayout col = new LinearLayout(this);
            col.setOrientation(LinearLayout.VERTICAL);
            col.setGravity(Gravity.CENTER_HORIZONTAL | Gravity.BOTTOM);
            TextView cnt = label(h.count[i] == 0 ? "" : String.valueOf(h.count[i]), 12, TEXT, true);
            cnt.setGravity(Gravity.CENTER);
            col.addView(cnt, new LinearLayout.LayoutParams(dp(34), ViewGroup.LayoutParams.WRAP_CONTENT));
            int bh = h.count[i] == 0 ? dp(3) : Math.max(dp(8), Math.round(dp(110) * h.count[i] / (float) maxC));
            int col2 = h.count[i] == 0 ? FIELD : (h.avgPerHour[i] >= s.minPerHour() ? GREEN : (h.avgPerHour[i] >= s.minPerHour() * 0.8 ? AMBER : Color.parseColor("#5B6B7C")));
            View bar = new View(this);
            bar.setBackground(rounded(col2, 6, 0));
            LinearLayout.LayoutParams blp = new LinearLayout.LayoutParams(dp(22), bh);
            blp.topMargin = dp(4);
            col.addView(bar, blp);
            TextView hl = label(i == curH ? i + "h\nagora" : i + "h", 11, i == curH ? GREEN : MUTED, i == curH);
            hl.setGravity(Gravity.CENTER);
            col.addView(hl, new LinearLayout.LayoutParams(dp(34), ViewGroup.LayoutParams.WRAP_CONTENT));
            cols.addView(col, new LinearLayout.LayoutParams(dp(38), dp(110) + dp(60)));
        }
        hs.addView(cols);
        hc.addView(hs, lp(10));
    }

    private void buildMap(LinearLayout parent, java.util.List<Stats.RegionStat> regs) {
        org.osmdroid.config.IConfigurationProvider cfg = org.osmdroid.config.Configuration.getInstance();
        cfg.setUserAgentValue(getPackageName());
        cfg.setOsmdroidBasePath(new java.io.File(getCacheDir(), "osmdroid"));
        cfg.setOsmdroidTileCache(new java.io.File(getCacheDir(), "osmdroid/tiles"));
        if (mapView != null) { mapView.onDetach(); }
        org.osmdroid.views.MapView mv = new org.osmdroid.views.MapView(this);
        mapView = mv;
        mv.setTileSource(org.osmdroid.tileprovider.tilesource.TileSourceFactory.MAPNIK);
        mv.setMultiTouchControls(true);
        mv.setOnTouchListener((v, e) -> { v.getParent().requestDisallowInterceptTouchEvent(true); return false; });
        LinearLayout.LayoutParams mlp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(340));
        mlp.topMargin = dp(10);
        parent.addView(mv, mlp);

        Store st = new Store(this);
        java.util.List<double[]> pts = new java.util.ArrayList<>();
        java.util.List<String> names = new java.util.ArrayList<>();
        java.util.List<String> need = new java.util.ArrayList<>();
        int max = regs.isEmpty() ? 1 : regs.get(0).count;
        for (int i = 0; i < Math.min(40, regs.size()); i++) {
            Stats.RegionStat r = regs.get(i);
            String key = r.name.toLowerCase(Locale.ROOT);
            double[] g = st.geoRow(key);
            if (g == null) { need.add(key); continue; }
            if (g[0] > 900) continue;
            pts.add(new double[]{g[0], g[1], r.count / (double) max, r.count});
            names.add(r.name);
        }
        mv.getOverlays().add(new HeatOverlay(pts, names));
        mv.getController().setZoom(11.5);
        mv.getController().setCenter(new org.osmdroid.util.GeoPoint(-30.0346, -51.2177));
        if (pts.size() == 1) {
            mv.getController().setZoom(14.0);
            mv.getController().setCenter(new org.osmdroid.util.GeoPoint(pts.get(0)[0], pts.get(0)[1]));
        } else if (pts.size() > 1) {
            java.util.List<org.osmdroid.util.GeoPoint> gp = new java.util.ArrayList<>();
            for (double[] p : pts) gp.add(new org.osmdroid.util.GeoPoint(p[0], p[1]));
            mv.post(() -> mv.zoomToBoundingBox(org.osmdroid.util.BoundingBox.fromGeoPoints(gp), false, dp(50)));
        }
        parent.addView(label(need.isEmpty() ? "Mapa © colaboradores do OpenStreetMap" : "Localizando bairros no mapa… (precisa de internet)  ·  Mapa © colaboradores do OpenStreetMap", 11, MUTED, false), lp(6));
        Geo.resolve(this, need, () -> { if (curTab == 0) refreshDash(); });
    }

    /** Desenha uma bolha de calor por bairro. */
    private class HeatOverlay extends org.osmdroid.views.overlay.Overlay {
        private final java.util.List<double[]> pts;
        private final java.util.List<String> names;
        private final android.graphics.Paint paint = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        private final android.graphics.Paint text = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);

        HeatOverlay(java.util.List<double[]> pts, java.util.List<String> names) {
            this.pts = pts; this.names = names;
            text.setColor(Color.WHITE);
            text.setTextSize(dp(11));
            text.setTextAlign(android.graphics.Paint.Align.CENTER);
            text.setFakeBoldText(true);
            text.setShadowLayer(dp(3), 0, 0, Color.BLACK);
        }

        private int heat(double w) {
            int a = Color.parseColor("#3B82F6"), b = Color.parseColor("#F59E0B"), c = Color.parseColor("#EF4444");
            return w < 0.5 ? mix(a, b, w * 2) : mix(b, c, (w - 0.5) * 2);
        }

        private int mix(int x, int y, double f) {
            return Color.rgb((int) (Color.red(x) + (Color.red(y) - Color.red(x)) * f),
                    (int) (Color.green(x) + (Color.green(y) - Color.green(x)) * f),
                    (int) (Color.blue(x) + (Color.blue(y) - Color.blue(x)) * f));
        }

        @Override public void draw(android.graphics.Canvas c, org.osmdroid.views.MapView mv, boolean shadow) {
            if (shadow) return;
            org.osmdroid.views.Projection proj = mv.getProjection();
            for (int i = 0; i < pts.size(); i++) {
                double[] p = pts.get(i);
                android.graphics.Point pt = proj.toPixels(new org.osmdroid.util.GeoPoint(p[0], p[1]), null);
                float r = dp(26) + dp(34) * (float) p[2];
                int col = heat(p[2]);
                paint.setShader(new android.graphics.RadialGradient(pt.x, pt.y, r,
                        Color.argb(200, Color.red(col), Color.green(col), Color.blue(col)),
                        Color.argb(0, Color.red(col), Color.green(col), Color.blue(col)), android.graphics.Shader.TileMode.CLAMP));
                c.drawCircle(pt.x, pt.y, r, paint);
                c.drawText(names.get(i) + " · " + (int) p[3], pt.x, pt.y + dp(4), text);
            }
        }
    }

    @Override protected void onPause() { super.onPause(); if (mapView != null) mapView.onPause(); }

    private static String money(double v) { return String.format(Locale.US, "R$ %.2f", v).replace('.', ','); }

    // ---- Histórico de ofertas ----
    private void buildHistory() {
        historyView = new ScrollView(this);
        historyView.setBackgroundColor(BG);
        LinearLayout h = new LinearLayout(this);
        h.setOrientation(LinearLayout.VERTICAL);
        h.setPadding(dp(18), dp(36), dp(18), dp(18));
        historyView.addView(h);
        h.addView(label("Histórico de Ofertas", 26, TEXT, true));

        LinearLayout chips = new LinearLayout(this);
        chips.setOrientation(LinearLayout.HORIZONTAL);
        String[][] f = {{"Todos", null}, {"99", "99"}, {"Uber", "Uber"}};
        for (String[] x : f) {
            Button c = button(x[0], FIELD, TEXT);
            c.setMinHeight(dp(40));
            c.setTextSize(14);
            final String val = x[1];
            c.setOnClickListener(v -> { filter = val; expandedId = -1; refreshHistory(); });
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1);
            lp.rightMargin = dp(8);
            chips.addView(c, lp);
        }
        h.addView(chips, lp(12));
        historyList = new LinearLayout(this);
        historyList.setOrientation(LinearLayout.VERTICAL);
        h.addView(historyList, lp(12));
    }

    private void refreshHistory() {
        historyList.removeAllViews();
        java.util.List<Store.Row> rows = new Store(this).list(filter, 200);
        if (rows.isEmpty()) {
            historyList.addView(label("Nenhuma oferta lida ainda. Elas aparecem aqui quando chegam na Uber ou na 99.", 14, MUTED, false));
            return;
        }
        for (Store.Row r : rows) historyList.addView(historyRow(r), lp(10));
    }

    private View historyRow(Store.Row r) {
        int cat = s.category(r.perKm());
        int dot = cat == 2 ? GREEN : (cat == 0 ? RED : AMBER);
        boolean open = r.id == expandedId;

        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(14), dp(12), dp(14), dp(12));
        box.setBackground(rounded(CARD, 16, open ? dot : 0));

        LinearLayout top = new LinearLayout(this);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        TextView badge = label(r.platform.equals("99") ? "99" : "Uber", 14, r.platform.equals("99") ? Color.BLACK : Color.WHITE, true);
        badge.setGravity(Gravity.CENTER);
        badge.setBackground(rounded(r.platform.equals("99") ? Color.parseColor("#FFD400") : Color.parseColor("#000000"), 24, r.platform.equals("99") ? 0 : MUTED));
        top.addView(badge, new LinearLayout.LayoutParams(dp(52), dp(52)));

        LinearLayout mid = new LinearLayout(this);
        mid.setOrientation(LinearLayout.VERTICAL);
        mid.setPadding(dp(12), 0, dp(8), 0);
        mid.addView(label(String.format(Locale.US, "R$ %.2f", r.value).replace('.', ','), 20, TEXT, true));
        if (!open) mid.addView(label(r.dest.isEmpty() ? "(endereço não lido)" : r.dest, 13, MUTED, false));
        top.addView(mid, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));

        LinearLayout right = new LinearLayout(this);
        right.setOrientation(LinearLayout.VERTICAL);
        right.setGravity(Gravity.END);
        right.addView(label(ago(r.at), 12, MUTED, false));
        right.addView(label((r.accepted ? "✔ aceita  " : "") + "●", 14, dot, true));
        top.addView(right);
        box.addView(top);

        if (open) {
            box.addView(label(new java.text.SimpleDateFormat("d 'de' MMMM 'de' yyyy, HH:mm", new Locale("pt", "BR")).format(new java.util.Date(r.at)), 13, MUTED, false), lp(6));
            LinearLayout chips = new LinearLayout(this);
            chips.setOrientation(LinearLayout.HORIZONTAL);
            String[] v = {String.format(Locale.US, "R$ %.2f/km", r.perKm()), String.format(Locale.US, "R$ %.2f/h", r.perHour()), String.format(Locale.US, "R$ %.2f/min", r.perMin())};
            for (String x : v) {
                TextView c = label(x.replace('.', ','), 13, TEXT, true);
                c.setGravity(Gravity.CENTER);
                c.setBackground(rounded(FIELD, 10, 0));
                c.setPadding(dp(4), dp(10), dp(4), dp(10));
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1);
                lp.rightMargin = dp(6);
                chips.addView(c, lp);
            }
            box.addView(chips, lp(12));
            box.addView(label(String.format(Locale.US, "%.0f minutos e %.1f km para o embarque", r.pickupMin, r.pickupKm).replace('.', ','), 14, TEXT, false), lp(12));
            box.addView(label(String.format(Locale.US, "%.0f minutos e %.1f km para o desembarque", r.tripMin, r.tripKm).replace('.', ','), 14, TEXT, false), lp(4));
            if (!r.dest.isEmpty()) {
                box.addView(label(r.dest, 15, TEXT, true), lp(10));
            }
            LinearLayout btns = new LinearLayout(this);
            btns.setOrientation(LinearLayout.HORIZONTAL);
            Button maps = button("Google Maps", GREEN, Color.parseColor("#06260F"));
            maps.setTextSize(15);
            maps.setEnabled(!r.dest.isEmpty());
            maps.setAlpha(r.dest.isEmpty() ? 0.4f : 1f);
            maps.setOnClickListener(x -> openMapsTo(r.dest));
            boolean hasPrint = Store.printFile(this, r.id).exists();
            Button print = button("Ver print", FIELD, TEXT);
            print.setTextSize(15);
            print.setEnabled(hasPrint);
            print.setAlpha(hasPrint ? 1f : 0.4f);
            print.setOnClickListener(x -> showPrint(r));
            LinearLayout.LayoutParams l1 = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1);
            l1.rightMargin = dp(8);
            btns.addView(maps, l1);
            btns.addView(print, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
            box.addView(btns, lp(12));
        }
        box.setOnClickListener(x -> { expandedId = open ? -1 : r.id; refreshHistory(); });
        return box;
    }

    private void showPrint(Store.Row r) {
        android.graphics.Bitmap bmp = android.graphics.BitmapFactory.decodeFile(Store.printFile(this, r.id).getAbsolutePath());
        if (bmp == null) { Toast.makeText(this, "Print não encontrado", Toast.LENGTH_SHORT).show(); return; }
        android.app.Dialog d = new android.app.Dialog(this, android.R.style.Theme_Black_NoTitleBar_Fullscreen);
        android.widget.ImageView iv = new android.widget.ImageView(this);
        iv.setBackgroundColor(Color.BLACK);
        iv.setImageBitmap(bmp);
        iv.setScaleType(android.widget.ImageView.ScaleType.FIT_CENTER);
        iv.setOnClickListener(v -> d.dismiss());
        d.setContentView(iv);
        d.show();
    }

    private static String ago(long at) {
        long m = (System.currentTimeMillis() - at) / 60000;
        if (m < 1) return "agora";
        if (m < 60) return m + " min atrás";
        if (m < 1440) return (m / 60) + " h atrás";
        return (m / 1440) + " d atrás";
    }

    @Override protected void onResume() {
        super.onResume();
        if (mapView != null) mapView.onResume();
        boolean on = serviceEnabled();
        statusCard.setBackground(rounded(CARD, 18, on ? GREEN : RED));
        statusTitle.setText(on ? "● Ativo" : "● Desativado");
        statusTitle.setTextColor(on ? GREEN : RED);
        statusSub.setText(on ? "Abra a Uber ou a 99 e aguarde uma corrida. O cartão aparece no topo da tela."
                             : "Ligue o serviço de acessibilidade para o app conseguir ler as corridas.");
        activate.setVisibility(on ? View.GONE : View.VISIBLE);
        if (curTab == 1) refreshHistory();
        if (curTab == 0) refreshDash();
        lastResult.setText(s.lastResult());
        diagText.setText("Serviço ligado no Android: " + (on ? "sim" : "NÃO") + "\n" + s.diag());
        String raw = s.lastRaw();
        lastRaw.setText(raw.isEmpty() ? "(nada capturado ainda)" : raw);
    }

    private String currentDest() {
        boolean hasAcc = !s.acceptedDest().isEmpty() && s.acceptedAt() >= s.lastOfferAt() - 120000;
        return hasAcc ? s.acceptedDest() : s.lastOfferDest();
    }

    private void openMaps() { openMapsTo(currentDest()); }

    private void openMapsTo(String dest) {
        if (dest == null || dest.isEmpty()) return;
        android.net.Uri uri = android.net.Uri.parse("https://www.google.com/maps/dir/?api=1&travelmode=driving&destination=" + android.net.Uri.encode(dest));
        Intent i = new Intent(Intent.ACTION_VIEW, uri);
        i.setPackage("com.google.android.apps.maps");
        try { startActivity(i); }
        catch (android.content.ActivityNotFoundException e) { startActivity(new Intent(Intent.ACTION_VIEW, uri)); }
    }

    private boolean serviceEnabled() {
        String enabled = android.provider.Settings.Secure.getString(getContentResolver(),
                android.provider.Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES);
        if (enabled == null) return false;
        String me = new ComponentName(this, OfferService.class).flattenToString();
        String meShort = new ComponentName(this, OfferService.class).flattenToShortString();
        return enabled.contains(me) || enabled.contains(meShort);
    }

    // ---- helpers de UI ----
    private int dp(int v) { return Math.round(v * getResources().getDisplayMetrics().density); }

    private GradientDrawable rounded(int fill, int radiusDp, int strokeColor) {
        GradientDrawable g = new GradientDrawable();
        g.setColor(fill);
        g.setCornerRadius(dp(radiusDp));
        if (strokeColor != 0) g.setStroke(dp(1), strokeColor);
        return g;
    }

    private LinearLayout card(LinearLayout parent) {
        LinearLayout c = new LinearLayout(this);
        c.setOrientation(LinearLayout.VERTICAL);
        c.setPadding(dp(16), dp(16), dp(16), dp(16));
        c.setBackground(rounded(CARD, 18, 0));
        parent.addView(c, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        return c;
    }

    private TextView label(String t, int sp, int color, boolean bold) {
        TextView v = new TextView(this);
        v.setText(t);
        v.setTextSize(sp);
        v.setTextColor(color);
        if (bold) v.setTypeface(v.getTypeface(), Typeface.BOLD);
        v.setPadding(0, dp(2), 0, dp(2));
        return v;
    }

    private Button button(String t, int bg, int fg) {
        Button b = new Button(this);
        b.setText(t);
        b.setAllCaps(false);
        b.setTextSize(16);
        b.setTypeface(b.getTypeface(), Typeface.BOLD);
        b.setTextColor(fg);
        b.setBackground(rounded(bg, 14, 0));
        b.setStateListAnimator(null);
        b.setMinHeight(dp(52));
        b.setGravity(Gravity.CENTER);
        return b;
    }

    private EditText field(String init) {
        EditText e = new EditText(this);
        e.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
        e.setText(init);
        e.setTextColor(TEXT);
        e.setTextSize(20);
        e.setTypeface(e.getTypeface(), Typeface.BOLD);
        e.setBackground(rounded(FIELD, 12, 0));
        e.setPadding(dp(14), dp(12), dp(14), dp(12));
        return e;
    }

    private LinearLayout fieldBox(String title, EditText e) {
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.addView(label(title, 12, MUTED, false));
        box.addView(e);
        return box;
    }

    private LinearLayout.LayoutParams lp(int topDp) {
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        p.topMargin = dp(topDp);
        return p;
    }

    private void space(LinearLayout parent, int dp) { space(parent, dp, false); }

    private void space(LinearLayout parent, int dp, boolean horizontal) {
        View v = new View(this);
        parent.addView(v, horizontal ? new LinearLayout.LayoutParams(dp(dp), 1) : new LinearLayout.LayoutParams(1, dp(dp)));
    }
}
