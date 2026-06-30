import {
  Activity,
  Blocks,
  BookOpen,
  Bot,
  ClipboardCheck,
  Database,
  FileText,
  Gauge,
  History,
  MessageSquareText,
  PlugZap,
  Search,
  Settings,
  ShieldCheck,
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
      "Monitor system health, indexing readiness, retrieval quality, model usage, and production risk.",
    section: "admin",
    icon: Activity,
  },
  {
    to: "/admin/knowledge-bases",
    label: "Knowledge",
    title: "Knowledge Bases",
    eyebrow: "Operations / Knowledge",
    description: "Manage knowledge bases, owners, indexing policy, and source coverage.",
    section: "admin",
    icon: BookOpen,
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
    description: "Track document ingestion, extraction, chunking, embedding, and indexing.",
    section: "admin",
    icon: UploadCloud,
  },
  {
    to: "/admin/vector-indexes",
    label: "Index",
    title: "Vector Indexes",
    eyebrow: "Operations / Index",
    description: "Monitor vector stores, embedding dimensions, record counts, and rebuild status.",
    section: "admin",
    icon: Database,
  },
  {
    to: "/admin/retrieval-profiles",
    label: "Retrieval",
    title: "Retrieval Profiles",
    eyebrow: "Operations / Retrieval",
    description: "Configure query rewrite, hybrid search, reranking, top-k, and context policy.",
    section: "admin",
    icon: Search,
  },
  {
    to: "/admin/models-prompts",
    label: "Generation",
    title: "Models & Prompt Management",
    eyebrow: "Operations / Generation",
    description: "Manage LLM providers, prompt versions, guardrails, and deployment status.",
    section: "admin",
    icon: Bot,
  },
  {
    to: "/admin/evaluations",
    label: "Evaluation",
    title: "Evaluation Center",
    eyebrow: "Operations / Evaluation",
    description: "Create datasets, run evaluations, compare candidates, and detect regressions.",
    section: "admin",
    icon: ClipboardCheck,
  },
  {
    to: "/admin/firewall",
    label: "Safety",
    title: "AI Data Firewall",
    eyebrow: "Operations / Safety",
    description: "Review policy rules, blocked events, sensitive data findings, and response risks.",
    section: "admin",
    icon: ShieldCheck,
  },
  {
    to: "/admin/traces",
    label: "Observability",
    title: "Trace Explorer",
    eyebrow: "Operations / Observability",
    description: "Debug retrieval, generation, citations, latency, and trace-level failures.",
    section: "admin",
    icon: History,
  },
  {
    to: "/admin/connectors",
    label: "Connectors",
    title: "Source Connectors",
    eyebrow: "Operations / Connectors",
    description: "Monitor source syncs, connector health, authentication, and import flow.",
    section: "admin",
    icon: PlugZap,
  },
  {
    to: "/admin/jobs-workers",
    label: "Ops",
    title: "Jobs & Worker Health",
    eyebrow: "Operations / Ops",
    description: "Track queues, workers, failed jobs, retries, and background processing capacity.",
    section: "admin",
    icon: Gauge,
  },
  {
    to: "/admin/settings",
    label: "Settings",
    title: "System Settings",
    eyebrow: "Operations / Settings",
    description: "Configure defaults, retrieval behavior, feature flags, and environment health.",
    section: "admin",
    icon: Settings,
  },
];

export const adminRouteMetadata: NavigationItem[] = [
  {
    to: "/admin/documents/detail",
    label: "Document Detail",
    title: "Document Detail",
    eyebrow: "Operations / Knowledge",
    description: "Inspect document metadata, chunks, versions, source text, and indexing decisions.",
    section: "admin",
    icon: FileText,
  },
  {
    to: "/admin/chunks",
    label: "Chunks",
    title: "Chunk Management",
    eyebrow: "Operations / Index",
    description: "Review chunk hierarchy, tokenization, metadata, and retrieval suitability.",
    section: "admin",
    icon: Blocks,
  },
  {
    to: "/admin/playground",
    label: "Playground",
    title: "Query Playground",
    eyebrow: "Operations / Retrieval",
    description: "Test prompts, retrieval profiles, citations, and source grounding before release.",
    section: "admin",
    icon: MessageSquareText,
  },
  {
    to: "/admin/feedback",
    label: "Feedback",
    title: "Human Feedback Review",
    eyebrow: "Operations / Evaluation",
    description: "Turn user feedback into trace review, document fixes, prompt work, and eval cases.",
    section: "admin",
    icon: ClipboardCheck,
  },
  {
    to: "/admin/usage-cost",
    label: "Usage",
    title: "Usage, Latency & Cost",
    eyebrow: "Operations / Observability",
    description: "Analyze query volume, latency distribution, token usage, and provider cost.",
    section: "admin",
    icon: Gauge,
  },
  {
    to: "/admin/audit-access",
    label: "Audit",
    title: "Audit & Access Control",
    eyebrow: "Operations / Settings",
    description: "Manage admin roles, permissions, sensitive access, and immutable audit logs.",
    section: "admin",
    icon: ShieldCheck,
  },
];

export function navigationItemForPath(pathname: string): NavigationItem | undefined {
  const normalized = pathname.replace(/\/$/, "");
  return [...adminRouteMetadata, ...adminNavigation, ...primaryNavigation]
    .filter((item) => normalized === item.to || normalized.startsWith(`${item.to}/`))
    .sort((left, right) => right.to.length - left.to.length)[0];
}

export function titleForPath(pathname: string): string {
  return navigationItemForPath(pathname)?.title ?? "Document Chat";
}
