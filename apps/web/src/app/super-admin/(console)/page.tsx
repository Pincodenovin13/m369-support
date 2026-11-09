"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, Building2, CreditCard, Layers3, ShieldCheck } from "lucide-react";
import { PageHeader, Loading, ErrorState } from "@/components/ui";
import {
  superAdminApi,
  type AgencyAdminDetailOut,
} from "@/lib/super-admin-api-client";

interface OverviewData {
  activeAgencies: number;
  totalAgencies: number;
  activePlans: number;
  activeSubscriptions: number;
  pendingPayments: number;
  recentAgencies: AgencyAdminDetailOut[];
}

export default function SuperAdminOverviewPage() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [allAgencies, activeAgencies, activePlans, activeSubscriptions, pendingPayments] =
          await Promise.all([
            superAdminApi.agencies.list({ limit: 5, offset: 0 }),
            superAdminApi.agencies.list({ is_active: true, limit: 1, offset: 0 }),
            superAdminApi.plans.list({ is_active: true, limit: 1, offset: 0 }),
            superAdminApi.subscriptions.list({ status: "active", limit: 1, offset: 0 }),
            superAdminApi.payments.list({ status: "pending", limit: 1, offset: 0 }),
          ]);
        if (cancelled) return;
        setData({
          totalAgencies: allAgencies.total,
          activeAgencies: activeAgencies.total,
          activePlans: activePlans.total,
          activeSubscriptions: activeSubscriptions.total,
          pendingPayments: pendingPayments.total,
          recentAgencies: allAgencies.items,
        });
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load platform overview");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <Loading label="Loading platform overview..." />;
  if (error) return <ErrorState message={error} />;
  if (!data) return <Loading />;

  const cards = [
    { label: "Total agencies", value: data.totalAgencies, detail: `${data.activeAgencies} active`, icon: Building2, tint: "bg-orange-50 text-brand-600" },
    { label: "Active plans", value: data.activePlans, detail: "Available for subscriptions", icon: Layers3, tint: "bg-blue-50 text-blue-600" },
    { label: "Active subscriptions", value: data.activeSubscriptions, detail: "Current active accounts", icon: ShieldCheck, tint: "bg-emerald-50 text-emerald-700" },
    { label: "Pending payments", value: data.pendingPayments, detail: "Require manual review", icon: CreditCard, tint: "bg-amber-50 text-amber-700" },
  ];

  return (
    <>
      <PageHeader
        title="Platform overview"
        description="A controlled view of agencies, plans, subscriptions, and payment operations."
      />

      <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <article key={card.label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-start justify-between">
                <div className="text-[10px] font-bold uppercase tracking-[0.15em] text-slate-400">{card.label}</div>
                <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${card.tint}`}>
                  <Icon size={18} />
                </div>
              </div>
              <div className="mt-4 text-3xl font-black tracking-tight text-slate-900">{card.value.toLocaleString()}</div>
              <div className="mt-1 text-[11px] text-slate-500">{card.detail}</div>
            </article>
          );
        })}
      </div>

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <div>
            <h2 className="text-sm font-extrabold text-slate-900">Recently registered agencies</h2>
            <p className="mt-1 text-xs text-slate-500">Latest tenant workspaces on the platform</p>
          </div>
          <Link href="/super-admin/agencies" className="inline-flex items-center gap-1 text-xs font-bold text-brand-700 hover:text-brand-800">
            All agencies <ArrowRight size={14} />
          </Link>
        </div>
        {data.recentAgencies.length === 0 ? (
          <div className="px-5 py-10 text-center text-sm text-slate-500">No agencies have registered yet.</div>
        ) : (
          <div className="divide-y divide-slate-100">
            {data.recentAgencies.map((agency) => (
              <Link
                key={agency.id}
                href={`/super-admin/agencies?selected=${agency.id}`}
                className="flex items-center justify-between gap-4 px-5 py-4 transition hover:bg-slate-50"
              >
                <div className="flex min-w-0 items-center gap-3">
                  <span className="h-9 w-9 shrink-0 rounded-xl border border-slate-100" style={{ backgroundColor: agency.brand_color || "#f26a3d" }} />
                  <div className="min-w-0">
                    <div className="truncate text-sm font-bold text-slate-800">{agency.name}</div>
                    <div className="mt-0.5 truncate text-[11px] text-slate-400">{agency.slug} · {agency.member_count} members</div>
                  </div>
                </div>
                <span className={`shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-bold ${agency.is_active ? "border-emerald-100 bg-emerald-50 text-emerald-700" : "border-slate-200 bg-slate-100 text-slate-500"}`}>
                  {agency.is_active ? "Active" : "Inactive"}
                </span>
              </Link>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
