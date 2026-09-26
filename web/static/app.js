const prompts = [
  {
    label: "Churn",
    text: "Which members look like churn risks and what win-back should we try?",
  },
  {
    label: "Rules",
    text: "Explain how tier multipliers affect dining earn rates.",
  },
  {
    label: "Member",
    text: "Give me a loyalty snapshot for member M1003 and suggested next action.",
  },
  {
    label: "Campaigns",
    text: "Which loyalty campaigns have the highest uplift right now?",
  },
  {
    label: "HITL",
    text: "Approve and deploy campaign C11 Travel Bonus Week to production.",
  },
];

const transcript = document.getElementById("transcript");
const composer = document.getElementById("composer");
const message = document.getElementById("message");
const send = document.getElementById("send");
const statusEl = document.getElementById("status");
const promptsEl = document.getElementById("prompts");
const healthEl = document.getElementById("health");
const providerEl = document.getElementById("provider");

const sessionId = `web-${crypto.randomUUID().slice(0, 8)}`;

function setEmpty() {
  transcript.innerHTML =
    '<div class="empty">Pick a starter question or ask about earn/burn rules, campaigns, tiers, member ids, or an approval (HITL).</div>';
}

function addBubble(role, html) {
  if (transcript.querySelector(".empty")) transcript.innerHTML = "";
  const div = document.createElement("div");
  div.className = `bubble ${role}`;
  div.innerHTML = html;
  transcript.appendChild(div);
  transcript.scrollTop = transcript.scrollHeight;
  return div;
}

async function resolveHitl(runId, approve) {
  statusEl.textContent = approve ? "Approving…" : "Rejecting…";
  const res = await fetch(`/api/hitl/${runId}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      approve,
      note: approve ? "Approved from LoyaltyDesk UI" : "Rejected from LoyaltyDesk UI",
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    statusEl.textContent = data.detail || "HITL resolve failed";
    return;
  }
  addBubble(
    "assistant",
    `<h3>HITL ${escapeHtml(data.status)}</h3><p>Run <code>${escapeHtml(runId)}</code> marked <strong>${escapeHtml(data.status)}</strong>.</p>`,
  );
  statusEl.textContent = `HITL ${data.status}.`;
}

function renderAnswer(answer, meta = {}) {
  const chips = [];
  (answer.agents_invoked || []).forEach((a) => chips.push(`<span class="chip">${a}</span>`));
  (answer.patterns_used || []).slice(0, 4).forEach((p) =>
    chips.push(`<span class="chip">${escapeHtml(p)}</span>`),
  );
  chips.push(`<span class="chip ok">confidence ${(answer.confidence * 100).toFixed(0)}%</span>`);
  if (answer.guarded) chips.push(`<span class="chip warn">guarded</span>`);
  if (answer.hitl_status === "pending") chips.push(`<span class="chip danger">HITL pending</span>`);
  if (meta.blocked) chips.push(`<span class="chip danger">blocked</span>`);
  if (meta.runId) chips.push(`<span class="chip">run ${meta.runId}</span>`);

  const insights = (answer.insights || [])
    .map((i) => `<li>${escapeHtml(i)}</li>`)
    .join("");
  const actions = (answer.recommended_actions || [])
    .map((i) => `<li>${escapeHtml(i)}</li>`)
    .join("");
  const sql = (answer.sql_used || [])
    .map((s) => `<li><code>${escapeHtml(s)}</code></li>`)
    .join("");
  const reflection = (answer.reflection_notes || [])
    .map((i) => `<li>${escapeHtml(i)}</li>`)
    .join("");

  const hitlControls =
    answer.hitl_status === "pending" && meta.runId
      ? `<div class="hitl-actions">
          <button type="button" class="hitl-approve" data-run="${escapeHtml(meta.runId)}">Approve</button>
          <button type="button" class="hitl-reject" data-run="${escapeHtml(meta.runId)}">Reject</button>
        </div>`
      : "";

  const bubble = addBubble(
    "assistant",
    `
      <h3>LoyaltyDesk</h3>
      <p>${escapeHtml(answer.summary)}</p>
      ${insights ? `<ul class="list">${insights}</ul>` : ""}
      ${actions ? `<p style="margin-top:.75rem"><strong>Actions</strong></p><ul class="list">${actions}</ul>` : ""}
      ${sql ? `<p style="margin-top:.75rem"><strong>SQL / semantic evidence</strong></p><ul class="list">${sql}</ul>` : ""}
      ${reflection ? `<p style="margin-top:.75rem"><strong>Reflection</strong></p><ul class="list">${reflection}</ul>` : ""}
      ${hitlControls}
      <div class="meta-row">${chips.join("")}</div>
    `,
  );

  bubble.querySelectorAll(".hitl-approve").forEach((btn) => {
    btn.addEventListener("click", () => resolveHitl(btn.dataset.run, true));
  });
  bubble.querySelectorAll(".hitl-reject").forEach((btn) => {
    btn.addEventListener("click", () => resolveHitl(btn.dataset.run, false));
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

prompts.forEach((p) => {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "prompt";
  btn.innerHTML = `<strong>${p.label}</strong>${escapeHtml(p.text)}`;
  btn.addEventListener("click", () => {
    message.value = p.text;
    message.focus();
  });
  promptsEl.appendChild(btn);
});

async function refreshHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    healthEl.textContent = data.warehouse_ready ? "warehouse ready" : "warehouse missing";
    providerEl.textContent = `llm: ${data.llm_provider}`;
  } catch {
    healthEl.textContent = "offline";
  }
}

composer.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = message.value.trim();
  if (!text) return;

  addBubble("user", `<p>${escapeHtml(text)}</p>`);
  message.value = "";
  send.disabled = true;
  statusEl.textContent = "Routing supervisor…";

  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId }),
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop() || "";
      for (const chunk of chunks) {
        const line = chunk.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        const payload = JSON.parse(line.slice(6));
        if (payload.event === "route") {
          statusEl.textContent = `Agents: ${(payload.agents || []).join(" → ")}`;
        } else if (payload.event === "handoff") {
          statusEl.textContent = `Handoff ${payload.from} → ${payload.to}`;
        } else if (payload.event === "agent") {
          statusEl.textContent = `${payload.agent} ${payload.status}`;
        } else if (payload.event === "synthesize") {
          statusEl.textContent = "Synthesizing structured answer…";
        } else if (payload.event === "reflection") {
          statusEl.textContent = "Reflection pass…";
        } else if (payload.event === "hitl") {
          statusEl.textContent = "HITL gate — awaiting approval";
        } else if (payload.event === "blocked") {
          renderAnswer(
            {
              summary:
                "I can't run that request. It looks like prompt-injection or a policy bypass attempt.",
              insights: payload.notes || [],
              recommended_actions: ["Ask a loyalty analytics question instead."],
              confidence: 1,
              guarded: true,
              agents_invoked: [],
              sql_used: [],
            },
            { blocked: true },
          );
          statusEl.textContent = "Blocked by input guardrails.";
        } else if (payload.event === "answer" && payload.answer) {
          renderAnswer(payload.answer, { runId: payload.run_id });
          statusEl.textContent =
            payload.answer.hitl_status === "pending"
              ? "Paused for human approval."
              : "Done. Trace persisted under data/traces.";
        }
      }
    }
  } catch (err) {
    statusEl.textContent = `Error: ${err.message}`;
  } finally {
    send.disabled = false;
  }
});

setEmpty();
refreshHealth();
