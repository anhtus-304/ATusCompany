const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const STATUS = {
  running: "Đang chạy", awaiting_approval: "Chờ sếp duyệt", needs_review: "Cần sếp xử lý",
  over_budget: "Chạm trần ngân sách", failed: "Lỗi", approved: "Đã duyệt", changes_requested: "Yêu cầu sửa",
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
       <span class="t">${esc(p.title)}</span><span class="badge">${esc(STATUS[p.status] || p.status)}</span></li>`).join("")
    || '<li class="muted">Chưa có dự án</li>';
}

function list(items) { return `<ul>${(items || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`; }

function render(p) {
  const a = p.artifacts || {};
  const cost = p.cost || {};
  const done = !["running"].includes(p.status);
  let html = `<h2>${esc(p.title)}</h2>
    <p><span class="badge">${esc(STATUS[p.status] || p.status)}</span>
    ${cost.spent_usd !== undefined ? `<span class="muted small"> · Chi phí model: $${cost.spent_usd.toFixed(4)} / $${cost.budget_usd.toFixed(2)} · ${cost.calls} lần gọi</span>` : ""}</p>
    <div class="board">${p.tasks.map((t) => `<div class="card"><div>${esc(t.label)}</div>
      <div class="s ${esc(t.status)}">${esc(t.status)}</div><div class="muted small">${esc(t.note)}</div></div>`).join("")}</div>`;

  if (a.report) {
    const r = a.report;
    html += `<section class="box"><h3>Báo cáo</h3><p>${esc(r.summary)}</p>
      <h4>Đã xong</h4>${list(r.done)}<h4>Còn lại</h4>${list(r.remaining)}
      <h4>Rủi ro</h4>${list(r.risks)}<h4>Cần sếp duyệt</h4>${list(r.decisions_needed)}
      ${["awaiting_approval", "needs_review"].includes(p.status) ? `<div class="actions">
        <button data-decide="1">Duyệt gửi khách</button>
        <button class="secondary" data-decide="0">Yêu cầu sửa</button></div>` : ""}</section>`;
  }
  if (a.report || a.qa) {
    html += `<section class="box"><h3>Bản demo</h3>
      <p><a href="/preview/${esc(p.id)}/" target="_blank">Mở trong tab mới</a></p>
      <iframe src="/preview/${esc(p.id)}/index.html?t=${Date.now()}" title="Bản demo"></iframe></section>`;
  }
  if (a.qa) {
    html += `<section class="box"><h3>QA</h3><ul class="checks">${a.qa.checks.map((c) =>
      `<li><span class="${c.passed ? "done" : "failed"}">${c.passed ? "✓" : "✗"}</span> ${esc(c.name)}
       ${c.detail ? `<span class="muted small">: ${esc(c.detail)}</span>` : ""}</li>`).join("")}</ul></section>`;
  }
  if (a.spec) {
    const s = a.spec;
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

async function open(id) {
  current = id;
  clearTimeout(timer);
  const tick = async () => {
    const p = await api(`/api/projects/${encodeURIComponent(id)}`);
    if (current !== id) return;
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
  const b = e.target.closest("[data-decide]");
  if (!b) return;
  const approve = b.dataset.decide === "1";
  const note = approve ? "" : prompt("Cần sửa gì?") || "";
  await api(`/api/projects/${encodeURIComponent(current)}/decision`, { method: "POST", body: JSON.stringify({ approve, note }) });
  open(current);
});

$("#new").addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = $("#msg").value.trim();
  if (message.length < 5) return;
  const btn = e.submitter; btn.disabled = true;
  try {
    const { id } = await api("/api/projects", { method: "POST", body: JSON.stringify({ message, budget_usd: Number($("#budget").value) || null }) });
    $("#msg").value = "";
    await loadList();
    open(id);
  } catch (err) { alert(err.message); } finally { btn.disabled = false; }
});

loadList();
