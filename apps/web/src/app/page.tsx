import Link from "next/link";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8 bg-gradient-to-b from-brand-50 to-white">
      <div className="max-w-2xl w-full text-center space-y-8">
        <div className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-brand-500 text-white text-4xl font-bold">
          M
        </div>
        <h1 className="text-5xl font-bold tracking-tight text-gray-900">
          M369 Support
        </h1>
        <p className="text-xl text-gray-600">
          AI-powered customer support for every business. Multi-tenant SaaS platform.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="/login"
            className="inline-flex items-center justify-center rounded-lg bg-brand-500 px-8 py-3 text-base font-medium text-white shadow-sm hover:bg-brand-600 transition-colors"
          >
            Sign in
          </Link>
          <Link
            href="/register"
            className="inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white px-8 py-3 text-base font-medium text-gray-700 shadow-sm hover:bg-gray-50 transition-colors"
          >
            Register agency
          </Link>
        </div>
      </div>
    </main>
  );
}
