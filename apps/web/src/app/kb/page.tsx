"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/use-auth";
import { DashboardShell } from "@/components/dashboard-shell";
import { Loading, ErrorState, EmptyState, PageHeader } from "@/components/ui";
import { kbApi, type KBArticleOut, type KBCategoryOut, type PaginatedResponse } from "@/lib/api-client";

export default function KBPage() {
  const { user, agency, loading, error, refresh } = useAuth();
  const [articles, setArticles] = useState<KBArticleOut[]>([]);
  const [categories, setCategories] = useState<KBCategoryOut[]>([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setListLoading(true);
    Promise.all([
      kbApi.listArticles({ limit: 50 }),
      kbApi.listCategories({ limit: 50 }),
    ])
      .then(([artsRes, catsRes]) => {
        setArticles((artsRes as PaginatedResponse<KBArticleOut>).items);
        setCategories((catsRes as PaginatedResponse<KBCategoryOut>).items);
        setListLoading(false);
      })
      .catch((err) => {
        setListError(err instanceof Error ? err.message : "Failed to load knowledge base");
        setListLoading(false);
      });
  }, [user]);

  if (loading) return <Loading label="Loading session..." />;
  if (error) return <ErrorState message={error} onRetry={refresh} />;
  if (!user || !agency) return <Loading />;

  const categoryName = (id: string | null) =>
    id ? categories.find((c) => c.id === id)?.name || "Uncategorized" : "Uncategorized";

  return (
    <DashboardShell user={user} agency={agency}>
      <PageHeader
        title="Knowledge Base"
        description="Internal articles and reference documents."
      />
      {categories.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          {categories.map((c) => (
            <span
              key={c.id}
              className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700"
            >
              {c.name}
            </span>
          ))}
        </div>
      )}
      <div className="bg-white rounded-lg border border-gray-200">
        {listLoading ? (
          <Loading label="Loading articles..." />
        ) : listError ? (
          <ErrorState message={listError} />
        ) : articles.length === 0 ? (
          <EmptyState title="No articles" description="KB articles will appear here once created." />
        ) : (
          <ul className="divide-y divide-gray-200">
            {articles.map((a) => (
              <li key={a.id} className="px-4 py-3">
                <button
                  onClick={() => setExpandedId(expandedId === a.id ? null : a.id)}
                  className="w-full text-left flex items-center justify-between"
                >
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-gray-900 truncate">{a.title}</div>
                    <div className="text-xs text-gray-500 truncate">
                      {categoryName(a.category_id)} · {a.is_published ? "Published" : "Draft"}
                    </div>
                  </div>
                  <span className="text-xs text-gray-400 ml-4">
                    Created {new Date(a.created_at).toLocaleDateString()}
                  </span>
                </button>
                {expandedId === a.id && (
                  <div className="mt-3 px-3 py-2 bg-gray-50 rounded-md text-sm text-gray-700 whitespace-pre-wrap">
                    {a.content_md}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
      <p className="mt-4 text-xs text-gray-500">
        Note: KB articles render as plain Markdown text. Server-side Markdown → HTML rendering is a planned future feature.
      </p>
    </DashboardShell>
  );
}
