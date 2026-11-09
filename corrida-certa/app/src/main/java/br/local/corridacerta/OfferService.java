package br.local.corridacerta;

import android.accessibilityservice.AccessibilityService;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
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
    }

    @Override public void onAccessibilityEvent(AccessibilityEvent e) {
        if (settings == null || !settings.enabled()) return;
        handler.removeCallbacks(scan);
        handler.postDelayed(scan, 120);
    }

    @Override public void onInterrupt() { handler.removeCallbacks(scan); }

    @Override public void onDestroy() { handler.removeCallbacksAndMessages(null); removeCard(); super.onDestroy(); }

    private void scanWindows() {
        boolean found = false;
        for (AccessibilityWindowInfo w : getWindows()) {
            AccessibilityNodeInfo root = w.getRoot();
            if (root == null) continue;
            String pkg = String.valueOf(root.getPackageName());
            if (!pkg.equals(UBER) && !pkg.equals(APP99)) continue;
            StringBuilder sb = new StringBuilder();
            read(root, sb, 0);
            String text = sb.toString();
            OfferParser.Offer o = OfferParser.parse(text);
            if (o != null) {
                found = true;
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
        if (!found) { lastShownText = ""; removeCard(); }
    }

    private void read(AccessibilityNodeInfo n, StringBuilder sb, int depth) {
        if (n == null || depth > 40 || sb.length() > 20000) return;
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
