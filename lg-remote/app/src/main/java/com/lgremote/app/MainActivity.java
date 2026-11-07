package com.lgremote.app;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.net.wifi.WifiManager;
import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.graphics.Color;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;

import org.json.JSONArray;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.DatagramPacket;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.net.DatagramSocket;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.net.NetworkInterface;
import java.net.Socket;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Enumeration;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

public class MainActivity extends Activity {
    private static final int REQ_VOICE = 77;
    private static final int REQ_AUDIO = 78;
    private SpeechRecognizer sr;
    private boolean continuous = false;
    private int errorStreak = 0;
    private long lastRms = 0;
    private final Handler handler = new Handler(Looper.getMainLooper());

    private void startListening() {
        if (!continuous) return;
        if (sr == null) { sr = SpeechRecognizer.createSpeechRecognizer(this); sr.setRecognitionListener(listener); }
        Intent i = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        i.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "pt-BR");
        i.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true);
        i.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 5);
        i.putExtra(RecognizerIntent.EXTRA_CALLING_PACKAGE, getPackageName());
        try { sr.startListening(i); js("window.__voiceState && window.__voiceState('listening')"); }
        catch (Exception e) { continuous = false; js("window.__voiceErr && window.__voiceErr('Falha ao iniciar o microfone')"); }
    }

    private void restartSoon(long ms) {
        handler.postDelayed(new Runnable() { @Override public void run() { startListening(); } }, ms);
    }

    private final RecognitionListener listener = new RecognitionListener() {
        @Override public void onReadyForSpeech(Bundle b) { js("window.__voiceState && window.__voiceState('listening')"); }
        @Override public void onBeginningOfSpeech() { js("window.__voiceState && window.__voiceState('hearing')"); }
        @Override public void onRmsChanged(float v) {
            long now = System.currentTimeMillis();
            if (now - lastRms > 70) { lastRms = now; js("window.__rms && window.__rms(" + v + ")"); }
        }
        @Override public void onBufferReceived(byte[] b) { }
        @Override public void onEndOfSpeech() { js("window.__voiceState && window.__voiceState('thinking')"); }
        @Override public void onEvent(int t, Bundle b) { }
        @Override public void onPartialResults(Bundle b) {
            ArrayList<String> r = b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
            if (r != null && !r.isEmpty()) js("window.__voicePartial && window.__voicePartial(" + new JSONArray(r.subList(0, 1)).toString() + "[0])");
        }
        @Override public void onResults(Bundle b) {
            errorStreak = 0;
            ArrayList<String> r = b.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
            if (r != null && !r.isEmpty()) js("window.__voice && window.__voice(" + new JSONArray(r).toString() + ")");
            if (continuous) restartSoon(350); else js("window.__voiceState && window.__voiceState('idle')");
        }
        @Override public void onError(int err) {
            if (err == SpeechRecognizer.ERROR_INSUFFICIENT_PERMISSIONS) {
                continuous = false; js("window.__voiceErr && window.__voiceErr('Sem permissão do microfone')"); return;
            }
            boolean soft = err == SpeechRecognizer.ERROR_NO_MATCH || err == SpeechRecognizer.ERROR_SPEECH_TIMEOUT;
            if (soft) errorStreak = 0; else errorStreak++;
            if (continuous && errorStreak < 5) { restartSoon(soft ? 250 : 900); return; }
            continuous = false;
            js("window.__voiceErr && window.__voiceErr('O reconhecimento de voz parou (erro " + err + ")')");
        }
    };

    @Override
    public void onRequestPermissionsResult(int req, String[] perms, int[] results) {
        super.onRequestPermissionsResult(req, perms, results);
        if (req != REQ_AUDIO) return;
        if (results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED) { continuous = true; startListening(); }
        else js("window.__voiceErr && window.__voiceErr('Permissão do microfone negada')");
    }
    private WebView web;

    private void js(String code) { web.evaluateJavascript(code, null); }

    @Override
    protected void onActivityResult(int req, int res, Intent data) {
        super.onActivityResult(req, res, data);
        if (req != REQ_VOICE) return;
        if (res == RESULT_OK && data != null) {
            ArrayList<String> r = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS);
            if (r != null && !r.isEmpty()) { js("window.__voice && window.__voice(" + new JSONArray(r).toString() + ")"); return; }
        }
        js("window.__voiceErr && window.__voiceErr('Não ouvi nenhum comando')");
    }

    /** Ponte mínima para ligar a TV (Wake-on-LAN). Só existe no assets locais do app. */
    public class Native {
        @JavascriptInterface
        public void wake(final String mac) {
            new Thread(new Runnable() {
                @Override public void run() {
                    try {
                        String[] parts = mac.split("[:-]");
                        if (parts.length != 6) return;
                        byte[] m = new byte[6];
                        for (int i = 0; i < 6; i++) m[i] = (byte) Integer.parseInt(parts[i], 16);
                        byte[] pkt = new byte[102];
                        for (int i = 0; i < 6; i++) pkt[i] = (byte) 0xFF;
                        for (int i = 1; i <= 16; i++) System.arraycopy(m, 0, pkt, i * 6, 6);
                        DatagramSocket sock = new DatagramSocket();
                        sock.setBroadcast(true);
                        InetAddress addr = InetAddress.getByName("255.255.255.255");
                        sock.send(new DatagramPacket(pkt, pkt.length, addr, 9));
                        sock.send(new DatagramPacket(pkt, pkt.length, addr, 7));
                        sock.close();
                    } catch (Exception ignored) { }
                }
            }).start();
        }



        /** Busca no YouTube (página de resultados, sem chave de API). Resposta em window.__ytResults([{id,title}]) ou window.__ytErr(msg). */
        @JavascriptInterface
        public void ytSearch(final String query) {
            new Thread(new Runnable() { @Override public void run() {
                String out;
                try {
                    URL u = new URL("https://www.youtube.com/results?hl=pt-BR&gl=BR&search_query=" + URLEncoder.encode(query, "UTF-8"));
                    HttpURLConnection c = (HttpURLConnection) u.openConnection();
                    c.setConnectTimeout(8000); c.setReadTimeout(10000);
                    c.setRequestProperty("User-Agent", "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36");
                    c.setRequestProperty("Accept-Language", "pt-BR,pt;q=0.9");
                    c.setRequestProperty("Cookie", "CONSENT=YES+1");
                    InputStream in = c.getInputStream();
                    ByteArrayOutputStream bo = new ByteArrayOutputStream();
                    byte[] buf = new byte[16384]; int n; int total = 0;
                    while ((n = in.read(buf)) > 0 && total < 3000000) { bo.write(buf, 0, n); total += n; }
                    in.close();
                    String html = bo.toString("UTF-8");
                    java.util.List<String[]> r = YtParser.parse(html, 8);
                    out = r.isEmpty() ? "window.__ytErr && window.__ytErr('O YouTube não retornou vídeos para essa busca')"
                                      : "window.__ytResults && window.__ytResults(" + YtParser.toJson(r) + ")";
                } catch (Exception e) {
                    out = "window.__ytErr && window.__ytErr('Não consegui buscar no YouTube (sem internet no celular?)')";
                }
                final String code = out;
                runOnUiThread(new Runnable() { @Override public void run() { js(code); } });
            } }).start();
        }


        /** Escuta contínua (sem janela do Google). Resultados em window.__voice / __voicePartial / __voiceState. */
        @JavascriptInterface
        public void voiceStart() {
            runOnUiThread(new Runnable() { @Override public void run() {
                if (!SpeechRecognizer.isRecognitionAvailable(MainActivity.this)) {
                    js("window.__voiceErr && window.__voiceErr('Reconhecimento de voz indisponível neste celular')"); return;
                }
                if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                    requestPermissions(new String[] { Manifest.permission.RECORD_AUDIO }, REQ_AUDIO); return;
                }
                continuous = true; errorStreak = 0; startListening();
            } });
        }

        @JavascriptInterface
        public void voiceStop() {
            runOnUiThread(new Runnable() { @Override public void run() {
                continuous = false;
                handler.removeCallbacksAndMessages(null);
                if (sr != null) { try { sr.cancel(); } catch (Exception ignored) { } }
                js("window.__voiceState && window.__voiceState('idle')");
            } });
        }

        /** Abre o reconhecimento de voz do Android (pt-BR). Resposta em window.__voice([...]) ou window.__voiceErr(msg). */
        @JavascriptInterface
        public void listen() {
            runOnUiThread(new Runnable() { @Override public void run() {
                try {
                    Intent i = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
                    i.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
                    i.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "pt-BR");
                    i.putExtra(RecognizerIntent.EXTRA_PROMPT, "Diga o comando para a TV");
                    i.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 5);
                    startActivityForResult(i, REQ_VOICE);
                } catch (Exception e) {
                    js("window.__voiceErr && window.__voiceErr('Reconhecimento de voz indisponível neste celular')");
                }
            } });
        }

        /** Procura TVs LG na rede (SSDP; se nada, varre a sub-rede na porta 3000). Resposta em window.__tvsFound(json). */
        @JavascriptInterface
        public void discover() {
            new Thread(new Runnable() {
                @Override public void run() {
                    List<String> found = new ArrayList<String>();
                    WifiManager.MulticastLock lock = null;
                    try {
                        WifiManager wm = (WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE);
                        if (wm != null) { lock = wm.createMulticastLock("lgremote"); lock.setReferenceCounted(false); lock.acquire(); }
                    } catch (Exception ignored) { }
                    try { ssdp(found); } catch (Exception ignored) { }
                    if (found.isEmpty()) { try { scan(found); } catch (Exception ignored) { } }
                    try { if (lock != null && lock.isHeld()) lock.release(); } catch (Exception ignored) { }
                    StringBuilder sb = new StringBuilder("[");
                    for (int i = 0; i < found.size(); i++) { if (i > 0) sb.append(','); sb.append('"').append(found.get(i)).append('"'); }
                    sb.append(']');
                    final String json = sb.toString();
                    runOnUiThread(new Runnable() { @Override public void run() {
                        web.evaluateJavascript("window.__tvsFound && window.__tvsFound('" + json + "')", null);
                    } });
                }
            }).start();
        }
    }


    private void ssdp(List<String> found) throws Exception {
        String msg = "M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\nMX: 2\r\n"
                + "ST: urn:lge-com:service:webos-second-screen:1\r\n\r\n";
        byte[] data = msg.getBytes("UTF-8");
        DatagramSocket sock = new DatagramSocket();
        sock.setSoTimeout(700);
        InetAddress group = InetAddress.getByName("239.255.255.250");
        for (int i = 0; i < 2; i++) sock.send(new DatagramPacket(data, data.length, group, 1900));
        long end = System.currentTimeMillis() + 3500;
        byte[] buf = new byte[2048];
        while (System.currentTimeMillis() < end) {
            try {
                DatagramPacket p = new DatagramPacket(buf, buf.length);
                sock.receive(p);
                String text = new String(p.getData(), 0, p.getLength(), "UTF-8").toLowerCase();
                String ip = p.getAddress().getHostAddress();
                if ((text.contains("webos") || text.contains("lge")) && !found.contains(ip)) found.add(ip);
            } catch (java.net.SocketTimeoutException ignored) { }
        }
        sock.close();
    }

    private String localPrefix() throws Exception {
        Enumeration<NetworkInterface> ifs = NetworkInterface.getNetworkInterfaces();
        for (NetworkInterface ni : Collections.list(ifs)) {
            if (!ni.isUp() || ni.isLoopback()) continue;
            for (InetAddress a : Collections.list(ni.getInetAddresses())) {
                if (a instanceof Inet4Address && a.isSiteLocalAddress()) {
                    String h = a.getHostAddress();
                    return h.substring(0, h.lastIndexOf('.') + 1);
                }
            }
        }
        return null;
    }

    private void scan(final List<String> found) throws Exception {
        final String prefix = localPrefix();
        if (prefix == null) return;
        ExecutorService ex = Executors.newFixedThreadPool(48);
        for (int i = 1; i < 255; i++) {
            final String ip = prefix + i;
            ex.execute(new Runnable() { @Override public void run() {
                Socket s = new Socket();
                try {
                    s.connect(new InetSocketAddress(ip, 3000), 500);
                    synchronized (found) { if (!found.contains(ip)) found.add(ip); }
                } catch (Exception ignored) { } finally { try { s.close(); } catch (Exception ignored) { } }
            } });
        }
        ex.shutdown();
        ex.awaitTermination(15, TimeUnit.SECONDS);
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);
        s.setAllowContentAccess(false);
        web.addJavascriptInterface(new Native(), "Native");
        web.setBackgroundColor(Color.parseColor("#050506"));
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(Color.parseColor("#050506"));
        root.addView(web, new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        /* Android 15+ desenha sob as barras do sistema: reserva o espaço delas */
        root.setOnApplyWindowInsetsListener(new View.OnApplyWindowInsetsListener() {
            @Override public WindowInsets onApplyWindowInsets(View v, WindowInsets in) {
                v.setPadding(in.getSystemWindowInsetLeft(), in.getSystemWindowInsetTop(), in.getSystemWindowInsetRight(), in.getSystemWindowInsetBottom());
                return in;
            }
        });
        setContentView(root);
        web.loadUrl("file:///android_asset/index.html");
    }
}
