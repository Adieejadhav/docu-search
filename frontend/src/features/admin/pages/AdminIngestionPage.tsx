import { ChangeEvent, DragEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Clock, FileUp, FolderOpen, RefreshCw, UploadCloud } from "lucide-react";
import { useAppData } from "../../../app/AppDataContext";
import { Button } from "../../../components/ui/Button";
import { EmptyState } from "../../../components/ui/EmptyState";
import { Panel } from "../../../components/ui/Panel";
import { Skeleton } from "../../../components/ui/Skeleton";
import { messageFromError } from "../../../lib/format";
import {
  createIngestionJob,
  getIngestionJob,
  listIngestionJobs,
} from "../../../services/api";
import type { IngestionJob, IngestionJobStatus } from "../../../services/types";

const POLL_INTERVAL_MS = 2500;
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

export function AdminIngestionPage() {
  const { refreshOverview, setError } = useAppData();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const [jobs, setJobs] = useState<IngestionJob[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [fileSelectionError, setFileSelectionError] = useState<string | null>(null);
  const [clearIndex, setClearIndex] = useState(false);
  const [replace, setReplace] = useState(true);
  const [continueOnError, setContinueOnError] = useState(true);
  const [isLoading, setLoading] = useState(true);
  const [isUploading, setUploading] = useState(false);
  const [isDragging, setDragging] = useState(false);

  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) ?? jobs[0],
    [jobs, selectedJobId],
  );
  const unsupportedFiles = useMemo(
    () => files.filter((file) => !SUPPORTED_UPLOAD_EXTENSIONS.has(fileExtension(file.name))),
    [files],
  );
  const hasActiveJob = jobs.some((job) => job.status === "queued" || job.status === "running");
  const canSubmit = files.length > 0 && !unsupportedFiles.length && !isUploading;

  useEffect(() => {
    void refreshJobs();
  }, []);

  useEffect(() => {
    if (!hasActiveJob) return;
    const timer = window.setInterval(() => void refreshJobs({ silent: true }), POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [hasActiveJob]);

  async function refreshJobs({ silent = false }: { silent?: boolean } = {}) {
    if (!silent) setLoading(true);
    setError(null);
    try {
      const payload = await listIngestionJobs();
      setJobs(payload.jobs);
      setSelectedJobId((current) => current ?? payload.jobs[0]?.id ?? null);
      if (!payload.jobs.some((job) => job.status === "queued" || job.status === "running")) {
        await refreshOverview("refresh");
      }
    } catch (error) {
      setError(messageFromError(error));
    } finally {
      if (!silent) setLoading(false);
    }
  }

  async function refreshSelectedJob(jobId: string) {
    setError(null);
    try {
      const job = await getIngestionJob(jobId);
      setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)]);
      setSelectedJobId(job.id);
    } catch (error) {
      setError(messageFromError(error));
    }
  }

  async function submitUpload(event: FormEvent) {
    event.preventDefault();
    if (!files.length || isUploading) return;

    if (unsupportedFiles.length) {
      setFileSelectionError(
        `Remove unsupported file type(s): ${unsupportedFiles
          .slice(0, 4)
          .map((file) => file.name)
          .join(", ")}${unsupportedFiles.length > 4 ? ", ..." : ""}`,
      );
      return;
    }

    setUploading(true);
    setError(null);
    setFileSelectionError(null);
    try {
      const response = await createIngestionJob({
        files,
        clear_index: clearIndex,
        replace,
        continue_on_error: continueOnError,
      });
      setFiles([]);
      setJobs((current) => [response.job, ...current.filter((job) => job.id !== response.job.id)]);
      setSelectedJobId(response.job.id);
    } catch (error) {
      setError(messageFromError(error));
    } finally {
      setUploading(false);
    }
  }

  function chooseFiles(event: ChangeEvent<HTMLInputElement>) {
    acceptSelectedFiles(Array.from(event.target.files ?? []));
    event.target.value = "";
  }

  function chooseFolder(event: ChangeEvent<HTMLInputElement>) {
    acceptSelectedFiles(Array.from(event.target.files ?? []));
    event.target.value = "";
  }

  function handleFileDrag(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = "copy";
    setDragging(true);
  }

  function handleFileDragLeave(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    setDragging(false);
  }

  async function handleFileDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    setDragging(false);
    setFileSelectionError(null);

    try {
      acceptSelectedFiles(await filesFromDrop(event.dataTransfer));
    } catch (error) {
      setFileSelectionError(messageFromError(error));
    }
  }

  function acceptSelectedFiles(selectedFiles: File[]) {
    const uniqueFiles = dedupeFiles(selectedFiles).filter((file) => file.name);
    setFiles(uniqueFiles);
    setFileSelectionError(
      uniqueFiles.length ? null : "No readable documents were found in that selection.",
    );
  }

  return (
    <section className="ingestion-layout">
      <Panel className="upload-panel" eyebrow="Upload" icon={<UploadCloud size={20} />} title="Create Ingestion Job">
        <form className="upload-form" onSubmit={(event) => void submitUpload(event)}>
          <div
            className={isDragging ? "file-drop dragging" : "file-drop"}
            onDragEnter={handleFileDrag}
            onDragLeave={handleFileDragLeave}
            onDragOver={handleFileDrag}
            onDrop={handleFileDrop}
          >
            <FileUp size={26} />
            <strong>{files.length ? `${files.length} file(s) ready` : "Drop documents here"}</strong>
            <span>Drop files or folders, or choose them from your computer.</span>
            <div className="upload-actions">
              <Button
                icon={<FileUp size={16} />}
                onClick={() => fileInputRef.current?.click()}
                variant="secondary"
              >
                Choose files
              </Button>
              <Button
                icon={<FolderOpen size={16} />}
                onClick={() => folderInputRef.current?.click()}
                variant="secondary"
              >
                Choose folder
              </Button>
            </div>
            <input
              aria-label="Choose documents to ingest"
              className="visually-hidden-input"
              multiple
              onChange={chooseFiles}
              ref={fileInputRef}
              type="file"
            />
            <input
              aria-label="Choose a folder to ingest"
              className="visually-hidden-input"
              multiple
              onChange={chooseFolder}
              ref={folderInputRef}
              type="file"
              {...({ directory: "", webkitdirectory: "" } as Record<string, string>)}
            />
          </div>

          {fileSelectionError && <div className="selection-error">{fileSelectionError}</div>}

          {!!files.length && (
            <div className="selected-files">
              {files.map((file) => (
                <span
                  className={SUPPORTED_UPLOAD_EXTENSIONS.has(fileExtension(file.name)) ? "" : "unsupported"}
                  key={fileKey(file)}
                >
                  {displayFileName(file)}
                </span>
              ))}
            </div>
          )}

          <div className="option-grid">
            <label className="toggle-row">
              <input
                checked={replace}
                onChange={(event) => setReplace(event.target.checked)}
                type="checkbox"
              />
              <span>Replace matching documents</span>
            </label>
            <label className="toggle-row">
              <input
                checked={continueOnError}
                onChange={(event) => setContinueOnError(event.target.checked)}
                type="checkbox"
              />
              <span>Continue when one file fails</span>
            </label>
            <label className="toggle-row danger-toggle">
              <input
                checked={clearIndex}
                onChange={(event) => setClearIndex(event.target.checked)}
                type="checkbox"
              />
              <span>Clear index before ingest</span>
            </label>
          </div>

          <Button
            disabled={!canSubmit}
            icon={<UploadCloud size={17} />}
            type="submit"
            variant="primary"
          >
            {isUploading ? "Uploading" : "Start Ingestion"}
          </Button>
        </form>
      </Panel>

      <Panel
        className="jobs-panel"
        eyebrow="Jobs"
        icon={
          <Button
            aria-label="Refresh ingestion jobs"
            icon={<RefreshCw size={16} />}
            onClick={() => void refreshJobs()}
            variant="icon"
          />
        }
        title="Ingestion Runs"
      >
        {isLoading ? (
          <Skeleton count={5} />
        ) : jobs.length ? (
          <div className="job-list">
            {jobs.map((job) => (
              <button
                className={job.id === selectedJob?.id ? "job-row active" : "job-row"}
                key={job.id}
                onClick={() => {
                  setSelectedJobId(job.id);
                  void refreshSelectedJob(job.id);
                }}
                type="button"
              >
                <span>
                  <strong>{job.file_count} file(s)</strong>
                  <small>{shortJobId(job.id)}</small>
                </span>
                <StatusPill status={job.status} />
              </button>
            ))}
          </div>
        ) : (
          <EmptyState icon={<Clock size={22} />}>No ingestion jobs yet.</EmptyState>
        )}
      </Panel>

      <Panel className="job-detail-panel" eyebrow="Selected Job" title={selectedJob ? shortJobId(selectedJob.id) : "No job selected"}>
        {selectedJob ? <JobDetail job={selectedJob} /> : <EmptyState>No job selected.</EmptyState>}
      </Panel>
    </section>
  );
}

async function filesFromDrop(dataTransfer: DataTransfer): Promise<File[]> {
  const entries = Array.from(dataTransfer.items)
    .map((item) => item.webkitGetAsEntry())
    .filter((entry): entry is FileSystemEntry => entry !== null);

  if (!entries.length) {
    return Array.from(dataTransfer.files);
  }

  const nestedFiles = await Promise.all(entries.map((entry) => filesFromEntry(entry)));
  return nestedFiles.flat();
}

async function filesFromEntry(entry: FileSystemEntry): Promise<File[]> {
  if (entry.isFile) {
    return [await fileFromEntry(entry as FileSystemFileEntry)];
  }

  if (entry.isDirectory) {
    return filesFromDirectory(entry as FileSystemDirectoryEntry);
  }

  return [];
}

function fileFromEntry(entry: FileSystemFileEntry): Promise<File> {
  return new Promise((resolve, reject) => {
    entry.file(resolve, reject);
  });
}

async function filesFromDirectory(entry: FileSystemDirectoryEntry): Promise<File[]> {
  const reader = entry.createReader();
  const files: File[] = [];

  while (true) {
    const entries = await readDirectoryBatch(reader);
    if (!entries.length) break;

    const nestedFiles = await Promise.all(entries.map((child) => filesFromEntry(child)));
    files.push(...nestedFiles.flat());
  }

  return files;
}

function readDirectoryBatch(
  reader: FileSystemDirectoryReader,
): Promise<FileSystemEntry[]> {
  return new Promise((resolve, reject) => {
    reader.readEntries(resolve, reject);
  });
}

function dedupeFiles(selectedFiles: File[]): File[] {
  const seen = new Set<string>();
  const uniqueFiles: File[] = [];

  for (const file of selectedFiles) {
    const key = fileKey(file);
    if (seen.has(key)) continue;
    seen.add(key);
    uniqueFiles.push(file);
  }

  return uniqueFiles;
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

function JobDetail({ job }: { job: IngestionJob }) {
  const latestEvents = [...job.events].reverse().slice(0, 12);

  return (
    <div className="job-detail">
      <div className="job-summary-grid">
        <JobStat label="Status" value={job.status} />
        <JobStat label="Files" value={String(job.file_count)} />
        <JobStat label="Parsed" value={String(job.parsed_document_count)} />
        <JobStat label="Parents" value={String(job.parent_chunk_count)} />
        <JobStat label="Children" value={String(job.child_chunk_count)} />
        <JobStat label="Indexed" value={String(job.indexed_child_count)} />
      </div>

      {job.error_message && (
        <div className="job-error">
          <strong>{job.error_code}</strong>
          <span>{job.error_message}</span>
        </div>
      )}

      <div className="job-timings">
        {Object.entries(job.timings_ms).map(([key, value]) => (
          <span key={key}>
            {key}: <strong>{formatMs(value)}</strong>
          </span>
        ))}
        {!Object.keys(job.timings_ms).length && <span>No timings yet.</span>}
      </div>

      <div className="event-timeline">
        {latestEvents.map((event, index) => (
          <article className="event-row" key={`${event.stage}-${event.timestamp}-${index}`}>
            <span className={`event-dot ${event.status}`} />
            <div>
              <strong>{event.stage.replaceAll("_", " ")}</strong>
              <p>{event.message}</p>
              <small>
                {event.duration_ms !== null ? `${formatMs(event.duration_ms)} - ` : ""}
                {event.path ?? event.timestamp ?? ""}
              </small>
            </div>
          </article>
        ))}
        {!latestEvents.length && <EmptyState compact>Waiting for job progress.</EmptyState>}
      </div>
    </div>
  );
}

function JobStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="job-stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function StatusPill({ status }: { status: IngestionJobStatus }) {
  return <span className={`status-pill ${status}`}>{status}</span>;
}

function shortJobId(jobId: string): string {
  return jobId.slice(0, 8);
}

function formatMs(value: number): string {
  return value >= 1000 ? `${(value / 1000).toFixed(2)}s` : `${value.toFixed(1)}ms`;
}
