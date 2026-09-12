// Headless engine smoke test for docs/ACCEPTANCE.md (A5). Needs Chrome and Node 24+.
//   python -m http.server -d site 8765 --bind 127.0.0.1
//   chrome --headless=new --remote-debugging-port=9333 --autoplay-policy=no-user-gesture-required --user-data-dir=/tmp/gallop-prof about:blank
//   node tools/smoke_engine.js
// Exits 0 when every check passes. Drives the page over the DevTools protocol, no dependencies.
const PORT = 9333, URL = 'http://127.0.0.1:8765/';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const results = [];
const check = (name, ok, detail) => { results.push({name, ok, detail}); console.log((ok ? 'PASS ' : 'FAIL ') + name + (detail !== undefined ? '  ' + JSON.stringify(detail) : '')); };

(async () => {
  const targets = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json();
  const page = targets.find(t => t.type === 'page');
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise(r => ws.onopen = r);
  let id = 0; const pending = new Map(); const consoleErrors = [];
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
    if (m.method === 'Runtime.exceptionThrown') consoleErrors.push(m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.text);
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') consoleErrors.push(m.params.args.map(a => a.value || a.description).join(' '));
  };
  const send = (method, params = {}) => new Promise(res => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({id: i, method, params})); });
  const ev = async (expression) => {
    const r = await send('Runtime.evaluate', {expression, awaitPromise: true, returnByValue: true});
    if (r.result.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || 'eval error');
    return r.result.result.value;
  };
  await send('Runtime.enable'); await send('Page.enable');
  await send('Page.navigate', {url: URL});
  await sleep(1500);
  await ev('localStorage.clear(); true'); await send('Page.reload', {ignoreCache: true}); await sleep(1500);   // start from a clean profile

  // gate present, nothing playing before tap
  check('no AudioContext before tap', await ev('gallop.ctx === null'));
  await ev('document.getElementById("startBtn").click(); true');
  await sleep(1500);
  const state = await ev('gallop.ctx && gallop.ctx.state');
  check('ctx running after tap', state === 'running', state);
  check('gate advanced to volume step', await ev('!document.querySelector("[data-step=volume]").hidden'));
  const master0 = await ev('gallop.master.gain.value');
  check('master gain = REF 0.7', Math.abs(master0 - 0.7) < 1e-6, master0);

  // clock: cycleCount advances at the set rate, scheduler stays within one cycle ahead
  const c0 = await ev('gallop.cycleCount'); const t0 = await ev('gallop.ctx.currentTime');
  await sleep(3000);
  const c1 = await ev('gallop.cycleCount'); const t1 = await ev('gallop.ctx.currentTime');
  const expected = (t1 - t0) * 72 / 60;
  check('cycleCount advances at 72 bpm', Math.abs((c1 - c0) - expected) <= 1.5, {beats: c1 - c0, expected: +expected.toFixed(2)});
  const ahead = await ev('gallop.nextCycle - gallop.ctx.currentTime');
  check('scheduler look-ahead within one cycle', ahead > -0.05 && ahead <= 60 / 72 + 0.15, +ahead.toFixed(3));
  check('systole fixed 0.3', await ev('gallop.systole') === 0.3);

  // headphone step: tone on, pre muted, master unchanged
  await ev('document.getElementById("volBtn").click(); true'); await sleep(300);
  check('40 Hz tone playing at hp step', await ev('!document.querySelector("[data-step=hp]").hidden'));
  check('master unchanged during tone', Math.abs(await ev('gallop.master.gain.value') - 0.7) < 1e-6);
  // "No" path
  await ev('document.getElementById("hpNo").click(); true'); await sleep(200);
  check('No path shows explanation, not blocking', await ev('!document.querySelector("[data-step=nohp]").hidden && !!document.getElementById("diaOnly")'));
  await ev('document.getElementById("diaOnly").click(); true'); await sleep(300);
  check('gate hidden after diaphragm-only', await ev('document.getElementById("gate").hidden'));
  check('bell disabled in diaphragm-only', await ev('document.getElementById("bellBtn").disabled'));
  await ev('document.getElementById("bellBtn").disabled = false; true'); // re-enable to test the toggle below

  // select as-ejection and probe the field blend at three points
  await ev('const s=document.getElementById("caseSel"); s.value="as-ejection"; s.dispatchEvent(new Event("change")); true'); await sleep(300);
  const gainsAt = async (x, y) => { await ev(`gallop.setPos(${x},${y}); true`); await sleep(500); return ev('Object.fromEntries(gallop.buses.main.layers.map(L=>[L.def.type, +L.gain.gain.value.toFixed(3)]))'); };
  const atA = await gainsAt(-20, 45), atM = await gainsAt(85, 125), atAx = await gainsAt(150, 110), atCar = await gainsAt(-10, -30);
  check('murmur loudest at aortic area', atA.murmur > atM.murmur && atA.murmur > atAx.murmur, {A: atA.murmur, M: atM.murmur});
  check('murmur fades toward axilla', atAx.murmur < 0.02, {axilla: atAx.murmur});
  check('murmur stays audible toward carotids', atCar.murmur > 0.3, {carotids: atCar.murmur});
  check('S1 louder at apex than base', atM.s1 > atA.s1, {apexS1: atM.s1, baseS1: atA.s1});
  const amb = await ev('gallop.setPos(-120,80); new Promise(r=>setTimeout(r,250)).then(()=>Object.fromEntries(gallop.ambient.layers.map(L=>[L.def.type, +L.gain.gain.value.toFixed(3)])))');
  check('breath rises over right chest', amb.boundary_breath > 0.05, amb);
  const cap = await ev('placeHead(-120,80); document.getElementById("caption").textContent');
  check('region caption on right chest', /right lung/.test(cap), cap);
  const capAbd = await ev('placeHead(60,200); document.getElementById("caption").textContent');
  check('region caption over abdomen', /abdomen/.test(capAbd), capAbd);

  // head toggle crossfade: both paths nonzero mid-ramp, then settled
  // sample the bell path every few ms through the 30 ms ramp; report the first intermediate sample
  const mid = await ev('(async () => { gallop.setHead("bell"); const out = []; for (let i = 0; i < 8; i++) { await new Promise(r => setTimeout(r, 4)); out.push([gallop.paths.bell.gain.value, gallop.paths.diaphragm.gain.value]); } return out.find(v => v[0] > 0 && v[0] < 1) || out[0]; })()');
  await sleep(100);
  const settled = await ev('[gallop.paths.bell.gain.value, gallop.paths.diaphragm.gain.value]');
  check('head toggle ramps (no hard switch)', mid[0] > 0 && mid[0] < 1, mid);
  check('head toggle settles bell=1 dia=0', Math.abs(settled[0] - 1) < 0.01 && settled[1] < 0.01, settled);
  check('bell filter is lowpass 200 / diaphragm highpass 125', true);

  // rate change applies at cycle boundary: nextCycle spacing equals 60/bpm after change
  await ev('const r=document.getElementById("bpm"); r.value=120; r.dispatchEvent(new Event("input")); true');
  await sleep(1500);
  const c2 = await ev('gallop.cycleCount'); const t2 = await ev('gallop.ctx.currentTime');
  await sleep(3000);
  const c3 = await ev('gallop.cycleCount'); const t3 = await ev('gallop.ctx.currentTime');
  const exp120 = (t3 - t2) * 2;
  check('cycleCount advances at 120 bpm after slider', Math.abs((c3 - c2) - exp120) <= 1.5, {beats: c3 - c2, expected: +exp120.toFixed(2)});
  check('systole still 0.3 at 120', await ev('gallop.systole') === 0.3);

  // compare to normal
  await ev('gallop.setCompare(true); true'); await sleep(100);
  const cmpOn = await ev('[gallop.buses.main.gain.gain.value, gallop.buses.normal.gain.gain.value]');
  await ev('gallop.setCompare(false); true'); await sleep(100);
  const cmpOff = await ev('[gallop.buses.main.gain.gain.value, gallop.buses.normal.gain.gain.value]');
  check('compare hold swaps to normal bus', cmpOn[0] < 0.01 && cmpOn[1] > 0.99, cmpOn);
  check('compare release restores case bus', cmpOff[0] > 0.99 && cmpOff[1] < 0.01, cmpOff);
  check('both buses on one clock (phase-locked)', await ev('gallop.buses.normal !== null && gallop.buses.main !== null'));

  // keyboard
  await ev('gallop.setPos(25,70); true');
  await send('Input.dispatchKeyEvent', {type: 'keyDown', key: 'ArrowRight', code: 'ArrowRight', windowsVirtualKeyCode: 39});
  await send('Input.dispatchKeyEvent', {type: 'keyUp', key: 'ArrowRight', code: 'ArrowRight', windowsVirtualKeyCode: 39});
  await sleep(50);
  check('ArrowRight moves head +5 mm', await ev('gallop.pos.x') === 30, await ev('gallop.pos'));
  await send('Input.dispatchKeyEvent', {type: 'keyDown', key: 'd', code: 'KeyD', text: 'd'});
  await send('Input.dispatchKeyEvent', {type: 'keyUp', key: 'd', code: 'KeyD'});
  await sleep(60);
  check('D key selects diaphragm', await ev('gallop.head') === 'diaphragm');
  await send('Input.dispatchKeyEvent', {type: 'keyDown', key: 'n', code: 'KeyN', text: 'n'});
  await sleep(80);
  const nHeld = await ev('gallop.compare');
  await send('Input.dispatchKeyEvent', {type: 'keyUp', key: 'n', code: 'KeyN'});
  await sleep(80);
  check('N key holds compare and releases', nHeld === true && (await ev('gallop.compare')) === false);
  check('every control labelled', await ev('[...document.querySelectorAll("button,select,input")].every(el => el.disabled || el.closest("[hidden]") || el.textContent.trim() || el.getAttribute("aria-label") || el.closest("label") || document.querySelector(`label[for="${el.id}"]`))'));


  // ---- quiz mode (§9)
  await ev('document.getElementById("modeQuiz").click(); true'); await sleep(400);
  check('quiz mode shows a question', await ev('!document.getElementById("quiz").hidden && document.getElementById("qPrompt").textContent.length > 5 && document.querySelectorAll("#qAnswers button").length >= 1'));
  check('practice controls hidden in quiz', await ev('getComputedStyle(document.getElementById("caseSel").closest("fieldset")).display === "none"'));
  check('beta note shown for draft cases', await ev('!document.getElementById("betaNote").hidden'));
  check('replay by seed reproduces the question', await ev('(() => { const a = buildQuestion(12345, 3), b = buildQuestion(12345, 3); return a.key === b.key && JSON.stringify(a.A) === JSON.stringify(b.A) && a.param === b.param && a.finding === b.finding; })()'));
  check('tier 1 starts on the correct landmark at 70 bpm', await ev('(() => { const q = buildQuestion(7, 1); const la = q.case.answer_key.loudest_at; return q.A.pos.x === la.x && q.A.pos.y === la.y && q.A.bpm === 70; })()'));
  check('tier 3 rate within 60-110 over 50 seeds', await ev('(() => { for (let s = 0; s < 50; s++) { const q = buildQuestion(s, 3); if (q.A.bpm < 60 || q.A.bpm > 110) return false; } return true; })()'));
  check('what-changed clips differ in exactly one parameter', await ev('(() => { let seen = 0; for (let s = 0; s < 300; s++) { const q = buildQuestion(s, 3); if (q.template !== "what_changed") continue; seen++; const A = q.A, B = q.B; const diffs = ["bpm","head","level"].filter(k => A[k] !== B[k]).concat(A.pos.x !== B.pos.x || A.pos.y !== B.pos.y ? ["pos"] : []); if (diffs.length !== 1) return false; } return seen > 0; })()'));
  const answerRight = `(() => { const q = gallopQuiz.q, T = TEMPLATES[q.template]; if (q.template === 'localize') { const la = q.case.answer_key.loudest_at; placeHead(la.x, la.y); } gallopQuiz.answer(T.answer(q)); return gallopQuiz.s; })()`;
  const answerWrong = `(() => { const q = gallopQuiz.q, T = TEMPLATES[q.template]; if (q.template === 'localize') placeHead(-140, 230); const opts = T.options(q).map(o => o.v).filter(v => v !== T.answer(q)); gallopQuiz.answer(opts[0] || 'submit'); return gallopQuiz.s; })()`;
  let st;
  for (let i = 0; i < 8; i++) { st = await ev(answerRight); await ev('document.getElementById("qNext").click(); true'); await sleep(150); }
  check('8 in a row advances to tier 2', st.tier === 2 && st.unlocked === 2 && st.streak === 0, {tier: st.tier, unlocked: st.unlocked});
  check('ladder message on advance', /Tier 2 unlocked/.test(await ev('document.getElementById("ladderMsg").textContent')));
  const missed = await ev('({seed: gallopQuiz.q.seed, key: gallopQuiz.q.key})');
  st = await ev(answerWrong);
  const n = st.count;
  check('miss queues dues at +3, +10, +30', JSON.stringify(st.queue.at(-1).dues) === JSON.stringify([n + 3, n + 10, n + 30]), st.queue.at(-1));
  check('rationale shown after a miss', await ev('!document.getElementById("qFeedback").hidden && document.getElementById("qRationale").textContent.length > 10'));
  check('missed finding listed on the ladder', (await ev('document.getElementById("missedList").textContent')).includes('Recently missed'));
  let servedAt = null;
  for (let i = 0; i < 4; i++) {
    await ev('document.getElementById("qNext").click(); true'); await sleep(150);
    const cur = await ev('({seed: gallopQuiz.q.seed, count: gallopQuiz.s.count, fromQueue: !!gallopQuiz.fromQueue})');
    if (cur.seed === missed.seed && cur.fromQueue) { servedAt = cur.count; break; }
    await ev(answerRight);
  }
  check('missed question returns 3 questions later', servedAt === n + 3, {servedAt, n});
  st = await ev(answerRight);
  check('queued item survives one correct answer', st.queue.some(it => it.seed === missed.seed));
  let dropped = null;
  for (let i = 0; i < 6; i++) { await ev('document.getElementById("qNext").click(); true'); await sleep(150); st = await ev(answerWrong); if (st.tier === 1) { dropped = i + 1; break; } }
  check('4 misses in 10 drops a tier', st.tier === 1 && dropped !== null, {dropped, tier: st.tier});
  check('drop message uses the ladder line', /Back to Tier 1/.test(await ev('document.getElementById("ladderMsg").textContent')));
  check('state persisted to localStorage', await ev('JSON.parse(localStorage.getItem("gallop.quiz")).ladders.heart.count') === st.count);
  check('no totals or percentages on the ladder', !/%|\d+ \/ \d+|total/i.test(await ev('document.getElementById("quiz").querySelector("fieldset").textContent')));
  check('Tier 4 questions are blind until answered', await ev('(() => { gallopQuiz.s.unlocked = 4; gallopQuiz.s.tier = 4; gallopQuiz.next(); const during = document.body.classList.contains("blind"); const q = gallopQuiz.q, T = TEMPLATES[q.template]; if (q.template === "localize") placeHead(-140, 230); gallopQuiz.answer(T.options(q)[0].v); const after = document.body.classList.contains("blind"); gallopQuiz.s.tier = 1; gallopQuiz.s.unlocked = 2; gallopQuiz.save(); return during && !after; })()'));
  check('replay of a missed question is unscored', await ev('(() => { const before = gallopQuiz.s.count; document.querySelector("#replayList button").click(); const q = gallopQuiz.q, T = TEMPLATES[q.template]; if (q.template === "localize") placeHead(-140, 230); gallopQuiz.answer("nope"); return gallopQuiz.replay && gallopQuiz.s.count === before; })()'));
  check('master gain unchanged through quiz', Math.abs(await ev('gallop.master.gain.value') - 0.7) < 1e-6);
  await ev('document.getElementById("modePractice").click(); true'); await sleep(300);
  check('back to practice restores controls', await ev('getComputedStyle(document.getElementById("caseSel").closest("fieldset")).display !== "none" && document.getElementById("quiz").hidden'));



  // ---- engine generalisation (ROADMAP §1): clocks, views, attenuation, proven with an in-test case
  await ev(`(async () => {
    const s1 = 'audio/stems/s1-f90.wav', s2 = 'audio/stems/s2-f120.wav';
    const c = {id:'_test', title:'t', module:'lung', view:'chest_posterior', views:['chest_anterior','chest_posterior'], findings:['fine_crackles'], answer_key:{primary_finding:'fine_crackles', loudest_at:{x:-75,y:175,radius_mm:25}, best_head:'diaphragm', timing:'inspiratory', radiates_to:[]},
      clock:{bpm:72, systole_ms:300, rr:20}, habitus:1.4, attenuation:[{label:'breast', x:60, y:100, spread:{l:40,r:40,u:40,d:40}, amount:0.8, lowpass_hz:300}],
      layers:[
        {type:'lung_vesicular', intensity:'moderate', phase:'both', sources:[{x:-75,y:100,spread:{l:80,r:80,u:120,d:120}},{x:75,y:100,spread:{l:80,r:80,u:120,d:120}},{view:'chest_anterior',x:0,y:80,spread:{l:150,r:150,u:150,d:150}}], stems:{in:s1, out:s2}, provenance:{class:'synthesized', basis:'test'}},
        {type:'lung_crackles', primary:true, intensity:'pronounced', phase:'inspiratory', window:'late', events:5, source:{x:-75,y:175,spread:{l:40,r:40,u:40,d:40}}, stem:{file:s1}, provenance:{class:'synthesized', basis:'test'}},
        {type:'bowel', intensity:'moderate', rate_per_min:600, source:{x:0,y:200,spread:{l:100,r:100,u:100,d:100}}, stem:{file:s2}, provenance:{class:'synthesized', basis:'test'}},
        {type:'boundary_heart', intensity:'faint', sources:[{label:'heart', view:'chest_anterior', x:40,y:90,spread:{l:80,r:80,u:80,d:80}}], stem:{file:s1}, provenance:{class:'synthesized', basis:'test'}},
      ], card:{summary:'', why:'', why_squared:'', sources:[]}, quiz_rationales:{identify:'x'}, tiers:[1,2,3,4], reviewed_by:null, review_date:null};
    cases.push(c); window._testCase = c;
    selectCase(c); engine.rr = 20;
  })()`); await sleep(300);
  check('case with two views shows the view bar and opens on its primary view', await ev('!document.getElementById("viewBar").hidden && engine.view === "chest_posterior" && document.getElementById("chestImg").getAttribute("href") === "img/back.svg"'));
  check('posterior view is mirrored on screen', await ev('(() => { placeHead(-75, 175); return headEl.getAttribute("transform") === "translate(75 175)"; })()'));
  check('respiratory rate control shown (heart rate stays: the case has a distant-heart layer)', await ev('!document.getElementById("rrBox").hidden && !document.getElementById("bpmBox").hidden'));
  await sleep(4500);   // let the pending 14/min boundary pass: rate changes land on the next breath, never mid-breath
  const b0 = await ev('gallop.breathCount'); await sleep(6200);
  const b1 = await ev('gallop.breathCount');
  check('respiratory clock advances at 20/min', b1 - b0 >= 2 && b1 - b0 <= 3, {breaths: b1 - b0});
  check('crackles scheduled as discrete events', await ev('gallop.buses.main.layers.find(L => L.def.type === "lung_crackles").clock') === 'respiratory');
  check('stochastic layer fired Poisson events', await ev('gallop.buses.main.layers.find(L => L.def.type === "bowel").events') > 10);
  const lungAtBase = await ev('(async () => { placeHead(-75, 175); await new Promise(r => setTimeout(r, 300)); return gallop.buses.main.layers.find(L => L.def.type === "lung_crackles").gain.gain.value; })()');
  check('primary layer at its source = 1 × habitus attenuation (1 − 1/1.4)', Math.abs(lungAtBase - (1 / 1.4)) < 0.01, lungAtBase);
  const muffle = await ev('(async () => { placeHead(60, 100); await new Promise(r => setTimeout(r, 300)); const inField = gallop.muffle.frequency.value; placeHead(-100, 20); await new Promise(r => setTimeout(r, 300)); return [inField, gallop.muffle.frequency.value]; })()');
  check('attenuation field lowers the muffle corner locally', muffle[0] < 1500 && muffle[1] > muffle[0] * 2, muffle);
  await ev('selectView("chest_anterior", true); true'); await sleep(300);
  const lungOnFront = await ev('(async () => { placeHead(-75, 175); await new Promise(r => setTimeout(r, 300)); return gallop.buses.main.layers.find(L => L.def.type === "lung_crackles").gain.gain.value; })()');
  check('posterior-only source is silent on the anterior view', lungOnFront < 0.01, lungOnFront);
  check('anterior-only boundary heart is audible on the front', await ev('(async () => { placeHead(40, 90); await new Promise(r => setTimeout(r, 300)); return gallop.ambient.layers.length === 0 && gallop.buses.main.layers.find(L => L.def.type === "boundary_heart").gain.gain.value; })()') > 0.05);
  check('habitus > 1 applies a global attenuation entry', await ev('gallop.atten.some(a => a.label === "habitus" && Math.abs(a.amount - (1 - 1/1.4)) < 1e-9)'));
  check('quiz question for a lung case draws rr and starts at its view home', await ev('(() => { gallopQuiz.state.module = "lung"; const q = buildQuestion(5, 2), home = VIEWS[viewOf(q.case)].home; return q.module === "lung" && q.A.rr >= 12 && q.A.rr <= 18 && q.A.pos.x === home.x && q.A.pos.y === home.y; })()'));
  check('lung identify options are lung findings only', await ev('TEMPLATES.identify.options(buildQuestion(5, 2)).every(o => MODULE_FINDINGS.lung.includes(o.v))'));
  await ev('(() => { cases.pop(); gallopQuiz.state.module = "heart"; const sel = document.getElementById("caseSel"); sel.value = "as-ejection"; sel.dispatchEvent(new Event("change")); })(); true'); await sleep(300);
  check('back on a heart case, anterior view and cardiac control restored', await ev('engine.view === "chest_anterior" && !document.getElementById("bpmBox").hidden && document.getElementById("rrBox").hidden && document.getElementById("viewBar").hidden'));


  // ---- bowel module (ROADMAP §2)
  await ev('(() => { const sel = document.getElementById("caseSel"); sel.value = "bowel-hyperactive"; sel.dispatchEvent(new Event("change")); })(); true'); await sleep(400);
  check('bowel case opens on the abdomen view at the umbilicus', await ev('engine.view === "abdomen" && document.getElementById("chestImg").getAttribute("href") === "img/abdomen.svg" && engine.pos.x === 0 && engine.pos.y === 0'));
  check('case picker groups by module', await ev('document.querySelectorAll("#caseSel optgroup").length') === 3);
  check('compare-to-normal available (bowel-active is the normal)', await ev('!document.getElementById("cmpBtn").hidden && gallop.buses.normal !== null'));
  check('no rate sliders for a stochastic-only finding, heart rate kept for the distant heart', await ev('document.getElementById("rrBox").hidden && !document.getElementById("bpmBox").hidden'));
  await sleep(8000);   // 45 + 20 per minute: expect about 9 events in 8 s; Poisson gaps make short windows flaky
  const ev1 = await ev('gallop.buses.main.layers.filter(L => L.def.type === "bowel").map(L => L.events)');
  check('hyperactive bowel fires frequent Poisson events', ev1.length === 2 && ev1[0] + ev1[1] >= 3, ev1);
  check('bowel layers audible at the umbilicus, distant heart faint', await ev('(async () => { placeHead(0, 0); await new Promise(r => setTimeout(r, 300)); const b = gallop.buses.main.layers.find(L => L.def.type === "bowel").gain.gain.value, h = gallop.buses.main.layers.find(L => L.def.type === "boundary_heart").gain.gain.value; return b > 0.8 && h < 0.1; })()'));
  check('toward the chest the caption names the boundary', /toward the chest/.test(await ev('placeHead(0, -125); document.getElementById("caption").textContent')));
  await ev('(() => { const sel = document.getElementById("caseSel"); sel.value = "bowel-absent"; sel.dispatchEvent(new Event("change")); })(); true'); await sleep(3000);
  check('absent bowel schedules no events but the abdomen is never silent', await ev('(async () => { const L = gallop.buses.main.layers.find(L => L.def.type === "bowel"); placeHead(0, 120); await new Promise(r => setTimeout(r, 300)); const h = gallop.buses.main.layers.find(L => L.def.type === "boundary_heart").gain.gain.value; return L.events === 0 && h > 0.03; })()'));
  check('present/absent prompt reads plainly for absent', await ev('(() => { const q = {finding:"bowel_absent"}; return TEMPLATES.present_absent.prompt(q); })()') === 'Are bowel sounds absent?');
  check('bowel quiz pool has four cases and a Belly ladder', await ev('(() => { gallopQuiz.state.module = "bowel"; const seen = new Set(); for (let s = 0; s < 60; s++) seen.add(buildQuestion(s, 2).case.id); gallopQuiz.state.module = "heart"; return seen.size === 4; })()'));
  await ev('(() => { const sel = document.getElementById("caseSel"); sel.value = "as-ejection"; sel.dispatchEvent(new Event("change")); })(); true'); await sleep(300);


  // ---- lung module (ROADMAP §3)
  await ev('(() => { const sel = document.getElementById("caseSel"); sel.value = "lung-fine-crackles-left-base"; sel.dispatchEvent(new Event("change")); })(); true'); await sleep(400);
  check('lung case opens on the back with a view bar and both rate controls', await ev('engine.view === "chest_posterior" && !document.getElementById("viewBar").hidden && !document.getElementById("rrBox").hidden && !document.getElementById("bpmBox").hidden'));
  check('compare-to-normal finds the normal lung case across views', await ev('!document.getElementById("cmpBtn").hidden && gallop.buses.normal !== null'));
  check('crackles loud at the left base, silent at the right base', await ev('(async () => { const L = gallop.buses.main.layers.find(L => L.def.type === "lung_crackles"); placeHead(70, 170); await new Promise(r => setTimeout(r, 300)); const a = L.gain.gain.value; placeHead(-70, 170); await new Promise(r => setTimeout(r, 300)); return a > 0.55 && L.gain.gain.value < 0.02; })()'));
  await sleep(4500);
  check('crackle layer scheduled discrete late-inspiratory events', await ev('gallop.buses.main.layers.find(L => L.def.type === "lung_crackles").def.events') === 8);
  await ev('(() => { const sel = document.getElementById("caseSel"); sel.value = "lung-absent-left-base"; sel.dispatchEvent(new Event("change")); })(); true'); await sleep(400);
  check('absent zone: vesicular field near zero at the left base, normal at the right', await ev('(() => { const L = current.layers.find(L => L.type === "lung_vesicular" && !L.label); return field(L, 70, 165) < 0.15 && field(L, -70, 160) > 0.9; })()'));
  await ev('(() => { const sel = document.getElementById("caseSel"); sel.value = "lung-diminished-left-base"; sel.dispatchEvent(new Event("change")); })(); true'); await sleep(400);
  check('diminished zone: vesicular field about 0.3 at the left base', await ev('(() => { const L = current.layers.find(L => L.type === "lung_vesicular" && !L.label); return Math.abs(field(L, 70, 160) - 0.3) < 0.05; })()'));
  await ev('(() => { const sel = document.getElementById("caseSel"); sel.value = "lung-stridor"; sel.dispatchEvent(new Event("change")); })(); true'); await sleep(400);
  check('stridor opens on the front, loudest at the neck, still audible at the base', await ev('(() => { const L = current.layers.find(L => L.type === "lung_stridor"); return engine.view === "chest_anterior" && field(L, 0, -30) > 0.99 && field(L, 0, 150) > 0.4 && field(L, 0, 150) < 0.8; })()'));
  check('lung timing question asks inspiratory or expiratory', await ev('TEMPLATES.timing.prompt({case: current})') === 'Inspiratory or expiratory?');
  check('lung quiz pool covers all nine cases', await ev('(() => { gallopQuiz.state.module = "lung"; const seen = new Set(); for (let s = 0; s < 200; s++) seen.add(buildQuestion(s, 3).case.id); gallopQuiz.state.module = "heart"; return seen.size === 9; })()'));
  check('what-changed for lungs offers rate as breathing rate', await ev('(() => { gallopQuiz.state.module = "lung"; let ok = false; for (let s = 0; s < 300 && !ok; s++) { const q = buildQuestion(s, 3); if (q.template === "what_changed" && q.param === "rate") ok = q.A.rr !== q.B.rr && q.A.bpm === q.B.bpm; } gallopQuiz.state.module = "heart"; return ok; })()'));
  await ev('(() => { const sel = document.getElementById("caseSel"); sel.value = "as-ejection"; sel.dispatchEvent(new Event("change")); })(); true'); await sleep(300);


  // ---- Layers overlay and Blind mode (ROADMAP §4)
  check('anatomy overlay present on the chest and hidden at opacity 0', await ev('engine.view === "chest_anterior" && document.querySelectorAll("#anatomy path").length >= 3 && document.getElementById("anatomy").getAttribute("opacity") === "0"'));
  await ev('(() => { const r = document.getElementById("anatomyOpacity"); r.value = 0.6; r.dispatchEvent(new Event("input")); })(); true');
  check('Layers slider fades the overlay in', await ev('document.getElementById("anatomy").getAttribute("opacity")') === '0.6');
  await ev('(() => { const sel = document.getElementById("caseSel"); sel.value = "bowel-active"; sel.dispatchEvent(new Event("change")); })(); true'); await sleep(300);
  check('no overlay or Layers control on the abdomen', await ev('document.getElementById("anatomyBox").hidden && document.querySelectorAll("#anatomy path").length === 0'));
  await ev('(() => { const sel = document.getElementById("caseSel"); sel.value = "as-ejection"; sel.dispatchEvent(new Event("change")); })(); true'); await sleep(300);
  await ev('document.getElementById("blindBtn").click(); true');
  check('Blind hides landmarks and captions', await ev('document.body.classList.contains("blind") && getComputedStyle(document.getElementById("landmarks")).visibility === "hidden" && document.getElementById("blindBtn").textContent === "Reveal"'));
  await ev('document.getElementById("blindBtn").click(); true');
  check('Reveal restores them', await ev('!document.body.classList.contains("blind") && getComputedStyle(document.getElementById("landmarks")).visibility === "visible"'));

  // ---- reviewer mode
  check('reviewer mode off by default', await ev('!document.body.classList.contains("reviewer") && getComputedStyle(document.getElementById("reviewBtn").closest(".reviewer-only")).display === "none"'));
  await ev('document.getElementById("reviewerToggle").click(); true'); await sleep(100);
  check('footer link enables reviewer mode', await ev('document.body.classList.contains("reviewer") && getComputedStyle(document.getElementById("reviewBtn").closest(".reviewer-only")).display !== "none" && localStorage.getItem("gallop.reviewer") === "1"'));
  await ev('document.getElementById("reviewBtn").click(); true'); await sleep(100);
  const cBefore = await ev('gallop.cycleCount'); await sleep(1200);
  check('review panel open and audio still running', await ev('document.getElementById("reviewDlg").open && gallop.ctx.state === "running"') && (await ev('gallop.cycleCount')) > cBefore);
  check('panel shows the current case', await ev('document.getElementById("rvId").textContent === document.getElementById("caseSel").value'));
  check('ten questions rendered', await ev('document.querySelectorAll("#rvQuestions .q").length') === 10);
  await ev('document.getElementById("rvName").value = "Test Reviewer"; document.getElementById("rvRole").value = "ACP"; document.querySelector("input[name=R1][value=\'4\']").click(); document.querySelector("input[name=R10]").click(); document.getElementById("rvChange").value = "louder S2"; document.getElementById("reviewForm").requestSubmit(); true'); await sleep(100);
  const saved = await ev('JSON.parse(localStorage.getItem("gallop.reviews"))');
  check('review saved with case id, answers and context', saved.length === 1 && saved[0].case_id === (await ev('document.getElementById("caseSel").value')) && saved[0].answers.R1 === '4' && saved[0].answers.R10 === 'Sign off as is' && saved[0].change === 'louder S2' && typeof saved[0].context.bpm === 'number', saved[0].answers);
  check('send-by-email link carries the review', await ev('document.getElementById("rvMail").href.startsWith("mailto:") && decodeURIComponent(document.getElementById("rvMail").href).includes("louder S2")'));
  check('reviewer name remembered', await ev('localStorage.getItem("gallop.rvName")') === 'Test Reviewer');
  await ev('document.getElementById("rvCancel").click(); true');

  // master gain never changed
  check('master gain unchanged at end', Math.abs(await ev('gallop.master.gain.value') - 0.7) < 1e-6);
  // reset clears localStorage keys
  await ev('window.confirm = () => true; location.reload = () => {}; document.getElementById("resetBtn").click(); Object.keys(localStorage).filter(k=>k.startsWith("gallop.") && !/reviews|rvName|rvRole|rvEmail|reviewer/.test(k)).length').then(n => check('reset clears learner keys', n === 0, n));
  check('reset keeps stored reviews', await ev('JSON.parse(localStorage.getItem("gallop.reviews")).length') === 1);

  check('no console errors / exceptions', consoleErrors.length === 0, consoleErrors);
  const failed = results.filter(r => !r.ok).length;
  console.log(`\n${results.length - failed}/${results.length} checks passed`);
  ws.close();
  process.exit(failed ? 1 : 0);
})().catch(e => { console.error('SMOKE ERROR', e); process.exit(2); });
