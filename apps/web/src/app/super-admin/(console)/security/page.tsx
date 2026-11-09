"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { KeyRound, ShieldCheck, ShieldOff } from "lucide-react";
import { PageHeader, ErrorState } from "@/components/ui";
import {
  superAdminAuthApi,
  SuperAdminApiError,
  type SuperAdminMFASetupResponse,
} from "@/lib/super-admin-api-client";

export default function SuperAdminSecurityPage() {
  const router = useRouter();
  const [setup, setSetup] = useState<SuperAdminMFASetupResponse | null>(null);
  const [mfaEnabled, setMfaEnabled] = useState(false);
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [code, setCode] = useState("");
  const [recoveryMode, setRecoveryMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function beginSetup() {
    if (loading) return;
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const result = await superAdminAuthApi.setupMfa();
      setSetup(result);
      setMfaEnabled(false);
      setRecoveryCodes([]);
    } catch (err) {
      if (err instanceof SuperAdminApiError && err.status === 409) {
        setMfaEnabled(true);
        setSetup(null);
        setNotice("Multi-factor authentication is already enabled for this account.");
      } else {
        setError(err instanceof Error ? err.message : "Unable to start MFA setup");
      }
    } finally {
      setLoading(false);
    }
  }

  async function enableMfa(event: React.FormEvent) {
    event.preventDefault();
    if (!setup || !code.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      const result = await superAdminAuthApi.enableMfa({ secret: setup.secret, code: code.trim() });
      setRecoveryCodes(result.recovery_codes);
      setMfaEnabled(true);
      setSetup(null);
      setCode("");
      setNotice("MFA is enabled. Save these recovery codes now; they are shown only once.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to enable MFA");
    } finally {
      setLoading(false);
    }
  }

  async function disableMfa(event: React.FormEvent) {
    event.preventDefault();
    if (!code.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      await superAdminAuthApi.disableMfa(
        recoveryMode ? { recovery_code: code.trim() } : { code: code.trim() },
      );
      setCode("");
      router.replace("/super-admin/login");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to disable MFA");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Account security"
        description="Protect the platform administrator account with an authenticator app and single-use recovery codes."
      />

      {error && <div className="mb-4"><ErrorState message={error} /></div>}
      {notice && <div role="status" className="mb-5 rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-xs font-semibold text-emerald-800">{notice}</div>}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_0.9fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700">
              <ShieldCheck size={20} />
            </div>
            <div>
              <h2 className="text-sm font-extrabold text-slate-900">Multi-factor authentication</h2>
              <p className="mt-1 text-xs text-slate-500">Time-based one-time password (TOTP)</p>
            </div>
          </div>

          {!mfaEnabled && !setup && (
            <div className="mt-6">
              <p className="text-sm leading-7 text-slate-600">
                Add a second factor to administrator sign-in. You will need an authenticator app and must confirm a valid code before MFA becomes active.
              </p>
              <button
                type="button"
                onClick={() => void beginSetup()}
                disabled={loading}
                className="mt-5 min-h-11 rounded-xl bg-slate-900 px-5 text-xs font-extrabold text-white transition hover:bg-slate-800 disabled:opacity-50"
              >
                {loading ? "Checking…" : "Check status / set up MFA"}
              </button>
            </div>
          )}

          {setup && (
            <form onSubmit={enableMfa} className="mt-6 space-y-4">
              <div className="rounded-xl border border-amber-100 bg-amber-50 p-4 text-xs leading-6 text-amber-900">
                This secret is shown for setup only. Add it to your authenticator app, then enter the current six-digit code below. Do not share the secret.
              </div>
              <div>
                <div className="mb-1 text-[10px] font-bold uppercase tracking-wide text-slate-400">Setup secret</div>
                <div className="break-all rounded-xl border border-slate-200 bg-slate-50 p-3 font-mono text-sm font-bold tracking-wider text-slate-800">{setup.secret}</div>
              </div>
              <div>
                <div className="mb-1 text-[10px] font-bold uppercase tracking-wide text-slate-400">Authenticator URI</div>
                <div className="break-all rounded-xl border border-slate-200 bg-slate-50 p-3 font-mono text-[10px] leading-5 text-slate-600">{setup.otpauth_url}</div>
              </div>
              <label className="block">
                <span className="text-xs font-bold text-slate-700">Current authenticator code</span>
                <input
                  required
                  minLength={6}
                  maxLength={8}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                  className="mt-2 min-h-12 w-full rounded-xl border border-slate-200 px-4 text-center text-lg font-bold tracking-[0.25em] outline-none focus:border-brand-400 focus:ring-4 focus:ring-orange-500/10"
                  placeholder="000000"
                />
              </label>
              <div className="flex flex-wrap gap-2">
                <button type="submit" disabled={loading || !code.trim()} className="min-h-10 rounded-xl bg-emerald-600 px-4 text-xs font-bold text-white hover:bg-emerald-700 disabled:opacity-50">
                  {loading ? "Verifying…" : "Enable MFA"}
                </button>
                <button type="button" onClick={() => { setSetup(null); setCode(""); }} className="min-h-10 rounded-xl border border-slate-200 px-4 text-xs font-bold text-slate-600 hover:bg-slate-50">
                  Cancel setup
                </button>
              </div>
            </form>
          )}

          {mfaEnabled && (
            <div className="mt-6">
              <div className="flex items-center gap-2 rounded-xl border border-emerald-100 bg-emerald-50 px-4 py-3 text-xs font-bold text-emerald-800">
                <ShieldCheck size={16} />
                MFA is enabled
              </div>
              <p className="mt-4 text-xs leading-6 text-slate-500">
                Disabling MFA requires a current authenticator code or an unused recovery code. After it is disabled, your current session cookie is revoked and you must sign in again.
              </p>
            </div>
          )}
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
              <KeyRound size={20} />
            </div>
            <div>
              <h2 className="text-sm font-extrabold text-slate-900">Recovery codes</h2>
              <p className="mt-1 text-xs text-slate-500">Single-use emergency access</p>
            </div>
          </div>

          {recoveryCodes.length > 0 ? (
            <div className="mt-5">
              <p className="mb-3 text-xs leading-5 text-slate-600">Store these codes in a secure offline location. They are not shown again after leaving this page.</p>
              <div className="grid grid-cols-2 gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3">
                {recoveryCodes.map((recoveryCode) => (
                  <code key={recoveryCode} className="rounded-lg bg-white px-2 py-2 text-center font-mono text-xs font-bold text-slate-800">{recoveryCode}</code>
                ))}
              </div>
            </div>
          ) : (
            <p className="mt-5 text-xs leading-6 text-slate-500">
              Recovery codes are generated once when MFA is enabled. Each code can be used only once. If you did not save the codes when they were issued, keep MFA enabled and use your authenticator app.
            </p>
          )}

          {mfaEnabled && (
            <form onSubmit={disableMfa} className="mt-6 border-t border-slate-100 pt-5">
              <div className="mb-3 flex items-center gap-2 text-xs font-extrabold text-slate-800">
                <ShieldOff size={15} className="text-red-500" />
                Disable MFA
              </div>
              <label className="block text-[11px] font-bold text-slate-600">
                {recoveryMode ? "Unused recovery code" : "Current authenticator code"}
                <input
                  required
                  type="text"
                  value={code}
                  onChange={(event) => setCode(event.target.value)}
                  className="mt-2 min-h-11 w-full rounded-xl border border-slate-200 px-3 text-sm outline-none focus:border-brand-400"
                />
              </label>
              <button type="button" onClick={() => { setRecoveryMode((value) => !value); setCode(""); }} className="mt-2 text-[10px] font-bold text-slate-500 hover:text-brand-700">
                {recoveryMode ? "Use authenticator code" : "Use recovery code"}
              </button>
              <button type="submit" disabled={loading || !code.trim()} className="mt-4 min-h-10 w-full rounded-xl border border-red-100 bg-red-50 text-xs font-bold text-red-700 hover:bg-red-100 disabled:opacity-50">
                {loading ? "Processing…" : "Disable MFA and sign out"}
              </button>
            </form>
          )}
        </section>
      </div>
    </>
  );
}
