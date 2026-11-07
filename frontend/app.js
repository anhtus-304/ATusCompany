const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const STATUS = {
  running: "Đang chạy", awaiting_choice: "Chờ sếp chọn phương án", awaiting_approval: "Chờ sếp duyệt", needs_review: "Cần sếp xử lý",
  over_budget: "Chạm trần ngân sách", failed: "Lỗi", approved: "Đã duyệt", changes_requested: "Yêu cầu sửa",
  stopped: "Đã dừng",
};
let current = null;
let timer = null;

async function api(path, opts) {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
  return r.json();
}

async function loadList() {
  const items = await api("/api/projects");
  $("#projects").innerHTML = items.map((p) =>
    `<li data-id="${esc(p.id)}" class="${p.id === current ? "active" : ""}">
       <span class="t">${esc(p.title)}</span>${p.client ? `<span class="muted small">${esc(p.client)} · </span>` : ""}<span class="badge">${esc(STATUS[p.status] || p.status)}</span></li>`).join("")
    || '<li class="muted">Chưa có dự án</li>';
}

const vnd = (n) => Number(n).toLocaleString("vi-VN") + " ₫";
const TIER = { fast: "Nhanh & rẻ", balanced: "Cân bằng", premium: "Cao cấp" };
const FEAT = {
  responsive: "Responsive", sticky_nav: "Menu dính", dark_mode: "Giao diện tối", animations: "Hiệu ứng",
  faq_accordion: "Hỏi đáp", contact_form: "Form liên hệ", seo_meta: "SEO + chia sẻ MXH",
};

function renderOptions(p) {
  const pr = p.artifacts.proposal;
  const chosen = p.artifacts.choice?.option_id;
  const waiting = p.status === "awaiting_choice";
  const revisions = p.artifacts.revisions?.notes || [];
  return `<section class="box"><h3>${waiting ? "Chọn phương án" : "Phương án"}</h3>
    <p class="muted">${esc(pr.reasoning)}</p>
    <div class="options">${pr.options.map((o) => `
      <div class="opt ${o.id === pr.recommended ? "rec" : ""} ${o.id === chosen ? "chosen" : ""}">
        <div class="opt-head"><b>${esc(o.id)}. ${esc(o.name)}</b>
          ${o.id === pr.recommended ? '<span class="badge">Khuyên chọn</span>' : ""}
          ${o.id === chosen ? '<span class="badge ok">Đã chọn</span>' : ""}</div>
        <div class="price">${vnd(o.est_price_vnd)}</div>
        <div class="muted small">${esc(o.est_days)} ngày · ${o.sections.length} mục · ${esc(TIER[o.tier] || o.tier)}</div>
        <p>${esc(o.summary)}</p>
        <div class="chips">${o.features.map((f) => `<span class="chip">${esc(FEAT[f] || f)}</span>`).join("")}</div>
        <div class="small muted">Mục: ${o.sections.map((x) => esc(x.heading)).join(" · ")}</div>
        <ul class="pc">${o.pros.map((x) => `<li class="pro">${esc(x)}</li>`).join("")}${o.cons.map((x) => `<li class="con">${esc(x)}</li>`).join("")}</ul>
        ${waiting ? `<button data-choose="${esc(o.id)}">Chọn ${esc(o.id)}</button>` : ""}
      </div>`).join("")}</div>
    ${waiting ? `<form id="revise" class="revise">
      <label for="note">Hoặc yêu cầu chỉnh lại các phương án</label>
      <textarea id="note" rows="2" placeholder="Ví dụ: khách chỉ có 3 triệu, bỏ thư viện ảnh, thêm bảng giá"></textarea>
      <button class="secondary" type="submit">Gửi góp ý</button></form>` : ""}
    ${revisions.length ? `<p class="muted small">Đã chỉnh ${revisions.length} lần: ${revisions.map(esc).join(" · ")}</p>` : ""}
  </section>`;
}

function list(items) { return `<ul>${(items || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`; }

function render(p) {
  const a = p.artifacts || {};
  const cost = p.cost || {};
  // Keep polling while the client email is being drafted after approval.
  const done = p.status !== "running" && !(p.status === "approved" && !a.client_message);
  let html = `<h2>${esc(p.title)}</h2>
    <p>${p.client ? `<a href="#" data-client="${p.client.id}">${esc(p.client.name)}</a> · ` : ""}<span class="badge">${esc(STATUS[p.status] || p.status)}</span>
    ${p.status === "approved" ? `<a class="small" href="/api/projects/${encodeURIComponent(p.id)}/export">Tải gói giao khách (.zip)</a>` : ""}
    ${cost.spent_usd !== undefined ? `<span class="muted small"> · Chi phí model: $${cost.spent_usd.toFixed(4)} / $${cost.budget_usd.toFixed(2)} · ${cost.calls} lần gọi</span>` : ""}</p>
    <div class="board">${p.tasks.map((t) => `<div class="card"><div>${esc(t.label)}</div>
      <div class="s ${esc(t.status)}">${esc(t.status)}</div><div class="muted small">${esc(t.note)}</div></div>`).join("")}</div>`;

  const mem = a.memory;
  if (mem && (mem.projects.length || mem.decisions.length)) {
    html += `<section class="box"><h3>Bộ nhớ về ${esc(mem.client_name)}</h3>
      <p class="muted small">Lễ tân, Kiến trúc sư và Báo cáo viên đã đọc phần này trước khi làm.</p>
      ${renderMemory(mem)}</section>`;
  }
  if (p.status === "over_budget") html += renderBudget(p);
  if (a.proposal && p.status === "awaiting_choice") html += renderOptions(p);
  if (a.report) {
    const r = a.report;
    html += `<section class="box"><h3>Báo cáo</h3><p>${esc(r.summary)}</p>
      <h4>Đã xong</h4>${list(r.done)}<h4>Còn lại</h4>${list(r.remaining)}
      <h4>Rủi ro</h4>${list(r.risks)}<h4>Cần sếp duyệt</h4>${list(r.decisions_needed)}
      ${["awaiting_approval", "needs_review"].includes(p.status) ? `<div class="actions">
        <button data-decide="1">Duyệt gửi khách</button>
        <button class="secondary" data-decide="0">Yêu cầu sửa</button></div>` : ""}</section>`;
  }
  if (a.delivery && a.report) html += renderDelivery(p);
  if (a.report || a.qa) {
    const demo = a.delivery?.staging ? `/staging/${encodeURIComponent(p.id)}/` : `/preview/${encodeURIComponent(p.id)}/`;
    html += `<section class="box"><h3>Bản demo</h3>
      <p><a href="${demo}" target="_blank">Mở trong tab mới</a></p>
      <iframe src="${demo}?t=${Date.now()}" title="Bản demo"></iframe></section>`;
  }
  if (a.review) {
    const f = a.review.findings || [];
    const SEV = { blocker: "Chặn", major: "Nặng", minor: "Gợi ý" };
    html += `<section class="box"><h3>Reviewer</h3>${f.length ? `<ul class="checks">${f.map((x) =>
      `<li><span class="${x.severity === "minor" ? "blocked" : "failed"}">${esc(SEV[x.severity] || x.severity)}</span>
       <code>${esc(x.file)}</code> ${esc(x.message)} <span class="muted small">(${esc(x.rule)}, giao ${esc(x.owner)})</span></li>`).join("")}</ul>`
      : '<p class="done">Không có vấn đề bảo mật hay chất lượng.</p>'}</section>`;
  }
  if (a.design) {
    const d = a.design;
    html += `<section class="box"><h3>Thiết kế</h3><div class="chips">${Object.entries(d.colors).map(([k, v]) =>
      `<span class="chip"><span class="sw" style="background:${esc(v)}"></span>${esc(k)} ${esc(v)}</span>`).join("")}</div>
      <p class="small muted">Font: ${esc(d.font_stack)} · Bố cục: ${d.sections.map((x) => `#${esc(x.id)} ${esc(x.layout)}`).join(", ")}</p>
      ${list(d.notes)}</section>`;
  }
  if (a.final_spec && a.final_spec.api && a.final_spec.api.length) {
    html += `<section class="box"><h3>API contract</h3>${a.final_spec.api.map((e) => `<p><code>${esc(e.method)} ${esc(e.path)}</code> ${esc(e.purpose)}</p>
      <ul>${e.fields.map((x) => `<li><code>${esc(x.name)}</code> ${esc(x.type)}${x.required ? ", bắt buộc" : ""}, tối đa ${x.max_length}</li>`).join("")}</ul>`).join("")}</section>`;
  }
  if (a.qa) {
    html += `<section class="box"><h3>QA</h3><ul class="checks">${a.qa.checks.map((c) =>
      `<li><span class="${c.passed ? "done" : "failed"}">${c.passed ? "✓" : "✗"}</span> ${esc(c.name)}${c.owner === "backend_dev" ? ' <span class="chip">backend</span>' : ""}
       ${c.detail ? `<span class="muted small">: ${esc(c.detail)}</span>` : ""}</li>`).join("")}</ul></section>`;
  }
  if (a.proposal && p.status !== "awaiting_choice") html += renderOptions(p);
  if (a.final_spec || a.spec) {
    const s = a.final_spec || a.spec;
    html += `<section class="box"><h3>Spec</h3><p><b>Mục tiêu:</b> ${esc(s.goal)}</p>
      <p><b>Đối tượng:</b> ${esc(s.audience)} · <b>Công nghệ:</b> ${esc(s.tech)}</p>
      <h4>Các mục</h4><ul>${s.sections.map((x) => `<li><code>#${esc(x.id)}</code> ${esc(x.heading)}: ${esc(x.purpose)}</li>`).join("")}</ul>
      <h4>Tiêu chí nghiệm thu</h4>${list(s.acceptance_criteria)}</section>`;
  }
  if (a.brief) {
    const b = a.brief;
    html += `<section class="box"><h3>Brief từ Lễ tân</h3>
      <p><b>Ngân sách:</b> ${esc(b.budget)} · <b>Thời hạn:</b> ${esc(b.deadline)} · <b>Giọng điệu:</b> ${esc(b.tone)}</p>
      <h4>Giả định</h4>${list(b.assumptions)}<h4>Câu hỏi mở</h4>${list(b.open_questions)}</section>`;
  }
  html += `<section class="box"><h3>Nhật ký</h3><div class="events">${p.events.map((e) => esc(e.text)).join("\n")}</div></section>`;
  $("#detail").innerHTML = html;
  return done;
}

const STAGE_NAMES = { intake: "Lễ tân", analyst: "BA / Architect", proposer: "Đề xuất phương án", designer: "Designer",
  backend_dev: "Backend Dev", frontend_dev: "Frontend Dev", qa: "QA", reviewer: "Reviewer", reporter: "Báo cáo viên" };

function renderBudget(p) {
  const stop = p.artifacts.budget_stop || {};
  const spent = stop.spent_usd ?? p.cost?.spent_usd ?? 0;
  return `<section class="box warn"><h3>Chạm trần ngân sách</h3>
    <p>Dự án dừng ở bước <b>${esc(STAGE_NAMES[stop.stage] || stop.stage || "?")}</b>: đã tiêu $${Number(spent).toFixed(4)} / trần $${Number(p.budget_usd).toFixed(2)}.
    Duyệt chi thêm thì đội làm tiếp từ bước đó, các bước đã xong không phải trả tiền lại.</p>
    <form id="budget-form" class="row wrap"><label for="add-usd">Cấp thêm (USD)</label>
      <input id="add-usd" type="number" min="0.01" max="50" step="0.01" value="${Math.max(1, Number(p.budget_usd)).toFixed(2)}">
      <button type="submit">Duyệt chi thêm</button>
      <button type="button" class="secondary" data-stop-project>Dừng dự án</button></form></section>`;
}

function renderDelivery(p) {
  const a = p.artifacts;
  const d = a.delivery || {};
  const approved = p.status === "approved";
  const short = (sha) => esc((sha || "").slice(0, 7));
  const link = (r) => `<a href="${esc(new URL(r.url).pathname)}" target="_blank">${esc(r.url)}</a>`;
  const m = a.client_message;
  let html = `<section class="box"><h3>Giao hàng</h3>
    <table class="tbl"><tbody>
    <tr><th>Staging</th><td>${d.staging ? `${link(d.staging)} <span class="muted small">commit ${short(d.staging.sha)} · ${esc(d.staging.at)}</span>`
      : '<span class="muted">Chưa có</span>'}<div class="muted small">Bản nội bộ để sếp xem, tự cập nhật sau mỗi lần build.</div></td></tr>
    <tr><th>Production</th><td>${d.production ? `${link(d.production)} <span class="muted small">commit ${short(d.production.sha)} · ${esc(d.production.at)}</span>` : '<span class="muted">Chưa deploy</span>'}
      ${approved ? `<div><button data-deploy>${d.production ? "Deploy lại bản đã duyệt" : "Deploy production"}</button></div>`
        : '<div class="muted small">Cần duyệt bàn giao trước khi deploy.</div>'}</td></tr>
    <tr><th>GitHub của khách</th><td>${(d.history || []).filter((h) => h.kind === "github").map((h) =>
      `<div>${esc(h.repo)} · nhánh ${esc(h.branch)} · commit ${short(h.sha)} <span class="muted small">${esc(h.at)}</span></div>`).join("")}
      ${approved ? `<form id="push-form" class="row wrap"><input id="repo" placeholder="chủ-repo/tên-repo" maxlength="201" required>
        <input id="branch" value="main" maxlength="100" class="short"><button class="secondary">Đẩy code</button></form>`
        : '<span class="muted small">Cần duyệt bàn giao trước.</span>'}</td></tr>
    </tbody></table>`;
  if (approved || m) {
    const sent = m?.sent;
    html += `<h4>Email gửi khách</h4>${!m ? '<p class="muted">Báo cáo viên đang soạn…</p>' : `
      ${sent ? `<p class="${sent.sent ? "done" : "blocked"}">${sent.sent ? `Đã gửi cho ${esc(sent.to)} lúc ${esc(sent.at)}`
        : `Chưa cấu hình máy chủ email nên chưa gửi thật: đã lưu vào hộp thư đi (${esc(sent.file)}) lúc ${esc(sent.at)}`}</p>` : ""}
      <form id="mail-form" class="mail">
        <label for="mail-to">Gửi tới</label><input id="mail-to" type="email" maxlength="200" value="${esc(m.to)}" placeholder="email của khách">
        <label for="mail-subject">Tiêu đề</label><input id="mail-subject" maxlength="200" value="${esc(m.subject)}">
        <label for="mail-body">Nội dung</label><textarea id="mail-body" rows="12" maxlength="10000">${esc(m.body)}</textarea>
        ${approved ? `<div class="actions"><button type="submit">Gửi cho khách</button>
          <button type="button" class="secondary" data-save-mail>Lưu bản nháp</button>
          <button type="button" class="secondary" data-redraft>Soạn lại</button></div>` : ""}
      </form>`}`;
  }
  return html + "</section>";
}

function renderMemory(mem) {
  const KIND = { choice: "Chọn", revision: "Góp ý", approved: "Duyệt", changes_requested: "Yêu cầu sửa", note: "Ghi nhớ",
    budget: "Chi thêm", stopped: "Dừng", deployed: "Deploy", sent: "Gửi khách", pushed: "Giao code" };
  return `${mem.projects.length ? `<h4>Dự án trước</h4><ul>${mem.projects.map((x) =>
      `<li>${esc(x.date)}: ${esc(x.title)} · ngân sách ${esc(x.budget)}${x.chosen_name ? ` · chọn <b>${esc(x.chosen_name)}</b> ${vnd(x.price_vnd)}` : ""} <span class="badge">${esc(STATUS[x.status] || x.status)}</span></li>`).join("")}</ul>` : ""}
    ${mem.decisions.length ? `<h4>Quyết định đã chốt</h4><ul>${mem.decisions.map((d) =>
      `<li><span class="chip">${esc(KIND[d.kind] || d.kind)}</span> ${esc(d.text)} <span class="muted small">${esc(d.date)}</span></li>`).join("")}</ul>` : ""}`;
}

let view = "projects";

async function showClients() {
  clearTimeout(timer);
  const items = await api("/api/clients");
  $("#detail").innerHTML = `<h2>Khách hàng</h2>${items.length ? `<table class="tbl"><thead><tr><th>Khách</th><th>Liên hệ</th><th>Dự án</th><th>Gần nhất</th></tr></thead><tbody>
    ${items.map((c) => `<tr><td><a href="#" data-client="${c.id}">${esc(c.name)}</a></td><td>${esc(c.contact || "")}</td><td>${c.projects}</td>
      <td>${c.last_project_at ? new Date(c.last_project_at * 1000).toLocaleDateString("vi-VN") : ""}</td></tr>`).join("")}</tbody></table>`
    : '<p class="muted">Chưa có khách hàng.</p>'}`;
}

async function showClient(cid) {
  clearTimeout(timer);
  const c = await api(`/api/clients/${cid}`);
  $("#detail").innerHTML = `<h2>${esc(c.name)}</h2>
    <form id="contact-form" class="row" data-cid="${c.id}"><label for="contact">Liên hệ</label>
      <input id="contact" maxlength="200" value="${esc(c.contact || "")}" placeholder="SĐT, email, Zalo"><button class="secondary">Lưu</button></form>
    <section class="box">${renderMemory(c.memory) || '<p class="muted">Chưa có lịch sử.</p>'}</section>
    <form id="note-form" class="revise" data-cid="${c.id}"><label for="cnote">Ghi nhớ về khách (sở thích, điều đã chốt)</label>
      <textarea id="cnote" rows="2" maxlength="1000" placeholder="Ví dụ: khách không thích màu đỏ, luôn cần bản tiếng Anh"></textarea>
      <button class="secondary">Ghi nhớ</button></form>`;
}

const AGENT_NAMES = { leader: "Trưởng phòng", intake: "Lễ tân", architect: "Kiến trúc sư", reporter: "Báo cáo viên",
  frontend: "Frontend Dev", backend: "Backend Dev", reviewer: "Reviewer", designer: "Designer", qa: "Tester" };
const pct = (x) => (x === undefined || x === null ? "–" : Math.round(x * 100) + "%");
const num = (x, d = 1) => (x === undefined || x === null ? "–" : Number(x).toFixed(d));

async function showTeam() {
  clearTimeout(timer);
  const card = await api("/api/agents/scorecard");
  const rows = Object.keys(AGENT_NAMES).filter((k) => card[k]).map((k) => [k, card[k]]);
  $("#detail").innerHTML = `<h2>Đội ngũ</h2>
    <p class="muted small">Tính trên mọi dự án. Đạt ngay lần đầu = QA và Reviewer không trả lỗi về cho dev đó.</p>
    ${rows.length ? `<table class="tbl"><thead><tr><th>Agent</th><th>Việc xong</th><th>Bị chặn/lỗi</th><th>Thời gian TB (s)</th>
      <th>Đạt ngay lần đầu</th><th>Vòng sửa TB</th><th>Chi phí model</th><th>Khác</th></tr></thead><tbody>
      ${rows.map(([k, m]) => `<tr><td>${esc(AGENT_NAMES[k])}</td><td>${m.tasksDone}</td><td>${m.tasksStuck}</td><td>${num(m.avgSeconds, 2)}</td>
        <td>${pct(m.firstPassRate)}</td><td>${num(m.avgRounds)}</td><td>$${num(m.costUsd, 4)}</td>
        <td class="small">${[m.findingsPerProject !== undefined ? `${num(m.findingsPerProject)} ghi chú/dự án, ${num(m.blockingPerProject)} chặn` : "",
          m.checksPerProject !== undefined ? `${num(m.checksPerProject, 0)} kiểm tra/dự án` : "",
          m.approvalRate !== undefined ? `sếp duyệt ${pct(m.approvalRate)}` : ""].filter(Boolean).join(" · ")}</td></tr>`).join("")}
      </tbody></table>` : '<p class="muted">Chưa có số liệu. Chạy xong một dự án sẽ có.</p>'}`;
}

function setView(v) {
  view = v;
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === v));
  if (v === "clients") showClients();
  else if (v === "team") showTeam();
  else if (current) open(current);
  else $("#detail").innerHTML = '<p class="muted">Giao việc mới hoặc chọn một dự án.</p>';
}

document.querySelector(".tabs").addEventListener("click", (e) => {
  const t = e.target.closest("[data-view]");
  if (t) setView(t.dataset.view);
});

async function loadClients() {
  const items = await api("/api/clients");
  $("#clientlist").innerHTML = items.map((c) => `<option value="${esc(c.name)}"></option>`).join("");
}

async function open(id) {
  current = id;
  view = "projects";
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === "projects"));
  clearTimeout(timer);
  const tick = async () => {
    const p = await api(`/api/projects/${encodeURIComponent(id)}`);
    if (current !== id || view !== "projects") return;
    const finished = render(p);
    loadList();
    if (!finished) timer = setTimeout(tick, 1200);
  };
  tick();
}

$("#projects").addEventListener("click", (e) => {
  const li = e.target.closest("li[data-id]");
  if (li) open(li.dataset.id);
});

$("#detail").addEventListener("click", async (e) => {
  const cl = e.target.closest("[data-client]");
  if (cl) {
    e.preventDefault();
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === "clients"));
    return showClient(cl.dataset.client);
  }
  const c = e.target.closest("[data-choose]");
  if (c) {
    c.disabled = true;
    try {
      await api(`/api/projects/${encodeURIComponent(current)}/choice`, { method: "POST", body: JSON.stringify({ option_id: c.dataset.choose }) });
    } catch (err) { alert(err.message); }
    return open(current);
  }
  const pid = encodeURIComponent(current);
  const act = async (fn) => { try { await fn(); } catch (err) { alert(err.message); } open(current); };
  if (e.target.closest("[data-stop-project]")) {
    if (!confirm("Dừng dự án ở đây? Đội sẽ không làm tiếp.")) return;
    return act(() => api(`/api/projects/${pid}/budget`, { method: "POST", body: JSON.stringify({ approve: false }) }));
  }
  if (e.target.closest("[data-deploy]")) {
    if (!confirm("Deploy bản sếp đã duyệt lên production? Khách và người ngoài sẽ xem được.")) return;
    return act(() => api(`/api/projects/${pid}/deploy`, { method: "POST", body: JSON.stringify({ confirm: true }) }));
  }
  if (e.target.closest("[data-redraft]")) {
    if (!confirm("Soạn lại email? Bản đang sửa sẽ mất.")) return;
    return act(() => api(`/api/projects/${pid}/client-message`, { method: "POST" }));
  }
  if (e.target.closest("[data-save-mail]")) return act(saveMail);
  const b = e.target.closest("[data-decide]");
  if (!b) return;
  const approve = b.dataset.decide === "1";
  const note = approve ? "" : prompt("Cần sửa gì?") || "";
  await api(`/api/projects/${encodeURIComponent(current)}/decision`, { method: "POST", body: JSON.stringify({ approve, note }) });
  open(current);
});

$("#detail").addEventListener("submit", async (e) => {
  if (e.target.id === "note-form" || e.target.id === "contact-form") {
    e.preventDefault();
    const cid = e.target.dataset.cid;
    try {
      if (e.target.id === "note-form") {
        const text = $("#cnote").value.trim();
        if (text.length < 2) return;
        await api(`/api/clients/${cid}/notes`, { method: "POST", body: JSON.stringify({ text }) });
      } else {
        await api(`/api/clients/${cid}`, { method: "PATCH", body: JSON.stringify({ contact: $("#contact").value.trim() }) });
      }
    } catch (err) { alert(err.message); }
    return showClient(cid);
  }
  const pid = encodeURIComponent(current);
  if (e.target.id === "budget-form") {
    e.preventDefault();
    const add_usd = Number($("#add-usd").value);
    if (!(add_usd > 0)) return;
    try { await api(`/api/projects/${pid}/budget`, { method: "POST", body: JSON.stringify({ approve: true, add_usd }) }); }
    catch (err) { alert(err.message); }
    return open(current);
  }
  if (e.target.id === "push-form") {
    e.preventDefault();
    const repo = $("#repo").value.trim(), branch = $("#branch").value.trim() || "main";
    if (!confirm(`Đẩy bản đã duyệt lên github.com/${repo}, nhánh ${branch}?`)) return;
    try { await api(`/api/projects/${pid}/github`, { method: "POST", body: JSON.stringify({ repo, branch, confirm: true }) }); }
    catch (err) { alert(err.message); }
    return open(current);
  }
  if (e.target.id === "mail-form") {
    e.preventDefault();
    const to = $("#mail-to").value.trim();
    if (!confirm(`Gửi email này cho ${to || "(chưa có địa chỉ)"}?`)) return;
    try {
      await saveMail();
      await api(`/api/projects/${pid}/client-message/send`, { method: "POST", body: JSON.stringify({ confirm: true }) });
    } catch (err) { alert(err.message); }
    return open(current);
  }
  if (e.target.id !== "revise") return;
  e.preventDefault();
  const note = $("#note").value.trim();
  if (!note) return;
  try {
    await api(`/api/projects/${encodeURIComponent(current)}/choice`, { method: "POST", body: JSON.stringify({ note }) });
  } catch (err) { alert(err.message); }
  open(current);
});

function saveMail() {
  return api(`/api/projects/${encodeURIComponent(current)}/client-message`, { method: "PUT", body: JSON.stringify({
    to: $("#mail-to").value.trim(), subject: $("#mail-subject").value.trim(), body: $("#mail-body").value }) });
}

$("#new").addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = $("#msg").value.trim();
  if (message.length < 5) return;
  const btn = e.submitter; btn.disabled = true;
  try {
    const client = $("#client").value.trim() || null;
    const { id } = await api("/api/projects", { method: "POST", body: JSON.stringify({ message, client, budget_usd: Number($("#budget").value) || null }) });
    $("#msg").value = "";
    loadClients();
    await loadList();
    open(id);
  } catch (err) { alert(err.message); } finally { btn.disabled = false; }
});

loadList();
loadClients();
