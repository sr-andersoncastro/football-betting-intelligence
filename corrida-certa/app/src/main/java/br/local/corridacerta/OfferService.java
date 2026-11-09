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
        wm = (WindowManager) getSystemService(WINDOW_SERVICE);
        connectedAt = now();
        diag("Serviço conectado.");
    }

    private String connectedAt = "";
    private int events, scans;
    private String lastEventPkg = "-", lastWindows = "-", lastUberInfo = "(nenhuma janela da Uber/99 vista)", lastOfferInfo = "(nenhum texto com R$ e km visto)";
    private final java.util.LinkedHashSet<String> pkgsSeen = new java.util.LinkedHashSet<>();

    private static String now() { return new java.text.SimpleDateFormat("HH:mm:ss", Locale.US).format(new java.util.Date()); }

    private void diag(String extra) {
        settings.setDiag("Conectado às " + connectedAt + "\nEventos recebidos: " + events + " (último de: " + lastEventPkg + ")"
                + "\nApps que geraram eventos: " + pkgsSeen
                + "\nLeituras feitas: " + scans + "\nJanelas vistas: " + lastWindows
                + "\nÚltimo texto com R$ e km: " + lastOfferInfo
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
            if (text.contains("R$") && text.contains("km")) {
                lastOfferInfo = pkg + " às " + now() + ", " + text.length() + " caracteres:\n" + (text.length() > 700 ? text.substring(0, 700) : text);
            }
            lastUberInfo = pkg + " às " + now() + ", " + text.length() + " caracteres lidos:\n" + preview;
            OfferParser.Offer o = OfferParser.parse(text);
            if (o == null) { // leitura por acessibilidade não achou corrida: tenta ler o print da tela (OCR)
                ocrPending = true;
                ocrScan();
            }
            if (o != null) {
                found = true;
                lastTreeHit = System.currentTimeMillis();
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
    private long lastTreeHit;
    private boolean ocrBusy;
    private long lastOcr;
    private String ocrInfo = "(OCR ainda não usado)";
    private com.google.mlkit.vision.text.TextRecognizer recognizer;

    private void ocrScan() {
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
                            .addOnSuccessListener(res -> { ocrBusy = false; img.recycle(); onOcrText(res.getText()); })
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

    private void onOcrText(String text) {
        ocrInfo = now() + ", " + text.length() + " caracteres:\n" + (text.length() > 500 ? text.substring(0, 500) : text);
        if (text.contains("R$") && text.contains("km")) lastOfferInfo = "OCR " + ocrInfo;
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
            handler.removeCallbacks(hide);
            handler.postDelayed(hide, 20000);
        } else if (System.currentTimeMillis() - lastTreeHit > 2500) {
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
        boolean kmOk = o.perKm() >= settings.minPerKm();
        boolean hourOk = o.perHour() >= settings.minPerHour();
        int color = kmOk && hourOk ? Color.rgb(27, 143, 76) : (!kmOk && !hourOk ? Color.rgb(198, 40, 40) : Color.rgb(230, 140, 0));

        card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setPadding(dp(16), dp(10), dp(16), dp(10));
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(color);
        bg.setCornerRadius(dp(14));
        card.setBackground(bg);

        TextView l1 = line(String.format(Locale.US, "R$ %.2f/km   R$ %.2f/h", o.perKm(), o.perHour()), 20, true);
        TextView l2 = line(String.format(Locale.US, "%.1f km · %.0f min%s", o.totalKm(), o.totalMin(), o.bundle ? " · pacote" : ""), 13, false);
        card.addView(l1);
        card.addView(l2);

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
