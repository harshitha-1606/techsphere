"use strict";
/* TECH SPHERE certificate portal - frontend (no build step). All dynamic text is inserted with
   textContent, never innerHTML, so spreadsheet content cannot inject markup. */
const BASE = (window.TS_API_BASE || "").replace(/\/$/, "");
const COLLEGE = "Audisankara College of Engineering and Technology, Gudur";
const EVENT = "TECH SPHERE POSTER PRESENTATION";
const DATE_LONG = "13 October 2026";
const $app = document.getElementById("app");

/* ---------- helpers ---------- */
function el(tag, props, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else if (k === "text") n.textContent = v;
    else if (v === true) n.setAttribute(k, "");
    else n.setAttribute(k, v);
  }
  for (const kid of kids.flat(Infinity)) if (kid != null && kid !== false) n.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  return n;
}

async function api(path, opts = {}) {
  const init = { credentials: "include", method: opts.method || "GET", headers: {} };
  if (opts.json) { init.body = JSON.stringify(opts.json); init.headers["Content-Type"] = "application/json"; if (!opts.method) init.method = "POST"; }
  if (opts.form) { init.body = opts.form; init.method = "POST"; }
  let res;
  try { res = await fetch(BASE + path, init); }
  catch { throw new ApiError("Cannot reach the server. Check your connection and try again.", 0); }
  if (opts.raw) return res;
  let data = null;
  try { data = await res.json(); } catch { /* non-JSON */ }
  if (!res.ok) throw new ApiError((data && data.error) || `Request failed (${res.status}).`, res.status);
  return data;
}
class ApiError extends Error { constructor(m, status) { super(m); this.status = status; } }

function toast(msg, type = "") {
  const t = el("div", { class: "toast " + type, role: type === "err" ? "alert" : "status", text: msg });
  document.getElementById("toasts").append(t);
  setTimeout(() => t.remove(), type === "err" ? 7000 : 4500);
}

function dialog(contentFn) {
  const d = document.getElementById("dlg");
  d.replaceChildren();
  return new Promise((resolve) => {
    const close = (v) => { d.close(); resolve(v); };
    d.onclose = () => resolve(undefined);
    d.append(el("div", { class: "dlg-in" }, contentFn(close)));
    d.showModal();
  });
}
const confirmBox = (title, text, okLabel = "Confirm", danger = false) =>
  dialog((close) => [
    el("h3", { text: title }), el("p", { text }),
    el("div", { class: "dlg-actions" },
      el("button", { class: "btn ghost", onclick: () => close(false), text: "Cancel" }),
      el("button", { class: "btn" + (danger ? " danger" : ""), onclick: () => close(true), text: okLabel }))
  ]).then(Boolean);

function filenameFrom(res, fallback) {
  const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(res.headers.get("Content-Disposition") || "");
  return m ? decodeURIComponent(m[1]) : fallback;
}
function saveBlob(blob, name) {
  const url = URL.createObjectURL(blob);
  const a = el("a", { href: url, download: name });
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
async function downloadFile(path, fallbackName, onProgress) {
  const res = await api(path, { raw: true });
  if (!res.ok) { let m = `Download failed (${res.status}).`; try { m = (await res.json()).error || m; } catch {} throw new ApiError(m, res.status); }
  const total = +res.headers.get("Content-Length") || 0;
  const reader = res.body.getReader(); const chunks = []; let got = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value); got += value.length;
    if (onProgress) onProgress(total ? got / total : null);
  }
  saveBlob(new Blob(chunks, { type: res.headers.get("Content-Type") || "application/octet-stream" }), filenameFrom(res, fallbackName));
}
function busy(btn, label, fn) {
  return async (...a) => {
    const old = btn.textContent; btn.disabled = true; btn.replaceChildren(el("span", { class: "spinner" }), " " + label);
    try { return await fn(...a); } finally { btn.disabled = false; btn.textContent = old; }
  };
}

/* ---------- layout ---------- */
function header(actions) {
  return el("header", { class: "site-header" }, el("div", { class: "in" },
    el("a", { class: "brand", href: "#/", "aria-label": "Home" },
      el("img", { src: "/assets/logo.jpg", alt: "Audisankara logo" }),
      el("span", {}, el("span", { class: "college", text: "Audisankara College of Engineering and Technology, Gudur" }),
        el("span", { class: "ev", text: "TECH SPHERE POSTER PRESENTATION 2026" }))),
    actions ? el("div", { class: "head-actions" }, actions) : null));
}
const footer = () => el("footer", { class: "site-footer" },
  el("div", {}, el("b", { text: COLLEGE })), el("div", { text: `${EVENT} 2026 · ${DATE_LONG}` }));
function page(headerActions, ...body) {
  $app.replaceChildren(header(headerActions), el("main", { id: "main" }, body), footer());
  document.title = `${EVENT} 2026 | ${COLLEGE}`;
  window.scrollTo(0, 0);
}

/* ---------- home ---------- */
function home() {
  const card = (ico, title, text, href, label) => el("div", { class: "login-card" },
    el("div", { class: "ico", "aria-hidden": "true", text: ico }), el("h2", { text: title }), el("p", { text }),
    el("a", { class: "btn lg", href, text: label }));
  $app.replaceChildren(
    header(),
    el("section", { class: "hero", id: "main" },
      el("div", { class: "logo-tile" }, el("img", { src: "/assets/logo.jpg", alt: "Audisankara logo" })),
      el("div", { class: "college", text: COLLEGE }),
      el("h1", { text: EVENT }),
      el("div", { class: "date", text: DATE_LONG }),
      el("p", { text: "Welcome to TECH SPHERE 2026 — Celebrating creativity, innovation, and student research." })),
    el("div", { class: "cards" },
      card("🛠", "COORDINATOR LOGIN", "Manage participant data and generate certificates.", "#/coordinator/login", "Coordinator Login"),
      card("🎓", "PARTICIPANT LOGIN", "Access, view, and download your participation certificate.", "#/participant/login", "Participant Login")),
    footer());
}

/* ---------- login ---------- */
function loginPage(kind) {
  const coord = kind === "coordinator";
  const err = el("div", { class: "alert err", role: "alert", hidden: true });
  const u = el("input", { id: "u", type: coord ? "text" : "email", autocomplete: "username", required: true, autocapitalize: "none", spellcheck: "false" });
  const p = el("input", { id: "p", type: "password", autocomplete: coord ? "current-password" : "off", required: true });
  const btn = el("button", { class: "btn lg", type: "submit", text: "Sign in" });
  const form = el("form", { novalidate: true },
    err,
    el("div", { class: "field" }, el("label", { for: "u", text: coord ? "Username" : "Email ID (username)" }), u),
    el("div", { class: "field" }, el("label", { for: "p", text: coord ? "Password" : "Password" }), p),
    coord ? null : el("p", { class: "muted", text: "For this event, your password is the same registered Email ID." }),
    btn);
  form.addEventListener("submit", async (e) => {
    e.preventDefault(); err.hidden = true;
    if (!u.value.trim() || !p.value) { err.textContent = "Please enter both fields."; err.hidden = false; return; }
    btn.disabled = true; btn.replaceChildren(el("span", { class: "spinner" }), " Signing in…");
    try {
      await api(`/api/${kind}/login`, { json: { username: u.value, password: p.value } });
      location.hash = coord ? "#/coordinator" : "#/participant";
    } catch (ex) { err.textContent = ex.message; err.hidden = false; btn.disabled = false; btn.textContent = "Sign in"; p.value = ""; p.focus(); }
  });
  page(el("a", { class: "btn ghost-light sm", href: "#/", text: "← Home" }),
    el("div", { class: "login-wrap panel" },
      el("h1", { text: coord ? "Coordinator Login" : "Participant Login", class: "" }), 
      el("p", { class: "muted", text: coord ? "Manage participant data and generate certificates." : "Access, view, and download your participation certificate." }),
      form));
  u.focus();
}

/* ---------- coordinator dashboard ---------- */
async function coordinatorDashboard() {
  try { await api("/api/coordinator/me"); } catch { location.hash = "#/coordinator/login"; return; }
  let people = [];
  const stats = el("div", { class: "stats" });
  const uploadBox = el("div", { class: "section" });
  const previewBox = el("div", { class: "section" });
  const genBox = el("div", { class: "section" });
  const tableBox = el("div", { class: "section" });

  const logout = el("button", { class: "btn ghost-light sm", text: "Logout" });
  logout.onclick = async () => {
    if (!(await confirmBox("Log out?", "You will need to sign in again to manage certificates.", "Log out"))) return;
    await api("/api/coordinator/logout", { json: {} }).catch(() => {});
    location.hash = "#/";
  };
  page(logout,
    el("div", { class: "dash-top" }, el("div", {},
      el("h1", { text: "Coordinator Dashboard" }),
      el("div", { class: "muted", text: `${EVENT} · ${DATE_LONG}` }))),
    stats, uploadBox, previewBox, genBox, tableBox);

  const stat = (n, l, cls = "") => el("div", { class: "stat " + cls }, el("div", { class: "n", text: String(n) }), el("div", { class: "l", text: l }));
  async function refresh() {
    const [s, list] = await Promise.all([api("/api/coordinator/summary"), api("/api/coordinator/participants")]);
    people = list;
    stats.replaceChildren(
      stat(s.total_participants, "Total participants uploaded"),
      stat(s.generated, "Successful certificate generations", "ok"),
      stat(s.available, "Certificates available for download", "gold"),
      stat(s.invalid_rows, "Rows with missing/invalid data (last upload)", "bad"));
    renderGen(s); renderTable();
  }

  /* upload */
  const file = el("input", { type: "file", accept: ".xlsx,.xls", hidden: true, id: "file" });
  const drop = el("div", { class: "drop", tabindex: "0", role: "button", "aria-label": "Upload participant Excel file" },
    el("div", { class: "big", "aria-hidden": "true", text: "📄" }),
    el("h3", { text: "Upload participant Excel file" }),
    el("p", { class: "muted", text: "Drag and drop a .xlsx or .xls file here, or" }),
    el("button", { class: "btn", type: "button", onclick: () => file.click(), text: "Browse File" }),
    el("p", { class: "muted", text: "Required columns: Student Name, Department, Email ID. Other columns are optional and detected by header name." }),
    el("p", {}, el("a", { href: "/assets/participants_template.xlsx", download: "participants_template.xlsx", text: "Download sample template" })));
  ["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", (e) => e.dataTransfer.files[0] && handleFile(e.dataTransfer.files[0]));
  drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); file.click(); } });
  file.addEventListener("change", () => { if (file.files[0]) handleFile(file.files[0]); file.value = ""; });
  uploadBox.append(el("h2", { text: "1. Upload participants" }), drop, file);

  async function handleFile(f) {
    previewBox.replaceChildren(el("div", { class: "alert info" }, el("span", { class: "spinner dark" }), " Reading and validating " + f.name + "…"));
    const fd = new FormData(); fd.append("file", f);
    try { renderPreview(await api("/api/coordinator/upload", { form: fd })); }
    catch (ex) { previewBox.replaceChildren(el("div", { class: "alert err", role: "alert", text: ex.message })); }
  }

  function renderPreview(r) {
    const invalidOnly = el("input", { type: "checkbox", id: "inv" });
    const body = el("tbody");
    const MAX_VALID = 200;
    const draw = () => {
      body.replaceChildren();
      let shownValid = 0, hiddenValid = 0;
      for (const row of r.rows) {
        if (invalidOnly.checked && row.valid) continue;
        if (row.valid && ++shownValid > MAX_VALID) { hiddenValid++; continue; }
        const d = row.data;
        body.append(el("tr", { class: row.valid ? "" : "invalid" },
          el("td", { text: row.row }),
          el("td", {}, el("span", { class: "badge " + (row.valid ? "valid" : "invalid"), text: row.valid ? "Valid" : "Invalid" })),
          el("td", { text: d.name }), el("td", { text: d.department }), el("td", { text: d.email }),
          el("td", { text: d.roll_no }), el("td", { text: d.team }),
          el("td", { text: [...row.errors, ...row.warnings.map((w) => "Note: " + w)].join("; ") })));
      }
      if (hiddenValid) body.append(el("tr", {}, el("td", { colspan: 8, class: "muted", text: `…and ${hiddenValid} more valid rows (all will be imported). Tick "Show invalid only" to review problems.` })));
    };
    invalidOnly.addEventListener("change", draw); draw();
    const missingOpt = Object.entries(r.columns_detected).filter(([, ok]) => !ok).map(([k]) => k);
    const confirm = el("button", { class: "btn", text: `Confirm import (${r.valid} valid)`, disabled: r.valid === 0 });
    confirm.onclick = async () => {
      const ok = await confirmBox("Import participants?", `${r.valid} valid record(s) will be imported or updated. ${r.invalid} invalid row(s) will NOT be imported — they stay listed above for you to fix in the spreadsheet.`, "Import");
      if (!ok) return;
      await busy(confirm, "Importing…", async () => {
        try {
          const res = await api("/api/coordinator/import", { json: { token: r.token } });
          previewBox.replaceChildren(el("div", { class: "alert ok", role: "status", text: `Import complete: ${res.inserted} new, ${res.updated} updated, ${res.unchanged} unchanged. ${res.invalid_skipped} invalid row(s) skipped.` }));
          toast("Participants imported.", "ok"); await refresh();
        } catch (ex) { toast(ex.message, "err"); }
      })();
    };
    const cancel = el("button", { class: "btn ghost", text: "Cancel import" });
    cancel.onclick = async () => { await api(`/api/coordinator/staging/${r.token}`, { method: "DELETE" }).catch(() => {}); previewBox.replaceChildren(); toast("Import cancelled."); };
    previewBox.replaceChildren(
      el("h2", { text: "2. Preview & validation" }),
      el("div", { class: "pills" },
        el("span", { class: "pill", text: `File: ${r.filename}` }),
        el("span", { class: "pill", text: `Total rows: ${r.total}` }),
        el("span", { class: "pill ok", text: `Valid: ${r.valid}` }),
        el("span", { class: "pill bad", text: `Invalid: ${r.invalid}` }),
        r.blank_rows_skipped ? el("span", { class: "pill", text: `Blank rows ignored: ${r.blank_rows_skipped}` }) : null,
        missingOpt.length ? el("span", { class: "pill", text: `Optional columns not found: ${missingOpt.join(", ")}` }) : null),
      el("div", { class: "toolbar" }, el("label", { for: "inv" }, invalidOnly, " Show invalid only")),
      el("div", { class: "table-wrap" }, el("table", {},
        el("thead", {}, el("tr", {}, ["Row", "Status", "Student Name", "Department", "Email ID", "Roll No.", "Team", "Issues"].map((h) => el("th", { text: h })))), body)),
      el("div", { class: "btn-row", }, confirm, cancel));
  }

  /* generation */
  const genBtn = el("button", { class: "btn gold lg", text: "GENERATE ALL CERTIFICATES" });
  const retryBtn = el("button", { class: "btn ghost", text: "Retry failed" });
  const zipBtn = el("button", { class: "btn lg", text: "DOWNLOAD ALL CERTIFICATES (ZIP)" });
  const genStatus = el("div", { "aria-live": "polite" });
  const bar = el("i"); const barWrap = el("div", { class: "progress", hidden: true, role: "progressbar" }, bar);
  genBox.append(el("h2", { text: "3. Certificates" }), el("div", { class: "btn-row" }, genBtn, retryBtn, zipBtn), barWrap, genStatus);

  function renderGen(s) {
    genBtn.disabled = s.total_participants === 0 || polling;
    retryBtn.hidden = !s.failed; retryBtn.disabled = polling;
    zipBtn.disabled = s.generated === 0;
    if (!polling && s.total_participants === 0) genStatus.replaceChildren(el("p", { class: "muted", text: "Import participants to enable certificate generation." }));
  }
  let polling = false;
  async function runGeneration(onlyFailed) {
    polling = true; genBtn.disabled = retryBtn.disabled = true;
    barWrap.hidden = false; bar.style.width = "0%";
    try { await api("/api/coordinator/generate", { json: { only_failed: onlyFailed } }); }
    catch (ex) { polling = false; barWrap.hidden = true; toast(ex.message, "err"); return refresh(); }
    for (;;) {
      await new Promise((r) => setTimeout(r, 500));
      let j; try { j = await api("/api/coordinator/generate/status"); } catch (ex) { toast(ex.message, "err"); break; }
      const pct = j.total ? Math.round((j.done / j.total) * 100) : 0;
      bar.style.width = pct + "%"; barWrap.setAttribute("aria-valuenow", pct);
      genStatus.replaceChildren(el("p", { text: `Generating… ${j.done} of ${j.total}` }));
      if (j.state === "done") {
        polling = false;
        genStatus.replaceChildren(el("div", { class: "alert " + (j.failed ? "err" : "ok"), role: "status",
          text: `Finished: ${j.success} generated, ${j.skipped} already up to date, ${j.failed} failed.${j.failed ? " Use “Retry failed”." : ""}` }));
        toast(j.failed ? `${j.failed} certificate(s) failed.` : "All certificates are ready.", j.failed ? "err" : "ok");
        break;
      }
    }
    polling = false; barWrap.hidden = true; await refresh();
  }
  genBtn.onclick = async () => { if (await confirmBox("Generate certificates?", "Certificates will be created for every imported participant. Up-to-date certificates are not duplicated.", "Generate")) runGeneration(false); };
  retryBtn.onclick = () => runGeneration(true);
  zipBtn.onclick = async () => {
    zipBtn.disabled = true; barWrap.hidden = false; bar.style.width = "0%";
    genStatus.replaceChildren(el("p", { text: "Preparing ZIP file…" }));
    try {
      await downloadFile("/api/coordinator/certificates.zip", "TechSphere_Certificates.zip", (f) => { if (f != null) bar.style.width = Math.round(f * 100) + "%"; });
      genStatus.replaceChildren(el("div", { class: "alert ok", role: "status", text: "ZIP downloaded." }));
    } catch (ex) { genStatus.replaceChildren(el("div", { class: "alert err", role: "alert", text: ex.message })); }
    barWrap.hidden = true; zipBtn.disabled = false;
  };

  /* participants table */
  const search = el("input", { type: "search", placeholder: "Search name, department or email…", "aria-label": "Search participants" });
  const tbody = el("tbody");
  function renderTable() {
    const q = search.value.trim().toLowerCase();
    tbody.replaceChildren();
    const list = people.filter((p) => !q || [p.name, p.department, p.email].some((v) => (v || "").toLowerCase().includes(q)));
    if (!list.length) tbody.append(el("tr", {}, el("td", { colspan: 7, class: "empty", text: people.length ? "No participants match your search." : "No participants yet. Upload an Excel file to get started." })));
    for (const p of list) {
      const ok = p.status === "generated";
      const prev = el("button", { class: "btn ghost sm", text: "Preview", disabled: !ok });
      prev.onclick = () => dialog((close) => [
        el("h3", { text: `${p.name} — ${p.certificate_id}` }),
        el("img", { class: "full", src: `${BASE}/api/coordinator/certificates/${p.certificate_id}/preview.jpg`, alt: `Certificate preview for ${p.name}` }),
        el("div", { class: "dlg-actions" }, el("button", { class: "btn", onclick: () => close(), text: "Close" }))]);
      const dl = el("button", { class: "btn sm", text: "Download PDF", disabled: !ok });
      dl.onclick = busy(dl, "…", async () => { try { await downloadFile(`/api/coordinator/certificates/${p.certificate_id}/pdf`, "certificate.pdf"); } catch (ex) { toast(ex.message, "err"); } });
      tbody.append(el("tr", {},
        el("td", { text: p.name }), el("td", { text: p.department }), el("td", { text: p.email }),
        el("td", { text: p.certificate_id || "—" }),
        el("td", {}, el("span", { class: "badge " + p.status, text: p.status === "generated" ? "Generated" : p.status === "failed" ? "Failed" : "Pending" }),
          p.error ? el("div", { class: "muted", text: p.error }) : null),
        el("td", {}, prev), el("td", {}, dl)));
    }
  }
  search.addEventListener("input", renderTable);
  tableBox.append(el("h2", { text: "4. Generated certificates" }),
    el("div", { class: "toolbar" }, el("div", { class: "grow" }, search)),
    el("div", { class: "table-wrap" }, el("table", {},
      el("thead", {}, el("tr", {}, ["Student Name", "Department", "Email ID", "Certificate ID", "Generation Status", "Preview", "Download PDF"].map((h) => el("th", { text: h })))), tbody)));

  try { await refresh(); } catch (ex) { toast(ex.message, "err"); }
}

/* ---------- participant ---------- */
async function participantDashboard() {
  let me;
  try { me = await api("/api/participant/me"); } catch { location.hash = "#/participant/login"; return; }
  const logout = el("button", { class: "btn ghost-light sm", text: "Logout" });
  logout.onclick = async () => { await api("/api/participant/logout", { json: {} }).catch(() => {}); location.hash = "#/"; };
  let certPart;
  if (me.ready) {
    const dl = el("button", { class: "btn lg", text: "DOWNLOAD CERTIFICATE" });
    dl.onclick = busy(dl, "Downloading…", async () => { try { await downloadFile("/api/participant/certificate.pdf", "certificate.pdf"); toast("Certificate downloaded.", "ok"); } catch (ex) { toast(ex.message, "err"); } });
    certPart = [
      el("p", { class: "ready", text: "YOUR PARTICIPATION CERTIFICATE IS READY" }),
      el("div", { class: "panel cert-card" },
        el("img", { class: "thumb", src: `${BASE}/api/participant/certificate/preview.jpg`, alt: "Preview of your certificate" }),
        el("div", {},
          el("dl", { class: "kv" },
            el("dt", { text: "Student name" }), el("dd", { text: me.name }),
            el("dt", { text: "Department" }), el("dd", { text: me.department }),
            el("dt", { text: "Event" }), el("dd", { text: EVENT }),
            el("dt", { text: "Event date" }), el("dd", { text: DATE_LONG }),
            el("dt", { text: "Certificate ID" }), el("dd", { text: me.certificate_id })),
          el("div", { class: "btn-row" },
            el("a", { class: "btn gold lg", href: "#/participant/certificate", text: "VIEW CERTIFICATE" }), dl)))];
  } else {
    certPart = [el("div", { class: "panel empty" }, el("h3", { text: "Your certificate is being prepared." }), el("p", { text: "Please check again later." }),
      el("button", { class: "btn ghost", onclick: () => participantDashboard(), text: "Check again" }))];
  }
  page(logout,
    el("section", { class: "welcome" },
      el("h1", { text: `Congratulations, ${me.name}!` }),
      el("p", { text: "Thank you for being part of TECH SPHERE POSTER PRESENTATION 2026. Your enthusiasm, creativity, and participation made this event special." })),
    certPart,
    el("section", { class: "thanks" }, el("h3", { text: "Thank you for participating in TECH SPHERE 2026!" }),
      el("p", { class: "muted", text: "We appreciate your enthusiasm and wish you success in your future innovations." })));
}

async function certificateViewer() {
  let me;
  try { me = await api("/api/participant/me"); } catch { location.hash = "#/participant/login"; return; }
  if (!me.ready) { location.hash = "#/participant"; return; }
  let zoom = 100;
  const img = el("img", { src: `${BASE}/api/participant/certificate/preview.jpg`, alt: `Certificate of ${me.name}` });
  const apply = () => { img.style.width = zoom + "%"; zl.textContent = zoom + "%"; };
  const zl = el("span", { class: "pill", text: "100%" });
  const dl = el("button", { class: "btn", text: "Download PDF" });
  dl.onclick = busy(dl, "Downloading…", async () => { try { await downloadFile("/api/participant/certificate.pdf", "certificate.pdf"); } catch (ex) { toast(ex.message, "err"); } });
  page(el("a", { class: "btn ghost-light sm", href: "#/participant", text: "← Back" }),
    el("h1", { text: "Your Certificate" }),
    el("div", { class: "toolbar" },
      el("button", { class: "btn ghost sm", "aria-label": "Zoom out", onclick: () => { zoom = Math.max(50, zoom - 25); apply(); }, text: "−" }), zl,
      el("button", { class: "btn ghost sm", "aria-label": "Zoom in", onclick: () => { zoom = Math.min(300, zoom + 25); apply(); }, text: "+" }),
      el("button", { class: "btn ghost sm", onclick: () => { zoom = 100; apply(); }, text: "Fit" }),
      el("a", { class: "btn ghost sm", href: `${BASE}/api/participant/certificate.pdf?inline=1`, target: "_blank", rel: "noopener", text: "Open PDF" }), dl,
      el("a", { class: "btn sm", href: "#/participant", text: "Return to dashboard" })),
    el("div", { class: "viewer" }, img));
  apply();
}

/* ---------- router ---------- */
const routes = {
  "": home, "/": home,
  "/coordinator/login": () => loginPage("coordinator"), "/coordinator": coordinatorDashboard,
  "/participant/login": () => loginPage("participant"), "/participant": participantDashboard,
  "/participant/certificate": certificateViewer,
};
function route() {
  document.getElementById("dlg").open && document.getElementById("dlg").close();
  document.getElementById("toasts").replaceChildren();
  const path = location.hash.replace(/^#/, "");
  (routes[path] || home)();
}
window.addEventListener("hashchange", route);
route();
