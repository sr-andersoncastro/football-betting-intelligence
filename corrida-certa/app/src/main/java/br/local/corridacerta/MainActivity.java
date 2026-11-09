package br.local.corridacerta;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.text.InputType;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

public class MainActivity extends Activity {
    private Settings s;
    private TextView last;

    @Override protected void onCreate(Bundle b) {
        super.onCreate(b);
        s = new Settings(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        int pad = Math.round(20 * getResources().getDisplayMetrics().density);
        root.setPadding(pad, pad * 2, pad, pad);

        root.addView(text("Corrida Certa", 26, true));
        root.addView(text("Mostra R$/km e R$/hora sobre o card da Uber e da 99.", 14, false));

        Button acc = new Button(this);
        acc.setText("1) Ativar serviço de acessibilidade");
        acc.setOnClickListener(v -> startActivity(new Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        root.addView(acc);
        root.addView(text("Em Acessibilidade > Apps instalados > Corrida Certa > Ligar. Se estiver bloqueado: Info do app > ⋮ > Permitir configurações restritas.", 12, false));

        Switch sw = new Switch(this);
        sw.setText("Mostrar cartão sobre as corridas");
        sw.setChecked(s.enabled());
        sw.setOnCheckedChangeListener((v, on) -> s.setEnabled(on));
        root.addView(sw);

        root.addView(text("Mínimo R$/km (verde acima disso)", 14, false));
        EditText km = number(String.format(java.util.Locale.US, "%.2f", s.minPerKm()));
        root.addView(km);
        root.addView(text("Mínimo R$/hora", 14, false));
        EditText hr = number(String.format(java.util.Locale.US, "%.2f", s.minPerHour()));
        root.addView(hr);

        Button save = new Button(this);
        save.setText("Salvar");
        save.setOnClickListener(v -> {
            try {
                s.save(Double.parseDouble(km.getText().toString().replace(',', '.')),
                       Double.parseDouble(hr.getText().toString().replace(',', '.')));
                Toast.makeText(this, "Salvo", Toast.LENGTH_SHORT).show();
            } catch (NumberFormatException e) { Toast.makeText(this, "Valor inválido", Toast.LENGTH_SHORT).show(); }
        });
        root.addView(save);

        root.addView(text("Última leitura", 16, true));
        last = text("", 13, false);
        root.addView(last);

        ScrollView sv = new ScrollView(this);
        sv.addView(root);
        setContentView(sv);
    }

    @Override protected void onResume() {
        super.onResume();
        String raw = s.lastRaw();
        last.setText(s.lastResult() + (raw.isEmpty() ? "" : "\n\nÚltimo texto capturado (para diagnóstico):\n" + raw));
    }

    private TextView text(String t, int sp, boolean bold) {
        TextView v = new TextView(this);
        v.setText(t);
        v.setTextSize(sp);
        v.setPadding(0, 12, 0, 12);
        if (bold) v.setTypeface(v.getTypeface(), android.graphics.Typeface.BOLD);
        return v;
    }

    private EditText number(String init) {
        EditText e = new EditText(this);
        e.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
        e.setText(init);
        return e;
    }
}
