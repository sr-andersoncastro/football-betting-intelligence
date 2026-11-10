package br.local.corridacerta;

import android.accessibilityservice.AccessibilityService;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.graphics.Bitmap;
import android.hardware.HardwareBuffer;
import android.view.Display;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityEvent;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityWindowInfo;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.util.Locale;

public class OfferService extends AccessibilityService {
    private static final String TAG = "CorridaCerta";
    private static final String UBER = "com.ubercab.driver";
    private static final String APP99 = "com.app99.driver";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable scan = this::scanWindows;
    private final Runnable hide = this::removeCard;
    private Settings settings;
    private WindowManager wm;
    private LinearLayout card;
    private String lastShownText = "";

    @Override protected void onServiceConnected() {
        settings = new Settings(this);
        store = new Store(this);
        wm = (WindowManager) getSystemService(WINDOW_SERVICE);
        connectedAt = now();
        diag("Serviço conectado.");
    }

    private String connectedAt = "";
    private int events, scans;
    private String lastEventPkg = "-", lastWindows = "-", lastUberInfo = "(nenhuma janela da Uber/99 vista)", lastOfferInfo = "(nenhum texto no formato 'N min (X km)' visto ainda)";
    private final java.util.LinkedHashSet<String> pkgsSeen = new java.util.LinkedHashSet<>();

    private static String now() { return new java.text.SimpleDateFormat("HH:mm:ss", Locale.US).format(new java.util.Date()); }

    private void diag(String extra) {
        settings.setDiag("Conectado às " + connectedAt + "\nEventos recebidos: " + events + " (último de: " + lastEventPkg + ")"
                + "\nApps que geraram eventos: " + pkgsSeen
                + "\nLeituras feitas: " + scans + "\nJanelas vistas: " + lastWindows
                + "\nÚltimo card de corrida visto: " + lastOfferInfo
                + "\nOCR: " + ocrInfo
                + "\nUber/99: " + lastUberInfo + "\n" + extra);
    }

    @Override public void onAccessibilityEvent(AccessibilityEvent e) {
        if (settings == null) return;
        events++;
        lastEventPkg = String.valueOf(e.getPackageName());
        if (pkgsSeen.size() < 8) pkgsSeen.add(lastEventPkg);
        if (!settings.enabled()) return;
        if (!lastEventPkg.equals(UBER) && !lastEventPkg.equals(APP99)) return;
        // Throttle (não debounce): a Uber manda eventos sem parar com o mapa/contagem na tela,
        // então esperar uma pausa nunca dispararia a leitura.
        if (!scanPending) {
            scanPending = true;
            handler.postDelayed(scan, 150);
        }
    }

    private boolean scanPending;

    @Override public void onInterrupt() { handler.removeCallbacks(scan); }

    @Override public void onDestroy() { handler.removeCallbacksAndMessages(null); removeCard(); super.onDestroy(); }

    private void scanWindows() {
        scanPending = false;
        boolean found = false;
        boolean ocrPending = false;
        scans++;
        java.util.List<AccessibilityWindowInfo> wins = getWindows();
        StringBuilder wl = new StringBuilder();
        wl.append(wins.size()).append(" [");
        java.util.List<AccessibilityNodeInfo> roots = new java.util.ArrayList<>();
        for (AccessibilityWindowInfo w : wins) {
            AccessibilityNodeInfo root = w.getRoot();
            wl.append(root == null ? "sem-raiz" : String.valueOf(root.getPackageName())).append(' ');
            if (root != null) roots.add(root);
        }
        wl.append(']');
        lastWindows = wl.toString();
        AccessibilityNodeInfo active = getRootInActiveWindow();
        if (active != null) roots.add(active); // alternativa caso getWindows() não traga a janela
        for (AccessibilityNodeInfo root : roots) {
            String pkg = String.valueOf(root.getPackageName());
            if (!pkg.equals(UBER) && !pkg.equals(APP99)) continue;
            StringBuilder sb = new StringBuilder();
            read(root, sb, 0);
            String text = sb.toString();
            String preview = text.length() > 400 ? text.substring(0, 400) : text;
            if (looksLikeOffer(text)) {
                lastOfferInfo = pkg + " às " + now() + ", " + text.length() + " caracteres:\n" + (text.length() > 700 ? text.substring(0, 700) : text);
            }
            lastUberInfo = pkg + " às " + now() + ", " + text.length() + " caracteres lidos:\n" + preview;
            OfferParser.Offer o = OfferParser.parse(text);
            if (o == null) { // leitura por acessibilidade não achou corrida: tenta ler o print da tela (OCR)
                checkAccepted(text);
                ocrPending = true;
                ocrScan(pkg);
            }
            if (o != null) {
                found = true;
                lastTreeHit = System.currentTimeMillis();
                rememberOffer(o, pkg.equals(UBER) ? "Uber" : "99", null);
                if (!text.equals(lastShownText)) {
                    lastShownText = text;
                    settings.setLastRaw(text);
                    settings.setLastResult(String.format(Locale.US, "%s: R$ %.2f | %.2f/km | %.2f/h (%.1f km, %.0f min)",
                            pkg.equals(UBER) ? "Uber" : "99", o.value, o.perKm(), o.perHour(), o.totalKm(), o.totalMin()));
                    showCard(o);
                }
                handler.removeCallbacks(hide);
                handler.postDelayed(hide, 20000);
            } else if (text.contains("R$")) {
                settings.setLastRaw(text); // card não reconhecido: guarda para diagnóstico
                Log.d(TAG, "Sem match:\n" + text);
            }
        }
        diag(found ? "Corrida reconhecida." : "Nenhuma corrida reconhecida neste momento.");
        if (!found && !ocrPending) { lastShownText = ""; removeCard(); }
    }

    // ---- Leitura por print + OCR (para apps que escondem o texto da acessibilidade, como a 99) ----
    private static boolean looksLikeOffer(String s) {
        return s.matches("(?is).*min\\w*\\s*[(\\[]\\s*[0-9][0-9.,]*\\s*(km|m)\\s*[)\\]].*");
    }

    private Store store;
    private String ocrPkg = UBER;
    private String pendingDest = "";
    private long pendingAt;

    private void rememberOffer(OfferParser.Offer o, String platform, Bitmap shot) {
        try {
            long id = store.add(platform, o, System.currentTimeMillis());
            if (id > 0) {
                if (shot != null) savePrint(id, shot);   // caminho do OCR: já temos o print
                else captureAndSave(id);                  // caminho da leitura normal: tira um print agora
            }
        } catch (Exception ex) { Log.e(TAG, "historico", ex); }
        if (o.destination == null) return;
        pendingDest = o.destination;
        pendingAt = System.currentTimeMillis();
        settings.setLastOffer(o.destination, pendingAt);
    }

    /** Se a oferta sumiu há pouco e a tela mostra uma corrida em andamento, considera aceita. */
    private void checkAccepted(String text) {
        if (pendingDest.isEmpty()) return;
        long age = System.currentTimeMillis() - pendingAt;
        if (age > 90000) { pendingDest = ""; return; }
        if (age < 1500) return;
        if (text.matches("(?is).*(Encerrar|Iniciar viagem|Iniciar corrida|Cheguei|Finalizar|Destino de ).*")) {
            settings.setAccepted(pendingDest, System.currentTimeMillis());
            try { store.markAccepted(pendingDest, pendingAt - 5000); } catch (Exception ex) { Log.e(TAG, "historico", ex); }
            pendingDest = "";
        }
    }

    private void savePrint(long id, Bitmap src) {
        try {
            int w = Math.min(720, src.getWidth());
            int h = Math.round(src.getHeight() * (w / (float) src.getWidth()));
            Bitmap small = Bitmap.createScaledBitmap(src, w, h, true);
            java.io.File f = Store.printFile(this, id);
            f.getParentFile().mkdirs();
            try (java.io.FileOutputStream out = new java.io.FileOutputStream(f)) { small.compress(Bitmap.CompressFormat.JPEG, 75, out); }
            if (small != src) small.recycle();
            store.cleanupPrints(this);
        } catch (Exception ex) { Log.e(TAG, "print", ex); }
    }

    private void captureAndSave(long id) {
        try {
            takeScreenshot(Display.DEFAULT_DISPLAY, getMainExecutor(), new TakeScreenshotCallback() {
                @Override public void onSuccess(ScreenshotResult r) {
                    try {
                        HardwareBuffer hb = r.getHardwareBuffer();
                        Bitmap hw = Bitmap.wrapHardwareBuffer(hb, r.getColorSpace());
                        Bitmap bmp = hw.copy(Bitmap.Config.ARGB_8888, false);
                        hw.recycle(); hb.close();
                        savePrint(id, bmp);
                        bmp.recycle();
                    } catch (Exception ex) { Log.e(TAG, "print", ex); }
                }
                @Override public void onFailure(int code) { Log.d(TAG, "print falhou " + code); }
            });
        } catch (Exception ex) { Log.e(TAG, "print", ex); }
    }

    private long lastTreeHit;
    private boolean ocrBusy;
    private long lastOcr;
    private String ocrInfo = "(OCR ainda não usado)";
    private com.google.mlkit.vision.text.TextRecognizer recognizer;

    private void ocrScan(String pkg) {
        ocrPkg = pkg;
        long t = System.currentTimeMillis();
        if (ocrBusy || t - lastOcr < 1200) return;
        ocrBusy = true;
        lastOcr = t;
        if (recognizer == null) {
            recognizer = com.google.mlkit.vision.text.TextRecognition.getClient(
                    com.google.mlkit.vision.text.latin.TextRecognizerOptions.DEFAULT_OPTIONS);
        }
        try {
            takeScreenshot(Display.DEFAULT_DISPLAY, getMainExecutor(), new TakeScreenshotCallback() {
                @Override public void onSuccess(ScreenshotResult r) {
                    Bitmap bmp = null;
                    try {
                        HardwareBuffer hb = r.getHardwareBuffer();
                        Bitmap hw = Bitmap.wrapHardwareBuffer(hb, r.getColorSpace());
                        bmp = hw.copy(Bitmap.Config.ARGB_8888, false);
                        hw.recycle();
                        hb.close();
                    } catch (Exception ex) {
                        ocrBusy = false;
                        ocrInfo = "erro ao converter print: " + ex;
                        diag("");
                        return;
                    }
                    final Bitmap img = bmp;
                    recognizer.process(com.google.mlkit.vision.common.InputImage.fromBitmap(img, 0))
                            .addOnSuccessListener(res -> { ocrBusy = false; onOcrText(res.getText(), img); img.recycle(); })
                            .addOnFailureListener(ex -> { ocrBusy = false; img.recycle(); ocrInfo = "OCR falhou: " + ex; diag(""); });
                }
                @Override public void onFailure(int code) {
                    ocrBusy = false;
                    ocrInfo = "print falhou, código " + code + " (" + now() + ")";
                    diag("");
                }
            });
        } catch (Exception ex) {
            ocrBusy = false;
            ocrInfo = "takeScreenshot erro: " + ex;
            diag("");
        }
    }

    private void onOcrText(String text, Bitmap shot) {
        ocrInfo = now() + ", " + text.length() + " caracteres:\n" + (text.length() > 500 ? text.substring(0, 500) : text);
        if (looksLikeOffer(text)) lastOfferInfo = "OCR " + ocrInfo;
        OfferParser.Offer o = OfferParser.parse(text);
        if (o != null) {
            String key = String.format(Locale.US, "%.2f|%.1f|%.1f", o.value, o.pickupKm, o.tripKm);
            if (!key.equals(lastShownText)) {
                lastShownText = key;
                settings.setLastRaw(text);
                settings.setLastResult(String.format(Locale.US, "Uber/99 (OCR): R$ %.2f | %.2f/km | %.2f/h (%.1f km, %.0f min)",
                        o.value, o.perKm(), o.perHour(), o.totalKm(), o.totalMin()));
                showCard(o);
            }
            rememberOffer(o, ocrPkg.equals(UBER) ? "Uber" : "99", shot);
            handler.removeCallbacks(hide);
            handler.postDelayed(hide, 20000);
        } else {
            checkAccepted(text);
        }
        if (o == null && System.currentTimeMillis() - lastTreeHit > 2500) {
            lastShownText = "";
            removeCard();
        }
        diag(o != null ? "Corrida reconhecida (OCR)." : "OCR sem corrida.");
    }

    private void read(AccessibilityNodeInfo n, StringBuilder sb, int depth) {
        if (n == null || depth > 60 || sb.length() > 80000) return;
        CharSequence t = n.getText();
        if (t != null && t.length() > 0) sb.append(t).append('\n');
        CharSequence d = n.getContentDescription();
        if (d != null && d.length() > 0 && !d.equals(t)) sb.append(d).append('\n');
        for (int i = 0; i < n.getChildCount(); i++) {
            AccessibilityNodeInfo c = n.getChild(i);
            if (c != null) read(c, sb, depth + 1);
        }
    }

    private void showCard(OfferParser.Offer o) {
        removeCard();
        int cat = settings.category(o.perKm()); // 0 ruim, 1 média, 2 boa (pelo R$/km)
        int top = cat == 2 ? Color.parseColor("#34D27B") : (cat == 1 ? Color.parseColor("#FBBF24") : Color.parseColor("#F87171"));
        int bottom = cat == 2 ? Color.parseColor("#0E8A4A") : (cat == 1 ? Color.parseColor("#D97706") : Color.parseColor("#B91C1C"));
        Locale br = new Locale("pt", "BR");
        float rad = dp(22);

        // ---- cartão com degradê, brilho no topo, borda clara e sombra (efeito 3D) ----
        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(16), dp(12), dp(16), dp(14));
        GradientDrawable base = new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM, new int[]{top, bottom});
        base.setCornerRadius(rad);
        base.setStroke(dp(2), Color.argb(150, 255, 255, 255));
        GradientDrawable gloss = new GradientDrawable(GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{Color.argb(95, 255, 255, 255), Color.argb(0, 255, 255, 255)});
        gloss.setCornerRadii(new float[]{rad, rad, rad, rad, 0, 0, 0, 0});
        android.graphics.drawable.LayerDrawable layers = new android.graphics.drawable.LayerDrawable(
                new android.graphics.drawable.Drawable[]{base, gloss});
        layers.setLayerInset(1, dp(3), dp(3), dp(3), dp(78));
        box.setBackground(layers);
        box.setElevation(dp(14));
        box.setOutlineProvider(new android.view.ViewOutlineProvider() {
            @Override public void getOutline(View v, android.graphics.Outline out) {
                out.setRoundRect(0, 0, v.getWidth(), v.getHeight(), rad);
            }
        });

        // etiqueta da categoria
        TextView pill = new TextView(this);
        pill.setText(cat == 2 ? "CORRIDA BOA" : (cat == 0 ? "CORRIDA RUIM" : "CORRIDA MÉDIA"));
        pill.setTextColor(Color.WHITE);
        pill.setTextSize(11);
        pill.setLetterSpacing(0.08f);
        pill.setTypeface(pill.getTypeface(), Typeface.BOLD);
        pill.setPadding(dp(10), dp(3), dp(10), dp(3));
        GradientDrawable pbg = new GradientDrawable();
        pbg.setColor(Color.argb(70, 0, 0, 0));
        pbg.setCornerRadius(dp(10));
        pill.setBackground(pbg);
        box.addView(pill, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        // números principais: R$/km e R$/h
        LinearLayout nums = new LinearLayout(this);
        nums.setOrientation(LinearLayout.HORIZONTAL);
        nums.setGravity(Gravity.CENTER_VERTICAL);
        nums.addView(bigNumber(String.format(br, "%.2f", o.perKm()), "/km", 32, Gravity.START),
                new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        View div = new View(this);
        div.setBackgroundColor(Color.argb(110, 255, 255, 255));
        nums.addView(div, new LinearLayout.LayoutParams(dp(1), dp(34)));
        nums.addView(bigNumber(String.format(br, "%.2f", o.perHour()), "/h", 26, Gravity.END),
                new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        LinearLayout.LayoutParams nlp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        nlp.topMargin = dp(6);
        box.addView(nums, nlp);

        // medidor ruim / média / boa com marcador
        LinearLayout.LayoutParams glp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(22));
        glp.topMargin = dp(8);
        box.addView(new Gauge(this, o.perKm(), settings.badBelowKm(), settings.goodFromKm()), glp);

        // detalhes
        TextView info = new TextView(this);
        info.setText(String.format(br, "%.1f km  ·  %.0f min  ·  R$ %.2f%s", o.totalKm(), o.totalMin(), o.value, o.bundle ? "  ·  pacote" : ""));
        info.setTextColor(Color.argb(235, 255, 255, 255));
        info.setTextSize(13);
        info.setGravity(Gravity.CENTER);
        info.setShadowLayer(dp(2), 0, dp(1), Color.argb(90, 0, 0, 0));
        LinearLayout.LayoutParams ilp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        ilp.topMargin = dp(6);
        box.addView(info, ilp);

        // ---- composição: figurinha em cima, "pisando" no cartão ----
        card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setGravity(Gravity.CENTER_HORIZONTAL);
        card.setClipChildren(false);
        card.setClipToPadding(false);
        card.setPadding(dp(14), dp(6), dp(14), dp(18)); // espaço para a sombra
        if (cat == 2) addSticker(card, R.raw.sticker_boa, 250, 140);
        else if (cat == 0) addSticker(card, R.raw.sticker_ruim, 250, 140);
        else addSticker(card, R.raw.sticker_media, 250, 140);
        card.addView(box, new LinearLayout.LayoutParams(dp(300), ViewGroup.LayoutParams.WRAP_CONTENT));

        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY, // não exige permissão de sobreposição
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN | WindowManager.LayoutParams.FLAG_HARDWARE_ACCELERATED,
                PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP | Gravity.CENTER_HORIZONTAL;
        lp.y = dp(40);
        try {
            wm.addView(card, lp);
            // entrada com "pulo"
            card.setScaleX(0.75f);
            card.setScaleY(0.75f);
            card.setAlpha(0f);
            card.animate().scaleX(1f).scaleY(1f).alpha(1f).setDuration(280)
                    .setInterpolator(new android.view.animation.OvershootInterpolator(1.3f)).start();
        } catch (Exception ex) { Log.e(TAG, "overlay", ex); card = null; }
    }

    /** "R$ 3,35/km": número grande, "R$" e unidade menores. */
    private TextView bigNumber(String number, String unit, int sp, int gravity) {
        android.text.SpannableStringBuilder sb = new android.text.SpannableStringBuilder();
        sb.append("R$ ");
        sb.setSpan(new android.text.style.RelativeSizeSpan(0.5f), 0, 3, android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        int s = sb.length();
        sb.append(number);
        sb.setSpan(new android.text.style.StyleSpan(Typeface.BOLD), s, sb.length(), android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        int u = sb.length();
        sb.append(unit);
        sb.setSpan(new android.text.style.RelativeSizeSpan(0.5f), u, sb.length(), android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        TextView v = new TextView(this);
        v.setText(sb);
        v.setTextColor(Color.WHITE);
        v.setTextSize(sp);
        v.setGravity(gravity | Gravity.CENTER_VERTICAL);
        v.setShadowLayer(dp(3), 0, dp(1), Color.argb(110, 0, 0, 0));
        return v;
    }

    /** Medidor horizontal: vermelho (ruim) / laranja (média) / verde (boa), com um marcador onde esta corrida está. */
    private class Gauge extends View {
        private final double v, bad, good;
        private final android.graphics.Paint p = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);

        Gauge(android.content.Context c, double perKm, double bad, double good) {
            super(c);
            this.v = perKm; this.bad = bad; this.good = good;
        }

        @Override protected void onDraw(android.graphics.Canvas c) {
            float w = getWidth(), h = getHeight();
            float barH = dp(8), cy = h / 2f, r = barH / 2f;
            double max = good * 1.5;
            float xb = (float) Math.min(1, bad / max) * w, xg = (float) Math.min(1, good / max) * w;
            // trilho escuro
            p.setColor(Color.argb(80, 0, 0, 0));
            c.drawRoundRect(0, cy - barH / 2 - dp(2), w, cy + barH / 2 + dp(2), r + dp(2), r + dp(2), p);
            android.graphics.Path clip = new android.graphics.Path();
            clip.addRoundRect(dp(2), cy - barH / 2, w - dp(2), cy + barH / 2, r, r, android.graphics.Path.Direction.CW);
            c.save();
            c.clipPath(clip);
            p.setColor(Color.parseColor("#EF4444")); c.drawRect(0, 0, xb, h, p);
            p.setColor(Color.parseColor("#F59E0B")); c.drawRect(xb, 0, xg, h, p);
            p.setColor(Color.parseColor("#22C55E")); c.drawRect(xg, 0, w, h, p);
            c.restore();
            // marcador
            float mx = (float) Math.max(0, Math.min(1, v / max)) * w;
            mx = Math.max(dp(8), Math.min(w - dp(8), mx));
            p.setColor(Color.argb(90, 0, 0, 0));
            c.drawCircle(mx, cy + dp(1), dp(8), p);
            p.setColor(Color.WHITE);
            c.drawCircle(mx, cy, dp(7), p);
            p.setColor(v >= good ? Color.parseColor("#22C55E") : (v >= bad ? Color.parseColor("#F59E0B") : Color.parseColor("#EF4444")));
            c.drawCircle(mx, cy, dp(4), p);
        }
    }

    /** Figurinha (GIF animado) acima do cartão. Se não conseguir animar, não mostra nada (o cartão continua normal). */
    private void addSticker(LinearLayout parent, int resId, int wDp, int hDp) {
        try {
            android.graphics.drawable.Drawable d = android.graphics.ImageDecoder.decodeDrawable(
                    android.graphics.ImageDecoder.createSource(getResources(), resId));
            android.widget.ImageView iv = new android.widget.ImageView(this);
            iv.setImageDrawable(d);
            iv.setScaleType(android.widget.ImageView.ScaleType.FIT_CENTER);
            if (d instanceof android.graphics.drawable.AnimatedImageDrawable) {
                android.graphics.drawable.AnimatedImageDrawable ad = (android.graphics.drawable.AnimatedImageDrawable) d;
                ad.setRepeatCount(android.graphics.drawable.AnimatedImageDrawable.REPEAT_INFINITE);
                ad.start();
            }
            LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(dp(wDp), dp(hDp));
            p.bottomMargin = -dp(34); // a figura "pisa" no cartão
            parent.addView(iv, p);
        } catch (Exception ex) {
            Log.e(TAG, "figurinha", ex);
        }
    }

    private TextView line(String s, int sp, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextColor(Color.WHITE);
        t.setTextSize(sp);
        t.setGravity(Gravity.CENTER);
        if (bold) t.setTypeface(t.getTypeface(), android.graphics.Typeface.BOLD);
        return t;
    }

    private void removeCard() {
        handler.removeCallbacks(hide);
        if (card != null) { try { wm.removeView(card); } catch (Exception ignored) {} card = null; }
    }

    private int dp(int v) { return Math.round(v * getResources().getDisplayMetrics().density); }
}
