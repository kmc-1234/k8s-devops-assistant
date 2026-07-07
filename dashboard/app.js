const h = React.createElement;

const quickNamespaces = ["default", "devops-assistant", "argocd", "ingress-nginx", "kube-system"];
const severityOrder = ["critical", "warning", "info"];

function App() {
  const [namespace, setNamespace] = React.useState("ingress-nginx");
  const [pod, setPod] = React.useState("");
  const [deployment, setDeployment] = React.useState("");
  const [useAi, setUseAi] = React.useState(false);
  const [sendAlert, setSendAlert] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [health, setHealth] = React.useState("checking");
  const [error, setError] = React.useState("");
  const [diagnosis, setDiagnosis] = React.useState(null);

  React.useEffect(() => {
    fetch("/healthz")
      .then((response) => {
        if (!response.ok) throw new Error("Health endpoint failed");
        return response.json();
      })
      .then(() => setHealth("ok"))
      .catch(() => setHealth("bad"));
  }, []);

  React.useEffect(() => {
    runDiagnosis("ingress-nginx");
  }, []);

  function runDiagnosis(nextNamespace) {
    const selectedNamespace = (nextNamespace || namespace || "default").trim();
    const params = new URLSearchParams({ namespace: selectedNamespace });
    if (pod.trim()) params.set("pod", pod.trim());
    if (deployment.trim()) params.set("deployment", deployment.trim());
    if (useAi) params.set("ai", "true");
    if (sendAlert) params.set("notify", "true");

    setNamespace(selectedNamespace);
    setLoading(true);
    setError("");

    fetch(`/diagnose?${params.toString()}`)
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "Diagnosis failed");
        return payload;
      })
      .then(setDiagnosis)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }

  const counts = countFindings(diagnosis);
  const highestSeverity = getHighestSeverity(counts);

  return h(
    "div",
    { className: "shell" },
    h(Header, { health }),
    h(
      "main",
      { className: "main" },
      h(
        "div",
        { className: "workspace" },
        h(ControlPanel, {
          namespace,
          setNamespace,
          pod,
          setPod,
          deployment,
          setDeployment,
          useAi,
          setUseAi,
          sendAlert,
          setSendAlert,
          loading,
          runDiagnosis,
        }),
        h(
          "section",
          { className: "content" },
          error ? h("div", { className: "error" }, error) : null,
          h(Metrics, { counts, diagnosis }),
          h(Summary, { diagnosis, highestSeverity }),
          h(Findings, { diagnosis, loading })
        )
      )
    )
  );
}

function Header({ health }) {
  const label = health === "ok" ? "API online" : health === "bad" ? "API offline" : "Checking API";
  return h(
    "header",
    { className: "topbar" },
    h(
      "div",
      { className: "topbar-inner" },
      h(
        "div",
        { className: "brand" },
        h("div", { className: "mark" }, "K8s"),
        h(
          "div",
          null,
          h("h1", null, "Kubernetes DevOps Assistant"),
          h("p", null, "Cluster diagnostics, pod health, logs, and recommended kubectl actions")
        )
      ),
      h(
        "div",
        { className: "status-pill" },
        h("span", { className: `status-dot ${health === "ok" ? "ok" : health === "bad" ? "bad" : ""}` }),
        label
      )
    )
  );
}

function ControlPanel(props) {
  return h(
    "aside",
    { className: "panel control-panel" },
    h(
      "div",
      { className: "panel-header" },
      h("h2", null, "Diagnostic Target"),
      h("p", null, "Run read-only analysis against a namespace, pod, or deployment.")
    ),
    h(
      "form",
      {
        className: "form",
        onSubmit: (event) => {
          event.preventDefault();
          props.runDiagnosis();
        },
      },
      h(Field, {
        label: "Namespace",
        value: props.namespace,
        onChange: props.setNamespace,
        placeholder: "ingress-nginx",
      }),
      h(Field, {
        label: "Pod",
        value: props.pod,
        onChange: props.setPod,
        placeholder: "optional pod name",
      }),
      h(Field, {
        label: "Deployment",
        value: props.deployment,
        onChange: props.setDeployment,
        placeholder: "optional deployment name",
      }),
      h(
        "label",
        { className: "toggle" },
        h("input", {
          type: "checkbox",
          checked: props.useAi,
          onChange: (event) => props.setUseAi(event.target.checked),
        }),
        h("span", null, "Include AI summary")
      ),
      h(
        "label",
        { className: "toggle" },
        h("input", {
          type: "checkbox",
          checked: props.sendAlert,
          onChange: (event) => props.setSendAlert(event.target.checked),
        }),
        h("span", null, "Send email alert")
      ),
      h(
        "button",
        { className: "primary", disabled: props.loading, type: "submit" },
        props.loading ? h("span", { className: "loader" }) : "Run Diagnosis"
      )
    ),
    h(
      "div",
      { className: "quick-list" },
      h("div", { className: "section-title" }, "Quick Namespaces"),
      h(
        "div",
        { className: "quick-buttons" },
        quickNamespaces.map((item) =>
          h(
            "button",
            {
              className: "chip",
              key: item,
              onClick: () => props.runDiagnosis(item),
              type: "button",
            },
            item
          )
        )
      )
    )
  );
}

function Field({ label, value, onChange, placeholder }) {
  return h(
    "div",
    { className: "field" },
    h("label", null, label),
    h("input", {
      value,
      placeholder,
      onChange: (event) => onChange(event.target.value),
    })
  );
}

function Metrics({ counts, diagnosis }) {
  return h(
    "div",
    { className: "summary-grid" },
    h(Metric, { label: "Critical", value: counts.critical, note: "Immediate attention" }),
    h(Metric, { label: "Warnings", value: counts.warning, note: "Needs review" }),
    h(Metric, { label: "Info", value: counts.info, note: "Operational notes" }),
    h(Metric, {
      label: "Findings",
      value: diagnosis ? diagnosis.findings.length : 0,
      note: diagnosis ? diagnosis.namespace : "No namespace loaded",
    })
  );
}

function Metric({ label, value, note }) {
  return h(
    "div",
    { className: "panel metric" },
    h("span", null, label),
    h("strong", null, value),
    h("small", null, note)
  );
}

function Summary({ diagnosis, highestSeverity }) {
  if (!diagnosis) {
    return h("div", { className: "panel empty" }, h("strong", null, "No diagnosis loaded"));
  }

  return h(
    "div",
    { className: "panel summary-card" },
    h(
      "div",
      { className: "summary-line" },
      h(
        "div",
        null,
        h("h2", { className: "section-title" }, diagnosis.namespace),
        h("p", null, diagnosis.summary || "No summary returned.")
      ),
      h("span", { className: `badge ${highestSeverity}` }, labelForSeverity(highestSeverity))
    ),
    diagnosis.notification ? h(NotificationStatus, { notification: diagnosis.notification }) : null,
    diagnosis.ai_summary
      ? h(
          "div",
          { className: "subsection" },
          h("div", { className: "subsection-title" }, "AI Summary"),
          h("p", null, diagnosis.ai_summary)
        )
      : null
  );
}

function NotificationStatus({ notification }) {
  const status = notification.sent ? "sent" : "not sent";
  const detail = notification.error || notification.reason || `${notification.finding_count || 0} alert finding(s)`;
  return h(
    "div",
    { className: `notification-status ${notification.sent ? "sent" : "skipped"}` },
    h("strong", null, `Notification ${status}`),
    h("span", null, detail)
  );
}

function Findings({ diagnosis, loading }) {
  if (loading) {
    return h("div", { className: "panel empty" }, h("strong", null, "Running cluster checks"));
  }
  if (!diagnosis) {
    return h("div", { className: "panel empty" }, h("strong", null, "Run a diagnosis"));
  }
  if (!diagnosis.findings.length) {
    return h(
      "div",
      { className: "panel empty" },
      h("strong", null, "No active issues detected"),
      h("p", null, "The assistant did not find common Kubernetes failure patterns for this target.")
    );
  }

  const sorted = [...diagnosis.findings].sort(
    (a, b) => severityOrder.indexOf(a.severity) - severityOrder.indexOf(b.severity)
  );

  return h(
    "div",
    { className: "findings" },
    sorted.map((finding, index) => h(FindingCard, { finding, key: `${finding.title}-${index}` }))
  );
}

function FindingCard({ finding }) {
  const evidence = (finding.evidence || []).filter(Boolean);
  return h(
    "article",
    { className: `panel finding ${finding.severity}` },
    h(
      "div",
      { className: "finding-head" },
      h("h3", null, finding.title),
      h("span", { className: `badge ${finding.severity}` }, finding.severity)
    ),
    h("p", null, finding.explanation),
    evidence.length
      ? h(
          "div",
          { className: "subsection" },
          h("div", { className: "subsection-title" }, "Evidence"),
          h(
            "ul",
            { className: "evidence-list" },
            evidence.map((item, index) => h("li", { key: index }, item))
          )
        )
      : null,
    finding.recommended_commands && finding.recommended_commands.length
      ? h(
          "div",
          { className: "subsection" },
          h("div", { className: "subsection-title" }, "Recommended Commands"),
          h(
            "div",
            { className: "code-list" },
            finding.recommended_commands.map((command, index) =>
              h("pre", { className: "code-item", key: index }, command)
            )
          )
        )
      : null
  );
}

function countFindings(diagnosis) {
  const counts = { critical: 0, warning: 0, info: 0 };
  if (!diagnosis) return counts;
  diagnosis.findings.forEach((finding) => {
    if (counts[finding.severity] !== undefined) counts[finding.severity] += 1;
  });
  return counts;
}

function getHighestSeverity(counts) {
  if (counts.critical) return "critical";
  if (counts.warning) return "warning";
  if (counts.info) return "info";
  return "ok";
}

function labelForSeverity(severity) {
  if (severity === "critical") return "Critical";
  if (severity === "warning") return "Warning";
  if (severity === "info") return "Informational";
  return "Healthy";
}

ReactDOM.createRoot(document.getElementById("root")).render(h(App));
