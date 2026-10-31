const API = "http://localhost:8000";
const TOKEN_KEY = "splitbill.token";
const EMAIL_KEY = "splitbill.email";

const state = {
  token: localStorage.getItem(TOKEN_KEY) || null,
  email: localStorage.getItem(EMAIL_KEY) || null,
  groups: [],
  group: null,
  groupId: null,
  members: [],
  expenses: [],
  balances: [],
  suggestions: [],
};

const $  = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

function show(el) { el.classList.remove("hidden"); }
function hide(el) { el.classList.add("hidden"); }

let toastTimer;
function toast(msg, kind = "ok") {
  const t = $("#toast");
  t.textContent = msg;
  t.className = `toast ${kind === "ok" ? "is-ok" : "is-err"}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 2800);
}

function money(n) {
  const sign = n < 0 ? "-" : "";
  return sign + "Rp " + Math.abs(n).toLocaleString("id-ID");
}

function setError(el, msg) {
  if (!msg) { hide(el); el.textContent = ""; return; }
  el.textContent = msg;
  show(el);
}

async function api(path, { method = "GET", body, auth = true, form = false } = {}) {
  const headers = {};
  if (auth && state.token) headers.Authorization = `Bearer ${state.token}`;
  if (body && form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
  } else if (body) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(API + path, {
    method,
    headers,
    body: body ? (form ? body : JSON.stringify(body)) : undefined,
  });

  if (res.status === 401 && auth) {
    logout();
    throw new Error("Session expired. Sign in again.");
  }

  let payload = null;
  const text = await res.text();
  if (text) {
    try { payload = JSON.parse(text); } catch { payload = text; }
  }

  if (!res.ok) {
    const detail = payload?.detail ?? `Request failed (${res.status})`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload;
}

function saveSession(token, email) {
  state.token = token;
  state.email = email;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(EMAIL_KEY, email);
}

function logout() {
  state.token = null;
  state.email = null;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(EMAIL_KEY);
  showView("auth");
}

function showView(name, opts = {}) {
  ["auth", "dashboard", "group"].forEach(v => hide($(`#view-${v}`)));
  show($(`#view-${name}`));

  if (name === "auth") {
    $("#auth-error").classList.add("hidden");
    $("#form-login").reset();
    $("#form-register").reset();
  }
  if (name === "dashboard") {
    loadDashboard();
  }
  if (name === "group") {
    enterGroup(opts.groupId);
  }
}

$("#form-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = new FormData(e.target);
  const body = new URLSearchParams();
  body.set("username", String(data.get("email") || "").trim());
  body.set("password", String(data.get("password") || ""));

  const err = $("#auth-error");
  setError(err, null);
  const btn = e.target.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    const r = await api("/auth/login", { method: "POST", body, form: true, auth: false });
    saveSession(r.access_token, String(data.get("email") || "").trim().toLowerCase());
    showView("dashboard");
  } catch (ex) {
    setError(err, ex.message);
  } finally {
    btn.disabled = false;
  }
});

$("#form-register").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = new FormData(e.target);
  const payload = {
    email: String(data.get("email") || "").trim(),
    password: String(data.get("password") || ""),
  };
  const err = $("#auth-error");
  setError(err, null);
  const btn = e.target.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    await api("/auth/register", { method: "POST", body: payload, auth: false });
    const body = new URLSearchParams();
    body.set("username", payload.email);
    body.set("password", payload.password);
    const r = await api("/auth/login", { method: "POST", body, form: true, auth: false });
    saveSession(r.access_token, payload.email.toLowerCase());
    showView("dashboard");
  } catch (ex) {
    setError(err, ex.message);
  } finally {
    btn.disabled = false;
  }
});

$$("[data-auth-tab]").forEach(btn => {
  btn.addEventListener("click", () => {
    $$("[data-auth-tab]").forEach(b => b.classList.toggle("is-active", b === btn));
    const which = btn.dataset.authTab;
    $("#form-login").classList.toggle("hidden", which !== "login");
    $("#form-register").classList.toggle("hidden", which !== "register");
    $("#auth-error").classList.add("hidden");
  });
});

$$("#btn-logout, #btn-logout-2").forEach(b => b.addEventListener("click", logout));

async function loadDashboard() {
  $("#dash-user").textContent = state.email || "";
  const list = $("#groups-list");
  list.innerHTML = "";
  try {
    const groups = await api("/groups");
    state.groups = groups;
    if (!groups.length) {
      show($("#groups-empty"));
    } else {
      hide($("#groups-empty"));
      for (const g of groups) {
        const li = document.createElement("li");
        li.className = "group-card";
        li.innerHTML = `
          <h3></h3>
          <span class="meta">Open group</span>
        `;
        li.querySelector("h3").textContent = g.name;
        li.addEventListener("click", () => showView("group", { groupId: g.id }));
        list.appendChild(li);
      }
    }
  } catch (ex) {
    toast(ex.message, "err");
  }
}

const dlgGroup = $("#dlg-group");
$("#btn-new-group").addEventListener("click", () => dlgGroup.showModal());
$("#btn-new-group-2").addEventListener("click", () => dlgGroup.showModal());
$$("[data-close]", dlgGroup).forEach(b => b.addEventListener("click", () => dlgGroup.close()));

$("#form-group").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = new FormData(e.target);
  const name = String(data.get("name") || "").trim();
  const err = $("#group-error");
  setError(err, null);
  if (!name) { setError(err, "Name is required."); return; }
  try {
    await api("/groups", { method: "POST", body: { name } });
    dlgGroup.close();
    e.target.reset();
    loadDashboard();
    toast("Group created.");
  } catch (ex) {
    setError(err, ex.message);
  }
});

$("#btn-back").addEventListener("click", () => showView("dashboard"));

async function enterGroup(groupId) {
  state.groupId = groupId;
  state.group = state.groups.find(g => g.id === groupId) || null;
  $("#group-user").textContent = state.email || "";
  $("#group-title").textContent = state.group?.name || "—";

  $$("[data-group-tab]").forEach(b => b.classList.toggle("is-active", b.dataset.groupTab === "expenses"));
  ["expenses", "balances", "members", "settle"].forEach(p =>
    $(`#panel-${p}`).classList.toggle("hidden", p !== "expenses")
  );

  try {
    await loadMembers();
    await loadExpenses();
  } catch (ex) {
    toast(ex.message, "err");
  }
}

$$("[data-group-tab]").forEach(btn => {
  btn.addEventListener("click", async () => {
    const which = btn.dataset.groupTab;
    $$("[data-group-tab]").forEach(b => b.classList.toggle("is-active", b === btn));
    ["expenses", "balances", "members", "settle"].forEach(p =>
      $(`#panel-${p}`).classList.toggle("hidden", p !== which)
    );
    try {
      if (which === "balances") await loadBalances();
      if (which === "members") await loadMembers();
      if (which === "settle") { await loadMembers(); await loadSuggestions(); }
      if (which === "expenses") await loadExpenses();
    } catch (ex) {
      toast(ex.message, "err");
    }
  });
});

async function loadMembers() {
  const rows = await api(`/groups/${state.groupId}/members`);
  state.members = rows;
  const ul = $("#members-list");
  ul.innerHTML = "";
  for (const m of rows) {
    const isMe = m.email === state.email;
    const li = document.createElement("li");
    li.className = "member-row";
    li.innerHTML = `
      <div class="member-id">
        <span class="member-email"></span>
        <span class="role-tag"></span>
      </div>
      <div class="member-actions"></div>
    `;
    li.querySelector(".member-email").textContent = m.email + (isMe ? " (you)" : "");
    const tag = li.querySelector(".role-tag");
    tag.textContent = m.role;
    tag.classList.toggle("admin", m.role === "admin");

    const actions = li.querySelector(".member-actions");
    if (!isMe) {
      const promote = document.createElement("button");
      promote.className = "btn btn-ghost btn-sm";
      promote.textContent = "Promote";
      promote.addEventListener("click", () => promoteMember(m.user_id));
      actions.appendChild(promote);

      const remove = document.createElement("button");
      remove.className = "btn btn-ghost btn-sm";
      remove.textContent = "Remove";
      remove.addEventListener("click", () => removeMember(m.user_id));
      actions.appendChild(remove);
    } else {
      const leave = document.createElement("button");
      leave.className = "btn btn-ghost btn-sm";
      leave.textContent = "Leave";
      leave.addEventListener("click", () => removeMember(m.user_id));
      actions.appendChild(leave);
    }
    ul.appendChild(li);
  }
  const sel = $("#form-settle select[name=payee_id]");
  sel.innerHTML = "";
  for (const m of rows) {
    if (m.email === state.email) continue;
    const opt = document.createElement("option");
    opt.value = String(m.user_id);
    opt.textContent = m.email;
    sel.appendChild(opt);
  }
}

async function promoteMember(userId) {
  try {
    await api(`/groups/${state.groupId}/members/${userId}/promote`, { method: "PATCH" });
    toast("Member promoted.");
    await loadMembers();
  } catch (ex) { toast(ex.message, "err"); }
}

async function removeMember(userId) {
  try {
    await api(`/groups/${state.groupId}/members/${userId}`, { method: "DELETE" });
    toast("Member removed.");
    await loadMembers();
    await loadExpenses();
  } catch (ex) { toast(ex.message, "err"); }
}

const dlgInvite = $("#dlg-invite");
$("#btn-invite").addEventListener("click", () => dlgInvite.showModal());
$$("[data-close]", dlgInvite).forEach(b => b.addEventListener("click", () => dlgInvite.close()));

$("#form-invite").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = new FormData(e.target);
  const email = String(data.get("email") || "").trim();
  const err = $("#invite-error");
  setError(err, null);
  if (!email) { setError(err, "Email is required."); return; }
  try {
    await api(`/groups/${state.groupId}/invite`, { method: "POST", body: { email } });
    dlgInvite.close();
    e.target.reset();
    await loadMembers();
    toast("Member invited.");
  } catch (ex) {
    setError(err, ex.message);
  }
});

async function loadExpenses() {
  const rows = await api(`/groups/${state.groupId}/expenses`);
  state.expenses = rows;
  const ol = $("#expenses-list");
  ol.innerHTML = "";
  if (!rows.length) {
    show($("#expenses-empty"));
    return;
  }
  hide($("#expenses-empty"));
  for (const x of rows) {
    const payerEmail = state.members.find(m => m.user_id === x.paid_by)?.email || `#${x.paid_by}`;
    const splitText = x.splits
      .map(s => `${state.members.find(m => m.user_id === s.user_id)?.email || "#" + s.user_id}: ${money(s.amount)}`)
      .join(" · ");
    const li = document.createElement("li");
    li.className = "expense-row";
    li.innerHTML = `
      <h4></h4>
      <span class="amount"></span>
      <span class="details"></span>
    `;
    li.querySelector("h4").textContent = x.description;
    li.querySelector(".amount").textContent = money(x.amount);
    li.querySelector(".details").innerHTML = `Paid by <strong></strong> · <code></code>`;
    li.querySelector(".details strong").textContent = payerEmail;
    li.querySelector(".details code").textContent = splitText;
    ol.appendChild(li);
  }
}

async function loadBalances() {
  const rows = await api(`/groups/${state.groupId}/balances`);
  state.balances = rows;
  const tbody = $("#balances-body");
  tbody.innerHTML = "";
  for (const b of rows) {
    const tr = document.createElement("tr");
    const cls = b.balance > 0 ? "pos" : b.balance < 0 ? "neg" : "zero";
    tr.innerHTML = `
      <td class="who"></td>
      <td class="num ${cls}"></td>
    `;
    tr.querySelector(".who").textContent = b.email;
    tr.querySelector(".num").textContent = money(b.balance);
    tbody.appendChild(tr);
  }
}

async function loadSuggestions() {
  const rows = await api(`/groups/${state.groupId}/settlements/suggested`);
  state.suggestions = rows;
  const ul = $("#suggestions-list");
  ul.innerHTML = "";
  if (!rows.length) {
    show($("#suggestions-empty"));
    return;
  }
  hide($("#suggestions-empty"));
  for (const s of rows) {
    const from = state.members.find(m => m.user_id === s.from)?.email || `#${s.from}`;
    const to   = state.members.find(m => m.user_id === s.to)?.email   || `#${s.to}`;
    const li = document.createElement("li");
    li.className = "suggestion";
    li.innerHTML = `
      <span class="who"></span>
      <span class="arrow">→</span>
      <span class="to"></span>
      <span class="amt"></span>
    `;
    li.querySelector(".who").textContent = from;
    li.querySelector(".to").textContent = to;
    li.querySelector(".amt").textContent = money(s.amount);
    ul.appendChild(li);
  }
}

$("#form-settle").addEventListener("submit", async (e) => {
  e.preventDefault();
  const data = new FormData(e.target);
  const payeeId = Number(data.get("payee_id"));
  const amount = Number(data.get("amount"));
  if (!payeeId || !amount || amount <= 0) {
    toast("Enter a valid amount.", "err");
    return;
  }
  const btn = e.target.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    await api(`/groups/${state.groupId}/settlements`, {
      method: "POST",
      body: { payee_id: payeeId, amount },
    });
    toast("Payment recorded.");
    e.target.reset();
    await loadSuggestions();
    await loadBalances();
  } catch (ex) {
    toast(ex.message, "err");
  } finally {
    btn.disabled = false;
  }
});

const dlgExpense = $("#dlg-expense");
$("#btn-add-expense").addEventListener("click", () => openExpenseDialog());
$$("[data-close]", dlgExpense).forEach(b => b.addEventListener("click", () => dlgExpense.close()));

function openExpenseDialog() {
  const form = $("#form-expense");
  form.reset();
  setError($("#expense-error"), null);
  $("#expense-payer").textContent = state.email;

  const list = $("#split-list");
  list.innerHTML = "";
  for (const m of state.members) {
    const li = document.createElement("li");
    li.className = "split-row";
    li.innerHTML = `
      <label>
        <input type="checkbox" name="inc-${m.user_id}" checked>
        <span class="split-email"></span>
      </label>
      <input type="number" min="0" step="1" name="amt-${m.user_id}" value="0">
    `;
    li.querySelector(".split-email").textContent = m.email;
    list.appendChild(li);
  }
  updateSplitSum();
  dlgExpense.showModal();
  form.querySelector("input[name=amount]").focus();
}

function updateSplitSum() {
  const form = $("#form-expense");
  const total = Number(form.querySelector("input[name=amount]").value) || 0;
  let sum = 0;
  for (const m of state.members) {
    const chk = form.querySelector(`input[name="inc-${m.user_id}"]`);
    const amt = form.querySelector(`input[name="amt-${m.user_id}"]`);
    amt.disabled = !chk.checked;
    if (chk.checked) sum += Number(amt.value) || 0;
  }
  const el = $("#split-sum");
  el.textContent = `${sum.toLocaleString("id-ID")} / ${total.toLocaleString("id-ID")}`;
  el.classList.toggle("is-match", sum === total && total > 0);
  el.classList.toggle("is-mismatch", sum !== total || total <= 0);
}

$("#form-expense").addEventListener("input", (e) => {
  if (e.target.matches("input[type=number], input[type=checkbox]")) updateSplitSum();
});

$("#btn-split-even").addEventListener("click", () => {
  const form = $("#form-expense");
  const total = Number(form.querySelector("input[name=amount]").value) || 0;
  const included = state.members.filter(m => form.querySelector(`input[name="inc-${m.user_id}"]`).checked);
  if (!included.length || !total) return;
  const base = Math.floor(total / included.length);
  const rem = total - base * included.length;
  included.forEach((m, i) => {
    const amt = form.querySelector(`input[name="amt-${m.user_id}"]`);
    amt.value = String(base + (i < rem ? 1 : 0));
  });
  for (const m of state.members) {
    if (!included.includes(m)) {
      form.querySelector(`input[name="amt-${m.user_id}"]`).value = "0";
    }
  }
  updateSplitSum();
});

$("#form-expense").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const err = $("#expense-error");
  setError(err, null);

  const description = String(form.querySelector("input[name=description]").value || "").trim();
  const amount = Number(form.querySelector("input[name=amount]").value);
  if (!description) { setError(err, "Description is required."); return; }
  if (!amount || amount <= 0) { setError(err, "Amount must be greater than 0."); return; }

  const me = state.members.find(m => m.email === state.email);
  if (!me) { setError(err, "Your membership could not be resolved."); return; }

  const splits = [];
  for (const m of state.members) {
    const chk = form.querySelector(`input[name="inc-${m.user_id}"]`);
    const amt = Number(form.querySelector(`input[name="amt-${m.user_id}"]`).value);
    if (!chk.checked) continue;
    if (!amt || amt <= 0) continue;
    splits.push({ user_id: m.user_id, amount: amt });
  }
  if (!splits.length) { setError(err, "Include at least one member in the split."); return; }

  const sum = splits.reduce((a, s) => a + s.amount, 0);
  if (sum !== amount) {
    setError(err, `Split total (${money(sum)}) must equal the expense amount (${money(amount)}).`);
    return;
  }

  const payload = {
    description,
    amount,
    paid_by: me.user_id,
    splits,
  };

  const btn = form.querySelector("button[type=submit]");
  btn.disabled = true;
  try {
    await api(`/groups/${state.groupId}/expenses`, { method: "POST", body: payload });
    dlgExpense.close();
    toast("Expense saved.");
    await loadExpenses();
  } catch (ex) {
    setError(err, ex.message);
  } finally {
    btn.disabled = false;
  }
});

(function boot() {
  if (state.token && state.email) {
    showView("dashboard");
  } else {
    showView("auth");
  }
})();