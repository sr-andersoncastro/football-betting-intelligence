/* Cliente mínimo do protocolo SSAP das LG webOS (rede local). Funciona no WebView e no Node 22. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.LGTV = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  var PERMISSIONS = ['LAUNCH', 'LAUNCH_WEBAPP', 'APP_TO_APP', 'CLOSE', 'TEST_OPEN', 'TEST_PROTECTED',
    'CONTROL_AUDIO', 'CONTROL_DISPLAY', 'CONTROL_INPUT_JOYSTICK', 'CONTROL_INPUT_MEDIA_RECORDING',
    'CONTROL_INPUT_MEDIA_PLAYBACK', 'CONTROL_INPUT_TV', 'CONTROL_POWER', 'READ_APP_STATUS',
    'READ_CURRENT_CHANNEL', 'READ_INPUT_DEVICE_LIST', 'READ_NETWORK_STATE', 'READ_RUNNING_APPS',
    'READ_TV_CHANNEL_LIST', 'WRITE_NOTIFICATION_TOAST', 'READ_POWER_STATE', 'READ_SETTINGS',
    'CONTROL_TV_SCREEN', 'CONTROL_TV_STANBY'];

  /* Manifesto assinado de exemplo da LG (o mesmo usado por pywebostv/aiopylgtv): sem ele a TV responde 401 "insufficient permissions". */
  var MANIFEST = {"appVersion":"1.1","manifestVersion":1,"permissions":["LAUNCH","LAUNCH_WEBAPP","APP_TO_APP","CLOSE","TEST_OPEN","TEST_PROTECTED","CONTROL_AUDIO","CONTROL_DISPLAY","CONTROL_INPUT_JOYSTICK","CONTROL_INPUT_MEDIA_RECORDING","CONTROL_INPUT_MEDIA_PLAYBACK","CONTROL_INPUT_TV","CONTROL_POWER","READ_APP_STATUS","READ_CURRENT_CHANNEL","READ_INPUT_DEVICE_LIST","READ_NETWORK_STATE","READ_RUNNING_APPS","READ_TV_CHANNEL_LIST","WRITE_NOTIFICATION_TOAST","READ_POWER_STATE","READ_COUNTRY_INFO","READ_SETTINGS","CONTROL_TV_SCREEN","CONTROL_TV_STANBY","CONTROL_FAVORITE_GROUP","CONTROL_USER_INFO","CHECK_BLUETOOTH_DEVICE","CONTROL_BLUETOOTH","CONTROL_TIMER_INFO","STB_INTERNAL_CONNECTION","CONTROL_RECORDING","READ_RECORDING_STATE","WRITE_RECORDING_LIST","READ_RECORDING_LIST","READ_RECORDING_SCHEDULE","WRITE_RECORDING_SCHEDULE","READ_STORAGE_DEVICE_LIST","READ_TV_PROGRAM_INFO","CONTROL_BOX_CHANNEL","READ_TV_ACR_AUTH_TOKEN","READ_TV_CONTENT_STATE","READ_TV_CURRENT_TIME","ADD_LAUNCHER_CHANNEL","SET_CHANNEL_SKIP","RELEASE_CHANNEL_SKIP","CONTROL_CHANNEL_BLOCK","DELETE_SELECT_CHANNEL","CONTROL_CHANNEL_GROUP","SCAN_TV_CHANNELS","CONTROL_TV_POWER","CONTROL_WOL"],"signatures":[{"signature":"eyJhbGdvcml0aG0iOiJSU0EtU0hBMjU2Iiwia2V5SWQiOiJ0ZXN0LXNpZ25pbmctY2VydCIsInNpZ25hdHVyZVZlcnNpb24iOjF9.hrVRgjCwXVvE2OOSpDZ58hR+59aFNwYDyjQgKk3auukd7pcegmE2CzPCa0bJ0ZsRAcKkCTJrWo5iDzNhMBWRyaMOv5zWSrthlf7G128qvIlpMT0YNY+n/FaOHE73uLrS/g7swl3/qH/BGFG2Hu4RlL48eb3lLKqTt2xKHdCs6Cd4RMfJPYnzgvI4BNrFUKsjkcu+WD4OO2A27Pq1n50cMchmcaXadJhGrOqH5YmHdOCj5NSHzJYrsW0HPlpuAx/ECMeIZYDh6RMqaFM2DXzdKX9NmmyqzJ3o/0lkk/N97gfVRLW5hA29yeAwaCViZNCP8iC9aO0q9fQojoa7NQnAtw==","signatureVersion":1}],"signed":{"appId":"com.lge.test","created":"20140509","localizedAppNames":{"":"LG Remote App","ko-KR":"리모컨 앱","zxx-XX":"ЛГ Rэмotэ AПП"},"localizedVendorNames":{"":"LG Electronics"},"permissions":["TEST_SECURE","CONTROL_INPUT_TEXT","CONTROL_MOUSE_AND_KEYBOARD","READ_INSTALLED_APPS","READ_LGE_SDX","READ_NOTIFICATIONS","SEARCH","WRITE_SETTINGS","WRITE_NOTIFICATION_ALERT","CONTROL_POWER","READ_CURRENT_CHANNEL","READ_RUNNING_APPS","READ_UPDATE_INFO","UPDATE_FROM_REMOTE_APP","READ_LGE_TV_INPUT_EVENTS","READ_TV_CURRENT_TIME"],"serial":"2f930e2d2cfe083771f68e4fe7bb07","vendorId":"com.lge"}};

  function LGTV(opts) {
    opts = opts || {};
    this.WS = opts.WebSocket || (typeof WebSocket !== 'undefined' ? WebSocket : null);
    this.clientKey = opts.clientKey || null;
    this.onKey = opts.onKey || function () {};
    this.onState = opts.onState || function () {};
    this.port = opts.port || 3000;
    this.ws = null; this.pointer = null; this.seq = 0; this.pending = {}; this.ready = false;
  }

  LGTV.prototype.connect = function (ip) {
    var self = this;
    return new Promise(function (resolve, reject) {
      var done = false;
      var ws;
      try { ws = new self.WS('ws://' + ip + ':' + self.port); } catch (e) { return reject(e); }
      self.ws = ws;
      var timer = setTimeout(function () { fail(new Error('Tempo esgotado: a TV não respondeu em ' + ip)); }, 60000);
      var openTimer = setTimeout(function () { fail(new Error('A TV não respondeu em ' + ip + '. IP mudou ou TV desligada?')); }, 6000);
      function fail(err) { clearTimeout(openTimer); if (done) return; done = true; clearTimeout(timer); try { ws.close(); } catch (e) {} reject(err); }
      ws.onerror = function () { fail(new Error('Não consegui falar com a TV em ' + ip + '. Confira o IP e se celular e TV estão na mesma rede.')); };
      ws.onclose = function () { self.ready = false; self.onState('desconectado'); fail(new Error('Conexão fechada')); };
      ws.onopen = function () {
        clearTimeout(openTimer);
        self.onState('aguardando permissão na TV');
        var payload = { forcePairing: false, pairingType: 'PROMPT', manifest: MANIFEST };
        if (self.clientKey) payload['client-key'] = self.clientKey;
        self.pending['register_0'] = function (msg) {
          if (msg.type === 'registered') {
            self.clientKey = msg.payload && msg.payload['client-key'];
            if (self.clientKey) self.onKey(self.clientKey);
            self.ready = true; self.onState('conectado');
            if (!done) { done = true; clearTimeout(timer); resolve(self); }
            return true;
          }
          if (msg.type === 'error') { fail(new Error(msg.error || 'Pareamento recusado')); return true; }
          return false; // "response" = pedido de permissão exibido na TV
        };
        ws.send(JSON.stringify({ type: 'register', id: 'register_0', payload: payload }));
      };
      ws.onmessage = function (ev) {
        var msg; try { msg = JSON.parse(ev.data); } catch (e) { return; }
        var cb = self.pending[msg.id];
        if (!cb) return;
        var finished = cb(msg);
        if (finished !== false) delete self.pending[msg.id];
      };
    });
  };

  LGTV.prototype.request = function (uri, payload) {
    var self = this;
    return new Promise(function (resolve, reject) {
      if (!self.ready) return reject(new Error('Não conectado'));
      var id = 'req_' + (++self.seq);
      var t = setTimeout(function () { delete self.pending[id]; reject(new Error('Sem resposta da TV')); }, 8000);
      self.pending[id] = function (msg) {
        clearTimeout(t);
        if (msg.type === 'error') reject(new Error(msg.error || 'Erro'));
        else resolve(msg.payload || {});
      };
      self.ws.send(JSON.stringify({ type: 'request', id: id, uri: uri, payload: payload || {} }));
    });
  };

  /* Botões e mouse vão por um segundo socket. */
  LGTV.prototype.pointerSend = function (text) {
    var self = this;
    if (self.pointer && self.pointer.readyState === 1) { self.pointer.send(text); return Promise.resolve(); }
    if (self.pointerOpening) return self.pointerOpening.then(function () { self.pointer.send(text); });
    self.pointerOpening = self.request('ssap://com.webos.service.networkinput/getPointerInputSocket').then(function (r) {
      return new Promise(function (resolve, reject) {
        var p = new self.WS(r.socketPath);
        self.pointer = p;
        p.onopen = function () { self.pointerOpening = null; resolve(); };
        p.onerror = function () { self.pointerOpening = null; reject(new Error('Falha no canal de botões/mouse')); };
        p.onclose = function () { self.pointer = null; };
      });
    });
    return self.pointerOpening.then(function () { self.pointer.send(text); });
  };
  LGTV.prototype.button = function (name) { return this.pointerSend('type:button\nname:' + name + '\n\n'); };
  LGTV.prototype.move = function (dx, dy, drag) { return this.pointerSend('type:move\ndx:' + Math.round(dx) + '\ndy:' + Math.round(dy) + '\ndown:' + (drag ? 1 : 0) + '\n\n'); };
  LGTV.prototype.click = function () { return this.pointerSend('type:click\n\n'); };
  LGTV.prototype.scroll = function (dx, dy) { return this.pointerSend('type:scroll\ndx:' + Math.round(dx) + '\ndy:' + Math.round(dy) + '\n\n'); };

  LGTV.prototype.volumeUp = function () { return this.request('ssap://audio/volumeUp'); };
  LGTV.prototype.volumeDown = function () { return this.request('ssap://audio/volumeDown'); };
  LGTV.prototype.mute = function (on) { return this.request('ssap://audio/setMute', { mute: !!on }); };
  LGTV.prototype.channelUp = function () { return this.request('ssap://tv/channelUp'); };
  LGTV.prototype.channelDown = function () { return this.request('ssap://tv/channelDown'); };
  LGTV.prototype.powerOff = function () { return this.request('ssap://system/turnOff'); };
  LGTV.prototype.launch = function (id) { return this.request('ssap://system.launcher/launch', { id: id }); };
  LGTV.prototype.toast = function (message) { return this.request('ssap://system.notifications/createToast', { message: message }); };
  LGTV.prototype.setVolume = function (v) { return this.request('ssap://audio/setVolume', { volume: v }); };
  LGTV.prototype.getInputs = function () { return this.request('ssap://tv/getExternalInputList').then(function (r) { return r.devices || []; }); };
  LGTV.prototype.setInput = function (id) { return this.request('ssap://tv/switchInput', { inputId: id }); };
  LGTV.prototype.getApps = function () { return this.request('ssap://com.webos.applicationManager/listLaunchPoints').then(function (r) { return r.launchPoints || []; }); };
  LGTV.prototype.media = function (a) { return this.request('ssap://media.controls/' + a); }; /* play pause stop rewind fastForward */
  LGTV.prototype.type = function (text) { return this.request('ssap://com.webos.service.ime/insertText', { text: text, replace: 0 }); };
  LGTV.prototype.enterKey = function () { return this.request('ssap://com.webos.service.ime/sendEnterKey'); };
  LGTV.prototype.backspace = function (n) { return this.request('ssap://com.webos.service.ime/deleteCharacters', { count: n || 1 }); };
  LGTV.prototype.screenOff = function () { return this.request('ssap://com.webos.service.tvpower/power/turnOffScreen'); };
  LGTV.prototype.screenOn = function () { return this.request('ssap://com.webos.service.tvpower/power/turnOnScreen'); };
  LGTV.prototype.getMac = function () {
    return this.request('ssap://com.webos.service.connectionmanager/getinfo').then(function (r) {
      return (r.wifiInfo && r.wifiInfo.macAddress) || (r.wiredInfo && r.wiredInfo.macAddress) || null;
    });
  };
  LGTV.prototype.close = function () { try { this.ws && this.ws.close(); this.pointer && this.pointer.close(); } catch (e) {} };

  LGTV.PERMISSIONS = PERMISSIONS;
  return LGTV;
});
