/* Job Hunt Assistant – browser app. Everything runs locally; nothing is uploaded. */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
  };
  const CATEGORIES = ["Data analyst", "Data engineer", "AI / ML engineer", "Software engineer", "Trust and safety", "Business / operations analyst", "Other"];
  const DEFAULT_CATS = CATEGORIES.filter(c => c !== "Other");
  const STATUS = ["Not applied", "Shortlisted", "Applied", "Skipped"];
  const RESULTS = ["", "Pending", "Online assessment", "Interview", "Offer", "Rejected", "No response"];
  const TRUST_CLASS = { "Verified employer": "t-verified", "Official job board": "t-official", "Unverified": "t-unverified", "Caution": "t-caution" };
  const PAGE = 40;

  let jobs = [], skillRx = {}, cv = store.get("jh.cv", null), tracked = store.get("jh.tracked", {}), shown = PAGE, ranked = [];

  /* ---------- text and scoring (mirrors jobhunt/match.py) ---------- */
  const STOP = new Set("a about above after again against all am an and any are as at be because been before being below between both but by can could did do does doing down during each few for from further had has have having he her here hers herself him himself his how i if in into is it its itself just me more most my myself no nor not now of off on once only or other our ours ourselves out over own same she should so some such than that the their theirs them themselves then there these they this those through to too under until up very was we were what when where which while who whom why will with you your yours yourself yourselves also within across using use role work team you'll we're including etc".split(" "));
  function tokens(text) {
    const words = (text.toLowerCase().match(/[a-z0-9+#][a-z0-9+#.-]*[a-z0-9+#]|[a-z0-9]/g) || []).filter(w => !STOP.has(w) && w.length > 1);
    const out = words.slice();
    for (let i = 0; i < words.length - 1; i++) out.push(words[i] + " " + words[i + 1]);
    return out;
  }
  function findSkills(text) {
    return Object.keys(skillRx).filter(name => skillRx[name].test(text || ""));
  }
  function tfidf(docs) {
    const df = new Map(), tfs = docs.map(d => { const m = new Map(); for (const t of tokens(d)) m.set(t, (m.get(t) || 0) + 1); return m; });
    tfs.forEach(m => m.forEach((_, t) => df.set(t, (df.get(t) || 0) + 1)));
    const n = docs.length;
    return tfs.map(m => {
      const v = new Map(); let norm = 0;
      m.forEach((c, t) => { const d = df.get(t); if (d / n > 0.9 && n > 3) return; const w = (1 + Math.log(c)) * (Math.log((1 + n) / (1 + d)) + 1); v.set(t, w); norm += w * w; });
      norm = Math.sqrt(norm) || 1; v.forEach((w, t) => v.set(t, w / norm)); return v;
    });
  }
  const cosine = (a, b) => { let s = 0; const [x, y] = a.size < b.size ? [a, b] : [b, a]; x.forEach((w, t) => { const o = y.get(t); if (o) s += w * o; }); return s; };

  function prefs() {
    return {
      cats: $$("#f-cats input:checked").map(i => i.value),
      entry: $("#f-entry").checked, notStated: $("#f-notstated").checked, intern: $("#f-intern").checked,
      years: +$("#f-years").value,
      trust: { "Verified employer": $("#f-verified").checked, "Official job board": $("#f-official").checked, "Unverified": $("#f-unverified").checked, "Caution": $("#f-caution").checked },
      langs: $("#f-langs").value.split(/[,;]/).map(s => s.trim().toLowerCase()).filter(Boolean),
      q: $("#f-q").value.trim().toLowerCase(), sort: $("#f-sort").value,
    };
  }
  function passes(j, p) {
    if (!p.cats.includes(j.category || "Other")) return false;
    const lvl = j.level;
    if (lvl === "Senior" || lvl === "Mid / senior") return false;
    if (lvl === "Graduate / entry" && !p.entry) return false;
    if (lvl === "Not stated" && !p.notStated) return false;
    if (lvl === "Internship" && !p.intern) return false;
    if (j.years != null && j.years > p.years) return false;
    if (j.language && !p.langs.includes(j.language.toLowerCase())) return false;
    if (!p.trust[j.trust || "Unverified"]) return false;
    if (p.q && !`${j.title} ${j.company} ${j.location} ${j.description}`.toLowerCase().includes(p.q)) return false;
    return true;
  }
  function rank() {
    const p = prefs();
    const list = jobs.filter(j => passes(j, p));
    if (cv && list.length) {
      const vecs = tfidf(list.map(j => `${j.title} ${j.title} ${j.description}`).concat([cv.text]));
      const mine = vecs[vecs.length - 1];
      const sims = list.map((_, i) => cosine(mine, vecs[i]));
      const top = Math.max(...sims, 1e-9);
      list.forEach((j, i) => {
        const wanted = j.skills || [];
        j._have = wanted.filter(s => cv.skills.includes(s));
        j._miss = wanted.filter(s => !cv.skills.includes(s));
        const coverage = wanted.length ? j._have.length / wanted.length : 0.5;
        const text = Math.min(sims[i] / top, 1) * 0.6 + Math.min(sims[i] / 0.25, 1) * 0.4;
        const level = { "Graduate / entry": 1, "Not stated": 0.6, "Internship": 0.5 }[j.level] ?? 0;
        j._score = Math.round(100 * (0.45 * text + 0.30 * coverage + 0.15 + 0.10 * level));
      });
    } else list.forEach(j => { j._score = null; j._have = []; j._miss = j.skills || []; });
    list.sort(p.sort === "date" || !cv ? (a, b) => (b.posted || "").localeCompare(a.posted || "") : (a, b) => b._score - a._score);
    ranked = list;
    shown = PAGE;
    renderJobs();
  }

  /* ---------- job list ---------- */
  function trustBadge(t) { return `<span class="trust ${TRUST_CLASS[t] || "t-unverified"}">${esc(t || "Unverified")}</span>`; }
  function renderJobs() {
    const box = $("#jobs");
    $("#result-count").textContent = `${ranked.length} job${ranked.length === 1 ? "" : "s"} match your filters` + (cv ? ", ranked by fit to your CV." : ". Upload your CV to rank them.");
    box.innerHTML = ranked.slice(0, shown).map(j => {
      const t = tracked[j.id];
      return `<article class="job" data-id="${esc(j.id)}">
        <div class="job-top">
          <div class="score ${j._score == null ? "na" : ""}" title="Match score out of 100">${j._score == null ? "—" : j._score}</div>
          <div>
            <h3>${esc(j.title)}</h3>
            <div class="sub">${esc(j.company)} · ${esc(j.location || "Location not stated")}${j.posted ? " · posted " + esc(j.posted) : ""}</div>
            <div class="tags">${trustBadge(j.trust)}<span class="tag">${esc(j.category)}</span><span class="tag">${esc(j.level)}</span>${j.years ? `<span class="tag">asks ${j.years}+ yrs</span>` : ""}<span class="tag">${esc(j.source)}</span></div>
          </div>
          <div class="side">
            <a class="btn primary small" href="${esc(j.apply_url || j.url)}" target="_blank" rel="noopener">Apply</a>
            <button class="btn small ${t ? "" : "ghost"}" data-act="track">${t ? "✓ " + esc(t.Status) : "Track"}</button>
            <button class="btn ghost small" data-act="more">Details</button>
          </div>
        </div>
        <div class="details"></div>
      </article>`;
    }).join("") || `<p class="empty">No jobs match. Try widening the filters.</p>`;
    $("#more").hidden = ranked.length <= shown;
  }
  function details(j) {
    const have = (j._have || []).map(s => `<span class="chip have">${esc(s)}</span>`).join("") || "<span class='meta'>None detected</span>";
    const miss = (j._miss || []).map(s => `<span class="chip miss">${esc(s)}</span>`).join("") || "<span class='meta'>None</span>";
    const tips = cv ? (j._miss || []).slice(0, 5).map(s => `<li>The advert mentions <b>${esc(s)}</b>. If you have used it, add one concrete example.</li>`).join("") : "";
    return `<div class="cols">
      <div><h4>Skills you show</h4><div class="chips">${have}</div>
        <h4 style="margin-top:10px">In the advert, not in your CV</h4><div class="chips">${miss}</div>
        ${tips ? `<h4 style="margin-top:10px">Tailoring tips</h4><ul class="evidence">${tips}</ul>` : ""}
        ${cv ? `<p><button class="btn small" data-act="cv">Download tailored CV (.docx)</button></p>` : ""}</div>
      <div><h4>Employer check</h4>${trustBadge(j.trust)}<ul class="evidence">${(j.trust_evidence || []).map(e => `<li>${esc(e)}</li>`).join("")}</ul>
        <p class="meta"><a href="${esc(j.url)}" target="_blank" rel="noopener">Open the advert on the employer's site</a></p></div>
    </div><div class="desc">${esc(j.description)}${j.description && j.description.length >= 2500 ? "…" : ""}</div>`;
  }
  $("#jobs").addEventListener("click", e => {
    const btn = e.target.closest("button[data-act]"); if (!btn) return;
    const card = btn.closest(".job"), j = jobs.find(x => x.id === card.dataset.id);
    if (btn.dataset.act === "more") {
      const d = $(".details", card); d.classList.toggle("open"); if (d.classList.contains("open")) d.innerHTML = details(j);
    } else if (btn.dataset.act === "track") {
      if (tracked[j.id]) delete tracked[j.id]; else tracked[j.id] = { Status: "Shortlisted", "Date applied": "", Result: "", Notes: "", job: slim(j) };
      saveTracked(); btn.outerHTML = tracked[j.id] ? `<button class="btn small" data-act="track">✓ Shortlisted</button>` : `<button class="btn small ghost" data-act="track">Track</button>`;
    } else if (btn.dataset.act === "cv") tailoredCv(j, btn);
  });
  $("#more").addEventListener("click", () => { shown += PAGE; renderJobs(); });
  const slim = j => ({ id: j.id, title: j.title, company: j.company, location: j.location, url: j.url, source: j.source, posted: j.posted,
    category: j.category, level: j.level, trust: j.trust, description: (j.description || "").slice(0, 700), score: j._score ?? 0,
    matched_skills: j._have || [], missing_skills: j._miss || [] });

  /* ---------- CV upload ---------- */
  async function readCv(file) {
    const name = file.name.toLowerCase();
    if (name.endsWith(".pdf")) {
      pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
      const pdf = await pdfjsLib.getDocument({ data: await file.arrayBuffer() }).promise;
      let text = "";
      for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i), content = await page.getTextContent();
        let lastY = null;
        for (const item of content.items) { if (lastY !== null && Math.abs(item.transform[5] - lastY) > 2) text += "\n"; text += item.str; lastY = item.transform[5]; }
        text += "\n";
      }
      return text;
    }
    if (name.endsWith(".docx")) return (await mammoth.extractRawText({ arrayBuffer: await file.arrayBuffer() })).value;
    return await file.text();
  }
  $("#cv-file").addEventListener("change", async e => {
    const file = e.target.files[0]; if (!file) return;
    $("#drop-title").textContent = "Reading…";
    try {
      const text = await readCv(file);
      cv = { name: file.name, text, skills: findSkills(text) };
      store.set("jh.cv", cv); showCv(); rank();
    } catch (err) { $("#drop-title").textContent = "Could not read that file"; $("#drop-sub").textContent = String(err.message || err); }
  });
  function showCv() {
    if (!cv) return;
    $("#drop").classList.add("loaded");
    $("#drop-title").textContent = cv.name;
    $("#drop-sub").textContent = `${cv.skills.length} skills found: ${cv.skills.slice(0, 8).join(", ")}${cv.skills.length > 8 ? " and more" : ""}. Click to replace.`;
  }

  /* ---------- tracker ---------- */
  function saveTracked() { store.set("jh.tracked", tracked); $("#tracked-count").textContent = Object.keys(tracked).length; }
  let charts = {};
  function renderTracker() {
    const rows = Object.entries(tracked);
    $("#tracker-empty").hidden = rows.length > 0;
    $("#tracker-table tbody").innerHTML = rows.map(([id, t]) => `<tr data-id="${esc(id)}">
      <td><a href="${esc(t.job.url)}" target="_blank" rel="noopener">${esc(t.job.title)}</a></td><td>${esc(t.job.company)}</td><td>${t.job.score || "—"}</td>
      <td>${trustBadge(t.job.trust)}</td>
      <td><select data-f="Status">${STATUS.map(s => `<option ${s === t.Status ? "selected" : ""}>${s}</option>`).join("")}</select></td>
      <td><input type="date" data-f="Date applied" value="${esc(t["Date applied"] || "")}"></td>
      <td><select data-f="Result">${RESULTS.map(s => `<option value="${s}" ${s === t.Result ? "selected" : ""}>${s || "—"}</option>`).join("")}</select></td>
      <td><input data-f="Notes" value="${esc(t.Notes || "")}"></td>
      <td><button class="btn ghost small" data-act="drop" title="Remove">✕</button></td></tr>`).join("");
    const count = (f, v) => rows.filter(([, t]) => t[f] === v).length;
    const applied = count("Status", "Applied"), responded = ["Online assessment", "Interview", "Offer", "Rejected"].reduce((s, r) => s + count("Result", r), 0);
    $("#kpis").innerHTML = [["Tracked", rows.length], ["Applied", applied], ["Interviews", count("Result", "Interview") + count("Result", "Offer")],
      ["Offers", count("Result", "Offer")], ["Response rate", applied ? Math.round(100 * responded / applied) + "%" : "—"]]
      .map(([k, v]) => `<div class="kpi"><b>${v}</b><span>${k}</span></div>`).join("");
    if (!window.Chart) return;
    const css = getComputedStyle(document.documentElement), ink = css.getPropertyValue("--muted").trim(), accent = css.getPropertyValue("--accent").trim();
    Chart.defaults.color = ink;
    const draw = (id, cfg) => { charts[id]?.destroy(); charts[id] = new Chart($(id), { ...cfg, options: { maintainAspectRatio: false, plugins: { legend: { display: cfg.type === "doughnut", position: "right" } }, ...(cfg.options || {}) } }); };
    draw("#c-status", { type: "doughnut", data: { labels: STATUS, datasets: [{ data: STATUS.map(s => count("Status", s)), backgroundColor: ["#c9d3da", "#f2c14e", accent, "#8a96a3"], borderWidth: 0 }] } });
    const res = RESULTS.filter(Boolean);
    draw("#c-results", { type: "bar", data: { labels: res, datasets: [{ data: res.map(r => count("Result", r)), backgroundColor: "#2f80ed", borderRadius: 4 }] }, options: { scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } } });
    const weeks = [], now = new Date(); const monday = new Date(now); monday.setDate(now.getDate() - ((now.getDay() + 6) % 7)); monday.setHours(0, 0, 0, 0);
    for (let w = 11; w >= 0; w--) { const d = new Date(monday); d.setDate(monday.getDate() - 7 * w); weeks.push(d); }
    const perWeek = weeks.map(d => rows.filter(([, t]) => { if (!t["Date applied"]) return false; const a = new Date(t["Date applied"]); return a >= d && a < new Date(d.getTime() + 7 * 864e5); }).length);
    draw("#c-weeks", { type: "line", data: { labels: weeks.map(d => d.toLocaleDateString(undefined, { day: "numeric", month: "short" })), datasets: [{ data: perWeek, borderColor: accent, backgroundColor: accent, tension: 0 }] }, options: { scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } } });
  }
  $("#tracker-table").addEventListener("change", e => {
    const el = e.target, id = el.closest("tr").dataset.id, t = tracked[id]; if (!t) return;
    t[el.dataset.f] = el.value;
    if (el.dataset.f === "Status" && el.value === "Applied") {
      if (!t["Date applied"]) t["Date applied"] = new Date().toISOString().slice(0, 10);
      if (!t.Result) t.Result = "Pending";
    }
    saveTracked(); renderTracker();
  });
  $("#tracker-table").addEventListener("click", e => {
    if (e.target.dataset.act !== "drop") return;
    delete tracked[e.target.closest("tr").dataset.id]; saveTracked(); renderTracker();
  });
  $("#json-export").addEventListener("click", () => download(new Blob([JSON.stringify({ tracked, cv }, null, 1)], { type: "application/json" }), "job-tracker-backup.json"));
  $("#json-import").addEventListener("change", async e => {
    const f = e.target.files[0]; if (!f) return;
    try { const data = JSON.parse(await f.text()); tracked = data.tracked || {}; if (data.cv) { cv = data.cv; store.set("jh.cv", cv); showCv(); } saveTracked(); renderTracker(); rank(); }
    catch { alert("That file is not a tracker backup."); }
  });
  function download(blob, name) { const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 4000); }

  /* ---------- Excel and Word via Pyodide (same Python code as the command-line tool) ---------- */
  let py = null;
  async function python() {
    if (py) return py;
    $("#py-status").textContent = "Loading Python in your browser (first time only, about 15 seconds)…";
    await new Promise((ok, fail) => { const s = document.createElement("script"); s.src = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js"; s.onload = ok; s.onerror = () => fail(new Error("Could not load Pyodide")); document.head.appendChild(s); });
    const pyodide = await loadPyodide();
    await pyodide.loadPackage("micropip");
    await pyodide.runPythonAsync("import micropip\nawait micropip.install(['openpyxl', 'python-docx'])");
    pyodide.FS.mkdirTree("/home/pyodide/jobhunt");
    for (const f of ["__init__.py", "models.py", "skills.py", "match.py", "cv.py", "tracker.py", "tailor.py"]) {
      const res = await fetch("py/jobhunt/" + f); if (!res.ok) throw new Error("Missing " + f);
      pyodide.FS.writeFile("/home/pyodide/jobhunt/" + f, await res.text());
    }
    await pyodide.runPythonAsync("import sys\nsys.path.insert(0, '/home/pyodide')");
    $("#py-status").textContent = "";
    py = pyodide; return py;
  }
  $("#xlsx").addEventListener("click", async e => {
    const btn = e.target; btn.disabled = true; const label = btn.textContent; btn.textContent = "Building…";
    try {
      const pyo = await python();
      const list = Object.values(tracked).map(t => t.job).concat(ranked.slice(0, 150).filter(j => !tracked[j.id]).map(slim));
      const overrides = Object.fromEntries(Object.entries(tracked).map(([id, t]) => [id, { Status: t.Status, "Date applied": t["Date applied"], Result: t.Result, Notes: t.Notes }]));
      pyo.globals.set("JOBS_JSON", JSON.stringify(list)); pyo.globals.set("OVERRIDES_JSON", JSON.stringify(overrides));
      await pyo.runPythonAsync(`
import json, os
from jobhunt.models import Job
from jobhunt.tracker import write_tracker
if os.path.exists('/tmp/tracker.xlsx'):
    os.remove('/tmp/tracker.xlsx')
jobs = [Job.from_dict(d) for d in json.loads(JOBS_JSON)]
write_tracker(jobs, '/tmp/tracker.xlsx', overrides=json.loads(OVERRIDES_JSON))`);
      download(new Blob([pyo.FS.readFile("/tmp/tracker.xlsx")], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }), `job_tracker_${new Date().toISOString().slice(0, 10)}.xlsx`);
    } catch (err) { $("#py-status").textContent = "Could not build the Excel file: " + (err.message || err); }
    btn.disabled = false; btn.textContent = label;
  });
  async function tailoredCv(j, btn) {
    btn.disabled = true; const label = btn.textContent; btn.textContent = "Building…";
    try {
      const pyo = await python();
      pyo.globals.set("CV_TEXT", cv.text); pyo.globals.set("JOB_JSON", JSON.stringify(slim(j)));
      await pyo.runPythonAsync(`
import json
from jobhunt.cv import parse
from jobhunt.models import Job
from jobhunt.tailor import tailor_plain_cv, write_text_docx
job = Job.from_dict(json.loads(JOB_JSON))
text, report = tailor_plain_cv(parse(CV_TEXT), job)
write_text_docx(text, '/tmp/cv.docx')`);
      const safe = `${j.company}_${j.title}`.replace(/[^A-Za-z0-9]+/g, "_").slice(0, 60);
      download(new Blob([pyo.FS.readFile("/tmp/cv.docx")], { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }), `CV_${safe}.docx`);
    } catch (err) { alert("Could not build the CV: " + (err.message || err)); }
    btn.disabled = false; btn.textContent = label;
  }

  /* ---------- tabs, filters, start-up ---------- */
  $$(".tab").forEach(b => b.addEventListener("click", () => {
    $$(".tab").forEach(x => x.classList.toggle("active", x === b));
    $$(".panel").forEach(p => p.classList.toggle("active", p.id === "tab-" + b.dataset.tab));
    if (b.dataset.tab === "tracker") renderTracker();
    window.scrollTo(0, 0);
  }));
  $("#f-cats").innerHTML = CATEGORIES.map(c => `<label><input type="checkbox" value="${esc(c)}" ${DEFAULT_CATS.includes(c) ? "checked" : ""}> ${esc(c)}</label>`).join("");
  if (innerWidth < 820) $(".filters").removeAttribute("open");
  let timer;
  $(".filters").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(rank, 200); });

  Promise.all([fetch("data/jobs.json").then(r => r.json()), fetch("data/skills.json").then(r => r.json()), fetch("data/companies.json").then(r => r.ok ? r.json() : null).catch(() => null)])
    .then(([data, skills, companies]) => {
      jobs = data.jobs;
      skillRx = Object.fromEntries(Object.entries(skills).map(([k, v]) => [k, new RegExp(v.source, v.flags)]));
      if (cv) { cv.skills = findSkills(cv.text); showCv(); }
      const when = new Date(data.generated);
      const ok = companies ? companies.companies.filter(c => c.board_ok) : [];
      $("#data-meta").textContent = `${jobs.length} jobs from ${data.companies_checked - data.companies_failed.length} employers, updated ${when.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}.`;
      if (companies) $("#about-companies").textContent = `Employers checked: ${ok.map(c => c.name).join(", ")}. ${ok.filter(c => c.links_board).length} of ${ok.length} were confirmed from the company's own website.`;
      saveTracked(); rank();
    })
    .catch(err => { $("#data-meta").textContent = "Could not load the job list: " + err.message; });
})();
