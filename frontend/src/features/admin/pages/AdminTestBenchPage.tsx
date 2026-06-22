import { useEffect, useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  useNodesState,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  BadgeCheck,
  Binary,
  Boxes,
  BrainCircuit,
  Braces,
  Check,
  CircleAlert,
  Clock3,
  Database,
  FileSearch,
  LoaderCircle,
  Play,
  RotateCcw,
  Search,
  Upload,
} from "lucide-react";
import { messageFromError, scorePercent } from "../../../lib/format";
import {
  askDocuments,
  searchDocuments,
  testPipelineNode,
} from "../../../services/api";
import type {
  AskResponse,
  PipelineNodeStage,
  PipelineNodeTestResponse,
  SearchResponse,
} from "../../../services/types";

type PipelineNodeId = PipelineNodeStage | "retrieve" | "generate";
type PipelineNodeStatus = "idle" | "running" | "completed" | "failed";

interface PipelineNodeData extends Record<string, unknown> {
  active: boolean;
  category: string;
  description: string;
  durationMs?: number;
  icon: PipelineNodeId;
  label: string;
  sourcePosition: Position;
  status: PipelineNodeStatus;
  step: number;
  targetPosition: Position;
}

type PipelineFlowNode = Node<PipelineNodeData, "pipeline">;

interface PipelineExecutionResult {
  durationMs: number;
  preview: Array<Record<string, unknown>>;
  summary: Record<string, unknown>;
}

interface NodeTone {
  bar: string;
  button: string;
  edge: string;
  handle: string;
  icon: string;
  ring: string;
  step: string;
  surface: string;
}

const EXAMPLE_QUERY = "Which policy mentions the 14-day satellite-mode exception?";
const FILE_NODE_IDS = new Set<PipelineNodeId>([
  "validate",
  "parse",
  "chunk",
  "embed",
  "index",
]);

const NODE_TONES: Record<PipelineNodeId, NodeTone> = {
  validate: {
    bar: "bg-teal-500",
    button: "bg-teal-600 hover:bg-teal-700 focus-visible:ring-teal-300",
    edge: "#14b8a6",
    handle: "!bg-teal-500",
    icon: "bg-teal-500 text-white",
    ring: "shadow-[0_0_0_6px_rgba(20,184,166,0.16),0_16px_32px_rgba(15,23,42,0.12)]",
    step: "bg-teal-100 text-teal-800",
    surface: "border-teal-400 bg-teal-50 text-teal-950",
  },
  parse: {
    bar: "bg-violet-500",
    button: "bg-violet-600 hover:bg-violet-700 focus-visible:ring-violet-300",
    edge: "#8b5cf6",
    handle: "!bg-violet-500",
    icon: "bg-violet-500 text-white",
    ring: "shadow-[0_0_0_6px_rgba(139,92,246,0.15),0_16px_32px_rgba(15,23,42,0.12)]",
    step: "bg-violet-100 text-violet-800",
    surface: "border-violet-400 bg-violet-50 text-violet-950",
  },
  chunk: {
    bar: "bg-amber-500",
    button: "bg-amber-600 hover:bg-amber-700 focus-visible:ring-amber-300",
    edge: "#f59e0b",
    handle: "!bg-amber-500",
    icon: "bg-amber-500 text-white",
    ring: "shadow-[0_0_0_6px_rgba(245,158,11,0.16),0_16px_32px_rgba(15,23,42,0.12)]",
    step: "bg-amber-100 text-amber-800",
    surface: "border-amber-400 bg-amber-50 text-amber-950",
  },
  embed: {
    bar: "bg-sky-500",
    button: "bg-sky-600 hover:bg-sky-700 focus-visible:ring-sky-300",
    edge: "#0ea5e9",
    handle: "!bg-sky-500",
    icon: "bg-sky-500 text-white",
    ring: "shadow-[0_0_0_6px_rgba(14,165,233,0.16),0_16px_32px_rgba(15,23,42,0.12)]",
    step: "bg-sky-100 text-sky-800",
    surface: "border-sky-400 bg-sky-50 text-sky-950",
  },
  index: {
    bar: "bg-indigo-500",
    button: "bg-indigo-600 hover:bg-indigo-700 focus-visible:ring-indigo-300",
    edge: "#6366f1",
    handle: "!bg-indigo-500",
    icon: "bg-indigo-500 text-white",
    ring: "shadow-[0_0_0_6px_rgba(99,102,241,0.15),0_16px_32px_rgba(15,23,42,0.12)]",
    step: "bg-indigo-100 text-indigo-800",
    surface: "border-indigo-400 bg-indigo-50 text-indigo-950",
  },
  retrieve: {
    bar: "bg-rose-500",
    button: "bg-rose-600 hover:bg-rose-700 focus-visible:ring-rose-300",
    edge: "#f43f5e",
    handle: "!bg-rose-500",
    icon: "bg-rose-500 text-white",
    ring: "shadow-[0_0_0_6px_rgba(244,63,94,0.15),0_16px_32px_rgba(15,23,42,0.12)]",
    step: "bg-rose-100 text-rose-800",
    surface: "border-rose-400 bg-rose-50 text-rose-950",
  },
  generate: {
    bar: "bg-emerald-500",
    button: "bg-emerald-600 hover:bg-emerald-700 focus-visible:ring-emerald-300",
    edge: "#10b981",
    handle: "!bg-emerald-500",
    icon: "bg-emerald-500 text-white",
    ring: "shadow-[0_0_0_6px_rgba(16,185,129,0.16),0_16px_32px_rgba(15,23,42,0.12)]",
    step: "bg-emerald-100 text-emerald-800",
    surface: "border-emerald-400 bg-emerald-50 text-emerald-950",
  },
};

const NODE_DEFINITIONS: Array<{
  id: PipelineNodeId;
  label: string;
  category: string;
  description: string;
  position: { x: number; y: number };
  targetPosition: Position;
  sourcePosition: Position;
}> = [
  {
    id: "validate",
    label: "Validate File",
    category: "Input",
    description: "Type, size and content checks",
    position: { x: 20, y: 30 },
    targetPosition: Position.Left,
    sourcePosition: Position.Right,
  },
  {
    id: "parse",
    label: "Parse & Normalize",
    category: "Document",
    description: "Structured normalized blocks",
    position: { x: 215, y: 30 },
    targetPosition: Position.Left,
    sourcePosition: Position.Right,
  },
  {
    id: "chunk",
    label: "Create Chunks",
    category: "Transform",
    description: "Parent and child contexts",
    position: { x: 410, y: 30 },
    targetPosition: Position.Left,
    sourcePosition: Position.Right,
  },
  {
    id: "embed",
    label: "Generate Embeddings",
    category: "Model",
    description: "Vector shape and sample values",
    position: { x: 605, y: 30 },
    targetPosition: Position.Left,
    sourcePosition: Position.Bottom,
  },
  {
    id: "index",
    label: "Index Readiness",
    category: "Storage",
    description: "Non-destructive pgvector check",
    position: { x: 605, y: 280 },
    targetPosition: Position.Top,
    sourcePosition: Position.Left,
  },
  {
    id: "retrieve",
    label: "Retrieve Context",
    category: "Search",
    description: "Hybrid ranked document chunks",
    position: { x: 410, y: 280 },
    targetPosition: Position.Right,
    sourcePosition: Position.Left,
  },
  {
    id: "generate",
    label: "Generate Answer",
    category: "LLM",
    description: "Grounded answer and citations",
    position: { x: 215, y: 280 },
    targetPosition: Position.Right,
    sourcePosition: Position.Left,
  },
];

const INITIAL_NODES: PipelineFlowNode[] = NODE_DEFINITIONS.map((definition, index) => ({
  id: definition.id,
  type: "pipeline",
  position: definition.position,
  data: {
    active: index === 0,
    category: definition.category,
    description: definition.description,
    icon: definition.id,
    label: definition.label,
    sourcePosition: definition.sourcePosition,
    status: "idle",
    step: index + 1,
    targetPosition: definition.targetPosition,
  },
}));

const BASE_EDGES: Edge[] = [
  ["validate", "parse"],
  ["parse", "chunk"],
  ["chunk", "embed"],
  ["embed", "index"],
  ["index", "retrieve"],
  ["retrieve", "generate"],
].map(([source, target]) => ({
  id: `${source}-${target}`,
  source,
  target,
  type: "smoothstep",
}));

const NODE_TYPES = { pipeline: PipelineNodeCircle };

export function AdminTestBenchPage() {
  const [nodes, setNodes, onNodesChange] = useNodesState<PipelineFlowNode>(INITIAL_NODES);
  const [selectedNodeId, setSelectedNodeId] = useState<PipelineNodeId>("validate");
  const [file, setFile] = useState<File | null>(null);
  const [query, setQuery] = useState(EXAMPLE_QUERY);
  const [topK, setTopK] = useState(5);
  const [statuses, setStatuses] = useState<Record<PipelineNodeId, PipelineNodeStatus>>(
    initialStatuses,
  );
  const [results, setResults] = useState<
    Partial<Record<PipelineNodeId, PipelineExecutionResult>>
  >({});
  const [errors, setErrors] = useState<Partial<Record<PipelineNodeId, string>>>({});

  const selectedDefinition = NODE_DEFINITIONS.find(
    (definition) => definition.id === selectedNodeId,
  )!;
  const selectedStep = NODE_DEFINITIONS.findIndex(
    (definition) => definition.id === selectedNodeId,
  ) + 1;
  const selectedResult = results[selectedNodeId];
  const selectedError = errors[selectedNodeId];
  const selectedStatus = statuses[selectedNodeId];
  const selectedNeedsFile = FILE_NODE_IDS.has(selectedNodeId);
  const selectedTone = NODE_TONES[selectedNodeId];
  const completedCount = Object.values(statuses).filter(
    (status) => status === "completed",
  ).length;
  const canRun = selectedNeedsFile ? Boolean(file) : Boolean(query.trim());

  useEffect(() => {
    setNodes((currentNodes) =>
      currentNodes.map((node) => ({
        ...node,
        data: {
          ...node.data,
          active: node.id === selectedNodeId,
          durationMs: results[node.id as PipelineNodeId]?.durationMs,
          status: statuses[node.id as PipelineNodeId],
        },
      })),
    );
  }, [results, selectedNodeId, setNodes, statuses]);

  const edges = useMemo(
    () =>
      BASE_EDGES.map((edge) => {
        const sourceId = edge.source as PipelineNodeId;
        const targetId = edge.target as PipelineNodeId;
        const sourceStatus = statuses[sourceId];
        const targetStatus = statuses[targetId];
        const active = sourceStatus === "running" || targetStatus === "running";
        const completed = sourceStatus === "completed";
        const stroke = completed || active ? NODE_TONES[targetId].edge : "#cbd5e1";
        return {
          ...edge,
          animated: active,
          markerEnd: { color: stroke, type: MarkerType.ArrowClosed },
          style: {
            stroke,
            strokeWidth: active || completed ? 2.5 : 1.75,
          },
        };
      }),
    [statuses],
  );

  async function runSelectedNode() {
    if (selectedNeedsFile && !file) {
      setErrors((current) => ({ ...current, [selectedNodeId]: "Select a document first." }));
      return;
    }
    if (!selectedNeedsFile && !query.trim()) {
      setErrors((current) => ({ ...current, [selectedNodeId]: "Enter a query first." }));
      return;
    }

    setStatuses((current) => ({ ...current, [selectedNodeId]: "running" }));
    setErrors((current) => ({ ...current, [selectedNodeId]: undefined }));
    const started = performance.now();
    try {
      let result: PipelineExecutionResult;
      if (FILE_NODE_IDS.has(selectedNodeId)) {
        const payload = await testPipelineNode(selectedNodeId as PipelineNodeStage, file!);
        result = resultFromPipelineTest(payload);
      } else if (selectedNodeId === "retrieve") {
        const payload = await searchDocuments({ query: query.trim(), top_k: topK });
        result = resultFromSearch(payload, performance.now() - started);
      } else {
        const payload = await askDocuments({ query: query.trim(), top_k: topK });
        result = resultFromAnswer(payload, performance.now() - started);
      }

      setResults((current) => ({ ...current, [selectedNodeId]: result }));
      setStatuses((current) => ({ ...current, [selectedNodeId]: "completed" }));
    } catch (caught) {
      setStatuses((current) => ({ ...current, [selectedNodeId]: "failed" }));
      setErrors((current) => ({
        ...current,
        [selectedNodeId]: messageFromError(caught),
      }));
    }
  }

  function selectFile(nextFile: File | null) {
    setFile(nextFile);
    setErrors((current) => {
      const next = { ...current };
      FILE_NODE_IDS.forEach((nodeId) => delete next[nodeId]);
      return next;
    });
    setResults((current) => {
      const next = { ...current };
      FILE_NODE_IDS.forEach((nodeId) => delete next[nodeId]);
      return next;
    });
    setStatuses((current) => {
      const next = { ...current };
      FILE_NODE_IDS.forEach((nodeId) => {
        next[nodeId] = "idle";
      });
      return next;
    });
  }

  function resetExecutions() {
    setStatuses(initialStatuses());
    setResults({});
    setErrors({});
  }

  return (
    <section className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_370px]">
        <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <header className="flex min-h-16 items-center justify-between gap-4 border-b border-slate-200 px-4 py-3">
            <div className="min-w-0">
              <div className="flex items-center gap-3">
                <p className="text-sm font-medium text-slate-900">Pipeline workflow</p>
                <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-medium text-slate-600">
                  {completedCount} / {NODE_DEFINITIONS.length} complete
                </span>
              </div>
              <div className="mt-2 flex items-center gap-1.5" aria-label="Pipeline completion">
                {NODE_DEFINITIONS.map((definition) => (
                  <span
                    className={`h-1.5 w-7 rounded-full transition-colors ${
                      statuses[definition.id] === "completed"
                        ? NODE_TONES[definition.id].bar
                        : statuses[definition.id] === "failed"
                          ? "bg-rose-400"
                          : "bg-slate-200"
                    }`}
                    key={definition.id}
                  />
                ))}
              </div>
            </div>
            <button
              className="grid size-9 shrink-0 place-items-center rounded-lg border border-slate-200 text-slate-500 transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-800"
              onClick={resetExecutions}
              title="Reset execution results"
              type="button"
            >
              <RotateCcw size={16} />
            </button>
          </header>

          <div className="pipeline-flow h-[555px] bg-slate-50">
            <ReactFlow
              edges={edges}
              fitView
              fitViewOptions={{ padding: 0.16 }}
              maxZoom={1.55}
              minZoom={0.45}
              nodeTypes={NODE_TYPES}
              nodes={nodes}
              nodesConnectable={false}
              onNodeClick={(_, node) => setSelectedNodeId(node.id as PipelineNodeId)}
              onNodesChange={onNodesChange}
            >
              <Background color="#d8e1ec" gap={24} size={1.2} variant={BackgroundVariant.Dots} />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>
        </section>

        <aside className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className={`h-1.5 ${selectedTone.bar}`} />
          <header className="border-b border-slate-200 px-4 py-4">
            <div className="flex items-start gap-3">
              <span className={`grid size-11 shrink-0 place-items-center rounded-full ${selectedTone.icon}`}>
                <NodeIcon nodeId={selectedNodeId} size={20} />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[11px] font-medium uppercase text-slate-400">
                    Step {selectedStep} · {selectedDefinition.category}
                  </p>
                  <NodeStatus status={selectedStatus} />
                </div>
                <p className="mt-1 text-base font-medium text-slate-900">
                  {selectedDefinition.label}
                </p>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  {selectedDefinition.description}
                </p>
              </div>
            </div>
          </header>

          <div className="space-y-4 p-4">
            {selectedNeedsFile ? (
              <label
                className="group relative grid min-h-32 cursor-pointer place-items-center rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-4 text-center transition hover:border-slate-400 hover:bg-white"
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  selectFile(event.dataTransfer.files?.[0] ?? null);
                }}
              >
                <span className={`grid size-10 place-items-center rounded-full ${selectedTone.step}`}>
                  {file ? <Check size={18} /> : <Upload size={18} />}
                </span>
                <span className="mt-2 block max-w-full truncate text-sm font-medium text-slate-700">
                  {file?.name ?? "Drop or choose a document"}
                </span>
                <span className="mt-1 block text-xs text-slate-400">
                  {file ? formatFileSize(file.size) : "PDF, DOCX, TXT, Markdown and data files"}
                </span>
                <input
                  className="sr-only"
                  onChange={(event) => selectFile(event.target.files?.[0] ?? null)}
                  type="file"
                />
              </label>
            ) : (
              <div className="space-y-4">
                <label className="!gap-2">
                  <span className="!font-normal">Query</span>
                  <textarea
                    className="!min-h-28 !bg-white text-sm"
                    onChange={(event) => setQuery(event.target.value)}
                    rows={4}
                    value={query}
                  />
                </label>
                <label className="!gap-2">
                  <span className="flex items-center justify-between !font-normal">
                    <span>Results</span>
                    <output className={`rounded-full px-2 py-0.5 text-xs font-medium ${selectedTone.step}`}>
                      {topK}
                    </output>
                  </span>
                  <input
                    className="pipeline-range !p-0"
                    max={20}
                    min={1}
                    onChange={(event) => setTopK(Number(event.target.value))}
                    type="range"
                    value={topK}
                  />
                  <span className="flex justify-between text-[11px] text-slate-400">
                    <span>1</span>
                    <span>20</span>
                  </span>
                </label>
              </div>
            )}

            {selectedError && (
              <div className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                <CircleAlert className="mt-0.5 shrink-0" size={16} />
                <span>{selectedError}</span>
              </div>
            )}

            <button
              className={`flex h-11 w-full items-center justify-center gap-2 rounded-lg px-4 text-sm font-medium text-white shadow-sm transition focus-visible:outline-none focus-visible:ring-4 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none ${selectedTone.button}`}
              disabled={selectedStatus === "running" || !canRun}
              onClick={() => void runSelectedNode()}
              type="button"
            >
              {selectedStatus === "running" ? (
                <LoaderCircle className="animate-spin" size={17} />
              ) : selectedStatus === "completed" ? (
                <Check size={17} />
              ) : (
                <Play fill="currentColor" size={16} />
              )}
              {selectedStatus === "running"
                ? "Running node"
                : selectedStatus === "completed"
                  ? "Run again"
                  : "Run this node"}
            </button>

            {selectedResult && (
              <div className="border-t border-slate-200 pt-4">
                <div className="mb-3 flex items-center justify-between">
                  <span className="text-xs text-slate-500">Last execution</span>
                  <span className="flex items-center gap-1.5 text-xs font-medium text-slate-700">
                    <Clock3 size={13} />
                    {selectedResult.durationMs.toFixed(1)}ms
                  </span>
                </div>
                <SummaryGrid summary={selectedResult.summary} />
              </div>
            )}
          </div>
        </aside>
      </div>

      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
        <header className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <div className="flex items-center gap-3">
            <span className={`grid size-8 place-items-center rounded-full ${selectedTone.step}`}>
              <NodeIcon nodeId={selectedNodeId} size={15} />
            </span>
            <div>
              <p className="text-sm font-medium text-slate-900">Node output</p>
              <p className="mt-0.5 text-xs text-slate-500">{selectedDefinition.label}</p>
            </div>
          </div>
          <NodeStatus status={selectedStatus} />
        </header>
        <div className="p-4">
          {selectedResult ? (
            <OutputPreview preview={selectedResult.preview} tone={selectedTone} />
          ) : (
            <div className="grid min-h-40 place-items-center text-center text-sm text-slate-400">
              <div>
                <span className={`mx-auto grid size-12 place-items-center rounded-full ${selectedTone.step}`}>
                  <NodeIcon nodeId={selectedNodeId} size={21} />
                </span>
                <p className="mt-3">No output for this node yet.</p>
              </div>
            </div>
          )}
        </div>
      </section>
    </section>
  );
}

function PipelineNodeCircle({ data, selected }: NodeProps<PipelineFlowNode>) {
  const tone = NODE_TONES[data.icon];
  const isActive = selected || data.active;
  const statusRing: Record<PipelineNodeStatus, string> = {
    idle: "",
    running: "animate-pulse",
    completed: "",
    failed: "ring-4 ring-rose-200",
  };

  return (
    <div
      className={[
        "group relative grid size-[146px] place-content-center justify-items-center rounded-full border-[3px] px-4 text-center shadow-sm transition duration-200 hover:-translate-y-1 hover:shadow-lg",
        tone.surface,
        statusRing[data.status],
        isActive ? `-translate-y-1 scale-[1.03] ${tone.ring}` : "",
      ].join(" ")}
      title={data.description}
    >
      <Handle
        className={`!size-3 !border-[3px] !border-white ${tone.handle}`}
        position={data.targetPosition}
        type="target"
      />

      <span className={`absolute right-1 top-2 grid size-7 place-items-center rounded-full text-[11px] font-semibold ${tone.step}`}>
        {data.step}
      </span>
      <span className={`grid size-11 place-items-center rounded-full shadow-sm ${tone.icon}`}>
        <NodeIcon nodeId={data.icon} size={20} />
      </span>
      <span className="mt-2 text-[10px] font-semibold uppercase opacity-60">
        {data.category}
      </span>
      <span className="mt-0.5 max-w-[112px] text-sm font-semibold leading-4">
        {data.label}
      </span>
      <span className="mt-1.5 flex min-h-4 items-center gap-1 text-[10px] font-medium opacity-70">
        <NodeStateGlyph status={data.status} />
        {data.durationMs !== undefined
          ? `${data.durationMs.toFixed(0)}ms`
          : statusLabel(data.status)}
      </span>

      <Handle
        className={`!size-3 !border-[3px] !border-white ${tone.handle}`}
        position={data.sourcePosition}
        type="source"
      />
    </div>
  );
}

function NodeIcon({ nodeId, size }: { nodeId: PipelineNodeId; size: number }) {
  const icons = {
    validate: BadgeCheck,
    parse: Braces,
    chunk: Boxes,
    embed: Binary,
    index: Database,
    retrieve: Search,
    generate: BrainCircuit,
  };
  const Icon = icons[nodeId];
  return <Icon size={size} />;
}

function NodeStateGlyph({ status }: { status: PipelineNodeStatus }) {
  if (status === "running") return <LoaderCircle className="animate-spin" size={11} />;
  if (status === "completed") return <Check size={11} strokeWidth={3} />;
  if (status === "failed") return <CircleAlert size={11} />;
  return <span className="size-1.5 rounded-full bg-current opacity-50" />;
}

function StatusDot({ status }: { status: PipelineNodeStatus }) {
  const classes: Record<PipelineNodeStatus, string> = {
    idle: "bg-slate-300",
    running: "animate-pulse bg-sky-500",
    completed: "bg-emerald-500",
    failed: "bg-rose-500",
  };
  return <span className={`size-2 shrink-0 rounded-full ${classes[status]}`} />;
}

function statusLabel(status: PipelineNodeStatus): string {
  const labels: Record<PipelineNodeStatus, string> = {
    idle: "Ready",
    running: "Running",
    completed: "Complete",
    failed: "Failed",
  };
  return labels[status];
}

function NodeStatus({ status }: { status: PipelineNodeStatus }) {
  return (
    <span className="flex shrink-0 items-center gap-2 text-xs text-slate-500">
      <StatusDot status={status} />
      {statusLabel(status)}
    </span>
  );
}

function SummaryGrid({ summary }: { summary: Record<string, unknown> }) {
  return (
    <dl className="space-y-2">
      {Object.entries(summary)
        .slice(0, 7)
        .map(([key, value]) => (
          <div className="grid grid-cols-[minmax(0,1fr)_auto] gap-3 text-xs" key={key}>
            <dt className="truncate text-slate-500">{humanizeKey(key)}</dt>
            <dd className="max-w-44 truncate text-right font-medium text-slate-700">
              {formatValue(value)}
            </dd>
          </div>
        ))}
    </dl>
  );
}

function OutputPreview({
  preview,
  tone,
}: {
  preview: Array<Record<string, unknown>>;
  tone: NodeTone;
}) {
  if (!preview.length) {
    return <p className="py-8 text-center text-sm text-slate-400">Node completed without preview data.</p>;
  }

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {preview.map((item, index) => (
        <article
          className="min-w-0 overflow-hidden rounded-lg border border-slate-200 bg-slate-50"
          key={`${index}-${Object.keys(item)[0] ?? "preview"}`}
        >
          <div className="flex items-center gap-2 border-b border-slate-200 bg-white px-3 py-2 text-xs text-slate-500">
            <span className={`grid size-6 place-items-center rounded-full ${tone.step}`}>
              <FileSearch size={12} />
            </span>
            Output {index + 1}
          </div>
          <div className="p-3">
            {typeof item.answer === "string" ? (
              <p className="whitespace-pre-wrap text-sm leading-6 text-slate-700">{item.answer}</p>
            ) : (
              <pre className="max-h-72 overflow-auto whitespace-pre-wrap break-words font-mono text-xs leading-5 text-slate-600">
                {JSON.stringify(item, null, 2)}
              </pre>
            )}
          </div>
        </article>
      ))}
    </div>
  );
}

function resultFromPipelineTest(payload: PipelineNodeTestResponse): PipelineExecutionResult {
  return {
    durationMs: payload.duration_ms,
    summary: payload.summary,
    preview: payload.preview,
  };
}

function resultFromSearch(
  payload: SearchResponse,
  durationMs: number,
): PipelineExecutionResult {
  return {
    durationMs,
    summary: {
      query: payload.query,
      embedding_model: payload.embedding_model,
      top_k: payload.top_k,
      result_count: payload.results.length,
    },
    preview: payload.results.map((result) => ({
      rank: result.rank,
      score: scorePercent(result.score),
      file_name: result.file_name,
      parent_path: result.parent_path,
      source_refs: result.source_refs,
      text: result.child_text,
    })),
  };
}

function resultFromAnswer(payload: AskResponse, durationMs: number): PipelineExecutionResult {
  return {
    durationMs,
    summary: {
      model: payload.llm_model,
      trace_id: payload.trace_id,
      source_count: payload.retrieval.results.length,
      top_k: payload.retrieval.top_k,
    },
    preview: [
      {
        answer: payload.answer,
        citations: payload.citations,
      },
    ],
  };
}

function initialStatuses(): Record<PipelineNodeId, PipelineNodeStatus> {
  return {
    validate: "idle",
    parse: "idle",
    chunk: "idle",
    embed: "idle",
    index: "idle",
    retrieve: "idle",
    generate: "idle",
  };
}

function humanizeKey(value: string): string {
  return value.replaceAll("_", " ");
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
