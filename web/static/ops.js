const statsEl = document.getElementById("stats");
const proofEl = document.getElementById("proof");
const beyondEl = document.getElementById("beyond");
const runsEl = document.getElementById("runs");
const healthEl = document.getElementById("health");

function esc(v) {
  return String(v)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

async function load() {
  const [health, proof, runs] = await Promise.all([
    fetch("/api/health").then((r) => r.json()),
    fetch("/api/jd-proof").then((r) => r.json()),
    fetch("/api/ops/runs?limit=20").then((r) => r.json()),
  ]);
  healthEl.textContent = `v${health.version} · ${health.llm_provider}`;

  const s = runs.stats || {};
  statsEl.innerHTML = [
    ["Runs", s.runs ?? 0],
    ["Avg latency", `${s.avg_latency_ms ?? 0} ms`],
    ["HITL rate", `${Math.round((s.hitl_rate || 0) * 100)}%`],
    ["Avg confidence", `${Math.round((s.avg_confidence || 0) * 100)}%`],
  ]
    .map(
      ([label, value]) =>
        `<div class="stat"><strong>${esc(value)}</strong><span>${esc(label)}</span></div>`,
    )
    .join("");

  proofEl.innerHTML = (proof.requirements || [])
    .map(
      (r) => `<article class="proof">
        <h3>${esc(r.jd)}</h3>
        <p><strong>Proof:</strong> <code>${esc(r.proof)}</code></p>
        <p><strong>Demo:</strong> ${esc(r.demo)}</p>
      </article>`,
    )
    .join("");

  beyondEl.innerHTML = (proof.beyond_expectation || [])
    .map((b) => `<li>${esc(b)}</li>`)
    .join("");

  runsEl.innerHTML = (runs.runs || [])
    .map((r) => {
      const when = (r.finished_at || "").slice(11, 19) || "—";
      return `<tr>
        <td>${esc(when)}</td>
        <td>${esc(r.latency_ms)} ms</td>
        <td>${Math.round((r.confidence || 0) * 100)}%</td>
        <td>${esc(r.hitl_status || (r.interrupted ? "pending" : "—"))}</td>
        <td class="q">${esc(r.question)}</td>
        <td>${esc((r.patterns || []).slice(0, 3).join(", "))}</td>
      </tr>`;
    })
    .join("");
}

load().catch((err) => {
  healthEl.textContent = "ops offline";
  console.error(err);
});
