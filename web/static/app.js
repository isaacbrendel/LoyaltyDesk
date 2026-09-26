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
    label: "Approve",
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
const versionEl = document.getElementById("version");
const pipelineEl = document.getElementById("pipeline");
const charcount = document.getElementById("charcount");
const grain = document.getElementById("grain");

const sessionId = `web-${crypto.randomUUID().slice(0, 8)}`;

function paintGrain() {
  if (!grain) return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduce) return;
  const w = 128;
  const h = 128;
  grain.width = w;
  grain.height = h;
  const ctx = grain.getContext("2d");
  const img = ctx.createImageData(w, h);
  for (let i = 0; i < img.data.length; i += 4) {
    const v = 220 + Math.random() * 35;
    img.data[i] = v;
    img.data[i + 1] = v;
    img.data[i + 2] = v;
    img.data[i + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
}

function setEmpty() {
  transcript.innerHTML = `
    <div class="empty">
      <strong>Ready when you are</strong>
      Pick a starter or ask about earn/burn rules, campaigns, tiers, member ids, or a production approval.
    </div>`;
}

function addBubble(role, html, extraClass = "") {
  if (transcript.querySelector(".empty")) transcript.innerHTML = "";
  const div = document.createElement("div");
  div.className = `bubble ${role} ${extraClass}`.trim();
  div.innerHTML = html;
  transcript.appendChild(div);
  transcript.scrollTop = transcript.scrollHeight;
  return div;
}

function showSkeleton() {
  if (transcript.querySelector(".empty")) transcript.innerHTML = "";
  const el = document.createElement("div");
  el.className = "skeleton";
  el.id = "pending-skeleton";
  el.innerHTML = `<div class="bar"></div><div class="bar"></div><div class="bar short"></div>`;
  transcript.appendChild(el);
  transcript.scrollTop = transcript.scrollHeight;
}

function clearSkeleton() {
  document.getElementById("pending-skeleton")?.remove();
}

async function resolveHitl(runId, approve) {
  statusEl.textContent = approve ? "Recording approval…" : "Recording rejection…";
  pipelineEl.textContent = "approval";
  try {
    const res = await fetch(`/api/hitl/${runId}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        approve,
        note: approve ? "Approved from LoyaltyDesk UI" : "Rejected from LoyaltyDesk UI",
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Approval failed");
    if (data.answer) {
      renderAnswer(data.answer, { runId });
    } else {
      addBubble(
        "assistant",
        `<h3>Approval ${escapeHtml(data.status)}</h3><p>Request <code>${escapeHtml(runId)}</code> was <strong>${escapeHtml(data.status)}</strong>.</p>`,
      );
    }
    statusEl.textContent = `Marked ${data.status}.`;
    pipelineEl.textContent = "Idle";
  } catch (err) {
    addBubble("assistant", `<h3>Error</h3><p>${escapeHtml(err.message)}</p>`, "error");
    statusEl.textContent = err.message;
  }
}

function metricChips(notes = []) {
  return notes
    .filter((n) => n.startsWith("faithfulness=") || n.startsWith("groundedness="))
    .map((n) => `<span class="chip ok">${escapeHtml(n)}</span>`)
    .join("");
}

function renderAnswer(answer, meta = {}) {
  clearSkeleton();
  const chips = [];
  chips.push(`<span class="chip ok">confidence ${(answer.confidence * 100).toFixed(0)}%</span>`);
  if (answer.guarded) chips.push(`<span class="chip warn">safety checked</span>`);
  if (answer.hitl_status === "pending") chips.push(`<span class="chip danger">needs approval</span>`);
  if (answer.hitl_status === "approved") chips.push(`<span class="chip ok">approved</span>`);
  if (answer.hitl_status === "rejected") chips.push(`<span class="chip danger">rejected</span>`);
  if (meta.blocked) chips.push(`<span class="chip danger">blocked</span>`);
  if ((answer.sql_used || []).length) chips.push(`<span class="chip">SQL evidence</span>`);

  const insights = (answer.insights || []).map((i) => `<li>${escapeHtml(i)}</li>`).join("");
  const actions = (answer.recommended_actions || [])
    .map((i) => `<li>${escapeHtml(i)}</li>`)
    .join("");
  const sql = (answer.sql_used || [])
    .map((s) => `<li><code>${escapeHtml(s)}</code></li>`)
    .join("");
  const reflection = (answer.reflection_notes || [])
    .map((i) => `<li>${escapeHtml(i)}</li>`)
    .join("");
  const traces = (meta.traces || [])
    .slice(-8)
    .map((t) => `<li><code>${escapeHtml(t.span)}</code> ${escapeHtml(t.role || "")}</li>`)
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
      ${reflection ? `<p style="margin-top:.75rem"><strong>Quality check</strong></p><ul class="list">${reflection}</ul>` : ""}
      ${hitlControls}
      ${traces ? `<details class="trace"><summary>What ran behind the scenes</summary><ul class="list">${traces}</ul></details>` : ""}
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
  btn.innerHTML = `<strong>${p.label}</strong><span>${escapeHtml(p.text)}</span>`;
  btn.addEventListener("click", () => {
    message.value = p.text;
    message.dispatchEvent(new Event("input"));
    message.focus();
  });
  promptsEl.appendChild(btn);
});

message.addEventListener("input", () => {
  charcount.textContent = `${message.value.length} / 4000`;
});

async function refreshHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    healthEl.textContent = data.warehouse_ready ? "warehouse ready" : "warehouse missing";
    providerEl.textContent = `llm: ${data.llm_provider}`;
    versionEl.textContent = `v${data.version}`;
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
  message.dispatchEvent(new Event("input"));
  send.disabled = true;
  statusEl.textContent = "Working…";
  pipelineEl.textContent = "routing";
  showSkeleton();

  try {
    const res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);

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
          pipelineEl.textContent = (payload.agents || []).join(" → ") || "routing";
          statusEl.textContent = "Figuring out which specialists to use…";
        } else if (payload.event === "handoff") {
          const dest = Array.isArray(payload.to) ? payload.to.join(", ") : payload.to;
          statusEl.textContent = `Handing off to ${dest}`;
          pipelineEl.textContent = dest;
        } else if (payload.event === "tools") {
          statusEl.textContent = `Querying data (${(payload.tools || []).join(", ")})…`;
        } else if (payload.event === "agent") {
          statusEl.textContent = `${payload.agent.replaceAll("_", " ")} ${payload.status}`;
          pipelineEl.textContent = payload.agent;
        } else if (payload.event === "synthesize") {
          statusEl.textContent = "Writing the answer…";
          pipelineEl.textContent = "answer";
        } else if (payload.event === "reflection") {
          statusEl.textContent = "Double-checking the evidence…";
          pipelineEl.textContent = "check";
        } else if (payload.event === "hitl") {
          statusEl.textContent =
            payload.status === "pending"
              ? "Needs your approval before anything ships"
              : `Approval ${payload.status}`;
          pipelineEl.textContent = "approval";
        } else if (payload.event === "blocked") {
          clearSkeleton();
          renderAnswer(
            {
              summary:
                "I can't run that request — it looks unsafe or like a policy bypass attempt.",
              insights: payload.notes || [],
              recommended_actions: ["Ask a normal loyalty analytics question instead."],
              confidence: 1,
              guarded: true,
              agents_invoked: [],
              sql_used: [],
            },
            { blocked: true },
          );
          statusEl.textContent = "Blocked for safety.";
          pipelineEl.textContent = "Idle";
        } else if (payload.event === "answer" && payload.answer) {
          renderAnswer(payload.answer, {
            runId: payload.run_id,
            traces: payload.traces,
            otel: payload.otel_trace_id,
          });
          const latency = payload.latency_ms != null ? ` · ${payload.latency_ms} ms` : "";
          statusEl.textContent =
            payload.answer.hitl_status === "pending"
              ? `Waiting on your Approve / Reject${latency}`
              : `Done${latency}`;
          pipelineEl.textContent = "Idle";
        }
      }
    }
  } catch (err) {
    clearSkeleton();
    addBubble("assistant", `<h3>Error</h3><p>${escapeHtml(err.message)}</p>`, "error");
    statusEl.textContent = `Error: ${err.message}`;
    pipelineEl.textContent = "error";
  } finally {
    send.disabled = false;
  }
});

paintGrain();
setEmpty();
refreshHealth();
