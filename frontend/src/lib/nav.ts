import {
  BarChart3,
  Boxes,
  FileDiff,
  FolderGit2,
  Home,
  ListChecks,
  type LucideIcon,
  Settings,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";

export type NavItem = { href: string; label: string; icon: LucideIcon; hint: string };

export const NAV_GROUPS: { label: string | null; items: NavItem[] }[] = [
  { label: null, items: [{ href: "/", label: "Home", icon: Home, hint: "Start here: what to do next" }] },
  {
    label: "Work",
    items: [
      { href: "/repos", label: "Repositories", icon: FolderGit2, hint: "Your projects and their status" },
      { href: "/runs", label: "Runs", icon: ListChecks, hint: "Every analysis and assistant run" },
      { href: "/patches", label: "Patches", icon: FileDiff, hint: "Changes waiting for your decision" },
    ],
  },
  {
    label: "Insights",
    items: [
      { href: "/trends", label: "Quality trends", icon: TrendingUp, hint: "How a repository changes over time" },
      { href: "/security", label: "Security", icon: ShieldCheck, hint: "Blocked actions and redactions" },
    ],
  },
  {
    label: "Platform",
    items: [
      { href: "/models", label: "Models", icon: Boxes, hint: "Which model runs, and how good it is" },
      { href: "/results", label: "Research results", icon: BarChart3, hint: "The benchmarks behind the model" },
      { href: "/settings", label: "Settings", icon: Settings, hint: "Configuration of this installation" },
    ],
  },
];

export const NAV: NavItem[] = NAV_GROUPS.flatMap((g) => g.items);

export function navFor(path: string | null): NavItem | undefined {
  if (!path) return undefined;
  return path === "/" ? NAV[0] : NAV.find((n) => n.href !== "/" && path.startsWith(n.href));
}
