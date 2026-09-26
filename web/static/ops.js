const statsEl = document.getElementById("stats");
const pendingEl = document.getElementById("pending");
const runsEl = document.getElementById("runs");
const healthEl = document.getElementById("health");

function esc(v) {
  return String(v)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

async function load() {
  const [health, runs, pending] = await Promise.all([
    fetch("/api/health").then((r) => r.json()),
    fetch("/api/ops/runs?limit=20").then((r) => r.json()),
    fetch("/api/hitl/pending").then((r) => r.json()),
  ]);
  healthEl.textContent = `v${health.version}`;

  const s = runs.stats || {};
  statsEl.innerHTML = [
    ["Runs", s.runs ?? 0],
    ["Avg latency", `${s.avg_latency_ms ?? 0} ms`],
    ["Awaiting approval", `${Math.round((s.hitl_rate || 0) * 100)}%`],
    ["Avg confidence", `${Math.round((s.avg_confidence || 0) * 100)}%`],
  ]
    .map(
      ([label, value]) =>
        `<div class="stat"><strong>${esc(value)}</strong><span>${esc(label)}</span></div>`,
    )
    .join("");

  const items = pending.pending || [];
  pendingEl.innerHTML = items.length
    ? items
        .map(
          (p) =>
            `<li><strong>${esc(p.run_id.slice(0, 8))}</strong> — ${esc(p.question)}</li>`,
        )
        .join("")
    : "<li>No pending approvals right now.</li>";

  runsEl.innerHTML = (runs.runs || [])
    .map((r) => {
      const when = (r.finished_at || "").slice(11, 19) || "—";
      const approval = r.hitl_status || (r.interrupted ? "pending" : "—");
      return `<tr>
        <td>${esc(when)}</td>
        <td>${esc(r.latency_ms)} ms</td>
        <td>${Math.round((r.confidence || 0) * 100)}%</td>
        <td>${esc(approval)}</td>
        <td class="q">${esc(r.question)}</td>
      </tr>`;
    })
    .join("");
}

load().catch((err) => {
  healthEl.textContent = "offline";
  console.error(err);
});
