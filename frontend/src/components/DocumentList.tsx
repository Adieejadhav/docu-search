import { Eye, FileText, RefreshCw, Trash2 } from "lucide-react";
import { Button } from "./ui/Button";
import type { DocumentSummary } from "../services/types";

interface DocumentListProps {
  documents: DocumentSummary[];
  onDelete?: (document: DocumentSummary) => void;
  onInspect?: (document: DocumentSummary) => void;
  onReindex?: (document: DocumentSummary) => void;
}

export function DocumentList({ documents, onDelete, onInspect, onReindex }: DocumentListProps) {
  if (!documents.length) {
    return (
      <div className="empty-state compact">
        <FileText size={22} />
        <span>No indexed documents.</span>
      </div>
    );
  }

  return (
    <div className="document-list">
      {documents.map((document) => (
        <article className="document-row" key={document.id}>
          <div>
            <strong>{document.file_name}</strong>
            <span>{document.title}</span>
          </div>
          <div className="document-counts">
            <span>{document.file_type}</span>
            <span>{document.child_chunk_count} chunks</span>
          </div>
          {(onDelete || onInspect || onReindex) && (
            <div className="document-actions">
              {onInspect && (
                <Button
                  icon={<Eye size={15} />}
                  onClick={() => onInspect(document)}
                  size="small"
                >
                  Inspect
                </Button>
              )}
              {onReindex && (
                <Button
                  icon={<RefreshCw size={15} />}
                  onClick={() => onReindex(document)}
                  size="small"
                >
                  Re-index
                </Button>
              )}
              {onDelete && (
                <Button
                  icon={<Trash2 size={15} />}
                  onClick={() => onDelete(document)}
                  size="small"
                  variant="danger"
                >
                  Delete
                </Button>
              )}
            </div>
          )}
        </article>
      ))}
    </div>
  );
}
