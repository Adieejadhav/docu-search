import { FileText } from "lucide-react";
import { useAppData } from "../../../app/AppDataContext";
import { DocumentList } from "../../../components/DocumentList";
import { EmptyState } from "../../../components/ui/EmptyState";
import { Panel } from "../../../components/ui/Panel";

export function AdminIndexPage() {
  const { documents, isRefreshing } = useAppData();
  const rows = documents?.documents ?? [];

  return (
    <Panel eyebrow="Index Inventory" title="Documents">
      {isRefreshing && !documents ? (
        <EmptyState icon={<FileText size={22} />}>Loading indexed documents.</EmptyState>
      ) : (
        <DocumentList documents={rows} />
      )}
    </Panel>
  );
}
