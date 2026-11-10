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
                + "\nCard: " + cardInfo + (cardError.isEmpty() ? "" : "\nERRO ao desenhar o card: " + cardError)
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
        if (active != null && !roots.contains(active)) roots.add(active); // alternativa caso getWindows() não traga a janela
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
                String key = offerKey(o);
                if (!key.equals(lastShownText)) {
                    lastShownText = key;
                    settings.setLastRaw(text);
                    settings.setLastResult(String.format(Locale.US, "%s: R$ %.2f | %.2f/km | %.2f/h (%.1f km, %.0f min)",
                            pkg.equals(UBER) ? "Uber" : "99", o.value, o.perKm(), o.perHour(), o.totalKm(), o.totalMin()));
                    showCardSafe(o, geometryFromTree(root), pkg.equals(UBER) ? "Uber" : "99", "árvore");
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
        if (overlayInShots && card != null) { // esconde o nosso card só durante a captura
            setOverlaysAlpha(0f);
            handler.postDelayed(this::captureNow, 90);
        } else {
            captureNow();
        }
    }

    private boolean overlayInShots;

    private void setOverlaysAlpha(float a) {
        if (card != null) card.setAlpha(a);
        if (declineWin != null) declineWin.setAlpha(a);
    }

    private void captureNow() {
        try {
            takeScreenshot(Display.DEFAULT_DISPLAY, getMainExecutor(), new TakeScreenshotCallback() {
                @Override public void onSuccess(ScreenshotResult r) {
                    setOverlaysAlpha(1f);
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
                            .addOnSuccessListener(res -> {
                                ocrBusy = false;
                                java.util.List<Object[]> ls = new java.util.ArrayList<>();
                                for (com.google.mlkit.vision.text.Text.TextBlock b : res.getTextBlocks())
                                    for (com.google.mlkit.vision.text.Text.Line ln : b.getLines())
                                        if (ln.getBoundingBox() != null) ls.add(new Object[]{ln.getText(), ln.getBoundingBox()});
                                ocrLines = ls;
                                onOcrText(res.getText(), img);
                                img.recycle();
                            })
                            .addOnFailureListener(ex -> { ocrBusy = false; img.recycle(); ocrInfo = "OCR falhou: " + ex; diag(""); });
                }
                @Override public void onFailure(int code) {
                    setOverlaysAlpha(1f);
                    ocrBusy = false;
                    ocrInfo = "print falhou, código " + code + " (" + now() + ")";
                    diag("");
                }
            });
        } catch (Exception ex) {
            setOverlaysAlpha(1f);
            ocrBusy = false;
            ocrInfo = "takeScreenshot erro: " + ex;
            diag("");
        }
    }

    private void onOcrText(String text, Bitmap shot) {
        ocrInfo = now() + ", " + text.length() + " caracteres:\n" + (text.length() > 500 ? text.substring(0, 500) : text);
        if (looksLikeOffer(text)) lastOfferInfo = "OCR " + ocrInfo;
        // se o print mostra o NOSSO card, ele cobre o real: passa a esconder o card durante a captura
        if (card != null && !overlayInShots && text.matches("(?s).*CORRIDA (BOA|M[ÉE]DIA|RUIM).*")) {
            overlayInShots = true;
            lastOcr = 0;
            handler.removeCallbacks(hide);
            handler.postDelayed(hide, 20000);
            diag("O card aparece no print: será escondido durante a captura.");
            return;
        }
        // qual app é? "Tenho interesse" = Uber; "Tentando encontrar" = 99 (a Uber pode estar numa bolinha com a 99 aberta)
        String plat = ocrPkg.equals(UBER) ? "Uber" : "99";
        for (Object[] ln : ocrLines) {
            String s = (String) ln[0];
            if (s.matches("(?is)^\\s*tenho interesse\\s*$")) plat = "Uber";
            else if (s.matches("(?is)^\\s*tentando encontrar.*$")) plat = "99";
        }
        OfferParser.Offer o = OfferParser.parse(text);
        // o botão de aceitar do card real aparece pelo "buraco" do nosso card: se ele está na tela, a oferta continua viva
        boolean alive = false;
        for (Object[] ln : ocrLines) if (ACCEPT_RE.matcher((String) ln[0]).matches()) { alive = true; break; }
        if (o != null) {
            String key = offerKey(o);
            if (!key.equals(lastShownText)) {
                lastShownText = key;
                settings.setLastRaw(text);
                settings.setLastResult(String.format(Locale.US, "%s (OCR): R$ %.2f | %.2f/km | %.2f/h (%.1f km, %.0f min)",
                        plat, o.value, o.perKm(), o.perHour(), o.totalKm(), o.totalMin()));
                showCardSafe(o, geometryFromOcr(), plat, "print");
            }
            rememberOffer(o, plat, shot);
            handler.removeCallbacks(hide);
            handler.postDelayed(hide, 20000);
        } else if (alive && !lastShownText.isEmpty()) {
            handler.removeCallbacks(hide);
            handler.postDelayed(hide, 20000);
        } else {
            checkAccepted(text);
            if (System.currentTimeMillis() - lastTreeHit > 2500) {
                lastShownText = "";
                removeCard();
            }
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

    // ===== card do tamanho exato do card da Uber/99, por cima dele, com "buracos" nos botões originais =====
    private static final java.util.regex.Pattern ACCEPT_RE = java.util.regex.Pattern.compile(
            "(?is)^\\s*(tenho interesse|aceitar.*|tentando encontrar.*|procurando.*|confirmar.*)\\s*$");
    private static final java.util.regex.Pattern PRICE_RE = java.util.regex.Pattern.compile(
            "(?s)^\\s*R\\$\\s*[0-9]{1,3}(?:\\.[0-9]{3})*,[0-9]{2}\\s*$");
    private java.util.List<Object[]> ocrLines = new java.util.ArrayList<>();

    /** Posição do card real na tela e dos botões que devem ficar visíveis (buracos). */
    private static final class CardGeometry {
        android.graphics.Rect rect;
        android.graphics.Rect accept;  // botão de aceitar (null se desconhecido)
        android.graphics.Rect close;   // X de recusar dentro do card (null se não houver)
    }

    private AccessibilityNodeInfo findNode(AccessibilityNodeInfo n, java.util.regex.Pattern re, int depth) {
        if (n == null || depth > 60) return null;
        CharSequence tx = n.getText(), d = n.getContentDescription();
        if (((tx != null && re.matcher(tx).matches()) || (d != null && re.matcher(d).matches())) && n.isVisibleToUser()) return n;
        for (int i = 0; i < n.getChildCount(); i++) {
            AccessibilityNodeInfo r = findNode(n.getChild(i), re, depth + 1);
            if (r != null) return r;
        }
        return null;
    }

    private void collectClickRects(AccessibilityNodeInfo n, android.graphics.Rect within, java.util.List<android.graphics.Rect> out, int depth) {
        if (n == null || depth > 60) return;
        if (n.isClickable()) {
            android.graphics.Rect r = new android.graphics.Rect();
            n.getBoundsInScreen(r);
            if (android.graphics.Rect.intersects(r, within)) out.add(r);
        }
        for (int i = 0; i < n.getChildCount(); i++) collectClickRects(n.getChild(i), within, out, depth + 1);
    }

    /** O retângulo do card precisa ser plausível (dentro da tela, largo, nem baixo nem alto demais). */
    private boolean sane(android.graphics.Rect r) {
        android.util.DisplayMetrics dm = getResources().getDisplayMetrics();
        return r.width() >= dm.widthPixels * 0.6f && r.width() <= dm.widthPixels * 1.05f
                && r.height() >= dp(120) && r.height() <= dm.heightPixels * 0.8f
                && r.left >= -dp(10) && r.right <= dm.widthPixels + dp(10) && r.top >= 0 && r.bottom <= dm.heightPixels + dp(40);
    }

    /** Uber: o X de recusar fica dentro do card, no canto de cima à direita (proporções medidas num card real). */
    private android.graphics.Rect uberCloseFallback(android.graphics.Rect card) {
        float w = card.width();
        int size = Math.round(0.0925f * w);
        int right = Math.round(card.right - 0.0297f * w);
        int top = Math.round(card.top + 0.0285f * w);
        return new android.graphics.Rect(right - size, top, right, top + size);
    }

    private static String offerKey(OfferParser.Offer o) {
        return String.format(Locale.US, "%.2f|%.1f|%.1f", o.value, o.pickupKm, o.tripKm);
    }

    private String cardInfo = "(nenhum card desenhado ainda)";
    private String cardError = "";

    /** Desenha o card; se algo falhar, registra o erro no Diagnóstico e tenta o card simples no alto da tela. */
    private void showCardSafe(OfferParser.Offer o, CardGeometry geo, String platform, String source) {
        try {
            showCard(o, geo, platform);
            cardInfo = platform + " (" + source + ") " + (geo == null ? "posição padrão" : "rect=" + geo.rect.toShortString()
                    + " aceitar=" + (geo.accept == null ? "-" : geo.accept.toShortString())
                    + " x=" + (geo.close == null ? "-" : geo.close.toShortString())) + " às " + now();
        } catch (Throwable ex) {
            cardError = ex + " às " + now();
            Log.e(TAG, "showCard", ex);
            try { showCard(o, null, platform); } catch (Throwable ex2) { Log.e(TAG, "showCard2", ex2); }
        }
    }

    /** Uber: acha o card pelo botão "Tenho interesse" e pelo preço (a acessibilidade informa as posições). */
    private CardGeometry geometryFromTree(AccessibilityNodeInfo root) {
        try {
            AccessibilityNodeInfo accept = findNode(root, ACCEPT_RE, 0);
            AccessibilityNodeInfo price = findNode(root, PRICE_RE, 0);
            if (accept == null || price == null) return null;
            int sw = getResources().getDisplayMetrics().widthPixels, sh = getResources().getDisplayMetrics().heightPixels;
            android.graphics.Rect ar = new android.graphics.Rect(), pr = new android.graphics.Rect();
            AccessibilityNodeInfo btn = accept;
            while (btn != null && !btn.isClickable()) btn = btn.getParent();
            (btn != null ? btn : accept).getBoundsInScreen(ar);
            price.getBoundsInScreen(pr);
            android.graphics.Rect card = null;
            AccessibilityNodeInfo p = accept.getParent();
            while (p != null) {
                android.graphics.Rect r = new android.graphics.Rect();
                p.getBoundsInScreen(r);
                if (r.contains(pr) && r.contains(ar) && r.width() >= sw * 0.8) {
                    if (r.height() < sh * 0.75) card = r;
                    break;
                }
                p = p.getParent();
            }
            if (card == null) card = new android.graphics.Rect(ar.left - dp(10), pr.top - dp(48), ar.right + dp(10), ar.bottom + dp(14));
            if (!sane(card)) return null;
            CardGeometry g = new CardGeometry();
            g.rect = card;
            g.accept = ar;
            java.util.List<android.graphics.Rect> clicks = new java.util.ArrayList<>();
            collectClickRects(root, card, clicks, 0);
            for (android.graphics.Rect r : clicks) { // o X: clicável pequeno no canto de cima à direita do card
                if (r.centerX() > card.left + card.width() * 0.7 && r.centerY() < card.top + card.height() * 0.35 && r.width() < card.width() * 0.3) { g.close = r; break; }
            }
            return g;
        } catch (Exception ex) { Log.e(TAG, "geometria", ex); return null; }
    }

    /** 99: o texto não vem pela acessibilidade; usa as posições do texto lido no print. */
    private CardGeometry geometryFromOcr() {
        try {
            android.graphics.Rect pr = null, ar = null;
            for (Object[] ln : ocrLines) {
                String s = (String) ln[0];
                android.graphics.Rect r = (android.graphics.Rect) ln[1];
                if (pr == null && PRICE_RE.matcher(s).matches()) pr = r;
                if (ar == null && ACCEPT_RE.matcher(s).matches()) ar = r;
            }
            if (pr == null || ar == null) return null;
            int sw = getResources().getDisplayMetrics().widthPixels;
            int minTop = pr.top;
            for (Object[] ln : ocrLines) {
                android.graphics.Rect r = (android.graphics.Rect) ln[1];
                if (r.top >= pr.top - dp(60) && r.bottom <= ar.bottom) minTop = Math.min(minTop, r.top);
            }
            int side = Math.round(sw * 0.018f);
            CardGeometry g = new CardGeometry();
            g.rect = new android.graphics.Rect(side, minTop - dp(18), sw - side, ar.centerY() + dp(22) + dp(13));
            if (!sane(g.rect)) return null;
            g.accept = new android.graphics.Rect(g.rect.left + dp(10), ar.centerY() - dp(22), g.rect.right - dp(10), ar.centerY() + dp(22));
            return g;
        } catch (Exception ex) { Log.e(TAG, "geometria", ex); return null; }
    }

    /** Botão nosso desenhado exatamente sobre um botão original (do mesmo tamanho; o toque passa para o original). */
    private static final class DecoBtn {
        final android.graphics.RectF r; final boolean accept;
        DecoBtn(android.graphics.RectF r, boolean accept) { this.r = r; this.accept = accept; }
    }

    /** Desenha o botão ACEITAR (verde, pulsando) ou o ✕ de recusar (vermelho). */
    private void drawDecoBtn(android.graphics.Canvas c, android.graphics.Paint p, DecoBtn b, float pulse) {
        android.graphics.RectF r = b.r;
        float rad = Math.min(dp(16), Math.min(r.width(), r.height()) / 2f);
        int c1 = b.accept ? Color.parseColor("#4ADE80") : Color.parseColor("#F87171");
        int c2 = b.accept ? Color.parseColor("#15803D") : Color.parseColor("#B91C1C");
        if (b.accept) { // brilho que pulsa em volta do botão
            p.setShader(null);
            p.setStyle(android.graphics.Paint.Style.STROKE);
            p.setStrokeWidth(dp(6));
            p.setColor(Color.argb((int) (60 + 140 * pulse), 255, 255, 255));
            c.drawRoundRect(r.left - dp(3), r.top - dp(3), r.right + dp(3), r.bottom + dp(3), rad + dp(3), rad + dp(3), p);
        }
        p.setStyle(android.graphics.Paint.Style.FILL);
        p.setShader(new android.graphics.LinearGradient(0, r.top, 0, r.bottom, c1, c2, android.graphics.Shader.TileMode.CLAMP));
        c.drawRoundRect(r, rad, rad, p);
        p.setShader(new android.graphics.LinearGradient(0, r.top, 0, r.top + r.height() * 0.5f, Color.argb(110, 255, 255, 255), Color.argb(0, 255, 255, 255), android.graphics.Shader.TileMode.CLAMP));
        c.drawRoundRect(r.left + dp(2), r.top + dp(2), r.right - dp(2), r.top + r.height() * 0.5f, rad, rad, p);
        p.setShader(null);
        p.setStyle(android.graphics.Paint.Style.STROKE);
        p.setStrokeWidth(dp(3));
        p.setColor(Color.WHITE);
        c.drawRoundRect(r, rad, rad, p);
        p.setStyle(android.graphics.Paint.Style.FILL);
        if (b.accept) {
            p.setColor(Color.WHITE);
            p.setTextAlign(android.graphics.Paint.Align.CENTER);
            p.setFakeBoldText(true);
            p.setTextSize(Math.min(dp(22), r.height() * 0.48f));
            p.setShadowLayer(dp(2), 0, dp(1), Color.argb(130, 0, 0, 0));
            c.drawText("✓ ACEITAR", r.centerX(), r.centerY() + p.getTextSize() * 0.35f, p);
            p.clearShadowLayer();
            p.setFakeBoldText(false);
        } else {
            float s = Math.min(r.width(), r.height()) * 0.24f;
            p.setStyle(android.graphics.Paint.Style.STROKE);
            p.setStrokeCap(android.graphics.Paint.Cap.ROUND);
            p.setStrokeWidth(Math.max(dp(3), Math.min(r.width(), r.height()) * 0.11f));
            p.setColor(Color.WHITE);
            c.drawLine(r.centerX() - s, r.centerY() - s, r.centerX() + s, r.centerY() + s, p);
            c.drawLine(r.centerX() + s, r.centerY() - s, r.centerX() - s, r.centerY() + s, p);
            p.setStrokeCap(android.graphics.Paint.Cap.BUTT);
            p.setStyle(android.graphics.Paint.Style.FILL);
        }
    }

    /** Fundo do card: degradê, brilho, borda e os botões desenhados por cima dos originais. */
    private class CardBg extends View {
        private final int top, bottom;
        private final java.util.List<DecoBtn> btns;
        private final android.graphics.Paint p = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        private float pulse;
        private android.animation.ValueAnimator anim;

        CardBg(android.content.Context c, int top, int bottom, java.util.List<DecoBtn> btns) {
            super(c);
            this.top = top; this.bottom = bottom; this.btns = btns;
        }

        @Override protected void onAttachedToWindow() {
            super.onAttachedToWindow();
            anim = android.animation.ValueAnimator.ofFloat(0f, 1f);
            anim.setDuration(750);
            anim.setRepeatMode(android.animation.ValueAnimator.REVERSE);
            anim.setRepeatCount(android.animation.ValueAnimator.INFINITE);
            anim.addUpdateListener(a -> { pulse = (float) a.getAnimatedValue(); invalidate(); });
            anim.start();
        }

        @Override protected void onDetachedFromWindow() {
            if (anim != null) anim.cancel();
            super.onDetachedFromWindow();
        }

        @Override protected void onDraw(android.graphics.Canvas c) {
            float w = getWidth(), h = getHeight(), r = dp(22);
            p.setStyle(android.graphics.Paint.Style.FILL);
            p.setShader(new android.graphics.LinearGradient(0, 0, 0, h, top, bottom, android.graphics.Shader.TileMode.CLAMP));
            c.drawRoundRect(0, 0, w, h, r, r, p);
            p.setShader(new android.graphics.LinearGradient(0, 0, 0, h * 0.45f, Color.argb(95, 255, 255, 255), Color.argb(0, 255, 255, 255), android.graphics.Shader.TileMode.CLAMP));
            c.drawRoundRect(dp(3), dp(3), w - dp(3), h * 0.45f, r, r, p);
            p.setShader(null);
            p.setStyle(android.graphics.Paint.Style.STROKE);
            p.setStrokeWidth(dp(2));
            p.setColor(Color.argb(150, 255, 255, 255));
            c.drawRoundRect(dp(1), dp(1), w - dp(1), h - dp(1), r, r, p);
            for (DecoBtn b : btns) drawDecoBtn(c, p, b, pulse);
        }
    }

    private TextView txt(String s, int sp, int color, boolean bold) {
        TextView v = new TextView(this);
        v.setText(s);
        v.setTextSize(sp);
        v.setTextColor(color);
        if (bold) v.setTypeface(v.getTypeface(), Typeface.BOLD);
        v.setShadowLayer(dp(2), 0, dp(1), Color.argb(100, 0, 0, 0));
        return v;
    }

    private TextView addressBlock(String label, double min, double km, String addr, Locale br) {
        TextView v = new TextView(this);
        android.text.SpannableStringBuilder sb = new android.text.SpannableStringBuilder();
        sb.append(label).append(String.format(br, "  ·  %.0f min  ·  %.1f km\n", min, km));
        sb.setSpan(new android.text.style.StyleSpan(Typeface.BOLD), 0, sb.length(), android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        sb.setSpan(new android.text.style.RelativeSizeSpan(0.82f), 0, sb.length(), android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        sb.setSpan(new android.text.style.ForegroundColorSpan(Color.argb(220, 255, 255, 255)), 0, sb.length(), android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        sb.append(addr == null || addr.isEmpty() ? "(endereço não lido)" : addr);
        v.setText(sb);
        v.setTextColor(Color.WHITE);
        v.setTextSize(14);
        v.setMaxLines(3);
        v.setEllipsize(android.text.TextUtils.TruncateAt.END);
        v.setShadowLayer(dp(2), 0, dp(1), Color.argb(100, 0, 0, 0));
        return v;
    }

    private void showCard(OfferParser.Offer o, CardGeometry geo, String platform) {
        removeCard();
        int cat = settings.category(o.perKm()); // 0 ruim, 1 média, 2 boa (pelo R$/km)
        int top = cat == 2 ? Color.parseColor("#34D27B") : (cat == 1 ? Color.parseColor("#FBBF24") : Color.parseColor("#F87171"));
        int bottom = cat == 2 ? Color.parseColor("#0E8A4A") : (cat == 1 ? Color.parseColor("#D97706") : Color.parseColor("#B91C1C"));
        Locale br = new Locale("pt", "BR");
        int sw = getResources().getDisplayMetrics().widthPixels;

        // retângulo do card real (ou, se não achou, um card padrão no alto da tela, sem buracos)
        android.graphics.Rect rect;
        android.graphics.Rect accept = null, close = null;
        if (geo != null && geo.rect != null) { rect = new android.graphics.Rect(geo.rect); accept = geo.accept; close = geo.close; if (close == null && platform.equals("Uber")) close = uberCloseFallback(rect); }
        else { int w = Math.min(sw - dp(24), dp(360)); int l = (sw - w) / 2; rect = new android.graphics.Rect(l, dp(110), l + w, dp(110) + dp(250)); }
        int W = rect.width();

        // conteúdo: reserva o espaço do botão de aceitar (embaixo) e do X (em cima, à direita)
        int bottomReserve = (accept != null) ? Math.max(dp(10), rect.bottom - accept.top + dp(6)) : dp(12);
        int topRightReserve = (close != null) ? Math.max(0, rect.right - close.left + dp(6)) : 0;

        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(dp(16), dp(10), dp(16), bottomReserve);

        // linha 1: categoria, plataforma e nota do passageiro
        LinearLayout head = new LinearLayout(this);
        head.setOrientation(LinearLayout.HORIZONTAL);
        head.setGravity(Gravity.CENTER_VERTICAL);
        head.setPadding(0, 0, topRightReserve, 0);
        TextView pill = txt("CORRIDA " + (cat == 2 ? "BOA" : (cat == 0 ? "RUIM" : "MÉDIA")) + " · " + platform.toUpperCase(Locale.ROOT), 12, Color.WHITE, true);
        pill.setLetterSpacing(0.08f);
        pill.setPadding(dp(10), dp(3), dp(10), dp(3));
        GradientDrawable pbg = new GradientDrawable();
        pbg.setColor(Color.argb(80, 0, 0, 0));
        pbg.setCornerRadius(dp(10));
        pill.setBackground(pbg);
        head.addView(pill);
        if (o.rating != null) {
            TextView star = txt("★ " + o.rating, 14, Color.WHITE, true);
            star.setPadding(dp(12), 0, 0, 0);
            head.addView(star);
        }
        content.addView(head);

        // linha 2: valor grande + R$/km e R$/h
        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        TextView value = bigNumber(String.format(br, "%.2f", o.value), "", 46, Gravity.START);
        row.addView(value, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1));
        LinearLayout rates = new LinearLayout(this);
        rates.setOrientation(LinearLayout.VERTICAL);
        rates.addView(bigNumber(String.format(br, "%.2f", o.perKm()), "/km", 26, Gravity.END));
        rates.addView(bigNumber(String.format(br, "%.2f", o.perHour()), "/h", 26, Gravity.END));
        row.addView(rates, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        content.addView(row);

        // medidor ruim / média / boa
        LinearLayout.LayoutParams glp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(20));
        glp.topMargin = dp(2);
        content.addView(new Gauge(this, o.perKm(), settings.badBelowKm(), settings.goodFromKm()), glp);

        // embarque e destino
        LinearLayout.LayoutParams alp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        alp.topMargin = dp(8);
        content.addView(addressBlock("EMBARQUE", o.pickupMin, o.pickupKm, o.pickupAddress, br), alp);
        LinearLayout.LayoutParams dlp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        dlp.topMargin = dp(6);
        content.addView(addressBlock("DESTINO", o.tripMin, o.tripKm, o.destination, br), dlp);

        // altura: a do card real; se o conteúdo precisar de mais, cresce para cima (a base fica alinhada)
        content.measure(View.MeasureSpec.makeMeasureSpec(W, View.MeasureSpec.EXACTLY), View.MeasureSpec.makeMeasureSpec(0, View.MeasureSpec.UNSPECIFIED));
        int H = Math.max(rect.height(), content.getMeasuredHeight());
        int cardTop = rect.bottom - H;

        // botões nossos, do mesmo tamanho dos originais, desenhados por cima deles (o toque passa para o original)
        java.util.List<DecoBtn> btns = new java.util.ArrayList<>();
        if (accept != null) btns.add(new DecoBtn(new android.graphics.RectF(accept.left - rect.left, accept.top - cardTop, accept.right - rect.left, accept.bottom - cardTop), true));
        if (close != null) btns.add(new DecoBtn(new android.graphics.RectF(close.left - rect.left, close.top - cardTop, close.right - rect.left, close.bottom - cardTop), false));

        android.widget.FrameLayout box = new android.widget.FrameLayout(this);
        box.addView(new CardBg(this, top, bottom, btns), new android.widget.FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        box.addView(content, new android.widget.FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        // composição: figurinha pequena "espiando" acima do canto do card
        card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setClipChildren(false);
        card.setClipToPadding(false);
        int stickerH = dp(140), overlap = dp(34);
        addSticker(card, cat == 2 ? R.raw.sticker_boa : (cat == 0 ? R.raw.sticker_ruim : R.raw.sticker_media), 250, 140, 34, -1);
        card.addView(box, new LinearLayout.LayoutParams(W, H));

        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                W, ViewGroup.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY, // não exige permissão de sobreposição
                // NOT_TOUCHABLE: os toques passam para o card real embaixo, então os botões originais seguem funcionando
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS
                        | WindowManager.LayoutParams.FLAG_HARDWARE_ACCELERATED,
                PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP | Gravity.START;
        lp.x = rect.left;
        lp.y = Math.max(0, cardTop - (stickerH - overlap));
        try {
            wm.addView(card, lp);
            card.setAlpha(0f);
            card.animate().alpha(1f).setDuration(160).start();
        } catch (Exception ex) { Log.e(TAG, "overlay", ex); card = null; }
        if (close == null && platform.equals("99") && geo != null) showDecline99();
    }

    private View declineWin;

    /** 99: o X de recusar fica no canto da tela (fora do card). Posição aproximada, medida nos prints da 99; mesmo tamanho do original. */
    private void showDecline99() {
        removeDecline99();
        android.util.DisplayMetrics dm = getResources().getDisplayMetrics();
        int d = Math.round(dm.widthPixels * 0.088f);
        final DecoBtn b = new DecoBtn(new android.graphics.RectF(0, 0, d, d), false);
        final android.graphics.Paint paint = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        declineWin = new View(this) {
            @Override protected void onDraw(android.graphics.Canvas c) { drawDecoBtn(c, paint, b, 0f); }
        };
        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(d, d,
                WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
                PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP | Gravity.START;
        lp.x = Math.round(dm.widthPixels * 0.938f) - d / 2;
        lp.y = Math.round(dm.heightPixels * 0.060f) - d / 2;
        try { wm.addView(declineWin, lp); } catch (Exception ex) { Log.e(TAG, "x99", ex); declineWin = null; }
    }

    private void removeDecline99() {
        if (declineWin != null) { try { wm.removeView(declineWin); } catch (Exception ignored) {} declineWin = null; }
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
        if (!unit.isEmpty()) {
            sb.append(unit);
            sb.setSpan(new android.text.style.RelativeSizeSpan(0.5f), u, sb.length(), android.text.Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        }
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
    private void addSticker(LinearLayout parent, int resId, int wDp, int hDp, int overlapDp, int startDp) {
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
            p.bottomMargin = -dp(overlapDp); // a figura "pisa" no card
            if (startDp >= 0) p.leftMargin = dp(startDp);
            p.gravity = startDp >= 0 ? Gravity.START : Gravity.CENTER_HORIZONTAL;
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
        removeDecline99();
        if (card != null) { try { wm.removeView(card); } catch (Exception ignored) {} card = null; }
    }

    private int dp(int v) { return Math.round(v * getResources().getDisplayMetrics().density); }
}
