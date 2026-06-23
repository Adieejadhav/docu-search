import {
  type ChangeEvent,
  type DragEvent,
  type ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  Background,
  BackgroundVariant,
  Handle,
  MarkerType,
  NodeToolbar,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Binary,
  Boxes,
  BrainCircuit,
  Braces,
  Check,
  ChevronRight,
  CircleAlert,
  Database,
  FileSearch,
  FileUp,
  FolderOpen,
  HardDriveUpload,
  LoaderCircle,
  Play,
  RefreshCw,
  Search,
  Settings2,
  TerminalSquare,
  UploadCloud,
} from "lucide-react";
import { useAppData } from "../../../app/AppDataContext";
import { messageFromError, scorePercent } from "../../../lib/format";
import {
  askDocuments,
  createIngestionJob,
  getIngestionJob,
  listIngestionJobs,
  searchDocuments,
} from "../../../services/api";
import type {
  AskResponse,
  IngestionJob,
  IngestionJobEvent,
  SearchResponse,
} from "../../../services/types";

type IngestionNodeId =
  | "source"
  | "discover"
  | "parse"
  | "chunk"
  | "index"
  | "vector_store";
type ActionNodeId = "retrieve" | "generate";
type NodeStatus = "idle" | "running" | "completed" | "failed";
type OutputSelection = IngestionNodeId | ActionNodeId;

interface StageSnapshot {
  durationMs?: number;
  elapsedMs?: number;
  status: NodeStatus;
}

interface PipelineNodeData extends Record<string, unknown> {
  category: string;
  description: string;
  durationMs?: number;
  elapsedMs?: number;
  endpoint?: "start" | "end";
  icon: IngestionNodeId;
  inputOpen: boolean;
  label: string;
  status: NodeStatus;
  step: number;
  toolbar?: ReactNode;
}

type PipelineFlowNode = Node<PipelineNodeData, "pipeline">;

interface ExecutionResult {
  durationMs: number;
  preview: Array<Record<string, unknown>>;
  summary: Record<string, unknown>;
}

interface NodeTone {
  edge: string;
  icon: string;
  ring: string;
  soft: string;
}

const POLL_INTERVAL_MS = 900;
const EXAMPLE_QUERY = "Which policy mentions the 14-day satellite-mode exception?";
const SUPPORTED_UPLOAD_EXTENSIONS = new Set([
  ".csv",
  ".docx",
  ".json",
  ".markdown",
  ".md",
  ".pdf",
  ".pptx",
  ".txt",
  ".xlsx",
]);

const NODE_TONES: Record<IngestionNodeId | ActionNodeId, NodeTone> = {
  source: {
    edge: "#0f766e",
    icon: "bg-teal-600 text-white",
    ring: "border-teal-500 shadow-[0_0_0_4px_rgba(20,184,166,0.13)]",
    soft: "bg-teal-50 text-teal-800",
  },
  discover: {
    edge: "#7c3aed",
    icon: "bg-violet-600 text-white",
    ring: "border-violet-500 shadow-[0_0_0_4px_rgba(139,92,246,0.13)]",
    soft: "bg-violet-50 text-violet-800",
  },
  parse: {
    edge: "#d97706",
    icon: "bg-amber-500 text-white",
    ring: "border-amber-500 shadow-[0_0_0_4px_rgba(245,158,11,0.13)]",
    soft: "bg-amber-50 text-amber-800",
  },
  chunk: {
    edge: "#0284c7",
    icon: "bg-sky-600 text-white",
    ring: "border-sky-500 shadow-[0_0_0_4px_rgba(14,165,233,0.13)]",
    soft: "bg-sky-50 text-sky-800",
  },
  index: {
    edge: "#4f46e5",
    icon: "bg-indigo-600 text-white",
    ring: "border-indigo-500 shadow-[0_0_0_4px_rgba(99,102,241,0.13)]",
    soft: "bg-indigo-50 text-indigo-800",
  },
  vector_store: {
    edge: "#047857",
    icon: "bg-emerald-600 text-white",
    ring: "border-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.13)]",
    soft: "bg-emerald-50 text-emerald-800",
  },
  retrieve: {
    edge: "#e11d48",
    icon: "bg-rose-600 text-white",
    ring: "border-rose-500 shadow-[0_0_0_4px_rgba(244,63,94,0.13)]",
    soft: "bg-rose-50 text-rose-800",
  },
  generate: {
    edge: "#059669",
    icon: "bg-emerald-600 text-white",
    ring: "border-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.13)]",
    soft: "bg-emerald-50 text-emerald-800",
  },
};

const INGESTION_DEFINITIONS: Array<{
  id: IngestionNodeId;
  label: string;
  category: string;
  description: string;
}> = [
  {
    id: "source",
    label: "Input files",
    category: "Start",
    description: "Upload and validate files or folders",
  },
  {
    id: "discover",
    label: "Discover files",
    category: "Discovery",
    description: "Resolve supported ingestion inputs",
  },
  {
    id: "parse",
    label: "Parse & normalize",
    category: "Document",
    description: "Create normalized document blocks",
  },
  {
    id: "chunk",
    label: "Create chunks",
    category: "Transform",
    description: "Build parent and child contexts",
  },
  {
    id: "index",
    label: "Embed & index",
    category: "Model + storage",
    description: "Generate embeddings and insert vectors",
  },
  {
    id: "vector_store",
    label: "Vector store",
    category: "End",
    description: "Read final pgvector index statistics",
  },
];

const BASE_EDGES: Edge[] = INGESTION_DEFINITIONS.slice(0, -1).map((definition, index) => ({
  id: `${definition.id}-${INGESTION_DEFINITIONS[index + 1].id}`,
  source: definition.id,
  target: INGESTION_DEFINITIONS[index + 1].id,
  type: "smoothstep",
}));

const NODE_TYPES = { pipeline: PipelineNodeCard };

export function AdminTestBenchPage() {
  const { refreshOverview, setError } = useAppData();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const pollingRef = useRef(false);
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [clearIndex, setClearIndex] = useState(false);
  const [replace, setReplace] = useState(true);
  const [continueOnError, setContinueOnError] = useState(true);
  const [isLoadingJobs, setLoadingJobs] = useState(true);
  const [isUploading, setUploading] = useState(false);
  const [isDragging, setDragging] = useState(false);
  const [inputError, setInputError] = useState<string | null>(null);
  const [sourceInputOpen, setSourceInputOpen] = useState(false);
  const [openAction, setOpenAction] = useState<ActionNodeId | null>(null);
  const [query, setQuery] = useState(EXAMPLE_QUERY);
  const [topK, setTopK] = useState(5);
  const [actionStatuses, setActionStatuses] = useState<Record<ActionNodeId, NodeStatus>>({
    retrieve: "idle",
    generate: "idle",
  });
  const [actionErrors, setActionErrors] = useState<Partial<Record<ActionNodeId, string>>>({});
  const [actionResults, setActionResults] = useState<
    Partial<Record<ActionNodeId, ExecutionResult>>
  >({});
  const [outputSelection, setOutputSelection] = useState<OutputSelection>("source");
  const [uploadDurations, setUploadDurations] = useState<Record<string, number>>({});
  const [now, setNow] = useState(() => Date.now());

  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) ?? jobs[0] ?? null,
    [jobs, selectedJobId],
  );
  const unsupportedFiles = useMemo(
    () => files.filter((file) => !SUPPORTED_UPLOAD_EXTENSIONS.has(fileExtension(file.name))),
    [files],
  );
  const isJobActive = selectedJob?.status === "queued" || selectedJob?.status === "running";
  const snapshots = useMemo(
    () => ingestionSnapshots(selectedJob, selectedJob ? uploadDurations[selectedJob.id] : undefined, now),
    [now, selectedJob, uploadDurations],
  );

  useEffect(() => {
    void refreshJobs();
  }, []);

  useEffect(() => {
    if (!selectedJob || !isJobActive) return;
    const timer = window.setInterval(() => void pollSelectedJob(selectedJob.id), POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [isJobActive, selectedJob?.id]);

  useEffect(() => {
    if (!isJobActive) return;
    const timer = window.setInterval(() => setNow(Date.now()), 100);
    return () => window.clearInterval(timer);
  }, [isJobActive]);

  async function refreshJobs({ silent = false }: { silent?: boolean } = {}) {
    if (!silent) setLoadingJobs(true);
    setError(null);
    try {
      const payload = await listIngestionJobs();
      setJobs(payload.jobs);
      setSelectedJobId((current) => current ?? payload.jobs[0]?.id ?? null);
    } catch (error) {
      setError(messageFromError(error));
    } finally {
      if (!silent) setLoadingJobs(false);
    }
  }

  async function pollSelectedJob(jobId: string) {
    if (pollingRef.current) return;
    pollingRef.current = true;
    try {
      const job = await getIngestionJob(jobId);
      setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)]);
      if (job.status === "completed" || job.status === "failed") {
        await refreshOverview("refresh");
      }
    } catch (error) {
      setError(messageFromError(error));
    } finally {
      pollingRef.current = false;
    }
  }

  async function startIngestion() {
    if (!files.length || isUploading) return;
    if (unsupportedFiles.length) {
      setInputError(
        `Remove unsupported file type(s): ${unsupportedFiles
          .slice(0, 4)
          .map((file) => displayFileName(file))
          .join(", ")}${unsupportedFiles.length > 4 ? ", ..." : ""}`,
      );
      return;
    }

    setUploading(true);
    setInputError(null);
    setError(null);
    const started = performance.now();
    try {
      const response = await createIngestionJob({
        files,
        clear_index: clearIndex,
        replace,
        continue_on_error: continueOnError,
      });
      setUploadDurations((current) => ({
        ...current,
        [response.job.id]: performance.now() - started,
      }));
      setJobs((current) => [
        response.job,
        ...current.filter((job) => job.id !== response.job.id),
      ]);
      setSelectedJobId(response.job.id);
      setFiles([]);
      setSourceInputOpen(false);
      setOutputSelection("source");
      setNow(Date.now());
    } catch (error) {
      setInputError(messageFromError(error));
    } finally {
      setUploading(false);
    }
  }

  async function runAction(action: ActionNodeId) {
    if (!query.trim() || actionStatuses[action] === "running") return;
    setActionStatuses((current) => ({ ...current, [action]: "running" }));
    setActionErrors((current) => ({ ...current, [action]: undefined }));
    setOutputSelection(action);
    const started = performance.now();
    try {
      const result =
        action === "retrieve"
          ? resultFromSearch(
              await searchDocuments({ query: query.trim(), top_k: topK }),
              performance.now() - started,
            )
          : resultFromAnswer(
              await askDocuments({ query: query.trim(), top_k: topK }),
              performance.now() - started,
            );
      setActionResults((current) => ({ ...current, [action]: result }));
      setActionStatuses((current) => ({ ...current, [action]: "completed" }));
      setOpenAction(null);
    } catch (error) {
      setActionStatuses((current) => ({ ...current, [action]: "failed" }));
      setActionErrors((current) => ({ ...current, [action]: messageFromError(error) }));
    }
  }

  function chooseFiles(event: ChangeEvent<HTMLInputElement>) {
    acceptSelectedFiles(Array.from(event.target.files ?? []));
    event.target.value = "";
  }

  function acceptSelectedFiles(selectedFiles: File[]) {
    const uniqueFiles = dedupeFiles(selectedFiles).filter((file) => file.name);
    setFiles(uniqueFiles);
    setInputError(uniqueFiles.length ? null : "No readable documents were found in that selection.");
  }

  async function handleFileDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    setDragging(false);
    try {
      acceptSelectedFiles(await filesFromDrop(event.dataTransfer));
    } catch (error) {
      setInputError(messageFromError(error));
    }
  }

  const sourceToolbar = (
    <SourceInputPopover
      clearIndex={clearIndex}
      continueOnError={continueOnError}
      fileInputRef={fileInputRef}
      files={files}
      folderInputRef={folderInputRef}
      inputError={inputError}
      isDragging={isDragging}
      isUploading={isUploading}
      onChooseFiles={chooseFiles}
      onDrop={handleFileDrop}
      onOpenFilePicker={() => fileInputRef.current?.click()}
      onOpenFolderPicker={() => folderInputRef.current?.click()}
      onSetClearIndex={setClearIndex}
      onSetContinueOnError={setContinueOnError}
      onSetDragging={setDragging}
      onSetReplace={setReplace}
      onStart={() => void startIngestion()}
      replace={replace}
      unsupportedFiles={unsupportedFiles}
    />
  );

  const nodes = useMemo<PipelineFlowNode[]>(
    () =>
      INGESTION_DEFINITIONS.map((definition, index) => ({
        id: definition.id,
        type: "pipeline",
        position: { x: index * 205, y: 36 },
        data: {
          category: definition.category,
          description: definition.description,
          durationMs: snapshots[definition.id].durationMs,
          elapsedMs: snapshots[definition.id].elapsedMs,
          endpoint:
            definition.id === "source"
              ? "start"
              : definition.id === "vector_store"
                ? "end"
                : undefined,
          icon: definition.id,
          inputOpen: definition.id === "source" && sourceInputOpen,
          label: definition.label,
          status: snapshots[definition.id].status,
          step: index + 1,
          toolbar: definition.id === "source" ? sourceToolbar : undefined,
        },
      })),
    [snapshots, sourceInputOpen, sourceToolbar],
  );

  const edges = useMemo(
    () =>
      BASE_EDGES.map((edge) => {
        const source = edge.source as IngestionNodeId;
        const target = edge.target as IngestionNodeId;
        const active = snapshots[source].status === "running" || snapshots[target].status === "running";
        const completed = snapshots[source].status === "completed";
        const stroke = active || completed ? NODE_TONES[target].edge : "#cbd5e1";
        return {
          ...edge,
          animated: active,
          markerEnd: { color: stroke, type: MarkerType.ArrowClosed },
          style: { stroke, strokeWidth: active || completed ? 2.5 : 1.75 },
        };
      }),
    [snapshots],
  );

  const completedStages = Object.values(snapshots).filter(
    (snapshot) => snapshot.status === "completed",
  ).length;
  const selectedActionResult =
    outputSelection === "retrieve" || outputSelection === "generate"
      ? actionResults[outputSelection]
      : undefined;

  return (
    <section className="space-y-4">
      <section className="relative overflow-visible rounded-xl border border-slate-200 bg-white shadow-sm">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-sm font-semibold text-slate-950">Production ingestion pipeline</h2>
              <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-semibold text-slate-600">
                {completedStages} / {INGESTION_DEFINITIONS.length} stages complete
              </span>
              {selectedJob && <JobStatusBadge status={selectedJob.status} />}
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Run a file or folder through the real pipeline and inspect every stage live.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <select
              aria-label="Select ingestion run"
              className="h-9 max-w-52 rounded-lg border border-slate-200 bg-white px-3 text-xs text-slate-700 outline-none focus:border-slate-400"
              disabled={isLoadingJobs || !jobs.length}
              onChange={(event) => {
                setSelectedJobId(event.target.value);
                setOutputSelection("source");
              }}
              value={selectedJob?.id ?? ""}
            >
              {!jobs.length && <option value="">No ingestion runs</option>}
              {jobs.map((job) => (
                <option key={job.id} value={job.id}>
                  {shortJobId(job.id)} · {job.file_count} file(s) · {job.status}
                </option>
              ))}
            </select>
            <button
              className="grid size-9 place-items-center rounded-lg border border-slate-200 text-slate-500 transition hover:bg-slate-50 hover:text-slate-800"
              onClick={() => void refreshJobs()}
              title="Refresh ingestion runs"
              type="button"
            >
              <RefreshCw className={isLoadingJobs ? "animate-spin" : ""} size={15} />
            </button>
            <button
              className="flex h-9 items-center gap-2 rounded-lg bg-slate-900 px-3 text-xs font-semibold text-white transition hover:bg-slate-700"
              onClick={() => setSourceInputOpen((current) => !current)}
              type="button"
            >
              <UploadCloud size={15} />
              New ingestion
            </button>
          </div>
        </header>

        <div className={`pipeline-flow bg-slate-50 transition-[height] ${sourceInputOpen ? "h-[500px]" : "h-[280px]"}`}>
          <ReactFlow
            edges={edges}
            elementsSelectable
            fitView
            fitViewOptions={{ padding: 0.08 }}
            maxZoom={1.2}
            minZoom={0.45}
            nodeTypes={NODE_TYPES}
            nodes={nodes}
            nodesConnectable={false}
            nodesDraggable={false}
            onNodeClick={(_, node) => {
              const nodeId = node.id as IngestionNodeId;
              setOutputSelection(nodeId);
              setOpenAction(null);
              if (nodeId === "source") setSourceInputOpen((current) => !current);
            }}
            panOnDrag
            zoomOnScroll={false}
          >
            <Background color="#d8e1ec" gap={22} size={1.1} variant={BackgroundVariant.Dots} />
          </ReactFlow>
        </div>
      </section>

      <section className="relative rounded-xl border-2 border-slate-800 bg-white p-4 shadow-sm">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded bg-slate-900 px-2 py-1 text-[10px] font-bold uppercase tracking-[0.14em] text-white">
                Important
              </span>
              <h2 className="text-sm font-bold text-slate-950">Post-ingestion tools</h2>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Retrieval and answer generation are intentionally separate from ingestion.
            </p>
          </div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Uses the current vector store
          </span>
        </div>

        <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr] md:items-center">
          <ActionNodeCard
            align="left"
            error={actionErrors.retrieve}
            icon={<Search size={20} />}
            inputOpen={openAction === "retrieve"}
            label="Retrieve context"
            onRun={() => void runAction("retrieve")}
            onToggle={() => {
              setOpenAction((current) => (current === "retrieve" ? null : "retrieve"));
              setOutputSelection("retrieve");
              setSourceInputOpen(false);
            }}
            query={query}
            setQuery={setQuery}
            setTopK={setTopK}
            status={actionStatuses.retrieve}
            summary="Search and rank relevant indexed chunks"
            tone={NODE_TONES.retrieve}
            topK={topK}
          />
          <ChevronRight className="hidden text-slate-300 md:block" size={22} />
          <ActionNodeCard
            align="right"
            error={actionErrors.generate}
            icon={<BrainCircuit size={20} />}
            inputOpen={openAction === "generate"}
            label="Generate answer"
            onRun={() => void runAction("generate")}
            onToggle={() => {
              setOpenAction((current) => (current === "generate" ? null : "generate"));
              setOutputSelection("generate");
              setSourceInputOpen(false);
            }}
            query={query}
            setQuery={setQuery}
            setTopK={setTopK}
            status={actionStatuses.generate}
            summary="Produce a grounded answer with citations"
            tone={NODE_TONES.generate}
            topK={topK}
          />
        </div>
      </section>

      <OutputTerminal
        actionResult={selectedActionResult}
        actionStatus={
          outputSelection === "retrieve" || outputSelection === "generate"
            ? actionStatuses[outputSelection]
            : undefined
        }
        job={selectedJob}
        selection={outputSelection}
        snapshot={
          outputSelection !== "retrieve" && outputSelection !== "generate"
            ? snapshots[outputSelection]
            : undefined
        }
      />
    </section>
  );
}

function PipelineNodeCard({ data, selected }: NodeProps<PipelineFlowNode>) {
  const tone = NODE_TONES[data.icon];
  const timing = data.elapsedMs ?? data.durationMs;
  const active = selected || data.status === "running" || data.inputOpen;

  return (
    <>
      <NodeToolbar align="start" isVisible={data.inputOpen} position={Position.Bottom}>
        <div className="nodrag nowheel mt-3" onClick={(event) => event.stopPropagation()}>
          {data.toolbar}
        </div>
      </NodeToolbar>
      <div
        className={[
          "relative flex h-[124px] w-[166px] flex-col rounded-2xl border-2 bg-white p-3 text-left shadow-sm transition",
          active ? tone.ring : "border-slate-200 hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md",
          data.status === "failed" ? "!border-rose-500 ring-4 ring-rose-100" : "",
          data.endpoint ? "border-dashed" : "",
        ].join(" ")}
        title={data.description}
      >
        <Handle
          className={`!size-3 !border-[3px] !border-white ${data.icon === "source" ? "!bg-teal-600" : "!bg-slate-400"}`}
          position={Position.Left}
          type="target"
        />
        <div className="flex items-start justify-between gap-2">
          <span className={`grid size-9 place-items-center rounded-xl ${tone.icon}`}>
            <IngestionNodeIcon nodeId={data.icon} />
          </span>
          <span className={`rounded-full px-2 py-1 text-[9px] font-bold uppercase tracking-wider ${tone.soft}`}>
            {data.endpoint ?? `0${data.step}`}
          </span>
        </div>
        <span className="mt-2 text-[9px] font-bold uppercase tracking-[0.12em] text-slate-400">
          {data.category}
        </span>
        <strong className="mt-0.5 truncate text-xs text-slate-900">{data.label}</strong>
        <span className="mt-auto flex items-center gap-1.5 text-[10px] font-semibold text-slate-500">
          <NodeStateGlyph status={data.status} />
          {timing !== undefined
            ? `${data.status === "running" ? "Running · " : ""}${formatMs(timing)}`
            : statusLabel(data.status)}
        </span>
        <Handle
          className={`!size-3 !border-[3px] !border-white ${data.icon === "vector_store" ? "!bg-emerald-600" : "!bg-slate-400"}`}
          position={Position.Right}
          type="source"
        />
      </div>
    </>
  );
}

function SourceInputPopover({
  clearIndex,
  continueOnError,
  fileInputRef,
  files,
  folderInputRef,
  inputError,
  isDragging,
  isUploading,
  onChooseFiles,
  onDrop,
  onOpenFilePicker,
  onOpenFolderPicker,
  onSetClearIndex,
  onSetContinueOnError,
  onSetDragging,
  onSetReplace,
  onStart,
  replace,
  unsupportedFiles,
}: {
  clearIndex: boolean;
  continueOnError: boolean;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  files: File[];
  folderInputRef: React.RefObject<HTMLInputElement | null>;
  inputError: string | null;
  isDragging: boolean;
  isUploading: boolean;
  onChooseFiles: (event: ChangeEvent<HTMLInputElement>) => void;
  onDrop: (event: DragEvent<HTMLDivElement>) => void;
  onOpenFilePicker: () => void;
  onOpenFolderPicker: () => void;
  onSetClearIndex: (value: boolean) => void;
  onSetContinueOnError: (value: boolean) => void;
  onSetDragging: (value: boolean) => void;
  onSetReplace: (value: boolean) => void;
  onStart: () => void;
  replace: boolean;
  unsupportedFiles: File[];
}) {
  return (
    <div className="w-[430px] rounded-xl border border-slate-200 bg-white p-4 text-left shadow-2xl">
      <div className="mb-3 flex items-center gap-2">
        <span className="grid size-8 place-items-center rounded-lg bg-teal-50 text-teal-700">
          <HardDriveUpload size={16} />
        </span>
        <div>
          <p className="text-xs font-bold text-slate-900">Ingestion input</p>
          <p className="text-[10px] text-slate-500">Choose files or a complete folder.</p>
        </div>
      </div>

      <div
        className={`rounded-lg border border-dashed px-3 py-3 transition ${
          isDragging ? "border-teal-500 bg-teal-50" : "border-slate-300 bg-slate-50"
        }`}
        onDragEnter={(event) => {
          event.preventDefault();
          onSetDragging(true);
        }}
        onDragLeave={(event) => {
          event.preventDefault();
          onSetDragging(false);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDrop={onDrop}
      >
        <div className="flex items-center justify-between gap-3">
          <span className="min-w-0 text-[11px] text-slate-500">
            {files.length ? <strong className="text-slate-800">{files.length} file(s) ready</strong> : "Drop files or a folder here"}
          </span>
          <div className="flex shrink-0 gap-2">
            <button className="input-picker-button" onClick={onOpenFilePicker} type="button">
              <FileUp size={13} /> Files
            </button>
            <button className="input-picker-button" onClick={onOpenFolderPicker} type="button">
              <FolderOpen size={13} /> Folder
            </button>
          </div>
        </div>
        {!!files.length && (
          <div className="mt-2 flex max-h-16 flex-wrap gap-1 overflow-auto">
            {files.slice(0, 12).map((file) => (
              <span
                className={`max-w-40 truncate rounded-full border px-2 py-1 text-[9px] ${
                  SUPPORTED_UPLOAD_EXTENSIONS.has(fileExtension(file.name))
                    ? "border-slate-200 bg-white text-slate-600"
                    : "border-rose-200 bg-rose-50 text-rose-700"
                }`}
                key={fileKey(file)}
              >
                {displayFileName(file)}
              </span>
            ))}
            {files.length > 12 && <span className="px-1 py-1 text-[9px] text-slate-400">+{files.length - 12} more</span>}
          </div>
        )}
      </div>

      <input className="sr-only" multiple onChange={onChooseFiles} ref={fileInputRef} type="file" />
      <input
        className="sr-only"
        multiple
        onChange={onChooseFiles}
        ref={folderInputRef}
        type="file"
        {...({ directory: "", webkitdirectory: "" } as Record<string, string>)}
      />

      <div className="mt-3 grid grid-cols-3 gap-2 text-[10px] text-slate-600">
        <CompactToggle checked={replace} label="Replace matches" onChange={onSetReplace} />
        <CompactToggle checked={continueOnError} label="Continue errors" onChange={onSetContinueOnError} />
        <CompactToggle checked={clearIndex} danger label="Clear index first" onChange={onSetClearIndex} />
      </div>

      {inputError && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-[10px] text-rose-700">
          <CircleAlert className="mt-0.5 shrink-0" size={13} />
          {inputError}
        </div>
      )}

      <button
        className="mt-3 flex h-9 w-full items-center justify-center gap-2 rounded-lg bg-teal-700 text-xs font-bold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-300"
        disabled={!files.length || !!unsupportedFiles.length || isUploading}
        onClick={onStart}
        type="button"
      >
        {isUploading ? <LoaderCircle className="animate-spin" size={14} /> : <Play fill="currentColor" size={13} />}
        {isUploading ? "Uploading inputs" : "Start ingestion"}
      </button>
    </div>
  );
}

function CompactToggle({
  checked,
  danger = false,
  label,
  onChange,
}: {
  checked: boolean;
  danger?: boolean;
  label: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className={`flex cursor-pointer items-start gap-1.5 rounded-lg border p-2 ${danger ? "border-rose-200 bg-rose-50" : "border-slate-200 bg-slate-50"}`}>
      <input
        checked={checked}
        className="mt-px size-3.5"
        onChange={(event) => onChange(event.target.checked)}
        type="checkbox"
      />
      <span>{label}</span>
    </label>
  );
}

function ActionNodeCard({
  align,
  error,
  icon,
  inputOpen,
  label,
  onRun,
  onToggle,
  query,
  setQuery,
  setTopK,
  status,
  summary,
  tone,
  topK,
}: {
  align: "left" | "right";
  error?: string;
  icon: ReactNode;
  inputOpen: boolean;
  label: string;
  onRun: () => void;
  onToggle: () => void;
  query: string;
  setQuery: (value: string) => void;
  setTopK: (value: number) => void;
  status: NodeStatus;
  summary: string;
  tone: NodeTone;
  topK: number;
}) {
  return (
    <div className="relative">
      <button
        className={`flex w-full items-center gap-3 rounded-xl border-2 bg-white p-3 text-left transition hover:-translate-y-0.5 hover:shadow-md ${
          inputOpen ? tone.ring : "border-slate-200"
        }`}
        onClick={onToggle}
        type="button"
      >
        <span className={`grid size-10 shrink-0 place-items-center rounded-xl ${tone.icon}`}>{icon}</span>
        <span className="min-w-0 flex-1">
          <strong className="block text-sm font-bold text-slate-950">{label}</strong>
          <span className="mt-0.5 block truncate text-xs text-slate-500">{summary}</span>
        </span>
        <span className="flex shrink-0 items-center gap-1.5 text-[11px] font-semibold text-slate-500">
          <NodeStateGlyph status={status} /> {statusLabel(status)}
        </span>
      </button>

      {inputOpen && (
        <div
          className={`absolute top-full z-30 mt-2 w-full min-w-[320px] max-w-[440px] rounded-xl border border-slate-200 bg-white p-4 shadow-2xl ${
            align === "right" ? "right-0" : "left-0"
          }`}
        >
          <div className="mb-3 flex items-center gap-2 text-xs font-bold text-slate-900">
            <Settings2 size={14} /> {label} input
          </div>
          <textarea
            className="min-h-20 w-full resize-y rounded-lg border border-slate-200 bg-slate-50 p-2.5 text-xs leading-5 text-slate-700 outline-none focus:border-slate-400"
            onChange={(event) => setQuery(event.target.value)}
            rows={3}
            value={query}
          />
          <label className="mt-3 block">
            <span className="mb-2 flex justify-between text-[10px] font-semibold text-slate-500">
              Results <output>{topK}</output>
            </span>
            <input
              className="pipeline-range"
              max={20}
              min={1}
              onChange={(event) => setTopK(Number(event.target.value))}
              type="range"
              value={topK}
            />
          </label>
          {error && <p className="mt-2 text-[10px] text-rose-700">{error}</p>}
          <button
            className="mt-3 flex h-9 w-full items-center justify-center gap-2 rounded-lg bg-slate-900 text-xs font-bold text-white disabled:bg-slate-300"
            disabled={!query.trim() || status === "running"}
            onClick={onRun}
            type="button"
          >
            {status === "running" ? <LoaderCircle className="animate-spin" size={14} /> : <Play fill="currentColor" size={13} />}
            {status === "running" ? "Running" : `Run ${label.toLowerCase()}`}
          </button>
        </div>
      )}
    </div>
  );
}

function OutputTerminal({
  actionResult,
  actionStatus,
  job,
  selection,
  snapshot,
}: {
  actionResult?: ExecutionResult;
  actionStatus?: NodeStatus;
  job: IngestionJob | null;
  selection: OutputSelection;
  snapshot?: StageSnapshot;
}) {
  const isAction = selection === "retrieve" || selection === "generate";
  const events = isAction || !job ? [] : eventsForSelection(job.events, selection);
  const title = isAction
    ? selection === "retrieve"
      ? "Retrieval output"
      : "Answer output"
    : `${INGESTION_DEFINITIONS.find((item) => item.id === selection)?.label ?? "Pipeline"} output`;

  return (
    <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950 shadow-sm">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 px-4 py-3">
        <div className="flex items-center gap-2">
          <TerminalSquare className="text-emerald-400" size={16} />
          <h2 className="font-mono text-xs font-bold text-slate-100">Output terminal</h2>
          <span className="font-mono text-[10px] text-slate-500">/ {title}</span>
        </div>
        <span className="flex items-center gap-1.5 font-mono text-[10px] text-slate-400">
          {(actionStatus === "running" || snapshot?.status === "running") && (
            <LoaderCircle className="animate-spin text-sky-400" size={12} />
          )}
          {actionResult
            ? `completed in ${formatMs(actionResult.durationMs)}`
            : snapshot?.elapsedMs !== undefined
              ? `running ${formatMs(snapshot.elapsedMs)}`
              : snapshot?.durationMs !== undefined
                ? `completed in ${formatMs(snapshot.durationMs)}`
                : job
                  ? `${shortJobId(job.id)} · ${job.status}`
                  : "ready"}
        </span>
      </header>

      <div className="max-h-[430px] min-h-44 overflow-auto p-4 font-mono text-[11px] leading-5">
        {actionResult ? (
          <div className="space-y-4">
            <pre className="overflow-auto whitespace-pre-wrap break-words text-slate-300">
              {JSON.stringify(actionResult.summary, null, 2)}
            </pre>
            {actionResult.preview.map((item, index) => (
              <div className="border-t border-slate-800 pt-3" key={`${selection}-${index}`}>
                <span className="text-emerald-400">output[{index}]</span>
                <pre className="mt-1 overflow-auto whitespace-pre-wrap break-words text-slate-300">
                  {JSON.stringify(item, null, 2)}
                </pre>
              </div>
            ))}
          </div>
        ) : events.length ? (
          <div className="space-y-1">
            {events.map((event, index) => (
              <div className="grid grid-cols-[72px_76px_minmax(0,1fr)_auto] gap-2" key={`${event.timestamp}-${event.stage}-${index}`}>
                <span className="text-slate-600">{formatEventTime(event.timestamp)}</span>
                <span className={event.status === "failed" ? "text-rose-400" : event.status === "started" ? "text-sky-400" : "text-emerald-400"}>
                  {event.status.padEnd(9, " ")}
                </span>
                <span className="break-words text-slate-300">
                  <span className="text-violet-300">[{event.stage}]</span> {event.message}
                  {event.path ? <span className="text-slate-600"> · {fileNameFromPath(event.path)}</span> : null}
                </span>
                <span className="text-amber-300">
                  {event.duration_ms !== null ? formatMs(event.duration_ms) : ""}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="grid min-h-36 place-items-center text-center text-slate-600">
            <div>
              <TerminalSquare className="mx-auto mb-2" size={22} />
              <p>{job ? "No output for this stage yet." : "Start an ingestion or select a post-ingestion tool."}</p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}

function ingestionSnapshots(
  job: IngestionJob | null,
  uploadDurationMs: number | undefined,
  now: number,
): Record<IngestionNodeId, StageSnapshot> {
  const idle: StageSnapshot = { status: "idle" };
  if (!job) {
    return {
      source: idle,
      discover: idle,
      parse: idle,
      chunk: idle,
      index: idle,
      vector_store: idle,
    };
  }

  return {
    source: { durationMs: uploadDurationMs, status: "completed" },
    discover: snapshotForStages(job, ["discover"], now),
    parse: snapshotForStages(job, ["parse"], now),
    chunk: snapshotForStages(job, ["chunk"], now),
    index: snapshotForStages(job, ["index"], now),
    vector_store: snapshotForStages(job, ["stats"], now),
  };
}

function snapshotForStages(job: IngestionJob, stages: string[], now: number): StageSnapshot {
  const events = job.events.filter((event) => stages.includes(event.stage));
  if (!events.length) return { status: "idle" };

  const completedDuration = events.reduce(
    (total, event) => total + (event.status === "completed" ? event.duration_ms ?? 0 : 0),
    0,
  );
  const latest = events[events.length - 1];
  if (latest.status === "started") {
    if (job.status === "failed") return { durationMs: completedDuration || undefined, status: "failed" };
    const startedAt = latest.timestamp ? Date.parse(latest.timestamp) : Number.NaN;
    return {
      elapsedMs: completedDuration + (Number.isFinite(startedAt) ? Math.max(0, now - startedAt) : 0),
      status: "running",
    };
  }
  if (latest.status === "failed") return { durationMs: completedDuration || undefined, status: "failed" };
  return { durationMs: completedDuration, status: "completed" };
}

function eventsForSelection(
  events: IngestionJobEvent[],
  selection: IngestionNodeId,
): IngestionJobEvent[] {
  const stages: Record<IngestionNodeId, string[]> = {
    source: [],
    discover: ["discover"],
    parse: ["parse", "file"],
    chunk: ["chunk", "file"],
    index: ["index", "index_clear", "index_document"],
    vector_store: ["stats", "ingest"],
  };
  if (selection === "source") return events;
  return events.filter((event) => stages[selection].includes(event.stage));
}

function IngestionNodeIcon({ nodeId }: { nodeId: IngestionNodeId }) {
  const icons = {
    source: HardDriveUpload,
    discover: FileSearch,
    parse: Braces,
    chunk: Boxes,
    index: Binary,
    vector_store: Database,
  };
  const Icon = icons[nodeId];
  return <Icon size={17} />;
}

function NodeStateGlyph({ status }: { status: NodeStatus }) {
  if (status === "running") return <LoaderCircle className="animate-spin" size={11} />;
  if (status === "completed") return <Check size={11} strokeWidth={3} />;
  if (status === "failed") return <CircleAlert size={11} />;
  return <span className="size-1.5 rounded-full bg-current opacity-50" />;
}

function JobStatusBadge({ status }: { status: IngestionJob["status"] }) {
  const classes = {
    queued: "bg-blue-50 text-blue-700",
    running: "bg-sky-50 text-sky-700",
    completed: "bg-emerald-50 text-emerald-700",
    failed: "bg-rose-50 text-rose-700",
  };
  return (
    <span className={`flex items-center gap-1.5 rounded-full px-2 py-1 text-[10px] font-bold uppercase ${classes[status]}`}>
      {status === "running" && <LoaderCircle className="animate-spin" size={10} />}
      {status}
    </span>
  );
}

function statusLabel(status: NodeStatus): string {
  return { idle: "Ready", running: "Running", completed: "Complete", failed: "Failed" }[status];
}

function resultFromSearch(payload: SearchResponse, durationMs: number): ExecutionResult {
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

function resultFromAnswer(payload: AskResponse, durationMs: number): ExecutionResult {
  return {
    durationMs,
    summary: {
      model: payload.llm_model,
      trace_id: payload.trace_id,
      source_count: payload.retrieval.results.length,
      top_k: payload.retrieval.top_k,
    },
    preview: [{ answer: payload.answer, citations: payload.citations }],
  };
}

async function filesFromDrop(dataTransfer: DataTransfer): Promise<File[]> {
  const entries = Array.from(dataTransfer.items)
    .map((item) => item.webkitGetAsEntry())
    .filter((entry): entry is FileSystemEntry => entry !== null);
  if (!entries.length) return Array.from(dataTransfer.files);
  return (await Promise.all(entries.map((entry) => filesFromEntry(entry)))).flat();
}

async function filesFromEntry(entry: FileSystemEntry): Promise<File[]> {
  if (entry.isFile) return [await fileFromEntry(entry as FileSystemFileEntry)];
  if (entry.isDirectory) return filesFromDirectory(entry as FileSystemDirectoryEntry);
  return [];
}

function fileFromEntry(entry: FileSystemFileEntry): Promise<File> {
  return new Promise((resolve, reject) => entry.file(resolve, reject));
}

async function filesFromDirectory(entry: FileSystemDirectoryEntry): Promise<File[]> {
  const reader = entry.createReader();
  const files: File[] = [];
  while (true) {
    const entries = await new Promise<FileSystemEntry[]>((resolve, reject) =>
      reader.readEntries(resolve, reject),
    );
    if (!entries.length) break;
    files.push(...(await Promise.all(entries.map((child) => filesFromEntry(child)))).flat());
  }
  return files;
}

function dedupeFiles(selectedFiles: File[]): File[] {
  const seen = new Set<string>();
  return selectedFiles.filter((file) => {
    const key = fileKey(file);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function displayFileName(file: File): string {
  return file.webkitRelativePath || file.name;
}

function fileKey(file: File): string {
  return `${displayFileName(file)}:${file.size}:${file.lastModified}`;
}

function fileExtension(fileName: string): string {
  const dotIndex = fileName.lastIndexOf(".");
  return dotIndex >= 0 ? fileName.slice(dotIndex).toLowerCase() : "";
}

function fileNameFromPath(path: string): string {
  return path.split(/[\\/]/).pop() ?? path;
}

function shortJobId(jobId: string): string {
  return jobId.slice(0, 8);
}

function formatEventTime(value: string | null): string {
  if (!value) return "--:--:--";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "--:--:--" : date.toLocaleTimeString([], { hour12: false });
}

function formatMs(value: number): string {
  if (value >= 60_000) return `${(value / 60_000).toFixed(1)}m`;
  if (value >= 1000) return `${(value / 1000).toFixed(2)}s`;
  return `${value.toFixed(1)}ms`;
}
