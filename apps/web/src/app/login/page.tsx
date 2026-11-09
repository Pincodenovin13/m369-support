"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { authApi, ApiError, type AgencyLoginOption } from "@/lib/api-client";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agencyOptions, setAgencyOptions] = useState<AgencyLoginOption[]>([]);
  const [selectedAgency, setSelectedAgency] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await authApi.login(email, password, selectedAgency ?? undefined);
      router.push("/dashboard");
      router.refresh();
    } catch (err) {
      if (err instanceof ApiError) {
        // Clear stale agency options on non-400 errors
        if (err.status !== 400) {
          setAgencyOptions([]);
          setSelectedAgency(null);
        }
        if (err.status === 400 && err.detail && typeof err.detail === "object" && "available_agencies" in err.detail) {
          // Multi-agency: server requires agency selection
          const detail = err.detail as { message?: string; available_agencies?: AgencyLoginOption[] };
          setAgencyOptions(detail.available_agencies ?? []);
          if (!selectedAgency) {
            setError(detail.message ?? "Please select an agency to continue.");
          } else {
            setError("The selected agency is not valid. Please choose again.");
            setSelectedAgency(null);
          }
        } else if (err.status === 401) {
          setError("Incorrect email or password");
        } else {
          setError(err.message);
        }
      } else {
        setError("An unexpected error occurred. Please check your connection.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-[#111c2e] via-[#17263c] to-[#263b55] px-4 py-10 sm:px-6">
      <div aria-hidden="true" className="pointer-events-none absolute -left-24 -top-24 h-80 w-80 rounded-full bg-brand-500/10 blur-3xl" />
      <div aria-hidden="true" className="pointer-events-none absolute -bottom-32 -right-20 h-96 w-96 rounded-full bg-cyan-400/10 blur-3xl" />
      <div className="relative z-10 w-full max-w-md space-y-8 rounded-[28px] border border-white/70 bg-white p-7 shadow-2xl shadow-slate-950/25 sm:p-10">
        <div className="text-center">
          <div className="mb-5 inline-flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-500 text-xl font-black text-white shadow-lg shadow-orange-500/25">
            M
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 sm:text-[28px]">Sign in to M369</h1>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            Enter your credentials to access your agency dashboard
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label htmlFor="email" className="block text-xs font-bold text-slate-700">
              Email
            </label>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              autoFocus
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                setAgencyOptions([]);
                setSelectedAgency(null);
              }}
              className="mt-2 block min-h-12 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-sm text-slate-900 placeholder-slate-400 transition focus:border-brand-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-orange-500/10"
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              placeholder="••••••••"
            />
          </div>

          {agencyOptions.length > 0 && (
            <div>
              <label htmlFor="agency" className="block text-sm font-medium text-gray-700">
                Select Agency
              </label>
              <select
                id="agency"
                value={selectedAgency ?? ""}
                onChange={(e) => setSelectedAgency(e.target.value || null)}
                className="mt-2 block min-h-12 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-sm text-slate-900 transition focus:border-brand-400 focus:bg-white focus:outline-none focus:ring-4 focus:ring-orange-500/10"
              >
                <option value="">— Choose an agency —</option>
                {agencyOptions.map((opt) => (
                  <option key={opt.agency_id} value={opt.agency_id}>
                    {opt.agency_name ?? opt.agency_id} ({opt.role})
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-gray-500">
                You belong to multiple agencies. Select which one to sign in to.
              </p>
            </div>
          )}

          {error && (
            <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="mt-1 min-h-12 w-full rounded-xl bg-brand-500 px-4 py-3 text-sm font-bold text-white shadow-lg shadow-orange-500/20 transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="text-center text-sm text-slate-500">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="font-bold text-brand-600 transition hover:text-brand-700">
            Register your agency
          </Link>
        </p>
      </div>
    </main>
  );
}
