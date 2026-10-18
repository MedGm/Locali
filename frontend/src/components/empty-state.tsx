import type { LucideIcon } from "lucide-react";

import { cn } from "@/lib/utils";

export function EmptyState({
  icon: Icon,
  title,
  children,
  action,
  className,
}: {
  icon: LucideIcon;
  title: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center rounded-xl border border-dashed px-6 py-10 text-center", className)}>
      <span className="mb-3 flex size-11 items-center justify-center rounded-full bg-brand-soft text-primary">
        <Icon className="size-5" />
      </span>
      <p className="font-medium">{title}</p>
      {children && <div className="mt-1 max-w-sm text-sm text-muted-foreground">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
