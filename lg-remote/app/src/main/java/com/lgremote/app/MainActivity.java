package com.lgremote.app;

import android.app.Activity;
import android.os.Bundle;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;

import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;

public class MainActivity extends Activity {
    private WebView web;

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
        setContentView(web);
        web.loadUrl("file:///android_asset/index.html");
    }
}
