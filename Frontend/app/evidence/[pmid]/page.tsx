"use client";

import { Suspense, useEffect, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { ArrowLeft, ExternalLink, FileText, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { getEvidence, getIndexedPaperPdf } from '@/lib/api';
import { useAuthStore } from '@/lib/store';
import { EvidenceDetail } from '@/types';


function EvidenceViewer() {
  const params = useParams<{ pmid: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const token = useAuthStore((state) => state.token);
  const hasHydrated = useAuthStore((state) => state.hasHydrated);
  const conversationId = searchParams.get('conversation_id') || '';
  const evidenceId = searchParams.get('chunk_id') || '';
  const [evidence, setEvidence] = useState<EvidenceDetail | null>(null);
  const [pdfObjectUrl, setPdfObjectUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!hasHydrated) return;
    if (!token) {
      router.replace('/login');
      return;
    }
    if (!conversationId || !evidenceId || !params.pmid) {
      setError('This evidence link is incomplete.');
      setLoading(false);
      return;
    }

    let objectUrl: string | null = null;
    let cancelled = false;
    const load = async () => {
      try {
        const detail = await getEvidence(conversationId, params.pmid, evidenceId);
        if (cancelled) return;
        setEvidence(detail);
        if (detail.pdf_available) {
          const pdf = await getIndexedPaperPdf(conversationId, params.pmid);
          if (cancelled) return;
          objectUrl = URL.createObjectURL(pdf);
          setPdfObjectUrl(objectUrl);
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : 'Unable to load evidence');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [conversationId, evidenceId, hasHydrated, params.pmid, router, token]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center gap-3 bg-background text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin" />
        Loading cited evidence…
      </div>
    );
  }

  if (error || !evidence) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 bg-background p-6 text-center">
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-5 text-destructive">
          {error || 'Evidence not found'}
        </div>
        <Button variant="outline" onClick={() => router.push('/')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to chat
        </Button>
      </div>
    );
  }

  const page = evidence.page_number || Number(searchParams.get('page')) || 1;
  const pdfViewerUrl = pdfObjectUrl
    ? `${pdfObjectUrl}#page=${page}&zoom=page-width`
    : null;

  return (
    <div className="flex h-screen min-w-0 flex-col bg-background">
      <header className="flex items-center justify-between gap-4 border-b px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => router.push('/')}>
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div className="min-w-0">
            <p className="text-xs font-medium text-primary">
              Ranked paper #{evidence.rank} · PMID {evidence.pmid}
            </p>
            <h1 className="truncate text-sm font-semibold">{evidence.title}</h1>
          </div>
        </div>
        {pdfViewerUrl && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => window.open(pdfViewerUrl, '_blank', 'noopener,noreferrer')}
          >
            <ExternalLink className="mr-2 h-4 w-4" />
            Open PDF page {page}
          </Button>
        )}
      </header>

      <main className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(0,2fr)_minmax(20rem,1fr)]">
        <section className="min-h-[48vh] min-w-0 border-b bg-muted/20 lg:border-b-0 lg:border-r">
          {pdfViewerUrl ? (
            <iframe
              src={pdfViewerUrl}
              title={`Paper ${evidence.pmid}, page ${page}`}
              className="h-full min-h-[48vh] w-full bg-white"
            />
          ) : (
            <div className="flex h-full min-h-[48vh] flex-col items-center justify-center gap-3 p-8 text-center text-muted-foreground">
              <FileText className="h-10 w-10" />
              <p>The source PDF was not retained by the older index.</p>
              <p className="max-w-md text-xs">
                Re-index this paper to enable exact-page PDF viewing. The retrieved evidence remains available.
              </p>
            </div>
          )}
        </section>

        <aside className="min-h-0 overflow-y-auto p-5">
          <div className="mb-4">
            <p className="text-xs font-medium uppercase tracking-wide text-primary">
              Highlighted retrieved evidence
            </p>
            <h2 className="mt-1 text-lg font-semibold">
              {evidence.content_type === 'table' ? 'Table evidence' : evidence.section || 'Paper passage'}
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              PDF page {evidence.page_number ?? 'not available'} · Evidence ID {evidence.evidence_id}
            </p>
          </div>
          <mark className="block whitespace-pre-wrap rounded-xl border border-amber-300/70 bg-amber-100/80 p-4 text-sm leading-7 text-slate-900 shadow-sm dark:bg-amber-200/90">
            {evidence.text}
          </mark>
        </aside>
      </main>
    </div>
  );
}


export default function EvidencePage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      }
    >
      <EvidenceViewer />
    </Suspense>
  );
}
