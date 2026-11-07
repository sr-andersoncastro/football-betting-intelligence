/* Esfera 3D de partículas (Three.js r128) que reage ao estado e ao volume da voz. */
(function (root) {
  var COLORS = {            /* [corA, corB] por estado */
    idle:      [[0.15, 0.75, 1.00], [0.45, 0.25, 1.00]],
    listening: [[0.10, 0.95, 1.00], [0.30, 0.45, 1.00]],
    hearing:   [[1.00, 0.30, 0.80], [0.40, 0.55, 1.00]],
    thinking:  [[1.00, 0.70, 0.15], [0.70, 0.25, 1.00]],
    ok:        [[0.15, 1.00, 0.45], [0.10, 0.80, 0.90]],
    err:       [[1.00, 0.20, 0.25], [1.00, 0.55, 0.10]]
  };

  var VERT = [
    'uniform float uTime, uAmp, uPulse, uSize, uPx, uSwirl;',
    'attribute float aSeed;',
    'varying float vGlow; varying float vSeed; varying vec3 vPos;',
    'float hash(vec3 p){ p = fract(p*0.3183099 + .1); p *= 17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }',
    'float noise(vec3 x){ vec3 i = floor(x), f = fract(x); f = f*f*(3.0-2.0*f);',
    '  return mix(mix(mix(hash(i+vec3(0,0,0)),hash(i+vec3(1,0,0)),f.x), mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x), f.y),',
    '             mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x), mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x), f.y), f.z); }',
    'void main(){',
    '  vec3 n = normalize(position);',
    '  float t = uTime;',
    '  float a = uSwirl * n.y;',                                  /* torção da esfera (estado "pensando") */
    '  mat2 r = mat2(cos(a), -sin(a), sin(a), cos(a));',
    '  vec3 q = vec3(r * n.xz, n.y).xzy;',
    '  float d = noise(q*2.3 + vec3(0.0, t*0.7, t*0.45));',
    '  float band = sin(n.y*7.0 - t*3.5)*0.5 + 0.5;',            /* onda que sobe pela esfera */
    '  float disp = (d - 0.5)*2.0*uAmp + band*uPulse;',
    '  vec3 p = position + n*disp;',
    '  vec4 mv = modelViewMatrix * vec4(p, 1.0);',
    '  gl_Position = projectionMatrix * mv;',
    '  gl_PointSize = uSize * uPx * (0.7 + aSeed*1.1) * (6.0 / -mv.z);',
    '  vGlow = d; vSeed = aSeed; vPos = n;',
    '}'
  ].join('\n');

  var FRAG = [
    'uniform vec3 uColA, uColB; uniform float uTime, uBright;',
    'varying float vGlow; varying float vSeed; varying vec3 vPos;',
    'void main(){',
    '  vec2 c = gl_PointCoord - 0.5; float r = length(c); if (r > 0.5) discard;',
    '  float a = smoothstep(0.5, 0.0, r); a *= a;',
    '  vec3 col = mix(uColA, uColB, clamp(vPos.y*0.5 + 0.5 + (vGlow-0.5)*0.9, 0.0, 1.0));',
    '  float tw = 0.6 + 0.4*sin(uTime*2.2 + vSeed*50.0);',
    '  gl_FragColor = vec4(col * (0.7 + vGlow*0.9) * uBright, a * tw);',
    '}'
  ].join('\n');

  var CORE_V = 'varying vec3 vN, vV; void main(){ vN = normalize(normalMatrix*normal); vec4 mv = modelViewMatrix*vec4(position,1.0); vV = normalize(-mv.xyz); gl_Position = projectionMatrix*mv; }';
  var CORE_F = 'uniform vec3 uCol; uniform float uInt; varying vec3 vN, vV; void main(){ float f = pow(1.0 - abs(dot(vN, vV)), 2.4); gl_FragColor = vec4(uCol*f*uInt, f*uInt); }';

  function glowTexture(THREE) {
    var c = document.createElement('canvas'); c.width = c.height = 64;
    var g = c.getContext('2d'), gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.25, 'rgba(255,255,255,.55)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
    return new THREE.CanvasTexture(c);
  }

  function init(canvas, opts) {
    var THREE = root.THREE; if (!THREE) return null;
    var renderer;
    try { renderer = new THREE.WebGLRenderer({ canvas: canvas, alpha: true, antialias: true, powerPreference: 'high-performance' }); }
    catch (e) { return null; }
    renderer.setClearColor(0x000000, 0);
    var scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(50, 1, 0.1, 100);
    var uniforms = {
      uTime: { value: 0 }, uAmp: { value: 0.1 }, uPulse: { value: 0 }, uSize: { value: 5.0 }, uPx: { value: 1 }, uSwirl: { value: 0 },
      uColA: { value: new THREE.Color(0.15, 0.75, 1) }, uColB: { value: new THREE.Color(0.45, 0.25, 1) }, uBright: { value: 1 }
    };

    /* 1) esfera de partículas (espiral de Fibonacci) */
    var N = opts.particles || 3600, pos = new Float32Array(N * 3), seed = new Float32Array(N), R = 1.6;
    for (var i = 0; i < N; i++) {
      var y = 1 - (i + 0.5) / N * 2, rad = Math.sqrt(1 - y * y), th = i * 2.399963229728653;
      pos[i * 3] = Math.cos(th) * rad * R; pos[i * 3 + 1] = y * R; pos[i * 3 + 2] = Math.sin(th) * rad * R; seed[i] = Math.random();
    }
    var geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3)); geo.setAttribute('aSeed', new THREE.BufferAttribute(seed, 1));
    var mat = new THREE.ShaderMaterial({ uniforms: uniforms, vertexShader: VERT, fragmentShader: FRAG, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
    var sphere = new THREE.Points(geo, mat);

    /* 2) núcleo com brilho de borda (fresnel) */
    var coreU = { uCol: { value: new THREE.Color(0.2, 0.7, 1) }, uInt: { value: 0.9 } };
    var core = new THREE.Mesh(new THREE.SphereGeometry(1.25, 48, 32),
      new THREE.ShaderMaterial({ uniforms: coreU, vertexShader: CORE_V, fragmentShader: CORE_F, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));

    /* 3) anéis tipo giroscópio com satélites */
    var tex = glowTexture(THREE), rings = [], sats = [];
    [[2.05, 0.4, 0.0, 0.9], [2.3, 1.2, 0.8, -0.65], [2.6, 0.2, 2.0, 0.45]].forEach(function (d, k) {
      var pts = [], seg = 180; for (var s = 0; s < seg; s++) { var a = s / seg * Math.PI * 2; pts.push(new THREE.Vector3(Math.cos(a) * d[0], 0, Math.sin(a) * d[0])); }
      var lg = new THREE.BufferGeometry().setFromPoints(pts);
      var lm = new THREE.LineBasicMaterial({ color: 0x4fd1ff, transparent: true, opacity: 0.38, blending: THREE.AdditiveBlending, depthWrite: false });
      var line = new THREE.LineLoop(lg, lm); var holder = new THREE.Group(); holder.add(line);
      var sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(3), 3));
      var sm = new THREE.PointsMaterial({ size: 0.34, map: tex, color: 0x9ef0ff, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending });
      var sat = new THREE.Points(sg, sm); holder.add(sat);
      holder.rotation.set(d[1], d[2], 0); scene.add(holder);
      rings.push({ g: holder, line: line, speed: d[3], r: d[0] }); sats.push({ p: sat, phase: k * 2.1, r: d[0], speed: 0.8 + k * 0.35 });
    });

    /* 4) estrelas ao fundo */
    var SN = 700, sp = new Float32Array(SN * 3);
    for (var s2 = 0; s2 < SN; s2++) { var rr = 9 + Math.random() * 16, u = Math.random() * 2 - 1, ph = Math.random() * Math.PI * 2, q = Math.sqrt(1 - u * u);
      sp[s2 * 3] = rr * q * Math.cos(ph); sp[s2 * 3 + 1] = rr * u; sp[s2 * 3 + 2] = rr * q * Math.sin(ph) - 6; }
    var stg = new THREE.BufferGeometry(); stg.setAttribute('position', new THREE.BufferAttribute(sp, 3));
    var stars = new THREE.Points(stg, new THREE.PointsMaterial({ size: 0.22, map: tex, color: 0x8fb8ff, transparent: true, opacity: 0.7, depthWrite: false, blending: THREE.AdditiveBlending }));
    scene.add(stars);

    var group = new THREE.Group(); group.add(sphere); group.add(core); scene.add(group);

    /* tamanho / posição: centraliza a esfera sobre o elemento .orbwrap */
    var W = 1, H = 1;
    function resize() {
      var rc = canvas.getBoundingClientRect(); W = Math.max(1, rc.width); H = Math.max(1, rc.height);
      var dpr = Math.min(window.devicePixelRatio || 1, opts.maxDpr || 2);
      renderer.setPixelRatio(dpr); renderer.setSize(W, H, false);
      uniforms.uPx.value = dpr * (H / 700);
      camera.aspect = W / H;
      var target = Math.min(W * 0.5, 215), ppu = target / (R * 2);
      camera.position.set(0, 0, (H / ppu) / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))));
      var anchor = opts.anchor && opts.anchor();
      var cx = anchor ? anchor.x - rc.left : W / 2, cy = anchor ? anchor.y - rc.top : H / 2;
      camera.setViewOffset(W, H, -(cx - W / 2), -(cy - H / 2), W, H);
      camera.updateProjectionMatrix();
    }
    window.addEventListener('resize', resize); resize();

    /* inclinação suave seguindo o toque (parallax) */
    var tiltX = 0, tiltY = 0, tx = 0, ty = 0;
    opts.pointerHost.addEventListener('pointermove', function (e) { tx = (e.clientX / window.innerWidth - 0.5) * 0.9; ty = (e.clientY / window.innerHeight - 0.5) * 0.6; });

    var cur = { a: new THREE.Color(0.15, 0.75, 1), b: new THREE.Color(0.45, 0.25, 1) };
    var amp = 0.1, pulse = 0, swirl = 0, spin = 0.25, ringBoost = 1, bright = 1, lvl = 0, last = performance.now(), running = true;

    function frame(now) {
      if (!running) return; requestAnimationFrame(frame);
      if (!opts.visible()) { last = now; return; }
      var dt = Math.min(0.05, (now - last) / 1000); last = now; var t = uniforms.uTime.value += dt;
      var st = opts.state(), col = COLORS[st] || COLORS.idle, lvTarget = opts.level();
      lvl += (lvTarget - lvl) * Math.min(1, dt * 12);
      var k = Math.min(1, dt * 4);
      cur.a.lerp(new THREE.Color(col[0][0], col[0][1], col[0][2]), k); cur.b.lerp(new THREE.Color(col[1][0], col[1][1], col[1][2]), k);
      uniforms.uColA.value.copy(cur.a); uniforms.uColB.value.copy(cur.b); coreU.uCol.value.copy(cur.a);

      var tAmp = 0.08, tPulse = 0.0, tSwirl = 0, tSpin = 0.25, tRing = 1, tBright = 1, scale = 1 + Math.sin(t * 1.3) * 0.025;
      if (st === 'listening') { tAmp = 0.14 + lvl * 0.2; tPulse = 0.05 + lvl * 0.15; tSpin = 0.4; tRing = 1.6; scale += lvl * 0.06; }
      else if (st === 'hearing') { tAmp = 0.22 + lvl * 0.55; tPulse = 0.12 + lvl * 0.5; tSpin = 0.7; tRing = 2.4; tBright = 1.25; scale += lvl * 0.18; }
      else if (st === 'thinking') { tAmp = 0.12; tSwirl = 5.0 + Math.sin(t * 3) * 2; tSpin = 3.0; tRing = 5.0; scale = 0.9 + Math.sin(t * 6) * 0.03; tBright = 1.2; }
      else if (st === 'ok') { tAmp = 0.35; tPulse = 0.3; tSpin = 1.2; tRing = 3; tBright = 1.5; scale = 1.1 + Math.sin(t * 9) * 0.03; }
      else if (st === 'err') { tAmp = 0.45 + Math.sin(t * 40) * 0.1; tPulse = 0.0; tSpin = 0.1; tRing = 0.5; tBright = 1.3; scale = 1 + Math.sin(t * 50) * 0.03; }
      amp += (tAmp - amp) * Math.min(1, dt * 6); pulse += (tPulse - pulse) * Math.min(1, dt * 6); swirl += (tSwirl - swirl) * Math.min(1, dt * 3);
      spin += (tSpin - spin) * Math.min(1, dt * 2.5); ringBoost += (tRing - ringBoost) * Math.min(1, dt * 3); bright += (tBright - bright) * Math.min(1, dt * 4);
      uniforms.uAmp.value = amp; uniforms.uPulse.value = pulse; uniforms.uSwirl.value = swirl; uniforms.uBright.value = bright; coreU.uInt.value = 0.55 + bright * 0.35 + lvl * 0.5;

      sphere.rotation.y += dt * spin; sphere.rotation.x = Math.sin(t * 0.3) * 0.25;
      core.rotation.y = sphere.rotation.y; group.scale.setScalar(scale);
      tiltX += (tx - tiltX) * 0.06; tiltY += (ty - tiltY) * 0.06; group.rotation.y = tiltX; group.rotation.x = tiltY;
      rings.forEach(function (r, i) { r.g.rotation.y += dt * r.speed * ringBoost; r.g.rotation.z += dt * 0.15 * ringBoost * (i % 2 ? -1 : 1);
        r.line.material.color.copy(cur.a); r.line.material.opacity = 0.28 + Math.min(0.5, lvl * 0.5 + (ringBoost - 1) * 0.06); });
      sats.forEach(function (s) { var a = t * s.speed * ringBoost + s.phase, arr = s.p.geometry.attributes.position.array;
        arr[0] = Math.cos(a) * s.r; arr[1] = 0; arr[2] = Math.sin(a) * s.r; s.p.geometry.attributes.position.needsUpdate = true; s.p.material.color.copy(cur.a); });
      stars.rotation.y += dt * 0.02; stars.rotation.x += dt * 0.006;
      renderer.render(scene, camera);
    }
    requestAnimationFrame(frame);
    return { resize: resize, dispose: function () { running = false; renderer.dispose(); } };
  }

  root.Orb3D = { init: init };
})(typeof self !== 'undefined' ? self : this);
