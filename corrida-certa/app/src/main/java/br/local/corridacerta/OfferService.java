package br.local.corridacerta;

import android.accessibilityservice.AccessibilityService;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.graphics.Bitmap;
import android.hardware.HardwareBuffer;
import android.view.Display;
import android.view.Gravity;
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
        int color = cat == 2 ? Color.rgb(27, 143, 76) : (cat == 0 ? Color.rgb(198, 40, 40) : Color.rgb(230, 140, 0));

        LinearLayout box = new LinearLayout(this);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setPadding(dp(16), dp(10), dp(16), dp(10));
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(color);
        bg.setCornerRadius(dp(14));
        box.setBackground(bg);

        TextView l1 = line(String.format(Locale.US, "R$ %.2f/km   R$ %.2f/h", o.perKm(), o.perHour()), 20, true);
        TextView l2 = line(String.format(Locale.US, "%.1f km · %.0f min%s", o.totalKm(), o.totalMin(), o.bundle ? " · pacote" : ""), 13, false);
        TextView l0 = line(cat == 2 ? "Corrida boa" : (cat == 0 ? "Corrida ruim" : "Corrida média"), 14, true);
        box.addView(l0);
        box.addView(l1);
        box.addView(l2);

        // contêiner transparente: figurinha animada em cima do cartão (só quando a corrida é boa)
        card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setGravity(Gravity.CENTER_HORIZONTAL);
        if (cat == 2) addSticker(card, R.raw.sticker_boa, 190, 105);
        card.addView(box, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY, // não exige permissão de sobreposição
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP | Gravity.CENTER_HORIZONTAL;
        lp.y = dp(80);
        try { wm.addView(card, lp); } catch (Exception ex) { Log.e(TAG, "overlay", ex); card = null; }
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
            p.bottomMargin = -dp(8); // a figura "pisa" no cartão
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
