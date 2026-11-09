import { AlertCircle, FolderOpen, RefreshCw } from "lucide-react";

export function Loading({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex min-h-48 items-center justify-center gap-3 rounded-2xl border border-slate-200 bg-white px-5 py-12 shadow-sm">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-brand-500" aria-hidden="true" />
      <span className="text-sm font-medium text-slate-500">{label}</span>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex min-h-64 flex-col items-center justify-center px-5 py-12 text-center">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-slate-200 bg-slate-50 text-slate-400">
        <FolderOpen size={25} strokeWidth={1.7} />
      </div>
      <h3 className="text-sm font-bold text-slate-800">{title}</h3>
      {description && <p className="mt-1.5 max-w-md text-sm leading-6 text-slate-500">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className="flex min-h-56 flex-col items-center justify-center px-5 py-12 text-center">
      <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-red-100 bg-red-50 text-red-500">
        <AlertCircle size={25} strokeWidth={1.8} />
      </div>
      <h3 className="text-sm font-bold text-slate-800">We couldn’t load this information</h3>
      <p className="mt-1.5 max-w-md text-sm leading-6 text-slate-500">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 inline-flex min-h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-xs font-bold text-slate-700 shadow-sm transition-colors hover:bg-slate-50"
        >
          <RefreshCw size={14} />
          Try again
        </button>
      )}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-7 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <div className="mb-2 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-400">Agency workspace</div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 sm:text-[28px]">{title}</h1>
        {description && <p className="mt-1.5 max-w-2xl text-sm leading-6 text-slate-500">{description}</p>}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

const BADGE_STYLES: Record<string, string> = {
  open: "border-emerald-100 bg-emerald-50 text-emerald-700",
  pending: "border-amber-100 bg-amber-50 text-amber-700",
  resolved: "border-blue-100 bg-blue-50 text-blue-700",
  closed: "border-slate-200 bg-slate-100 text-slate-600",
};

export function Badge({ status }: { status: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold capitalize tracking-wide ${BADGE_STYLES[status] ?? "border-slate-200 bg-slate-100 text-slate-600"}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />
      {status.replaceAll("_", " ")}
    </span>
  );
}
