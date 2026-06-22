import { Activity, ClipboardCheck, FileText, History, MessageSquareText, Search, Settings, UploadCloud } from "lucide-react";
import type { ComponentType } from "react";

export type AppSection = "chat" | "admin";

export interface NavigationItem {
  to: string;
  label: string;
  title: string;
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
    section: "admin",
    icon: Activity,
  },
];

export const adminNavigation: NavigationItem[] = [
  {
    to: "/admin/overview",
    label: "Overview",
    title: "RAG Admin Console",
    section: "admin",
    icon: Activity,
  },
  {
    to: "/admin/test-bench",
    label: "Pipeline Lab",
    title: "Pipeline Lab",
    section: "admin",
    icon: Search,
  },
  {
    to: "/admin/evaluation",
    label: "Evaluation",
    title: "RAG Evaluation",
    section: "admin",
    icon: ClipboardCheck,
  },
  {
    to: "/admin/traces",
    label: "Traces",
    title: "RAG Trace History",
    section: "admin",
    icon: History,
  },
  {
    to: "/admin/index",
    label: "Index",
    title: "Index Inventory",
    section: "admin",
    icon: FileText,
  },
  {
    to: "/admin/ingestion",
    label: "Ingestion",
    title: "Ingestion Jobs",
    section: "admin",
    icon: UploadCloud,
  },
  {
    to: "/admin/ops",
    label: "Ops",
    title: "Operations",
    section: "admin",
    icon: Settings,
  },
];

export function titleForPath(pathname: string): string {
  return (
    [...adminNavigation, ...primaryNavigation]
      .filter((item) => pathname === item.to || pathname.startsWith(`${item.to}/`))
      .sort((left, right) => right.to.length - left.to.length)[0]?.title ?? "Document Chat"
  );
}
