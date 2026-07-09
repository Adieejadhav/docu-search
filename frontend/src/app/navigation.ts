import {
  Activity,
  Database,
  FileText,
  Gauge,
  History,
  MessageSquareText,
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
    label: "Ingestion Jobs",
    title: "Ingestion Jobs",
    eyebrow: "Operations / Ingestion",
    description: "Inspect document ingestion jobs, indexed chunks, failures, and job events.",
    section: "admin",
    icon: UploadCloud,
  },
  {
    to: "/admin/vector-indexes",
    label: "Index",
    title: "Search Index",
    eyebrow: "Operations / Index",
    description: "Monitor vector coverage, retrieval readiness, and index maintenance controls.",
    section: "admin",
    icon: Database,
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
