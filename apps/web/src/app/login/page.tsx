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
    <main className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
      <div className="w-full max-w-md space-y-8 rounded-xl bg-white p-8 shadow-lg">
        <div className="text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-brand-500 text-white text-2xl font-bold mb-4">
            M
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Sign in to M369</h1>
          <p className="mt-2 text-sm text-gray-600">
            Enter your credentials to access your agency dashboard
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700">
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
              className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
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
                className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2 text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="">— Choose an agency —</option>
                {agencyOptions.map((opt) => (
                  <option key={opt.agency_id} value={opt.agency_id}>
                    {opt.agency_id} ({opt.role})
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
            className="w-full rounded-lg bg-brand-500 px-4 py-2.5 text-sm font-medium text-white shadow-sm hover:bg-brand-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <p className="text-center text-sm text-gray-600">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="font-medium text-brand-600 hover:text-brand-700">
            Register your agency
          </Link>
        </p>
      </div>
    </main>
  );
}
