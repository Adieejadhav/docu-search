import { FileText } from "lucide-react";
import type { DocumentSummary } from "../services/types";

export function DocumentList({ documents }: { documents: DocumentSummary[] }) {
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
        </article>
      ))}
    </div>
  );
}
