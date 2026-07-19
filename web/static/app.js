"use strict";

// --------------------------------------------------------------------- //
// Ícones (lucide, embutidos — sem CDN em runtime)
// --------------------------------------------------------------------- //
const ICONS = {
  folder: '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />',
  file: '<path d="M6 22a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h8a2.4 2.4 0 0 1 1.704.706l3.588 3.588A2.4 2.4 0 0 1 20 8v12a2 2 0 0 1-2 2z" /><path d="M14 2v5a1 1 0 0 0 1 1h5" /><path d="M10 9H8" /><path d="M16 13H8" /><path d="M16 17H8" />',
  lock: '<rect width="18" height="11" x="3" y="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />',
  delete: '<path d="M10 5a2 2 0 0 0-1.344.519l-6.328 5.74a1 1 0 0 0 0 1.481l6.328 5.741A2 2 0 0 0 10 19h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2z" /><path d="m12 9 6 6" /><path d="m18 9-6 6" />',
  cornerDownLeft: '<path d="M20 4v7a4 4 0 0 1-4 4H4" /><path d="m9 10-5 5 5 5" />',
  cornerDownRight: '<path d="m15 10 5 5-5 5" /><path d="M4 4v7a4 4 0 0 0 4 4h12" />',
  radar: '<path d="M19.07 4.93A10 10 0 0 0 6.99 3.34" /><path d="M4 6h.01" /><path d="M2.29 9.62A10 10 0 1 0 21.31 8.35" /><path d="M16.24 7.76A6 6 0 1 0 8.23 16.67" /><path d="M12 18h.01" /><path d="M17.99 11.66A6 6 0 0 1 15.77 16.67" /><circle cx="12" cy="12" r="2" /><path d="m13.41 10.59 5.66-5.66" />',
  save: '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" /><path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7" /><path d="M7 3v4a1 1 0 0 0 1 1h7" />',
  terminal: '<path d="M12 19h8" /><path d="m4 17 6-6-6-6" />',
  x: '<path d="M18 6 6 18" /><path d="m6 6 12 12" />',
  refreshCw: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" /><path d="M21 3v5h-5" /><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" /><path d="M8 16H3v5" />',
  package: '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z" /><path d="M12 22V12" /><polyline points="3.29 7 12 12 20.71 7" /><path d="m7.5 4.27 9 5.15" />',
  play: '<path d="M5 5a2 2 0 0 1 3.008-1.728l11.997 6.998a2 2 0 0 1 .003 3.458l-12 7A2 2 0 0 1 5 19z" />',
  trash2: '<path d="M10 11v6" /><path d="M14 11v6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" /><path d="M3 6h18" /><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />',
  square: '<rect width="18" height="18" x="3" y="3" rx="2" />',
  cpu: '<path d="M12 20v2" /><path d="M12 2v2" /><path d="M17 20v2" /><path d="M17 2v2" /><path d="M2 12h2" /><path d="M2 17h2" /><path d="M2 7h2" /><path d="M20 12h2" /><path d="M20 17h2" /><path d="M20 7h2" /><path d="M7 20v2" /><path d="M7 2v2" /><rect x="4" y="4" width="16" height="16" rx="2" /><rect x="8" y="8" width="8" height="8" rx="1" />',
  thermometer: '<path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z" />',
  backpack: '<path d="M4 10a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" /><path d="M8 10h8" /><path d="M8 18h8" /><path d="M8 22v-6a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v6" /><path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" />',
};

function svgIcon(name, extraClass) {
  const wrap = document.createElement("div");
  wrap.innerHTML =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" class="icon' +
    (extraClass ? " " + extraClass : "") + '">' + ICONS[name] + "</svg>";
  return wrap.firstElementChild;
}

// --------------------------------------------------------------------- //
// WebSocket
// --------------------------------------------------------------------- //
let ws = null;
let sessionId = null;
let lastState = null;
let typed = "";
let _lastNetJson = null;
let _lastFsJson = null;

function proto() { return location.protocol === "https:" ? "wss:" : "ws:"; }

function connect() {
  ws = new WebSocket(proto() + "//" + location.host + "/ws");
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.session_id) sessionId = msg.session_id;
    if (msg.type === "state") {
      render(msg.snapshot, msg.log || []);
    }
  };
  ws.onclose = () => {
    appendLog([{ text: "conexão perdida — reconectando em 2s...", kind: "warn" }]);
    setTimeout(connect, 2000);
  };
}

function send(action, extra) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify(Object.assign({ action }, extra || {})));
}

// --------------------------------------------------------------------- //
// Render
// --------------------------------------------------------------------- //
function render(state, log) {
  lastState = state;

  document.getElementById("stat-sector").textContent = state.sector;
  document.getElementById("stat-host").textContent = state.location;
  document.getElementById("stat-wallet").textContent = state.wallet.toFixed(2);
  const heatEl = document.getElementById("stat-heat");
  heatEl.textContent = Math.round(state.heat) + "°";
  heatEl.classList.toggle("stat-hot", state.overheated);
  document.getElementById("stat-mining-icon").classList.toggle(
    "hidden", !state.processes.includes("miner")
  );

  renderInventory(state);

  const pct = Math.round(state.trace);
  const fill = document.getElementById("trace-fill");
  fill.style.width = pct + "%";
  fill.style.background =
    pct >= 100 ? "#ff4d4d" : pct >= 75 ? "#ff8a4d" : pct >= 40 ? "#ffd23f" : "#33ff66";
  document.getElementById("trace-pct").textContent = pct + "%";

  // Reconstruir mapa/filesystem do zero é caro e, no toque, troca o elemento
  // debaixo do dedo no meio do gesto — só refaz quando os dados de verdade
  // mudaram (a maioria dos ticks de combate/lockdown não mexe nem no mapa
  // nem no filesystem).
  const netJson = JSON.stringify(state.net);
  if (netJson !== _lastNetJson) {
    renderMap(state.net);
    _lastNetJson = netJson;
  }
  const fsJson = JSON.stringify([state.cwd, state.listing]);
  if (fsJson !== _lastFsJson) {
    renderFs(state);
    _lastFsJson = fsJson;
  }
  appendLog(log);

  const explore = document.getElementById("explore");
  const duel = document.getElementById("duel-overlay");
  const dead = document.getElementById("dead-overlay");

  duel.classList.toggle("hidden", state.mode !== "combat" && state.mode !== "lockdown");
  dead.classList.toggle("hidden", state.mode !== "dead");
  explore.style.visibility = "visible";

  if (state.mode === "combat" && state.combat) {
    renderDuel(state.combat, "combat_submit", false);
  } else if (state.mode === "lockdown" && state.lockdown) {
    renderDuel(state.lockdown, "lockdown_submit", true);
  }

  if (state.mode === "dead") {
    document.getElementById("dead-line").textContent = state.villain_said || "";
  }
}

function renderMap(net) {
  const el = document.getElementById("netmap");
  el.innerHTML = "";
  for (const n of net) {
    const canHack = !n.here && n.state !== "compromised" && n.state !== "fog";
    const btn = document.createElement("button");
    const classes = ["node-btn", n.state];
    if (n.here) classes.push("here");
    if (canHack) classes.push("tappable");
    btn.className = classes.join(" ");
    btn.style.gridColumnStart = n.col + 1;
    btn.style.gridRowStart = n.row + 1;
    btn.textContent = n.state === "fog" ? "????" : n.label;
    btn.disabled = !canHack;
    btn.setAttribute("aria-label", (n.state === "fog" ? "host desconhecido" : n.label));
    if (canHack) {
      btn.addEventListener("click", () => send("hack", { target: n.label }));
    }
    el.appendChild(btn);
  }
}

// Botões extra pra um item de loot ainda na pasta (não tomado pro buffer).
// Mesma regra de app.py:_apply_item — keycard/backdoor só funcionam depois
// de `take` (então só ganham TAKE); miner/spoof rodam direto da pasta (TAKE +
// RUN); o resto (wallet/credits/adminkey/coolant/scrambler) funciona igual
// na pasta ou no bolso (TAKE + USE). "reader" é fixo na sala, sem botão.
function itemButtons(item) {
  const kind = item.item;
  if (!kind || kind === "reader") return [];
  const buttons = [{ label: "TAKE", cls: "btn-item", action: () => send("take", { target: item.name }) }];
  if (kind === "miner" || kind === "spoof") {
    buttons.push({ label: "RUN", cls: "btn-item btn-run", action: () => send("run", { target: item.name }) });
  } else if (kind !== "keycard" && kind !== "backdoor") {
    buttons.push({ label: "USE", cls: "btn-item btn-run", action: () => send("use", { args: [item.name] }) });
  }
  return buttons;
}

function renderFs(state) {
  document.getElementById("fs-path").textContent = state.cwd || "/";
  document.getElementById("fs-up").style.visibility = state.cwd ? "visible" : "hidden";
  const el = document.getElementById("fs-listing");
  el.innerHTML = "";
  for (const item of state.listing) {
    const row = document.createElement("div");
    row.className = "fs-row " + (item.is_dir ? "dir" : "file");
    const kindIcon = () => svgIcon(item.item ? "package" : item.is_dir ? "folder" : "file", "icon-sm");
    if (item.locked) {
      const name = document.createElement("span");
      name.className = "fs-name";
      name.appendChild(svgIcon("lock", "icon-sm lockicon"));
      name.appendChild(kindIcon());
      name.append(item.name);
      row.appendChild(name);
      const btn = document.createElement("button");
      btn.className = "btn-hack";
      btn.textContent = "HACK";
      btn.addEventListener("click", () => send("hack", { target: item.name }));
      row.appendChild(btn);
    } else {
      const btn = document.createElement("button");
      btn.className = "fs-name fs-name-btn";
      btn.appendChild(kindIcon());
      btn.append(item.name);
      btn.addEventListener("click", () => {
        if (item.is_dir) send("cd", { target: item.name });
        else openCat(item.name);
      });
      row.appendChild(btn);
      for (const b of itemButtons(item)) {
        const ibtn = document.createElement("button");
        ibtn.className = b.cls;
        ibtn.textContent = b.label;
        ibtn.addEventListener("click", b.action);
        row.appendChild(ibtn);
      }
    }
    el.appendChild(row);
  }
}

// --------------------------------------------------------------------- //
// Inventário (buffer de itens + processos) — overlay, não modal de leitura
// --------------------------------------------------------------------- //
function renderInventory(state) {
  document.getElementById("inv-wallet").textContent = state.wallet.toFixed(2);
  document.getElementById("inv-adminkey").textContent = state.adminkey;
  document.getElementById("inv-ram").textContent = state.ram_free + "/" + state.ram_total + "KB";
  document.getElementById("inv-heat").textContent = Math.round(state.heat) + "°" + (state.overheated ? " [THROTTLE]" : "");

  const procEl = document.getElementById("inv-processes");
  procEl.innerHTML = "";
  if (state.processes.includes("miner")) {
    const row = document.createElement("div");
    row.className = "inv-row";
    const label = document.createElement("span");
    label.textContent = "miner  " + state.hashrate + "h/s";
    row.appendChild(label);
    const killBtn = document.createElement("button");
    killBtn.className = "btn-item";
    killBtn.appendChild(svgIcon("square", "icon-sm"));
    killBtn.append(" KILL");
    killBtn.addEventListener("click", () => send("kill", { target: "miner" }));
    row.appendChild(killBtn);
    procEl.appendChild(row);
  } else {
    procEl.innerHTML = '<div class="inv-empty">nenhum processo rodando</div>';
  }

  const listEl = document.getElementById("inv-list");
  listEl.innerHTML = "";
  if (!state.inventory.length) {
    listEl.innerHTML = '<div class="inv-empty">buffer vazio</div>';
    return;
  }
  for (const it of state.inventory) {
    const row = document.createElement("div");
    row.className = "inv-row";
    const label = document.createElement("span");
    label.appendChild(svgIcon("package", "icon-sm"));
    label.append(" " + it.name + " (" + it.kind + ")");
    row.appendChild(label);
    const actions = document.createElement("div");
    actions.className = "inv-actions";
    if (it.kind === "miner" || it.kind === "spoof") {
      const runBtn = document.createElement("button");
      runBtn.className = "btn-item btn-run";
      runBtn.appendChild(svgIcon("play", "icon-sm"));
      runBtn.append(" RUN");
      runBtn.addEventListener("click", () => send("run", { target: it.name }));
      actions.appendChild(runBtn);
    } else {
      const useBtn = document.createElement("button");
      useBtn.className = "btn-item btn-run";
      useBtn.appendChild(svgIcon("play", "icon-sm"));
      useBtn.append(" USE");
      useBtn.addEventListener("click", () => {
        // backdoor precisa de um alvo (rede ou pasta trancada) — sem um
        // seletor dedicado nesta onda, pergunta direto; os demais usam sem alvo.
        if (it.kind === "backdoor") {
          const alvo = window.prompt("usar backdoor em qual alvo?");
          if (alvo) send("use", { args: [it.name, alvo] });
        } else if (it.kind === "keycard") {
          send("use", { args: [it.name] }); // usa o leitor da sala atual, se houver
        } else {
          send("use", { args: [it.name] });
        }
      });
      actions.appendChild(useBtn);
    }
    const dropBtn = document.createElement("button");
    dropBtn.className = "btn-item btn-drop";
    dropBtn.appendChild(svgIcon("trash2", "icon-sm"));
    dropBtn.append(" DROP");
    dropBtn.addEventListener("click", () => send("drop", { target: it.name }));
    actions.appendChild(dropBtn);
    row.appendChild(actions);
    listEl.appendChild(row);
  }
}

function openCat(name) {
  send("cat", { target: name });
  pendingCatName = name;
}
let pendingCatName = null;

function appendLog(lines) {
  if (!lines || !lines.length) return;
  const el = document.getElementById("log");
  for (const l of lines) {
    // conteúdo de arquivo (kind "file") abre no modal em vez de poluir o log
    if (l.kind === "file" && pendingCatName !== null) {
      document.getElementById("cat-content").textContent = l.text;
      document.getElementById("cat-overlay").classList.remove("hidden");
      pendingCatName = null;
      continue;
    }
    const div = document.createElement("div");
    div.className = "log-line log-" + l.kind;
    div.textContent = l.text;
    el.appendChild(div);
  }
  el.scrollTop = el.scrollHeight;
}

// --------------------------------------------------------------------- //
// Duelo (combate / LOCKDOWN) — teclado tátil próprio
// --------------------------------------------------------------------- //
// Disposição QWERTY, linha de números no topo — cada string é uma fileira do
// teclado. O conjunto de caracteres cobre o alfabeto do código: A-Z, 0-9 e os
// separadores "-" e ":" (ver coldboot/combat.py).
const KEY_ROWS = [
  "1234567890".split(""),
  "QWERTYUIOP".split(""),
  "ASDFGHJKL".split(""),
  "ZXCVBNM".split(""),
];
// Um dos prefixos do código é literalmente "0x" (x minúsculo) — o único
// caractere minúsculo que aparece fora do modo fácil (que esta onda não tem).
// Em vez de uma tecla "x" minúscula fácil de confundir com o "X" maiúsculo
// do teclado, um botão dedicado digita o par inteiro de uma vez. Fica na
// mesma fileira que os separadores "-" e ":".
const COMBO_KEYS = ["0x"];
const PUNCT_KEYS = ["-", ":"];

function buildKeypad() {
  const el = document.getElementById("keypad");
  el.innerHTML = "";
  const append = (s) => {
    typed += s;
    document.getElementById("duel-typed").value = typed;
  };
  const makeKey = (label, extraClass, onClick) => {
    const btn = document.createElement("button");
    btn.className = extraClass ? "key " + extraClass : "key";
    if (label instanceof Node) btn.appendChild(label);
    else btn.textContent = label;
    btn.addEventListener("click", onClick);
    return btn;
  };
  const labelWithIcon = (iconName, text) => {
    const span = document.createElement("span");
    span.className = "key-label";
    span.appendChild(svgIcon(iconName));
    span.append(" " + text);
    return span;
  };

  // Uma fileira de teclado por linha, cada uma numa <div class="key-row">.
  for (const rowKeys of KEY_ROWS) {
    const row = document.createElement("div");
    row.className = "key-row";
    for (const k of rowKeys) {
      row.appendChild(makeKey(k, "", () => append(k)));
    }
    el.appendChild(row);
  }

  // Fileira dos separadores + combo "0x".
  const punctRow = document.createElement("div");
  punctRow.className = "key-row";
  for (const k of PUNCT_KEYS) {
    punctRow.appendChild(makeKey(k, "", () => append(k)));
  }
  for (const k of COMBO_KEYS) {
    punctRow.appendChild(makeKey(k, "key-combo", () => append(k)));
  }
  el.appendChild(punctRow);

  // Fileira de ações: apagar + enviar.
  const actionRow = document.createElement("div");
  actionRow.className = "key-row key-row-actions";
  actionRow.appendChild(
    makeKey(labelWithIcon("delete", "APAGAR"), "key-back", () => {
      typed = typed.slice(0, -1);
      document.getElementById("duel-typed").value = typed;
    })
  );
  actionRow.appendChild(makeKey(labelWithIcon("cornerDownLeft", "ENVIAR"), "key-enter", submitTyped));
  el.appendChild(actionRow);
}

let submitAction = "combat_submit";
function submitTyped() {
  send(submitAction, { text: typed });
  typed = "";
  document.getElementById("duel-typed").value = "";
}

// O campo do código é um <input> de verdade: tanto o teclado tátil quanto o
// teclado nativo (quem preferir digitar em vez de tocar) escrevem nele.
const duelTypedInput = document.getElementById("duel-typed");
duelTypedInput.addEventListener("input", () => { typed = duelTypedInput.value; });
duelTypedInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); submitTyped(); }
});

function renderDuel(session, action, isLockdown) {
  submitAction = action;
  document.getElementById("duel-title").textContent = isLockdown
    ? "LOCKDOWN — REBATER O SINAL"
    : session.name + " [" + session.ice_type + "]";
  const total = isLockdown ? session.total : session.total_rounds;
  document.getElementById("duel-round").textContent =
    "round " + (session.round + 1) + "/" + total;
  const code = isLockdown ? session.code : session.code_display;
  document.getElementById("duel-code").textContent = code;
  const timeLeft = session.time_left;
  const timeMax = isLockdown ? session.time_limit : session.round_time;
  const pct = Math.max(0, Math.min(100, (timeLeft / timeMax) * 100));
  document.getElementById("duel-timerfill").style.width = pct + "%";
}

// --------------------------------------------------------------------- //
// Terminal — comandos digitados, alternativa ao toque (não só modais)
// --------------------------------------------------------------------- //
// Verbos que o terminal web de fato entende (subconjunto de
// parser.COMPLETION_VERBS — só o que submitTerminal sabe despachar nesta onda).
const TERMINAL_VERBS = [
  "cd", "cat", "look", "scan", "hack", "save", "ls", "pwd", "help", "reboot",
  "take", "drop", "use", "run", "kill", "inv", "ps",
];

function commonPrefix(strs) {
  if (!strs.length) return "";
  let p = strs[0];
  for (const s of strs.slice(1)) {
    let i = 0;
    while (i < p.length && i < s.length && p[i].toLowerCase() === s[i].toLowerCase()) i++;
    p = p.slice(0, i);
    if (!p) break;
  }
  return p;
}

// Espelha app.py:_arg_candidates — mesma regra por verbo, restrita ao que o
// cliente já tem em `lastState` (listing do cwd + mapa da rede).
function argCandidates(verb, frag) {
  if (!lastState) return [];
  const fl = frag.toLowerCase();
  const pref = (seq) => seq.filter((n) => n.toLowerCase().startsWith(fl)).sort();
  const names = lastState.listing.map((i) => i.name);
  if (verb === "cd") {
    return pref(lastState.listing.filter((i) => i.is_dir).map((i) => i.name));
  }
  if (verb === "cat") {
    return pref(lastState.listing.filter((i) => !i.is_dir).map((i) => i.name));
  }
  if (verb === "hack") {
    const locked = lastState.listing.filter((i) => i.locked).map((i) => i.name);
    const hosts = lastState.net.filter((n) => n.state === "discovered").map((n) => n.label);
    return pref(locked.concat(hosts));
  }
  if (verb === "take" || verb === "run") {
    return pref(lastState.listing.filter((i) => i.item).map((i) => i.name));
  }
  if (verb === "use") {
    return pref(
      lastState.inventory.map((it) => it.name)
        .concat(lastState.listing.filter((i) => i.item).map((i) => i.name))
    );
  }
  if (verb === "drop") {
    return pref(lastState.inventory.map((it) => it.name));
  }
  if (verb === "kill") {
    return pref(lastState.processes);
  }
  return pref(names); // "look" e qualquer outro: sem regra própria, cai no default (app.py faz o mesmo)
}

// Espelha app.py:compute_completion — devolve [novo_valor_ou_null, candidatos].
function computeCompletion(text) {
  const parts = text.split(" ");
  const frag = parts[parts.length - 1];
  const cands = parts.length === 1
    ? TERMINAL_VERBS.filter((v) => v.startsWith(frag.toLowerCase()))
    : argCandidates(parts[0].toLowerCase(), frag);
  if (!cands.length) return [null, []];
  if (cands.length === 1) {
    parts[parts.length - 1] = cands[0];
    return [parts.join(" ") + " ", []];
  }
  const prefix = commonPrefix(cands);
  if (prefix.length > frag.length) {
    // estende até o prefixo comum, mas ainda ambíguo: atualiza o campo E lista
    parts[parts.length - 1] = prefix;
    return [parts.join(" "), cands];
  }
  return [null, cands];
}

document.getElementById("terminal-input").addEventListener("keydown", (e) => {
  if (e.key !== "Tab") return;
  e.preventDefault(); // era isto que pulava pro próximo botão — agora autocompleta
  const input = e.target;
  const [newValue, candidates] = computeCompletion(input.value);
  if (candidates.length > 1) {
    appendLog([{ text: candidates.join("  "), kind: "info" }]);
  }
  if (newValue !== null) {
    input.value = newValue;
  }
});

function logListing() {
  if (!lastState) return;
  const names = lastState.listing
    .map((i) => i.name + (i.is_dir ? "/" : "") + (i.locked ? " [locked]" : ""))
    .join("  ");
  appendLog([{ text: names || "(vazio)", kind: "info" }]);
}

function logInventory() {
  if (!lastState) return;
  const bits = ["CRN " + lastState.wallet.toFixed(2)];
  if (lastState.adminkey) bits.push("chave-admin x" + lastState.adminkey);
  appendLog([{ text: bits.join(" · "), kind: "info" }]);
  const lines = lastState.inventory.length
    ? lastState.inventory.map((it) => "  " + it.name + " (" + it.kind + ")").join("\n")
    : "(buffer vazio)";
  appendLog([{ text: lines, kind: "info" }]);
}

function logProcesses() {
  if (!lastState) return;
  const lines = [];
  if (lastState.processes.includes("miner")) {
    lines.push(
      "miner  hashrate " + lastState.hashrate + (lastState.overheated ? "  [THROTTLE]" : "")
    );
  }
  lines.push("buffer: " + lastState.inventory.length + " itens");
  lines.push("RAM livre: " + lastState.ram_free + "/" + lastState.ram_total + " KB");
  appendLog([{ text: lines.join("\n"), kind: "info" }]);
}

function submitTerminal(raw) {
  const line = raw.trim();
  if (!line || !lastState) return;

  // Dentro de um duelo, o terminal digita o código em vez de interpretar
  // verbo — mesma ação que o teclado tátil dispara.
  if (lastState.mode === "combat" || lastState.mode === "lockdown") {
    send(submitAction, { text: line });
    return;
  }
  if (lastState.mode === "dead") {
    if (line.split(/\s+/)[0].toLowerCase() === "reboot") send("reboot");
    else appendLog([{ text: "sem conexão. digite reboot.", kind: "warn" }]);
    return;
  }

  const sp = line.indexOf(" ");
  const verb = (sp === -1 ? line : line.slice(0, sp)).toLowerCase();
  const arg = sp === -1 ? "" : line.slice(sp + 1).trim();
  switch (verb) {
    case "cd": send("cd", { target: arg }); break;
    case "cat": case "read": case "open": if (arg) openCat(arg); break;
    case "look": case "olhar": send("look", { target: arg }); break;
    case "scan": case "nmap": send("scan"); break;
    case "hack": case "crack": send("hack", { target: arg }); break;
    case "save": send("save"); break;
    case "ls": case "dir": logListing(); break;
    case "pwd": appendLog([{ text: lastState.cwd || "/", kind: "info" }]); break;
    case "take": case "pegar": send("take", { target: arg }); break;
    case "drop": case "largar": send("drop", { target: arg }); break;
    case "run": case "exec": case "rodar": send("run", { target: arg }); break;
    case "kill": case "matar": case "stop": send("kill", { target: arg }); break;
    case "inv": case "inventory": case "inventario": logInventory(); break;
    case "ps": logProcesses(); break;
    case "use": case "usar": {
      const words = arg.split(/\s+/).filter((w) => w && !["no", "em", "on", "in"].includes(w.toLowerCase()));
      send("use", { args: words });
      break;
    }
    case "help": case "?":
      appendLog([{
        text: "comandos: cd, cat, look, scan, hack, save, ls, pwd, take, drop, use, run, kill, inv, ps",
        kind: "info",
      }]);
      break;
    default:
      appendLog([{ text: "comando desconhecido: " + verb, kind: "warn" }]);
  }
}

document.getElementById("terminal-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = document.getElementById("terminal-input");
  const val = input.value;
  if (val.trim()) appendLog([{ text: "> " + val, kind: "info" }]);
  submitTerminal(val);
  input.value = "";
});

// --------------------------------------------------------------------- //
// Botões fixos
// --------------------------------------------------------------------- //
document.getElementById("fs-up").addEventListener("click", () => send("cd", { target: ".." }));
document.getElementById("btn-scan").addEventListener("click", () => send("scan"));
document.getElementById("btn-save").addEventListener("click", () => send("save"));
document.getElementById("btn-reboot").addEventListener("click", () => send("reboot"));
document.getElementById("btn-cat-close").addEventListener("click", () => {
  document.getElementById("cat-overlay").classList.add("hidden");
});
document.getElementById("btn-inv").addEventListener("click", () => {
  document.getElementById("inv-overlay").classList.remove("hidden");
});
document.getElementById("btn-inv-close").addEventListener("click", () => {
  document.getElementById("inv-overlay").classList.add("hidden");
});

// Ícones estáticos (montados uma vez — não mudam por render).
document.getElementById("btn-scan").prepend(svgIcon("radar"));
document.getElementById("btn-save").prepend(svgIcon("save"));
document.getElementById("btn-inv").prepend(svgIcon("backpack"));
document.getElementById("btn-reboot").prepend(svgIcon("refreshCw"));
document.getElementById("btn-cat-close").prepend(svgIcon("x"));
document.getElementById("btn-inv-close").prepend(svgIcon("x"));
document.getElementById("terminal-icon").appendChild(svgIcon("terminal"));
document.getElementById("terminal-send").appendChild(svgIcon("cornerDownRight"));
document.getElementById("stat-mining-icon").appendChild(svgIcon("cpu", "icon-sm"));

buildKeypad();
connect();
