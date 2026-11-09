import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  Inbox,
  LayoutDashboard,
  ShieldCheck,
  UsersRound,
} from "lucide-react";

const FEATURES = [
  {
    icon: Inbox,
    title: "One clear inbox",
    description: "Bring customer conversations into a focused workspace your team can manage together.",
  },
  {
    icon: ShieldCheck,
    title: "Isolation by design",
    description: "Each agency has its own protected workspace, users, customers, and operational data.",
  },
  {
    icon: UsersRound,
    title: "Teams that stay aligned",
    description: "Organize people, assign work, and keep ownership visible as your support operation grows.",
  },
];

export default function HomePage() {
  return (
    <main className="min-h-screen overflow-hidden bg-[#f4f6fa]">
      <header className="relative z-10 mx-auto flex w-full max-w-7xl items-center justify-between px-5 py-5 sm:px-8">
        <Link href="/" className="flex items-center gap-3" aria-label="M369 Support home">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500 text-base font-black text-white shadow-lg shadow-orange-500/20">
            M
          </span>
          <span className="text-base font-extrabold tracking-tight text-slate-900">
            M369 <span className="font-medium text-slate-500">Support</span>
          </span>
        </Link>
        <nav className="flex items-center gap-2 sm:gap-3" aria-label="Account">
          <Link
            href="/login"
            className="rounded-xl px-4 py-2.5 text-xs font-bold text-slate-600 transition hover:bg-white hover:text-slate-900 sm:text-sm"
          >
            Sign in
          </Link>
          <Link
            href="/register"
            className="inline-flex min-h-10 items-center gap-2 rounded-xl bg-brand-500 px-4 py-2.5 text-xs font-bold text-white shadow-lg shadow-orange-500/20 transition hover:bg-brand-600 sm:text-sm"
          >
            Create agency
            <ArrowRight size={15} />
          </Link>
        </nav>
      </header>

      <section className="relative mx-auto grid w-full max-w-7xl items-center gap-12 px-5 pb-16 pt-12 sm:px-8 sm:pb-24 sm:pt-20 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16">
        <div aria-hidden="true" className="pointer-events-none absolute -left-40 top-0 h-96 w-96 rounded-full bg-brand-400/10 blur-3xl" />
        <div className="relative z-10">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-orange-100 bg-white/80 px-3 py-1.5 text-[10px] font-extrabold uppercase tracking-[0.16em] text-brand-700 shadow-sm">
            <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
            Customer support workspace
          </div>
          <h1 className="max-w-2xl text-4xl font-black leading-[1.08] tracking-[-0.045em] text-slate-950 sm:text-5xl lg:text-[62px]">
            Every customer conversation, <span className="text-brand-600">in good hands.</span>
          </h1>
          <p className="mt-6 max-w-xl text-base leading-8 text-slate-500 sm:text-lg">
            A structured support workspace for growing teams. Bring your conversations, contacts, and people together without losing control of your data.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/register"
              className="inline-flex min-h-13 items-center justify-center gap-2 rounded-xl bg-brand-500 px-6 py-3.5 text-sm font-extrabold text-white shadow-xl shadow-orange-500/20 transition hover:-translate-y-0.5 hover:bg-brand-600"
            >
              Create your agency
              <ArrowRight size={17} />
            </Link>
            <Link
              href="/login"
              className="inline-flex min-h-13 items-center justify-center rounded-xl border border-slate-200 bg-white px-6 py-3.5 text-sm font-bold text-slate-700 shadow-sm transition hover:border-slate-300 hover:bg-slate-50"
            >
              Sign in to workspace
            </Link>
          </div>
          <div className="mt-8 flex items-center gap-3 text-xs font-medium text-slate-400">
            <ShieldCheck size={16} className="text-emerald-600" />
            Tenant isolation and role-based access are enforced by the backend.
          </div>
        </div>

        <div className="relative z-10">
          <div className="absolute -inset-5 rounded-[36px] bg-gradient-to-br from-brand-200/40 via-transparent to-sky-200/50 blur-2xl" />
          <div className="relative overflow-hidden rounded-[28px] border border-white/80 bg-[#111c2e] p-5 shadow-2xl shadow-slate-900/20 sm:p-7">
            <div className="mb-6 flex items-center justify-between">
              <div>
                <div className="text-[10px] font-bold uppercase tracking-[0.17em] text-slate-500">Workspace preview</div>
                <div className="mt-1 text-base font-extrabold text-white">Support overview</div>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10 text-brand-300">
                <LayoutDashboard size={19} />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-4">
                <div className="text-[10px] font-semibold text-slate-400">Conversations</div>
                <div className="mt-3 text-2xl font-black text-white">Inbox</div>
                <div className="mt-1 text-[10px] text-slate-500">One place for customer replies</div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-4">
                <div className="text-[10px] font-semibold text-slate-400">Customer records</div>
                <div className="mt-3 text-2xl font-black text-white">Contacts</div>
                <div className="mt-1 text-[10px] text-slate-500">Context alongside each request</div>
              </div>
              <div className="col-span-2 rounded-2xl border border-white/10 bg-white/[0.06] p-4">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500/15 text-brand-300">
                    <UsersRound size={18} />
                  </div>
                  <div className="flex-1">
                    <div className="text-xs font-bold text-white">Your team, your workspace</div>
                    <div className="mt-1 text-[10px] text-slate-500">Roles, teams, and channels in one place</div>
                  </div>
                  <BookOpen size={17} className="text-slate-500" />
                </div>
                <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full w-2/3 rounded-full bg-gradient-to-r from-brand-500 to-orange-300" />
                </div>
                <div className="mt-2 text-[9px] font-semibold uppercase tracking-[0.15em] text-slate-500">Built to grow with your operation</div>
              </div>
            </div>
            <div className="mt-5 flex items-center justify-between border-t border-white/10 pt-4 text-[10px] text-slate-500">
              <span>Agency workspace</span>
              <span className="font-bold tracking-[0.12em] text-slate-400">M369 SUPPORT</span>
            </div>
          </div>
        </div>
      </section>

      <section className="border-t border-slate-200/80 bg-white">
        <div className="mx-auto grid w-full max-w-7xl gap-4 px-5 py-12 sm:grid-cols-3 sm:px-8 sm:py-16">
          {FEATURES.map((feature) => {
            const Icon = feature.icon;
            return (
              <article key={feature.title} className="rounded-2xl border border-slate-100 bg-slate-50/70 p-5 sm:p-6">
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-orange-50 text-brand-600">
                  <Icon size={19} />
                </div>
                <h2 className="text-sm font-extrabold text-slate-900">{feature.title}</h2>
                <p className="mt-2 text-xs leading-6 text-slate-500">{feature.description}</p>
              </article>
            );
          })}
        </div>
      </section>
    </main>
  );
}
