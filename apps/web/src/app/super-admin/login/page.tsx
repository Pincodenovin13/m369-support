"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, LockKeyhole, ShieldCheck } from "lucide-react";
import {
  superAdminAuthApi,
  SuperAdminApiError,
} from "@/lib/super-admin-api-client";

export default function SuperAdminLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [challenge, setChallenge] = useState<string | null>(null);
  const [challengeExpires, setChallengeExpires] = useState(0);
  const [code, setCode] = useState("");
  const [recoveryMode, setRecoveryMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handlePasswordSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (loading) return;
    setLoading(true);
    setError(null);
    try {
      const result = await superAdminAuthApi.login({ email: email.trim(), password });
      if ("mfa_required" in result && result.mfa_required) {
        setChallenge(result.mfa_challenge);
        setChallengeExpires(result.expires_in_seconds);
        setPassword("");
      } else {
        router.replace("/super-admin");
        router.refresh();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleMfaSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!challenge || !code.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      await superAdminAuthApi.verifyMfa(
        recoveryMode
          ? { mfa_challenge: challenge, recovery_code: code.trim() }
          : { mfa_challenge: challenge, code: code.trim() },
      );
      setChallenge(null);
      router.replace("/super-admin");
      router.refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Verification failed";
      // The backend consumes an MFA challenge before validating the second
      // factor. After a failed verification, require a fresh password login.
      setChallenge(null);
      setCode("");
      setRecoveryMode(false);
      setError(`${message}. Sign in again to request a fresh MFA challenge.`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-[#0d1728] via-[#14243a] to-[#263b55] px-4 py-10 sm:px-6">
      <div aria-hidden="true" className="pointer-events-none absolute -left-24 -top-24 h-80 w-80 rounded-full bg-brand-500/10 blur-3xl" />
      <div aria-hidden="true" className="pointer-events-none absolute -bottom-32 -right-20 h-96 w-96 rounded-full bg-cyan-400/10 blur-3xl" />
      <section className="relative z-10 w-full max-w-md rounded-[28px] border border-white/70 bg-white p-7 shadow-2xl shadow-slate-950/30 sm:p-10">
        <Link href="/" className="mb-8 inline-flex items-center gap-2 text-xs font-bold text-slate-400 transition hover:text-slate-700">
          <ArrowLeft size={14} />
          Back to M369 Support
        </Link>

        <div className="mb-7 flex h-14 w-14 items-center justify-center rounded-2xl bg-[#111c2e] text-white shadow-lg shadow-slate-900/20">
          {challenge ? <ShieldCheck size={25} /> : <LockKeyhole size={24} />}
        </div>

        <div>
          <div className="text-[10px] font-extrabold uppercase tracking-[0.18em] text-brand-600">Restricted access</div>
          <h1 className="mt-2 text-2xl font-extrabold tracking-tight text-slate-950">
            {challenge ? "Verify your identity" : "Super Admin sign in"}
          </h1>
          <p className="mt-2 text-sm leading-6 text-slate-500">
            {challenge
              ? "Enter the authenticator code for your administrator account. The challenge is short-lived."
              : "This area is reserved for authorized M369 platform administrators."}
          </p>
        </div>

        {error && (
          <div role="alert" className="mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-xs font-medium leading-5 text-red-700">
            {error}
          </div>
        )}

        {!challenge ? (
          <form onSubmit={handlePasswordSubmit} className="mt-7 space-y-5">
            <div>
              <label htmlFor="sa-email" className="block text-xs font-bold text-slate-700">Administrator email</label>
              <input
                id="sa-email"
                type="email"
                required
                autoComplete="username"
                autoFocus
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="mt-2 min-h-12 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-brand-400 focus:bg-white focus:ring-4 focus:ring-orange-500/10"
                placeholder="admin@example.com"
              />
            </div>
            <div>
              <label htmlFor="sa-password" className="block text-xs font-bold text-slate-700">Password</label>
              <input
                id="sa-password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="mt-2 min-h-12 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-brand-400 focus:bg-white focus:ring-4 focus:ring-orange-500/10"
                placeholder="Your administrator password"
              />
            </div>
            <button
              type="submit"
              disabled={loading || !email.trim() || !password}
              className="min-h-12 w-full rounded-xl bg-brand-500 px-4 py-3 text-sm font-extrabold text-white shadow-lg shadow-orange-500/20 transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "Verifying…" : "Continue securely"}
            </button>
          </form>
        ) : (
          <form onSubmit={handleMfaSubmit} className="mt-7 space-y-5">
            <div>
              <label htmlFor="sa-mfa-code" className="block text-xs font-bold text-slate-700">
                {recoveryMode ? "Recovery code" : "Authenticator code"}
              </label>
              <input
                id="sa-mfa-code"
                type="text"
                required
                autoFocus
                autoComplete={recoveryMode ? "off" : "one-time-code"}
                inputMode={recoveryMode ? "text" : "numeric"}
                maxLength={recoveryMode ? 64 : 8}
                value={code}
                onChange={(event) => setCode(event.target.value)}
                className="mt-2 min-h-12 w-full rounded-xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-center text-lg font-bold tracking-[0.25em] text-slate-900 outline-none transition focus:border-brand-400 focus:bg-white focus:ring-4 focus:ring-orange-500/10"
                placeholder={recoveryMode ? "Enter recovery code" : "000000"}
              />
              <p className="mt-2 text-[11px] text-slate-400">
                Challenge expires in about {Math.max(1, Math.ceil(challengeExpires / 60))} minute(s). If it expires, sign in again.
              </p>
            </div>
            <button
              type="submit"
              disabled={loading || !code.trim()}
              className="min-h-12 w-full rounded-xl bg-brand-500 px-4 py-3 text-sm font-extrabold text-white shadow-lg shadow-orange-500/20 transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "Checking…" : "Verify and sign in"}
            </button>
            <button
              type="button"
              onClick={() => {
                setRecoveryMode((current) => !current);
                setCode("");
                setError(null);
              }}
              className="w-full py-2 text-xs font-bold text-slate-500 transition hover:text-brand-700"
            >
              {recoveryMode ? "Use authenticator code instead" : "Use a recovery code"}
            </button>
            <button
              type="button"
              onClick={() => {
                setChallenge(null);
                setCode("");
                setRecoveryMode(false);
                setError(null);
              }}
              className="w-full py-1 text-[11px] font-semibold text-slate-400 hover:text-slate-600"
            >
              Start over
            </button>
          </form>
        )}

        <div className="mt-8 border-t border-slate-100 pt-5 text-[10px] leading-5 text-slate-400">
          Protected by server-side session validation, rate limiting, and MFA. Access tokens are held in an HttpOnly cookie, not browser storage.
        </div>
      </section>
    </main>
  );
}
