import { FileText, Layers3 } from "lucide-react";
import { useState } from "react";
import { useAppData } from "../../../app/AppDataContext";
import { DocumentList } from "../../../components/DocumentList";
import { Button } from "../../../components/ui/Button";
import { ConfirmDialog } from "../../../components/ui/ConfirmDialog";
import { EmptyState } from "../../../components/ui/EmptyState";
import { Panel } from "../../../components/ui/Panel";
import { Skeleton } from "../../../components/ui/Skeleton";
import { messageFromError } from "../../../lib/format";
import { deleteDocument, getDocumentChunks, reindexDocument } from "../../../services/api";
import type { DocumentChunkListResponse, DocumentSummary } from "../../../services/types";

export function AdminIndexPage() {
  const { documents, isRefreshing, refreshOverview, setError } = useAppData();
  const [selectedDocument, setSelectedDocument] = useState<DocumentSummary | null>(null);
  const [documentToDelete, setDocumentToDelete] = useState<DocumentSummary | null>(null);
  const [chunkDetail, setChunkDetail] = useState<DocumentChunkListResponse | null>(null);
  const [isLoadingChunks, setLoadingChunks] = useState(false);
  const [isDeleting, setDeleting] = useState(false);
  const [isReindexing, setReindexing] = useState(false);
  const rows = documents?.documents ?? [];

  async function inspectDocument(document: DocumentSummary) {
    setSelectedDocument(document);
    setChunkDetail(null);
    setLoadingChunks(true);
    setError(null);
    try {
      setChunkDetail(await getDocumentChunks(document.id));
    } catch (error) {
      setError(messageFromError(error));
    } finally {
      setLoadingChunks(false);
    }
  }

  async function confirmDelete() {
    if (!documentToDelete) return;

    setDeleting(true);
    setError(null);
    try {
      await deleteDocument(documentToDelete.id);
      if (selectedDocument?.id === documentToDelete.id) {
        setSelectedDocument(null);
        setChunkDetail(null);
      }
      setDocumentToDelete(null);
      await refreshOverview();
    } catch (error) {
      setError(messageFromError(error));
    } finally {
      setDeleting(false);
    }
  }

  async function startReindex(document: DocumentSummary) {
    setReindexing(true);
    setError(null);
    try {
      await reindexDocument(document.id);
      await refreshOverview();
    } catch (error) {
      setError(messageFromError(error));
    } finally {
      setReindexing(false);
    }
  }

  return (
    <section className="index-management-layout">
      <Panel eyebrow="Index Inventory" title="Documents">
        {isRefreshing && !documents ? (
          <EmptyState icon={<FileText size={22} />}>Loading indexed documents.</EmptyState>
        ) : (
          <DocumentList
            documents={rows}
            onDelete={setDocumentToDelete}
            onInspect={(document) => void inspectDocument(document)}
            onReindex={(document) => void startReindex(document)}
          />
        )}
        {isReindexing && <p className="panel-caption">Re-index job queued.</p>}
      </Panel>

      <Panel
        eyebrow="Document Detail"
        icon={<Layers3 size={20} />}
        title={selectedDocument?.file_name ?? "Select a document"}
      >
        {isLoadingChunks && <Skeleton count={4} />}
        {!isLoadingChunks && !selectedDocument && (
          <EmptyState icon={<Layers3 size={22} />}>
            Inspect a document to review stored parent-child chunks.
          </EmptyState>
        )}
        {!isLoadingChunks && selectedDocument && chunkDetail && (
          <div className="chunk-inspector">
            <div className="chunk-inspector-summary">
              <span>{chunkDetail.total} child chunks</span>
              <span>{chunkDetail.document.parent_chunk_count} parent chunks</span>
              <span>{chunkDetail.document.file_type}</span>
            </div>
            {chunkDetail.chunks.slice(0, 8).map((chunk) => (
              <article className="chunk-row" key={chunk.child_chunk_id}>
                <header>
                  <strong>Child #{chunk.child_index}</strong>
                  <small>{chunk.source_refs.join(", ") || "no source ref"}</small>
                </header>
                <p>{chunk.child_text}</p>
                <small>{chunk.parent_path.join(" > ") || "root"}</small>
              </article>
            ))}
          </div>
        )}
      </Panel>

      <ConfirmDialog
        confirmDisabled={isDeleting}
        confirmLabel={isDeleting ? "Deleting" : "Delete Document"}
        isOpen={!!documentToDelete}
        onCancel={() => setDocumentToDelete(null)}
        onConfirm={() => void confirmDelete()}
        title="Delete indexed document?"
      >
        <p>
          This removes the document, parent chunks, child chunks, and embeddings for{" "}
          <strong>{documentToDelete?.file_name}</strong>. Source files are not deleted.
        </p>
      </ConfirmDialog>
    </section>
  );
}
