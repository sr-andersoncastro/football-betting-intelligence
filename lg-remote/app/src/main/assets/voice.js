/* Interpreta comandos de voz em português e os transforma em ações na TV. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Voice = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  var W = { zero:0, um:1, uma:1, dois:2, duas:2, tres:3, quatro:4, cinco:5, seis:6, sete:7, oito:8, nove:9, dez:10, onze:11, doze:12,
    treze:13, catorze:14, quatorze:14, quinze:15, dezesseis:16, dezessete:17, dezoito:18, dezenove:19, vinte:20, trinta:30,
    quarenta:40, cinquenta:50, sessenta:60, setenta:70, oitenta:80, noventa:90, cem:100 };
  var BUILTIN = [['netflix', 'netflix'], ['youtube', 'youtube.leanback.v4'], ['prime video', 'amazon'], ['prime', 'amazon'], ['amazon', 'amazon']];

  function norm(t) { return String(t || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim(); }

  /* primeiro número (dígitos ou por extenso, ex.: "vinte e cinco") */
  function num(t) {
    var d = t.match(/\b\d+\b/); if (d) return parseInt(d[0], 10);
    var w = t.split(' '), total = null;
    for (var i = 0; i < w.length; i++) {
      if (W.hasOwnProperty(w[i])) {
        total = W[w[i]];
        if (total >= 20 && total < 100 && w[i + 1] === 'e' && W.hasOwnProperty(w[i + 2]) && W[w[i + 2]] < 10) total += W[w[i + 2]];
        return total;
      }
    }
    return null;
  }
  function times(t) { var m = t.match(/(\S+) vezes?/); if (m) { var n = num(m[1]); if (n) return Math.min(n, 20); } return 1; }
  function seq(n, fn) { var p = Promise.resolve(); for (var i = 0; i < n; i++) p = p.then(fn); return p; }
  function find(list, key, getName) {
    for (var i = 0; i < (list || []).length; i++) { var n = norm(getName(list[i])); if (n && (n.indexOf(key) >= 0 || key.indexOf(n) >= 0)) return list[i]; }
    return null;
  }

  /* devolve { label, run(tv, ctx) } ou null */
  function interpret(raw, ctx) {
    ctx = ctx || {};
    var t = norm(raw); if (!t) return null;
    var n = times(t), m;
    function act(label, fn) { return { label: label, run: fn }; }
    function btn(label, name) { return act(label, function (tv) { return seq(n, function () { return tv.button(name); }); }); }

    // desligar / ligar
    if (/^(desligar|desliga|apagar|apaga)( a| essa| esta)?( tv| televisao)?$/.test(t) || /^(desligar|desliga) (tudo|a tv|a televisao)/.test(t)) return act('Desligar a TV', function (tv) { return tv.powerOff(); });
    if (/^(ligar|liga|acordar)( a| essa)?( tv| televisao)?$/.test(t)) return act('Ligar a TV', function (tv, c) { return c.wake ? c.wake() : Promise.reject(new Error('Não sei o MAC da TV')); });

    // som
    if (/(tirar|tira|desativar|desativa|desligar|desliga|cancelar) .*mudo/.test(t) || /(ativar|ativa|ligar|liga|voltar|volta|devolver|restaurar) .*som/.test(t) || /^(com som|sem mudo)$/.test(t)) return act('Som ligado', function (tv) { return tv.mute(false); });
    if (/\b(mudo|silenciar|silencio|sem som)\b/.test(t)) return act('Mudo', function (tv) { return tv.mute(true); });
    if ((m = t.match(/volume (?:em |para |no |a )?(.+)/)) && num(m[1]) !== null && !/(aument|diminu|mais|menos|vezes|sobe|subir|abaix|baix)/.test(t)) {
      var v = Math.max(0, Math.min(100, num(m[1]))); return act('Volume ' + v, function (tv) { return tv.setVolume(v); });
    }
    if (/(aumenta|aumentar|sobe|subir|mais alto|mais volume|volume mais|mais som)/.test(t) && /(volume|som|alto)/.test(t)) return act('Volume +' + (n > 1 ? ' ×' + n : ''), function (tv) { return seq(n, function () { return tv.volumeUp(); }); });
    if (/(diminui|diminuir|abaixa|abaixar|baixa|baixar|menos volume|volume menos|menos som|mais baixo|menos alto)/.test(t) && /(volume|som|baixo|alto)/.test(t)) return act('Volume −' + (n > 1 ? ' ×' + n : ''), function (tv) { return seq(n, function () { return tv.volumeDown(); }); });

    // canais
    if (/(proximo canal|canal (acima|seguinte|proximo)|passa(r)? (o )?canal|muda(r)? (o )?canal$)/.test(t)) return act('Canal +', function (tv) { return seq(n, function () { return tv.channelUp(); }); });
    if (/(canal (anterior|abaixo)|voltar canal|volta canal)/.test(t)) return act('Canal −', function (tv) { return seq(n, function () { return tv.channelDown(); }); });
    if ((m = t.match(/canal (.+)/)) && num(m[1]) !== null) {
      var digits = String(num(m[1])).split(''); return act('Canal ' + digits.join(''), function (tv) {
        return digits.reduce(function (p, d) { return p.then(function () { return tv.button(d); }); }, Promise.resolve()).then(function () { return tv.button('ENTER'); });
      });
    }

    // entradas
    if ((m = t.match(/(?:hdmi|entrada) ?(\d)/))) {
      var key = 'hdmi ' + m[1]; return act('Entrada HDMI ' + m[1], function (tv, c) {
        var hit = find(c.inputs, key, function (i) { return i.label || i.id; }) || find(c.inputs, 'hdmi' + m[1], function (i) { return i.id; });
        return tv.setInput(hit ? hit.id : 'HDMI_' + m[1]);
      });
    }

    // apps
    var an = (t.match(/^(?:abrir|abre|abra|iniciar|inicia|colocar|coloca|colocar no|ir para|va para|ir pro|vai pro|ligar o|liga o)\s+(?:o |a |no |na )?(.+)/) || [])[1] || (BUILTIN.some(function (b) { return t === b[0]; }) ? t : null);
    if (an) {
      for (var i = 0; i < BUILTIN.length; i++) if (an.indexOf(BUILTIN[i][0]) === 0 || BUILTIN[i][0] === an) { var id = BUILTIN[i][1]; return act('Abrir ' + an, function (tv) { return tv.launch(id); }); }
      return act('Abrir ' + an, function (tv, c) {
        var hit = find(c.apps, an, function (a) { return a.title; });
        return hit ? tv.launch(hit.id) : Promise.reject(new Error('Não achei o app "' + an + '" na TV'));
      });
    }

    // mídia
    if (/^(pausar|pausa|pause)\b/.test(t)) return act('Pausar', function (tv) { return tv.media('pause'); });
    if (/^(play|reproduzir|reproduz|continuar|continua|dar play|retomar)\b/.test(t)) return act('Reproduzir', function (tv) { return tv.media('play'); });
    if (/^(avancar|avanca|adiantar)/.test(t)) return act('Avançar', function (tv) { return tv.media('fastForward'); });
    if (/^(retroceder|retrocede|rebobinar|rebobina)/.test(t)) return act('Retroceder', function (tv) { return tv.media('rewind'); });
    if (/^(parar|para)$/.test(t)) return act('Parar', function (tv) { return tv.media('stop'); });

    // digitar
    if ((m = raw.toLowerCase().match(/^\s*(?:digitar|digita|escrever|escreve|pesquisar|pesquisa|buscar|busca|procurar|procura)\s+(.+)/))) {
      var text = m[1].trim(); return act('Digitar “' + text + '”', function (tv) { return tv.type(text); });
    }

    // navegação
    if (/^(clicar|clique|clica)\b/.test(t)) return act('Clique', function (tv) { return tv.click(); });
    if (/\b(cima|sobe|subir)\b/.test(t)) return btn('Cima', 'UP');
    if (/\b(baixo|desce|descer)\b/.test(t)) return btn('Baixo', 'DOWN');
    if (/\besquerda\b/.test(t)) return btn('Esquerda', 'LEFT');
    if (/\bdireita\b/.test(t)) return btn('Direita', 'RIGHT');
    if (/^(ok|okay|confirmar|confirma|selecionar|seleciona|entrar|enter|escolher)\b/.test(t)) return btn('OK', 'ENTER');
    if (/^(voltar|volta|retornar|anterior)\b/.test(t)) return btn('Voltar', 'BACK');
    if (/(inicio|home|tela inicial|menu inicial)/.test(t)) return btn('Início', 'HOME');
    if (/(configuracoes|ajustes|configurar)/.test(t)) return btn('Configurações', 'QMENU');
    if (/^menu\b/.test(t)) return btn('Menu', 'MENU');
    if (/^(sair|fechar|fecha)\b/.test(t)) return btn('Sair', 'EXIT');
    if (/\b(guia|programacao)\b/.test(t)) return btn('Guia', 'GUIDE');
    if (/^info/.test(t)) return btn('Info', 'INFO');
    return null;
  }

  /* tenta cada alternativa do reconhecedor até uma fazer sentido */
  function pick(alternatives, ctx) {
    for (var i = 0; i < alternatives.length; i++) { var c = interpret(alternatives[i], ctx); if (c) { c.heard = alternatives[i]; return c; } }
    return null;
  }
  return { interpret: interpret, pick: pick, norm: norm };
});
