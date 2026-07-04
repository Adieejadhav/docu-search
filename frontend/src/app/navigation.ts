import {
  Activity,
  ClipboardCheck,
  Database,
  FileText,
  Gauge,
  History,
  MessageSquareText,
  Search,
  UploadCloud,
} from "lucide-react";
import type { ComponentType } from "react";

export type AppSection = "chat" | "admin";

export interface NavigationItem {
  to: string;
  label: string;
  title: string;
  eyebrow?: string;
  description?: string;
  section: AppSection;
  icon: ComponentType<{ size?: number }>;
}

export const primaryNavigation: NavigationItem[] = [
  {
    to: "/chat",
    label: "Chat",
    title: "Document Chat",
    section: "chat",
    icon: MessageSquareText,
  },
  {
    to: "/admin/overview",
    label: "Admin",
    title: "RAG Admin Console",
    eyebrow: "Operations",
    description: "Monitor and operate the production RAG workspace.",
    section: "admin",
    icon: Activity,
  },
];

export const adminNavigation: NavigationItem[] = [
  {
    to: "/admin/overview",
    label: "Overview",
    title: "RAG Operations Overview",
    eyebrow: "Operations / Overview",
    description:
      "Monitor backend health, index readiness, query volume, ingestion jobs, and recent traces.",
    section: "admin",
    icon: Activity,
  },
  {
    to: "/admin/documents",
    label: "Documents",
    title: "Documents",
    eyebrow: "Operations / Knowledge",
    description: "Inspect indexed documents, versions, metadata, and ingestion state.",
    section: "admin",
    icon: FileText,
  },
  {
    to: "/admin/pipeline",
    label: "Pipeline",
    title: "Pipeline Monitor",
    eyebrow: "Operations / Pipeline",
    description: "Track ingestion jobs, stage timings, indexing totals, failures, and job events.",
    section: "admin",
    icon: UploadCloud,
  },
  {
    to: "/admin/vector-indexes",
    label: "Index",
    title: "Vector Indexes",
    eyebrow: "Operations / Index",
    description: "Monitor document, chunk, and vector counts with index maintenance controls.",
    section: "admin",
    icon: Database,
  },
  {
    to: "/admin/playground",
    label: "Playground",
    title: "Query Playground",
    eyebrow: "Operations / Retrieval",
    description: "Test live search and answer generation against the indexed documents.",
    section: "admin",
    icon: Search,
  },
  {
    to: "/admin/traces",
    label: "Traces",
    title: "Trace Explorer",
    eyebrow: "Operations / Observability",
    description: "Debug retrieval, generation, citations, latency, and trace-level failures.",
    section: "admin",
    icon: History,
  },
  {
    to: "/admin/evaluations",
    label: "Evaluation",
    title: "Evaluation Center",
    eyebrow: "Operations / Evaluation",
    description: "Run the current evaluation cases and inspect saved evaluation history.",
    section: "admin",
    icon: ClipboardCheck,
  },
  {
    to: "/admin/test-bench",
    label: "Test Bench",
    title: "Pipeline Test Bench",
    eyebrow: "Operations / Test Bench",
    description: "Upload files, run pipeline stages, inspect retrieval, and test full RAG answers.",
    section: "admin",
    icon: Gauge,
  },
];

export const adminRouteMetadata: NavigationItem[] = [];

export function navigationItemForPath(pathname: string): NavigationItem | undefined {
  const normalized = pathname.replace(/\/$/, "");
  return [...adminRouteMetadata, ...adminNavigation, ...primaryNavigation]
    .filter((item) => normalized === item.to || normalized.startsWith(`${item.to}/`))
    .sort((left, right) => right.to.length - left.to.length)[0];
}

export function titleForPath(pathname: string): string {
  return navigationItemForPath(pathname)?.title ?? "Document Chat";
}
