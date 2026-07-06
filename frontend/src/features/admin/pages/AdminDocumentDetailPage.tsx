import { useEffect, useState } from "react";
import { ArrowLeft, FileText, RefreshCw, Trash2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { useAppData } from "../../../app/AppDataContext";
import { Button } from "../../../components/ui/Button";
import { ConfirmDialog } from "../../../components/ui/ConfirmDialog";
import { EmptyState } from "../../../components/ui/EmptyState";
import { Skeleton } from "../../../components/ui/Skeleton";
import { formatDateTime, messageFromError } from "../../../lib/format";
import { deleteDocument, getDocumentChunks, reindexDocument } from "../../../services/api";
import type { DocumentChunkListResponse, DocumentChunkSummary } from "../../../services/types";
import { BlueprintPage, BlueprintPanel } from "../AdminBlueprintPrimitives";

export function AdminDocumentDetailPage() {
  const { documentId } = useParams();
  const navigate = useNavigate();
  const { refreshOverview, setError: setGlobalError } = useAppData();
  const [chunkDetail, setChunkDetail] = useState<DocumentChunkListResponse | null>(null);
  const [isLoading, setLoading] = useState(true);
  const [isDeleting, setDeleting] = useState(false);
  const [isReindexing, setReindexing] = useState(false);
  const [isDeleteOpen, setDeleteOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void loadDocument();
  }, [documentId]);

  async function loadDocument() {
    if (!documentId) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    setGlobalError(null);
    try {
      setChunkDetail(await getDocumentChunks(documentId));
    } catch (caught) {
      const message = messageFromError(caught);
      setError(message);
      setGlobalError(message);
    } finally {
      setLoading(false);
    }
  }

  async function startReindex() {
    if (!documentId) return;

    setReindexing(true);
    setError(null);
    setGlobalError(null);
    try {
      await reindexDocument(documentId);
      await refreshOverview();
    } catch (caught) {
      const message = messageFromError(caught);
      setError(message);
      setGlobalError(message);
    } finally {
      setReindexing(false);
    }
  }

  async function confirmDelete() {
    if (!documentId) return;

    setDeleting(true);
    setError(null);
    setGlobalError(null);
    try {
      await deleteDocument(documentId);
      await refreshOverview();
      navigate("/admin/documents");
    } catch (caught) {
      const message = messageFromError(caught);
      setError(message);
      setGlobalError(message);
    } finally {
      setDeleting(false);
    }
  }

  const document = chunkDetail?.document;
  const chunks = chunkDetail?.chunks ?? [];
  const displayTitle = document ? cleanDocumentTitle(document.file_name, document.title) : "";

  return (
    <BlueprintPage>
      <section className="ops-panel ops-panel-full document-detail-hero">
        <header>
          <div className="document-detail-title">
            <h2>{document?.file_name ?? "Document Detail"}</h2>
            <p>{displayTitle || "Indexed document details and stored chunks"}</p>
          </div>
          <div className="document-detail-actions">
            <Button icon={<ArrowLeft size={16} />} onClick={() => navigate("/admin/documents")}>
              Back
            </Button>
            <Button
              disabled={!documentId || isReindexing}
              icon={<RefreshCw size={16} />}
              onClick={() => void startReindex()}
            >
              {isReindexing ? "Queued" : "Re-index"}
            </Button>
            <Button
              disabled={!documentId || isDeleting}
              icon={<Trash2 size={16} />}
              onClick={() => setDeleteOpen(true)}
              variant="danger"
            >
              Delete
            </Button>
          </div>
        </header>
      </section>

      {error && <div className="selection-error">{error}</div>}
      {isLoading ? (
        <BlueprintPanel title="Loading Document">
          <Skeleton count={6} />
        </BlueprintPanel>
      ) : document ? (
        <>
          <section className="ops-panel ops-panel-full">
            <header>
              <div>
                <h2>Document Summary</h2>
                <p>Index metadata for this document</p>
              </div>
            </header>
            <div className="ops-panel-body">
              <div className="ops-table-wrap">
                <table className="ops-table">
                  <thead>
                    <tr>
                      <th>Type</th>
                      <th>Parent chunks</th>
                      <th>Child chunks</th>
                      <th>Created</th>
                      <th>Updated</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>
                        <span className="document-table-pill type">{document.file_type}</span>
                      </td>
                      <td>
                        <span className="document-table-pill parent">
                          {formatMetric(document.parent_chunk_count)}
                        </span>
                      </td>
                      <td>
                        <span className="document-table-pill child">
                          {formatMetric(document.child_chunk_count)}
                        </span>
                      </td>
                      <td>{formatDateTime(document.created_at)}</td>
                      <td>{formatDateTime(document.updated_at)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          <BlueprintPanel
            description="Stored child chunks. Expand a row to read the chunk text."
            title="Stored Chunks"
          >
            {chunks.length ? (
              <div className="chunk-inspector">
                {chunks.map((chunk) => (
                  <ChunkCard chunk={chunk} key={chunk.child_chunk_id} />
                ))}
              </div>
            ) : (
              <EmptyState icon={<FileText size={22} />}>No chunks returned for this document.</EmptyState>
            )}
          </BlueprintPanel>
        </>
      ) : (
        <BlueprintPanel title="Document Not Found">
          <EmptyState icon={<FileText size={22} />}>The selected document could not be loaded.</EmptyState>
        </BlueprintPanel>
      )}

      <ConfirmDialog
        confirmDisabled={isDeleting}
        confirmLabel={isDeleting ? "Deleting" : "Delete Document"}
        isOpen={isDeleteOpen}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={() => void confirmDelete()}
        title="Delete indexed document?"
      >
        <p>
          This removes the document, parent chunks, child chunks, and embeddings for{" "}
          <strong>{document?.file_name}</strong>. Source files are not deleted.
        </p>
      </ConfirmDialog>
    </BlueprintPage>
  );
}

function ChunkCard({ chunk }: { chunk: DocumentChunkSummary }) {
  return (
    <details className="chunk-row chunk-collapsible">
      <summary>
        <span className="chunk-disclosure" aria-hidden="true" />
        <span className="chunk-summary-main">
          <strong>
            Chunk #{chunk.child_index}
          </strong>
          <small>Parent #{chunk.parent_index}</small>
        </span>
        <span className="chunk-summary-meta">
          {formatMetric(chunk.child_token_count)} tokens
        </span>
      </summary>
      <div className="chunk-content">
        <p>{chunk.child_text}</p>
      </div>
    </details>
  );
}

function cleanDocumentTitle(fileName: string, title: string): string {
  const normalizedFileName = fileName.replace(/\.[^.]+$/, "");
  return title && title !== fileName && title !== normalizedFileName ? title : "";
}

function formatMetric(value: number | null | undefined): string {
  return typeof value === "number" ? new Intl.NumberFormat().format(value) : "-";
}
