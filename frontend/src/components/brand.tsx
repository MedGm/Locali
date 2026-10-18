import { cn } from "@/lib/utils";

// The Locali mark: an L between code brackets, on an indigo tile. Drawn with strokes so it stays
// crisp from the 16 px favicon up to the sidebar.
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" aria-hidden className={cn("size-8", className)}>
      <defs>
        <linearGradient id="locali-tile" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6366f1" />
          <stop offset="1" stopColor="#4338ca" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="url(#locali-tile)" />
      <path d="M10 10.5 5.5 16l4.5 5.5M22 10.5l4.5 5.5-4.5 5.5" fill="none" stroke="#c7d2fe" strokeWidth="2.2"
            strokeLinecap="round" strokeLinejoin="round" />
      <path d="M13.6 9.5v12h5.4" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round"
            strokeLinejoin="round" />
    </svg>
  );
}

export function Wordmark({ compact }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <LogoMark className="size-8 shrink-0 drop-shadow-sm" />
      {!compact && (
        <span className="flex flex-col leading-none">
          <span className="text-[15px] font-semibold tracking-tight">Locali</span>
          <span className="mt-1 text-[11px] font-medium text-muted-foreground">local code assistant</span>
        </span>
      )}
    </span>
  );
}
