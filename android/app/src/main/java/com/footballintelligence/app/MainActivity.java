package com.footballintelligence.app;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;

public final class MainActivity extends Activity {
    private static final String HOME = "https://football-betting-intelligence.onrender.com/";
    private WebView web;
    private TextView message;
    private ProgressBar progress;
    private boolean failed;
    private boolean allowed(Uri uri) {
        return "https".equals(uri.getScheme()) && "football-betting-intelligence.onrender.com".equals(uri.getHost()) && (uri.getPort() == -1 || uri.getPort() == 443);
    }
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(Color.rgb(16,27,38));
        root.setOnApplyWindowInsetsListener((v,insets)->{
            if(android.os.Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
                v.setPadding(bars.left,bars.top,bars.right,bars.bottom);
            } else {v.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());}
            return insets;
        });
        LinearLayout toolbar = new LinearLayout(this);
        Button refresh = new Button(this); refresh.setText("Atualizar");
        Button browser = new Button(this); browser.setText("Abrir no navegador");
        toolbar.addView(refresh); toolbar.addView(browser);
        root.addView(toolbar);
        message = new TextView(this); message.setTextColor(Color.WHITE); message.setPadding(20,12,20,12);
        message.setText("Conectando… O servidor gratuito pode levar mais de um minuto para responder.");
        root.addView(message);
        progress = new ProgressBar(this,null,android.R.attr.progressBarStyleHorizontal); root.addView(progress);
        web = new WebView(this); web.setBackgroundColor(Color.rgb(12,19,27));
        root.addView(web,new LinearLayout.LayoutParams(-1,0,1));
        setContentView(root); root.requestApplyInsets();
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSupportMultipleWindows(false);
        android.webkit.CookieManager.getInstance().setAcceptThirdPartyCookies(web,false);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
                if(allowed(request.getUrl())) return false;
                if(request.isForMainFrame() && "https".equals(request.getUrl().getScheme())) new AlertDialog.Builder(MainActivity.this).setMessage("Abrir este link no navegador?").setPositiveButton("Abrir",(d,w)->openBrowser(request.getUrl())).setNegativeButton("Cancelar",null).show();
                return true;
            }
            @Override public void onPageStarted(WebView view,String url,android.graphics.Bitmap favicon){failed=false;message.setVisibility(View.VISIBLE);message.setText("Carregando… Aguarde o servidor responder.");progress.setVisibility(View.VISIBLE);}
            @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){if(request.isForMainFrame()){failed=true;message.setVisibility(View.VISIBLE);message.setText("Sem conexão com o painel. Confira sua internet e toque em Atualizar.");}}
            @Override public void onPageFinished(WebView view,String url){progress.setVisibility(View.GONE);if(!failed)message.setVisibility(View.GONE);}
        });
        web.setWebChromeClient(new WebChromeClient(){@Override public void onProgressChanged(WebView v,int value){progress.setProgress(value);}});
        web.setDownloadListener((url,agent,disposition,mime,length)->new AlertDialog.Builder(this).setMessage("Para exportar o CSV, abra o painel no navegador e toque em Exportar seleção CSV.").setPositiveButton("Abrir painel",(d,w)->openBrowser(Uri.parse(HOME))).setNegativeButton("Cancelar",null).show());
        refresh.setOnClickListener(v->web.loadUrl(HOME));
        browser.setOnClickListener(v->openBrowser(Uri.parse(HOME)));
        web.loadUrl(HOME);
    }
    private void openBrowser(Uri uri){try{startActivity(new Intent(Intent.ACTION_VIEW,uri));}catch(android.content.ActivityNotFoundException e){message.setVisibility(View.VISIBLE);message.setText("Nenhum navegador disponível neste aparelho.");}}
    @Override public void onBackPressed(){if(web.canGoBack())web.goBack();else super.onBackPressed();}
    @Override protected void onDestroy(){web.destroy();super.onDestroy();}
}

