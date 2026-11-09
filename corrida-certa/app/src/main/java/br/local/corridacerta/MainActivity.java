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
    private TextView statusTitle, statusSub, lastResult, lastRaw, diagText, destTitle, destAddr;
    private Button mapsBtn;
    private android.widget.FrameLayout content;
    private ScrollView homeView, historyView;
    private LinearLayout historyList;
    private Button tabHome, tabHistory;
    private String filter = null; // null = todos
    private long expandedId = -1;
    private boolean onHistory;
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

        LinearLayout dest = card(root);
        destTitle = label("Destino do passageiro", 18, TEXT, true);
        dest.addView(destTitle);
        destAddr = label("", 15, TEXT, false);
        dest.addView(destAddr, lp(6));
        mapsBtn = button("Abrir no Google Maps", GREEN, Color.parseColor("#06260F"));
        mapsBtn.setOnClickListener(v -> openMaps());
        dest.addView(mapsBtn, lp(12));
        Button clear = button("Apagar dados capturados", FIELD, TEXT);
        clear.setOnClickListener(v -> { s.clearTrips(); new Store(this).clear(); onResume(); Toast.makeText(this, "Dados apagados", Toast.LENGTH_SHORT).show(); });
        dest.addView(clear, lp(8));
        space(root, 14);
        LinearLayout dg = card(root);
        dg.addView(label("Diagnóstico", 18, TEXT, true));
        diagText = label("", 11, MUTED, false);
        dg.addView(diagText, lp(8));
        Button copy = button("Copiar diagnóstico", FIELD, TEXT);
        copy.setOnClickListener(v -> {
            android.content.ClipboardManager cm = (android.content.ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
            cm.setPrimaryClip(android.content.ClipData.newPlainText("diagnostico", diagText.getText()));
            Toast.makeText(this, "Copiado. Cole na conversa.", Toast.LENGTH_SHORT).show();
        });
        dg.addView(copy, lp(12));

        space(root, 14);

        // Metas
        LinearLayout goals = card(root);
        goals.addView(label("Suas metas", 18, TEXT, true));
        goals.addView(label("Verde: acima das duas metas · Laranja: abaixo de uma · Vermelho: abaixo das duas.", 12, MUTED, false));
        Switch sw = new Switch(this);
        sw.setText("Mostrar cartão sobre as corridas");
        sw.setTextColor(TEXT);
        sw.setChecked(s.enabled());
        sw.setThumbTintList(ColorStateList.valueOf(GREEN));
        sw.setTrackTintList(ColorStateList.valueOf(Color.parseColor("#3B4856")));
        sw.setOnCheckedChangeListener((v, on) -> s.setEnabled(on));
        goals.addView(sw, lp(14));

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        EditText km = field(String.format(Locale.US, "%.2f", s.minPerKm()));
        EditText hr = field(String.format(Locale.US, "%.2f", s.minPerHour()));
        row.addView(fieldBox("Mínimo R$/km", km), new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        space(row, 12, true);
        row.addView(fieldBox("Mínimo R$/hora", hr), new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        goals.addView(row, lp(14));

        Button save = button("Salvar metas", GREEN, Color.parseColor("#06260F"));
        save.setOnClickListener(v -> {
            try {
                s.save(Double.parseDouble(km.getText().toString().replace(',', '.')),
                       Double.parseDouble(hr.getText().toString().replace(',', '.')));
                Toast.makeText(this, "Metas salvas", Toast.LENGTH_SHORT).show();
            } catch (NumberFormatException e) {
                Toast.makeText(this, "Valor inválido", Toast.LENGTH_SHORT).show();
            }
        });
        goals.addView(save, lp(16));
        space(root, 14);

        // Última leitura
        LinearLayout last = card(root);
        last.addView(label("Última corrida lida", 18, TEXT, true));
        lastResult = label("", 15, TEXT, false);
        last.addView(lastResult, lp(8));
        Button toggle = button("Ver texto capturado (diagnóstico)", FIELD, TEXT);
        lastRaw = label("", 11, MUTED, false);
        lastRaw.setVisibility(View.GONE);
        toggle.setOnClickListener(v -> lastRaw.setVisibility(lastRaw.getVisibility() == View.GONE ? View.VISIBLE : View.GONE));
        last.addView(toggle, lp(12));
        last.addView(lastRaw, lp(8));

        homeView = sv;
        buildHistory();

        LinearLayout outer = new LinearLayout(this);
        outer.setOrientation(LinearLayout.VERTICAL);
        outer.setBackgroundColor(BG);
        content = new android.widget.FrameLayout(this);
        outer.addView(content, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1));
        LinearLayout nav = new LinearLayout(this);
        nav.setOrientation(LinearLayout.HORIZONTAL);
        nav.setBackgroundColor(CARD);
        nav.setPadding(dp(10), dp(8), dp(10), dp(8));
        tabHome = tab("Início", false);
        tabHistory = tab("Histórico", true);
        nav.addView(tabHome, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        nav.addView(tabHistory, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        outer.addView(nav);
        setContentView(outer);
        showTab(false);
    }

    private Button tab(String name, boolean history) {
        Button b = button(name, CARD, MUTED);
        b.setMinHeight(dp(44));
        b.setOnClickListener(v -> showTab(history));
        return b;
    }

    private void showTab(boolean history) {
        onHistory = history;
        content.removeAllViews();
        content.addView(history ? historyView : homeView);
        tabHome.setBackground(rounded(history ? CARD : FIELD, 14, 0));
        tabHome.setTextColor(history ? MUTED : GREEN);
        tabHistory.setBackground(rounded(history ? FIELD : CARD, 14, 0));
        tabHistory.setTextColor(history ? GREEN : MUTED);
        if (history) refreshHistory();
    }

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
        boolean kmOk = r.perKm() >= s.minPerKm(), hourOk = r.perHour() >= s.minPerHour();
        int dot = kmOk && hourOk ? GREEN : (!kmOk && !hourOk ? RED : AMBER);
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
                Button maps = button("Abrir no Google Maps", GREEN, Color.parseColor("#06260F"));
                maps.setOnClickListener(x -> openMapsTo(r.dest));
                box.addView(maps, lp(10));
            }
        }
        box.setOnClickListener(x -> { expandedId = open ? -1 : r.id; refreshHistory(); });
        return box;
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
        boolean on = serviceEnabled();
        statusCard.setBackground(rounded(CARD, 18, on ? GREEN : RED));
        statusTitle.setText(on ? "● Ativo" : "● Desativado");
        statusTitle.setTextColor(on ? GREEN : RED);
        statusSub.setText(on ? "Abra a Uber ou a 99 e aguarde uma corrida. O cartão aparece no topo da tela."
                             : "Ligue o serviço de acessibilidade para o app conseguir ler as corridas.");
        activate.setVisibility(on ? View.GONE : View.VISIBLE);
        if (onHistory) refreshHistory();
        lastResult.setText(s.lastResult());
        String dest = currentDest();
        boolean hasAcc = !s.acceptedDest().isEmpty() && s.acceptedAt() >= s.lastOfferAt() - 120000;
        destTitle.setText(hasAcc ? "Destino do passageiro (corrida aceita)" : "Destino da última oferta vista");
        destAddr.setText(dest.isEmpty() ? "Nenhuma corrida lida ainda." : dest);
        mapsBtn.setVisibility(dest.isEmpty() ? View.GONE : View.VISIBLE);
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
