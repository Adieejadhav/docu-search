import { FileText } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAppData } from "../../../app/AppDataContext";
import { EmptyState } from "../../../components/ui/EmptyState";
import { formatDateTime } from "../../../lib/format";
import type { DocumentSummary } from "../../../services/types";
import { BlueprintPage } from "../AdminBlueprintPrimitives";

export function AdminIndexPage() {
  const { documents, isRefreshing } = useAppData();
  const navigate = useNavigate();
  const rows = documents?.documents ?? [];
  const parentChunkTotal = rows.reduce(
    (total, document) => total + document.parent_chunk_count,
    0,
  );
  const childChunkTotal = rows.reduce(
    (total, document) => total + document.child_chunk_count,
    0,
  );

  return (
    <BlueprintPage>
      <section className="document-summary-strip" aria-label="Document index summary">
        <SummaryCard
          detail="indexed records"
          label="Total Documents"
          value={formatMetric(documents?.total)}
        />
        <SummaryCard
          detail="retrieval groups"
          label="Parent Chunks"
          value={formatMetric(parentChunkTotal)}
        />
        <SummaryCard
          detail="search records"
          label="Child Chunks"
          value={formatMetric(childChunkTotal)}
        />
      </section>

      <section className="ops-panel ops-panel-full">
        <header>
          <div>
            <h2>Indexed Documents</h2>
            <p>Documents currently stored in the RAG index</p>
          </div>
        </header>
        <div className="ops-panel-body">
          {isRefreshing && !documents ? (
            <EmptyState icon={<FileText size={22} />}>Loading indexed documents.</EmptyState>
          ) : (
            <div className="ops-table-wrap">
              <table className="ops-table">
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Type</th>
                    <th>Parent chunks</th>
                    <th>Child chunks</th>
                    <th>Created</th>
                    <th>Updated</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.length ? (
                    rows.map((document) => (
                      <DocumentRow
                        document={document}
                        key={document.id}
                        onView={() => navigate(`/admin/documents/${document.id}`)}
                      />
                    ))
                  ) : (
                    <tr>
                      <td colSpan={7}>No indexed documents.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </section>
    </BlueprintPage>
  );
}

function SummaryCard({
  detail,
  label,
  value,
}: {
  detail: string;
  label: string;
  value: string;
}) {
  return (
    <article className="document-summary-card">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function DocumentRow({
  document,
  onView,
}: {
  document: DocumentSummary;
  onView: () => void;
}) {
  return (
    <tr>
      <td>
        <strong>{document.file_name}</strong>
        <br />
        <small>{document.title || document.id}</small>
      </td>
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
      <td>
        <button onClick={onView} type="button">
          View
        </button>
      </td>
    </tr>
  );
}

function formatMetric(value: number | null | undefined): string {
  return typeof value === "number" ? new Intl.NumberFormat().format(value) : "-";
}
