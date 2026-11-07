package com.lgremote.app;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.net.wifi.WifiManager;
import android.os.Bundle;
import android.speech.RecognizerIntent;
import android.graphics.Color;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;

import org.json.JSONArray;

import java.net.DatagramPacket;
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
