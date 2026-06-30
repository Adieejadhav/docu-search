import type { ReactNode } from "react";
import { Link } from "react-router-dom";

type BlueprintPage =
  | "audit-access"
  | "chunks"
  | "connectors"
  | "documents"
  | "document-detail"
  | "evaluations"
  | "feedback"
  | "firewall"
  | "jobs-workers"
  | "knowledge-bases"
  | "models-prompts"
  | "pipeline"
  | "playground"
  | "retrieval-profiles"
  | "traces"
  | "usage-cost"
  | "vector-indexes"
  | "settings";

type BadgeTone = "danger" | "info" | "mute" | "ok" | "warn";

export function AdminBlueprintPage({ page }: { page: BlueprintPage }) {
  switch (page) {
    case "knowledge-bases":
      return <KnowledgeBasesPage />;
    case "documents":
      return <DocumentsPage />;
    case "document-detail":
      return <DocumentDetailPage />;
    case "pipeline":
      return <PipelineMonitorPage />;
    case "chunks":
      return <ChunkManagementPage />;
    case "vector-indexes":
      return <VectorIndexesPage />;
    case "retrieval-profiles":
      return <RetrievalProfilesPage />;
    case "playground":
      return <QueryPlaygroundPage />;
    case "models-prompts":
      return <ModelsPromptsPage />;
    case "traces":
      return <TraceExplorerPage />;
    case "evaluations":
      return <EvaluationCenterPage />;
    case "feedback":
      return <FeedbackReviewPage />;
    case "firewall":
      return <FirewallPage />;
    case "connectors":
      return <ConnectorsPage />;
    case "usage-cost":
      return <UsageCostPage />;
    case "jobs-workers":
      return <JobsWorkersPage />;
    case "audit-access":
      return <AuditAccessPage />;
    case "settings":
      return <SystemSettingsPage />;
    default:
      return null;
  }
}

function KnowledgeBasesPage() {
  return (
    <BlueprintPageShell>
      <MetricGrid columns={4}>
        <Metric label="Knowledge bases" value="4" detail="3 production, 1 sandbox" />
        <Metric label="Documents" value="10" detail="all indexed" tone="ok" />
        <Metric label="Owners" value="6" detail="domain admins" />
        <Metric label="Sync health" value="98%" detail="connector SLA" tone="ok" />
      </MetricGrid>
      <Panel title="Knowledge Bases">
        <DataTable
          columns={["Name", "Owner", "Documents", "Vectors", "Last sync", "Status", "Action"]}
          rows={[
            ["HR Policy", "People Ops", "4", "112", "8m ago", <Badge tone="ok">healthy</Badge>, <ButtonLink to="/admin/documents">Open</ButtonLink>],
            ["Finance SOP", "Finance", "3", "86", "22m ago", <Badge tone="ok">healthy</Badge>, <ButtonLink to="/admin/documents">Open</ButtonLink>],
            ["Legal FAQ", "Legal", "2", "61", "7d ago", <Badge tone="warn">stale</Badge>, <ButtonLink to="/admin/documents">Review</ButtonLink>],
            ["Vendor Ops", "Procurement", "1", "23", "2h ago", <Badge tone="ok">ready</Badge>, <ButtonLink to="/admin/documents">Open</ButtonLink>],
          ]}
        />
      </Panel>
      <TwoColumnLayout>
        <Panel title="Indexing Policy">
          <KeyValueGrid
            items={[
              ["Default parser", "PDF + DOCX"],
              ["Chunk policy", "800 / 120 overlap"],
              ["Embedding", "bge-small-en-v1.5"],
              ["Retention", "Versioned documents"],
            ]}
          />
        </Panel>
        <Panel title="Operational Backlog">
          <AlertList
            items={[
              ["Legal FAQ connector has not synced in 7 days", "Reconnect", "warn"],
              ["Add evaluation set for Vendor Ops", "Create", "info"],
              ["No missing vectors detected", "Inspect", "ok"],
            ]}
          />
        </Panel>
      </TwoColumnLayout>
    </BlueprintPageShell>
  );
}

function DocumentsPage() {
  return (
    <BlueprintPageShell>
      <FilterBar placeholder="Search documents, owners, tags, or source paths" chips={["All KBs", "Indexed", "PDF", "Last 30 days"]} />
      <Panel title="Documents">
        <DataTable
          columns={["Document", "KB", "Version", "Chunks", "Vectors", "Updated", "Status", "Action"]}
          rows={[
            ["HR Policy.pdf", "HR Policy", "v4", "42", "42", "8m ago", <Badge tone="ok">indexed</Badge>, <ButtonLink to="/admin/documents/detail">Open</ButtonLink>],
            ["Finance SOP.pdf", "Finance SOP", "v2", "51", "51", "22m ago", <Badge tone="ok">indexed</Badge>, <ButtonLink to="/admin/documents/detail">Open</ButtonLink>],
            ["Contract Renewal.pdf", "Legal FAQ", "v1", "31", "31", "7d ago", <Badge tone="warn">review</Badge>, <ButtonLink to="/admin/documents/detail">Open</ButtonLink>],
            ["Vendor SOP.docx", "Vendor Ops", "v3", "23", "23", "2h ago", <Badge tone="ok">indexed</Badge>, <ButtonLink to="/admin/documents/detail">Open</ButtonLink>],
          ]}
        />
      </Panel>
      <TwoColumnLayout>
        <Panel title="Bulk Actions">
          <ActionStack actions={["Upload documents", "Re-index selected", "Export metadata", "Run firewall scan"]} primary="Upload documents" />
        </Panel>
        <Panel title="Document Quality Checks">
          <QualityGrid
            metrics={[
              ["100%", "Vector coverage"],
              ["0", "Failed parses"],
              ["2", "Sensitive findings"],
              ["91%", "Avg groundedness"],
            ]}
          />
        </Panel>
      </TwoColumnLayout>
    </BlueprintPageShell>
  );
}

function DocumentDetailPage() {
  return (
    <BlueprintPageShell>
      <section className="admin-doc-hero">
        <div>
          <h2>HR Policy.pdf</h2>
          <p>Knowledge base: HR Policy · Version v4 · Indexed 8 minutes ago</p>
          <div className="blueprint-chip-row">
            <Badge tone="ok">indexed</Badge>
            <Badge tone="info">42 chunks</Badge>
            <Badge tone="info">42 vectors</Badge>
            <Badge tone="mute">owner: People Ops</Badge>
          </div>
        </div>
        <div className="score-ring">94<span>quality</span></div>
      </section>
      <ThreeColumnLayout
        left={
          <Panel title="Document Metadata">
            <KeyValueGrid
              items={[
                ["Source", "Google Drive"],
                ["Parser", "PDF text"],
                ["Language", "English"],
                ["Access", "HR-only"],
                ["Checksum", "sha256:82af..."],
                ["Retention", "Active"],
              ]}
            />
          </Panel>
        }
        middle={
          <Panel title="Extracted Source Preview">
            <div className="blueprint-text-box">
              Employees may retain internal documents only for approved business purposes. Personal data must be minimized, access must be logged, and expired records must be reviewed according to HR retention policy.
            </div>
          </Panel>
        }
        right={
          <Panel title="Actions">
            <ActionStack actions={["Re-index document", "Open source file", "Create eval case", "Flag for review"]} primary="Re-index document" />
          </Panel>
        }
      />
      <Panel title="Chunk Preview">
        <DataTable
          columns={["Chunk", "Parent", "Tokens", "Embedding", "Quality", "Action"]}
          rows={[
            ["child_001", "parent_001", "214", <Badge tone="ok">ready</Badge>, "94%", <ButtonLink to="/admin/chunks">Inspect</ButtonLink>],
            ["child_002", "parent_001", "188", <Badge tone="ok">ready</Badge>, "92%", <ButtonLink to="/admin/chunks">Inspect</ButtonLink>],
            ["child_003", "parent_002", "231", <Badge tone="ok">ready</Badge>, "90%", <ButtonLink to="/admin/chunks">Inspect</ButtonLink>],
          ]}
        />
      </Panel>
    </BlueprintPageShell>
  );
}

function PipelineMonitorPage() {
  return (
    <BlueprintPageShell>
      <MetricGrid columns={5}>
        <Metric label="Queued" value="0" detail="waiting" />
        <Metric label="Running" value="1" detail="active job" tone="info" />
        <Metric label="Completed" value="18" detail="last 24h" tone="ok" />
        <Metric label="Failed" value="0" detail="all clear" tone="ok" />
        <Metric label="Avg/doc" value="14.2s" detail="processing" />
      </MetricGrid>
      <Panel title="Pipeline Stage Board">
        <div className="pipeline-board">
          {[
            ["Upload", "10", "completed"],
            ["Extract", "10", "completed"],
            ["Chunk", "10", "completed"],
            ["Embed", "282", "vectors"],
            ["Index", "282", "records"],
            ["Ready", "10", "documents"],
          ].map(([label, value, detail]) => (
            <article key={label}>
              <h4>{label}</h4>
              <b>{value}</b>
              <span>{detail}</span>
            </article>
          ))}
        </div>
      </Panel>
      <Panel title="Active Jobs">
        <DataTable
          columns={["Task", "Document", "Stage", "Status", "Duration", "Progress", "Action"]}
          rows={[
            ["task_7a2", "HR Policy.pdf", "Indexed", <Badge tone="ok">completed</Badge>, "12.4s", <Progress value={100} />, <button type="button">Inspect</button>],
            ["task_7a3", "Legal FAQ.pdf", "Firewall scan", <Badge tone="info">running</Badge>, "6.4s", <Progress value={62} />, <button type="button">Open</button>],
            ["task_7a4", "Vendor SOP.docx", "Index vectors", <Badge tone="ok">completed</Badge>, "18.7s", <Progress value={100} />, <button type="button">Inspect</button>],
          ]}
        />
      </Panel>
    </BlueprintPageShell>
  );
}

function ChunkManagementPage() {
  const chunks = [
    ["child_001", "HR Policy.pdf", "214 tokens", "Retention policy paragraph"],
    ["child_002", "HR Policy.pdf", "188 tokens", "Employee document access rules"],
    ["child_003", "Finance SOP.pdf", "231 tokens", "Approval matrix and audit steps"],
  ];

  return (
    <BlueprintPageShell>
      <ThreeColumnLayout
        left={
          <Panel title="Chunk List">
            <div className="chunk-list">
              {chunks.map(([id, doc, tokens, summary], index) => (
                <article className={index === 0 ? "chunk active" : "chunk"} key={id}>
                  <b>{id}</b>
                  <span>{doc} · {tokens}</span>
                  <p>{summary}</p>
                </article>
              ))}
            </div>
          </Panel>
        }
        middle={
          <Panel title="Chunk Text">
            <div className="blueprint-text-box">
              Retention policy excerpts are split into retrieval-safe passages. Each child chunk maps to a parent chunk, source reference, and vector record so answer citations can be audited.
            </div>
            <div className="admin-flow">
              <span>Document</span><span>Parent chunk</span><span>Child chunk</span><span>Vector</span><span>Citation</span>
            </div>
          </Panel>
        }
        right={
          <Panel title="Inspector">
            <KeyValueGrid
              items={[
                ["Parent", "parent_001"],
                ["Rank", "1"],
                ["Tokens", "214"],
                ["Embedding", "ready"],
                ["Source refs", "2"],
                ["Quality", "94%"],
              ]}
            />
            <ActionStack actions={["Open document", "Create test case", "Exclude chunk"]} />
          </Panel>
        }
      />
    </BlueprintPageShell>
  );
}

function VectorIndexesPage() {
  return (
    <BlueprintPageShell>
      <MetricGrid columns={4}>
        <Metric label="Vector stores" value="1" detail="pgvector" />
        <Metric label="Embeddings" value="282" detail="indexed" tone="ok" />
        <Metric label="Missing vectors" value="0" detail="all clear" tone="ok" />
        <Metric label="Dimensions" value="384" detail="bge-small" />
      </MetricGrid>
      <Panel title="Vector Indexes">
        <DataTable
          columns={["Index", "Provider", "Dimensions", "Records", "Last rebuild", "Status", "Action"]}
          rows={[
            ["main_documents_idx", "PostgreSQL pgvector", "384", "282", "8m ago", <Badge tone="ok">ready</Badge>, <button type="button">Inspect</button>],
            ["eval_candidates_idx", "PostgreSQL pgvector", "384", "86", "1d ago", <Badge tone="ok">ready</Badge>, <button type="button">Inspect</button>],
          ]}
        />
      </Panel>
      <TwoColumnLayout>
        <Panel title="Rebuild Plan">
          <AlertList
            items={[
              ["No full rebuild required", "Verify", "ok"],
              ["Legal FAQ stale source sync", "Sync", "warn"],
              ["Embedding model is consistent across indexes", "View", "ok"],
            ]}
          />
        </Panel>
        <Panel title="Index Diagnostics">
          <KeyValueGrid items={[["Recall sample", "94%"], ["Duplicate vectors", "0"], ["Orphan chunks", "0"], ["Avg query", "38ms"]]} />
        </Panel>
      </TwoColumnLayout>
    </BlueprintPageShell>
  );
}

function RetrievalProfilesPage() {
  return (
    <BlueprintPageShell>
      <Panel title="Retrieval Profiles">
        <DataTable
          columns={["Profile", "KB", "Search", "Top K", "Reranker", "Status", "Action"]}
          rows={[
            ["Production Hybrid", "All", "Hybrid", "8", "on", <Badge tone="ok">active</Badge>, <button type="button">Edit</button>],
            ["Fast Local", "All", "Vector", "5", "off", <Badge tone="info">draft</Badge>, <button type="button">Open</button>],
            ["Legal Strict", "Legal FAQ", "Hybrid", "12", "on", <Badge tone="ok">active</Badge>, <button type="button">Edit</button>],
          ]}
        />
      </Panel>
      <TwoColumnLayout>
        <Panel title="Retrieval Flow">
          <div className="admin-flow">
            <span>User query</span><span>Rewrite</span><span>Hybrid search</span><span>Rerank</span><span>Context pack</span><span>Generate</span>
          </div>
        </Panel>
        <Panel title="Profile Parameters">
          <KeyValueGrid items={[["Top K", "8"], ["BM25 weight", "0.35"], ["Vector weight", "0.65"], ["Max context", "6,000 tokens"]]} />
        </Panel>
      </TwoColumnLayout>
    </BlueprintPageShell>
  );
}

function QueryPlaygroundPage() {
  return (
    <BlueprintPageShell>
      <section className="playground">
        <Panel title="Query Controls">
          <label>Query</label>
          <div className="blueprint-input large">What is the document retention policy?</div>
          <label>Retrieval profile</label>
          <div className="blueprint-select">Production Hybrid</div>
          <label>Knowledge base</label>
          <div className="blueprint-select">All knowledge bases</div>
          <ActionStack actions={["Run Query", "Compare Profile", "Save as Eval Case"]} primary="Run Query" />
        </Panel>
        <Panel title="Generated Answer">
          <div className="blueprint-text-box">
            The document retention policy requires business-purpose retention, minimized personal data, logged access, and periodic review for expired records.
          </div>
          <div className="source-list">
            <article><b>HR Policy.pdf</b><span>chunk_001 · score 0.92 · page 4</span></article>
            <article><b>Finance SOP.pdf</b><span>chunk_021 · score 0.79 · page 11</span></article>
          </div>
        </Panel>
      </section>
      <Panel title="Trace Preview">
        <div className="admin-flow">
          <span>Query rewrite 32ms</span><span>Search 41ms</span><span>Rerank 118ms</span><span>Generate 1.3s</span><span>Citations 22ms</span>
        </div>
      </Panel>
    </BlueprintPageShell>
  );
}

function ModelsPromptsPage() {
  return (
    <BlueprintPageShell>
      <TwoColumnLayout>
        <Panel title="Model Providers">
          <DataTable
            compact
            columns={["Model", "Role", "Host", "Status"]}
            rows={[
              ["gpt-oss:120b-cloud", "Generation", "localhost:11434", <Badge tone="ok">online</Badge>],
              ["bge-small-en-v1.5", "Embedding", "local", <Badge tone="ok">ready</Badge>],
              ["reranker-mini", "Rerank", "local", <Badge tone="info">optional</Badge>],
            ]}
          />
        </Panel>
        <Panel title="Prompt Versions">
          <DataTable
            compact
            columns={["Prompt", "Version", "Eval", "Status", "Action"]}
            rows={[
              ["System QA", "v7", "91%", <Badge tone="ok">production</Badge>, <button type="button">Open</button>],
              ["Citation guardrail", "v3", "88%", <Badge tone="ok">active</Badge>, <button type="button">Open</button>],
              ["No-answer policy", "v2", "96%", <Badge tone="info">candidate</Badge>, <button type="button">Compare</button>],
            ]}
          />
        </Panel>
      </TwoColumnLayout>
      <Panel title="Prompt Diff">
        <div className="blueprint-diff">
          <article><b>Production v7</b><p>Answer only from retrieved sources. Cite every factual claim using available source references.</p></article>
          <article><b>Candidate v8</b><p>Answer only from retrieved sources. If evidence is weak, ask for clarification and mark confidence.</p></article>
        </div>
      </Panel>
    </BlueprintPageShell>
  );
}

function TraceExplorerPage() {
  return (
    <BlueprintPageShell>
      <FilterBar placeholder="Search trace id, query, document, model, or feedback" chips={["All statuses", "Warnings", "Last 7 days", "Production"]} />
      <Panel title="Trace Explorer">
        <DataTable
          columns={["Query", "Status", "Chunks", "Latency", "Grounded", "Model", "Feedback", "Action"]}
          rows={[
            ["What is the document retention policy?", <Badge tone="ok">success</Badge>, "4", "1.6s", "92%", "gpt-oss:120b", "positive", <button type="button">View</button>],
            ["Summarize onboarding steps for HR.", <Badge tone="ok">success</Badge>, "3", "2.1s", "88%", "gpt-oss:120b", "none", <button type="button">View</button>],
            ["Who approved the finance SOP?", <Badge tone="warn">warning</Badge>, "1", "3.2s", "61%", "gpt-oss:120b", "negative", <button type="button">Review</button>],
          ]}
        />
      </Panel>
      <TwoColumnLayout>
        <Panel title="Selected Trace Timeline">
          <div className="trace-steps">
            <article><span>Request received</span><b>0ms</b></article>
            <article><span>Retrieved chunks</span><b>41ms</b></article>
            <article><span>Reranked context</span><b>118ms</b></article>
            <article><span>Generated answer</span><b>1.6s</b></article>
          </div>
        </Panel>
        <Panel title="Trace Risk">
          <QualityGrid metrics={[["61%", "Groundedness"], ["1", "Source chunks"], ["0", "Citations"], ["high", "Review priority"]]} />
        </Panel>
      </TwoColumnLayout>
    </BlueprintPageShell>
  );
}

function EvaluationCenterPage() {
  return (
    <BlueprintPageShell>
      <Panel title="Evaluation Datasets">
        <DataTable
          columns={["Dataset", "KB", "Cases", "Last Run", "Score", "Status", "Action"]}
          rows={[
            ["HR Policy Eval", "HR Policy", "42", "2d ago", "91%", <Badge tone="ok">passed</Badge>, <button type="button">Run</button>],
            ["Legal Eval", "Legal", "28", "7d ago", "84%", <Badge tone="warn">stale</Badge>, <button type="button">Run</button>],
            ["No Answer Eval", "All", "31", "1d ago", "96%", <Badge tone="ok">passed</Badge>, <button type="button">Run</button>],
          ]}
        />
      </Panel>
      <TwoColumnLayout>
        <Panel title="Eval Metrics">
          <QualityGrid metrics={[["93%", "Context precision"], ["89%", "Context recall"], ["91%", "Faithfulness"], ["88%", "Citation accuracy"]]} />
        </Panel>
        <Panel title="Regression Gate">
          <DataTable
            compact
            columns={["Candidate", "Compared To", "Quality Δ", "Latency Δ", "Decision"]}
            rows={[
              ["Prompt v8", "Prompt v7", "+2.1%", "+180ms", <button type="button">Review</button>],
              ["Reranker on", "Reranker off", "+5.4%", "+520ms", <button className="primary" type="button">Approve</button>],
            ]}
          />
        </Panel>
      </TwoColumnLayout>
    </BlueprintPageShell>
  );
}

function FeedbackReviewPage() {
  return (
    <BlueprintPageShell>
      <Panel title="Feedback Queue">
        <DataTable
          columns={["Feedback", "Query", "Reason", "Grounded", "Status", "Action"]}
          rows={[
            ["👎", "Who approved renewal?", "Wrong answer", "61%", <Badge tone="warn">open</Badge>, <button type="button">Review</button>],
            ["👎", "Explain leave policy", "Missing citation", "72%", <Badge tone="warn">open</Badge>, <button type="button">Review</button>],
            ["👍", "Summarize vendor SOP", "Helpful", "88%", <Badge tone="ok">closed</Badge>, <button type="button">Open</button>],
          ]}
        />
      </Panel>
      <Panel title="Review Actions">
        <ActionStack actions={["Create Eval Test Case", "Flag Source Document", "Send to Domain Expert", "Update Prompt Backlog", "Mark Resolved"]} primary="Mark Resolved" inline />
      </Panel>
    </BlueprintPageShell>
  );
}

function FirewallPage() {
  return (
    <BlueprintPageShell>
      <Panel title="Firewall Rules">
        <DataTable
          columns={["Rule", "Scope", "Severity", "Mode", "Hits", "Status", "Action"]}
          rows={[
            ["Secret/API key detector", "Ingestion", "High", "Block", "1", <Badge tone="ok">active</Badge>, <button type="button">Edit</button>],
            ["Prompt injection detector", "Query", "High", "Block", "3", <Badge tone="ok">active</Badge>, <button type="button">Edit</button>],
            ["Missing citation check", "Response", "Medium", "Flag", "2", <Badge tone="ok">active</Badge>, <button type="button">Edit</button>],
            ["Cross-tenant access", "Retrieval", "Critical", "Block", "0", <Badge tone="ok">active</Badge>, <button type="button">Edit</button>],
          ]}
        />
      </Panel>
      <Panel title="Flagged Events">
        <DataTable
          compact
          columns={["Event", "Scope", "Object", "Severity", "Decision", "Action"]}
          rows={[
            ["fw_882", "Document", "Contract Renewal.pdf", "High", "Pending", <button type="button">Review</button>],
            ["fw_881", "Query", "ignore previous instructions", "High", "Blocked", <button type="button">Open</button>],
            ["fw_880", "Response", "missing source citation", "Medium", "Flagged", <button type="button">Review</button>],
          ]}
        />
      </Panel>
    </BlueprintPageShell>
  );
}

function ConnectorsPage() {
  return (
    <BlueprintPageShell>
      <Panel title="Source Connectors">
        <DataTable
          columns={["Connector", "Type", "KB", "Sync", "Last Sync", "Imported", "Auth", "Status", "Action"]}
          rows={[
            ["HR Drive", "Google Drive", "HR Policy", "Hourly", "8m ago", "4", "Connected", <Badge tone="ok">healthy</Badge>, <button type="button">Open</button>],
            ["Finance SOP Bucket", "S3", "Finance SOP", "Daily", "22m ago", "3", "Connected", <Badge tone="ok">healthy</Badge>, <button type="button">Open</button>],
            ["Legal SharePoint", "SharePoint", "Legal", "Daily", "7d ago", "2", "Expired", <Badge tone="warn">failed</Badge>, <button type="button">Reconnect</button>],
            ["Manual Upload", "Upload", "All", "Manual", "2h ago", "1", "N/A", <Badge tone="ok">ready</Badge>, <button type="button">Open</button>],
          ]}
        />
      </Panel>
      <Panel title="Connector Sync Flow">
        <div className="admin-flow">
          <span>Authenticate</span><span>Discover files</span><span>Detect changes</span><span>Import versions</span><span>Run pipeline</span><span>Update KB</span>
        </div>
      </Panel>
    </BlueprintPageShell>
  );
}

function UsageCostPage() {
  return (
    <BlueprintPageShell>
      <TwoColumnLayout>
        <Panel title="Usage by Knowledge Base">
          <DataTable
            columns={["KB", "Queries", "Avg Latency", "Tokens", "Cost", "Trend"]}
            rows={[
              ["HR Policy", "8", "1.6s", "22k", "$0", "↗"],
              ["Finance SOP", "4", "2.0s", "14k", "$0", "→"],
              ["Legal", "3", "3.1s", "15k", "$0", "↘"],
            ]}
          />
        </Panel>
        <Panel title="Budget Controls">
          <KeyValueGrid items={[["Monthly budget", "$100"], ["Used", "$0.00"], ["Max tokens/query", "8,000"], ["Fallback", "Local model"]]} />
          <ActionStack actions={["Update Budget Policy"]} primary="Update Budget Policy" />
        </Panel>
      </TwoColumnLayout>
      <Panel title="Latency Distribution">
        <div className="bars">
          {[34, 58, 76, 44, 28, 62, 39].map((height) => <span key={height} style={{ height: `${height}%` }} />)}
        </div>
      </Panel>
    </BlueprintPageShell>
  );
}

function JobsWorkersPage() {
  return (
    <BlueprintPageShell>
      <TwoColumnLayout>
        <Panel title="Celery Jobs">
          <DataTable
            columns={["Task", "Type", "Object", "Status", "Attempts", "Duration", "Action"]}
            rows={[
              ["task_7a2", "embed_document", "HR Policy.pdf", <Badge tone="ok">success</Badge>, "1", "12.4s", <button type="button">Open</button>],
              ["task_7a3", "firewall_scan", "Legal FAQ.pdf", <Badge tone="info">running</Badge>, "1", "6.4s", <button type="button">Open</button>],
              ["task_7a4", "index_vectors", "Vendor SOP.docx", <Badge tone="ok">success</Badge>, "1", "18.7s", <button type="button">Open</button>],
            ]}
          />
        </Panel>
        <Panel title="Worker Health">
          <div className="worker-list">
            <Worker name="worker-ingest-1" heartbeat="8s ago" />
            <Worker name="worker-embed-1" heartbeat="11s ago" />
            <Worker name="worker-index-1" heartbeat="12s ago" />
          </div>
          <ActionStack actions={["Pause Queue", "Drain Queue", "Retry Failed"]} primary="Retry Failed" />
        </Panel>
      </TwoColumnLayout>
    </BlueprintPageShell>
  );
}

function AuditAccessPage() {
  return (
    <BlueprintPageShell>
      <MetricGrid columns={4}>
        <Metric label="Admin users" value="7" detail="2 super admins" />
        <Metric label="Roles" value="4" detail="least privilege" />
        <Metric label="Audit events" value="128" detail="last 7 days" />
        <Metric label="Sensitive access" value="3" detail="reviewed" tone="warn" />
      </MetricGrid>
      <Panel title="Roles & Permissions">
        <DataTable
          columns={["Role", "Users", "Documents", "Prompts", "Evals", "Firewall", "Audit"]}
          rows={[
            ["Super Admin", "2", "Full", "Full", "Full", "Full", "Full"],
            ["KB Admin", "3", "Manage", "View", "Run", "View", "View"],
            ["RAG Evaluator", "1", "View", "View", "Manage", "View", "View"],
            ["Security Reviewer", "1", "View sensitive", "No", "View", "Manage", "Full"],
          ]}
        />
      </Panel>
      <Panel title="Audit Log">
        <DataTable
          columns={["Time", "Actor", "Action", "Object", "IP", "Result"]}
          rows={[
            ["12:28", "admin", "Re-indexed document", "HR Policy.pdf", "127.0.0.1", "success"],
            ["12:17", "admin", "Changed prompt", "System QA v7", "127.0.0.1", "success"],
            ["11:52", "security", "Reviewed firewall event", "fw_882", "127.0.0.1", "pending"],
          ]}
        />
      </Panel>
    </BlueprintPageShell>
  );
}

function SystemSettingsPage() {
  return (
    <BlueprintPageShell>
      <TwoColumnLayout>
        <Panel title="System Defaults">
          <FormList items={[["Default LLM", "gpt-oss:120b-cloud"], ["Default embedding", "bge-small-en-v1.5"], ["Vector DB", "PostgreSQL pgvector"], ["Default retrieval", "Hybrid + reranker"]]} />
          <ActionStack actions={["Save Defaults"]} primary="Save Defaults" />
        </Panel>
        <Panel title="RAG Behavior">
          <FormList items={[["Chunk size", "800 tokens"], ["Chunk overlap", "120 tokens"], ["Top K", "8"], ["Max context tokens", "6000"]]} />
          <ActionStack actions={["Save RAG Config"]} primary="Save RAG Config" />
        </Panel>
      </TwoColumnLayout>
      <TwoColumnLayout>
        <Panel title="Feature Flags">
          <ToggleList items={[["Query rewrite", true], ["Citations required", true], ["User feedback", true], ["Public sharing", false], ["Eval gate", true]]} />
        </Panel>
        <Panel title="Environment Health">
          <KeyValueGrid items={[["API base", "http://localhost:8000/api"], ["Admin UI", "http://127.0.0.1:5174/admin"], ["LLM host", "localhost:11434"], ["Database", "PostgreSQL + pgvector"], ["Queue", "Celery + Redis"], ["Storage", "Local / S3 ready"]]} />
        </Panel>
      </TwoColumnLayout>
    </BlueprintPageShell>
  );
}

function BlueprintPageShell({ children }: { children: ReactNode }) {
  return <div className="blueprint-page">{children}</div>;
}

function Panel({
  children,
  title,
}: {
  children: ReactNode;
  title: string;
}) {
  return (
    <section className="blueprint-panel">
      <header>
        <h2>{title}</h2>
      </header>
      <div className="blueprint-panel-body">{children}</div>
    </section>
  );
}

function MetricGrid({
  children,
  columns,
}: {
  children: ReactNode;
  columns: 4 | 5;
}) {
  return <section className={`blueprint-metric-grid columns-${columns}`}>{children}</section>;
}

function Metric({
  detail,
  label,
  tone,
  value,
}: {
  detail: string;
  label: string;
  tone?: "info" | "ok" | "warn";
  value: string;
}) {
  return (
    <article className={["blueprint-metric", tone].filter(Boolean).join(" ")}>
      <div>
        <span>{label}</span>
        <i>⌁</i>
      </div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function DataTable({
  columns,
  compact,
  rows,
}: {
  columns: string[];
  compact?: boolean;
  rows: ReactNode[][];
}) {
  return (
    <div className="blueprint-table-wrap">
      <table className={compact ? "blueprint-table compact" : "blueprint-table"}>
        <thead>
          <tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => <td key={`${rowIndex}-${cellIndex}`}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Badge({ children, tone }: { children: ReactNode; tone: BadgeTone }) {
  return <span className={`blueprint-badge ${tone}`}>{children}</span>;
}

function ButtonLink({ children, to }: { children: ReactNode; to: string }) {
  return <Link className="blueprint-button-link" to={to}>{children}</Link>;
}

function TwoColumnLayout({ children }: { children: ReactNode }) {
  return <section className="blueprint-layout two">{children}</section>;
}

function ThreeColumnLayout({
  left,
  middle,
  right,
}: {
  left: ReactNode;
  middle: ReactNode;
  right: ReactNode;
}) {
  return (
    <section className="blueprint-layout three">
      {left}
      {middle}
      {right}
    </section>
  );
}

function FilterBar({ chips, placeholder }: { chips: string[]; placeholder: string }) {
  return (
    <section className="blueprint-filterbar">
      <div className="blueprint-search">{placeholder}</div>
      {chips.map((chip) => <span key={chip}>{chip}</span>)}
    </section>
  );
}

function KeyValueGrid({ items }: { items: [string, string][] }) {
  return (
    <div className="blueprint-kv-grid">
      {items.map(([label, value]) => (
        <article key={label}>
          <span>{label}</span>
          <b>{value}</b>
        </article>
      ))}
    </div>
  );
}

function AlertList({ items }: { items: [string, string, BadgeTone][] }) {
  return (
    <div className="blueprint-alert-list">
      {items.map(([label, action, tone]) => (
        <article className={tone} key={label}>
          <span>{label}</span>
          <button type="button">{action}</button>
        </article>
      ))}
    </div>
  );
}

function ActionStack({
  actions,
  inline,
  primary,
}: {
  actions: string[];
  inline?: boolean;
  primary?: string;
}) {
  return (
    <div className={inline ? "blueprint-action-stack inline" : "blueprint-action-stack"}>
      {actions.map((action) => (
        <button className={action === primary ? "primary" : undefined} key={action} type="button">
          {action}
        </button>
      ))}
    </div>
  );
}

function QualityGrid({ metrics }: { metrics: [string, string][] }) {
  return (
    <div className="blueprint-quality-grid">
      {metrics.map(([value, label]) => (
        <article key={label}>
          <b>{value}</b>
          <span>{label}</span>
        </article>
      ))}
    </div>
  );
}

function Progress({ value }: { value: number }) {
  return (
    <div className="blueprint-progress" aria-label={`${value}% complete`}>
      <i style={{ width: `${value}%` }} />
    </div>
  );
}

function Worker({ heartbeat, name }: { heartbeat: string; name: string }) {
  return (
    <article>
      <b>{name}</b>
      <Badge tone="ok">online</Badge>
      <small>heartbeat {heartbeat}</small>
    </article>
  );
}

function FormList({ items }: { items: [string, string][] }) {
  return (
    <div className="blueprint-form-list">
      {items.map(([label, value]) => (
        <label key={label}>
          <span>{label}</span>
          <div>{value}</div>
        </label>
      ))}
    </div>
  );
}

function ToggleList({ items }: { items: [string, boolean][] }) {
  return (
    <div className="blueprint-toggle-list">
      {items.map(([label, enabled]) => (
        <article className={enabled ? "on" : "off"} key={label}>
          <span>{label}</span>
          <b>{enabled ? "on" : "off"}</b>
        </article>
      ))}
    </div>
  );
}
