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

        setContentView(sv);
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
        lastResult.setText(s.lastResult());
        diagText.setText("Serviço ligado no Android: " + (on ? "sim" : "NÃO") + "\n" + s.diag());
        String raw = s.lastRaw();
        lastRaw.setText(raw.isEmpty() ? "(nada capturado ainda)" : raw);
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
