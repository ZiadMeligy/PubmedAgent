"use client";

import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  BookOpenText,
  ExternalLink,
  Images,
  Image as ImageIcon,
  Loader2,
  RefreshCw,
  Table2,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  getEvidence,
  getIndexedPaperPdf,
  getPaperArtifacts,
  summarizePaper,
} from '@/lib/api';
import {
  EvidenceDetail,
  Paper,
  PaperArtifactDetail,
  PaperSummary,
} from '@/types';


const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';


function EvidenceMarkdown({ children }: { children: string }) {
  return (
    <div className="prose prose-sm min-w-0 max-w-none overflow-hidden dark:prose-invert">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          table: ({ node, ...props }) => (
            <div className="not-prose my-3 max-w-full overflow-x-auto rounded-lg border">
              <table
                {...props}
                className="w-full min-w-[640px] border-collapse text-left text-xs"
              />
            </div>
          ),
          thead: ({ node, ...props }) => <thead {...props} className="bg-muted/70" />,
          tr: ({ node, ...props }) => <tr {...props} className="border-b last:border-0" />,
          th: ({ node, ...props }) => (
            <th {...props} className="border-r px-3 py-2 align-top font-semibold last:border-0" />
          ),
          td: ({ node, ...props }) => (
            <td
              {...props}
              className="border-r px-3 py-2 align-top last:border-0 [overflow-wrap:anywhere]"
            />
          ),
          a: ({ node, ...props }) => (
            <a {...props} className="text-primary underline" target="_blank" rel="noreferrer" />
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}


interface PaperToolsProps {
  paper: Paper;
  conversationId: string;
}


export function PaperTools({ paper, conversationId }: PaperToolsProps) {
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [summary, setSummary] = useState<PaperSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [artifactsOpen, setArtifactsOpen] = useState(false);
  const [artifacts, setArtifacts] = useState<PaperArtifactDetail[]>([]);
  const [artifactsLoading, setArtifactsLoading] = useState(false);
  const [artifactsError, setArtifactsError] = useState<string | null>(null);
  const [sourceOpen, setSourceOpen] = useState(false);
  const [sourceEvidence, setSourceEvidence] = useState<EvidenceDetail | null>(null);
  const [sourcePdfUrl, setSourcePdfUrl] = useState<string | null>(null);
  const [sourceLoading, setSourceLoading] = useState(false);
  const [sourceError, setSourceError] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (sourcePdfUrl) URL.revokeObjectURL(sourcePdfUrl);
    };
  }, [sourcePdfUrl]);

  const loadSummary = async (refresh = false) => {
    setSummaryOpen(true);
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      setSummary(await summarizePaper(conversationId, paper.rank, refresh));
    } catch (error) {
      setSummaryError(error instanceof Error ? error.message : 'Unable to summarize this paper');
    } finally {
      setSummaryLoading(false);
    }
  };

  const loadArtifacts = async () => {
    setArtifactsOpen(true);
    if (artifacts.length > 0) return;
    setArtifactsLoading(true);
    setArtifactsError(null);
    try {
      const result = await getPaperArtifacts(conversationId, paper.pubmed_id);
      setArtifacts(result.artifacts);
    } catch (error) {
      setArtifactsError(error instanceof Error ? error.message : 'Unable to load paper artifacts');
    } finally {
      setArtifactsLoading(false);
    }
  };

  const openSource = async (artifact: PaperArtifactDetail) => {
    setArtifactsOpen(false);
    setSourceOpen(true);
    setSourceLoading(true);
    setSourceError(null);
    setSourceEvidence(null);
    if (sourcePdfUrl) {
      URL.revokeObjectURL(sourcePdfUrl);
      setSourcePdfUrl(null);
    }
    try {
      const evidence = await getEvidence(
        conversationId,
        paper.pubmed_id,
        artifact.evidence_id,
      );
      setSourceEvidence(evidence);
      if (evidence.pdf_available) {
        const pdf = await getIndexedPaperPdf(conversationId, paper.pubmed_id);
        setSourcePdfUrl(URL.createObjectURL(pdf));
      }
    } catch (error) {
      setSourceError(error instanceof Error ? error.message : 'Unable to load source evidence');
    } finally {
      setSourceLoading(false);
    }
  };

  const tables = artifacts.filter((artifact) => artifact.type === 'table');
  const figures = artifacts.filter((artifact) => artifact.type === 'image');

  return (
    <>
      <div className="grid w-full grid-cols-2 gap-2">
        <Button
          variant="secondary"
          size="sm"
          className="h-8 text-xs"
          onClick={(event) => {
            event.stopPropagation();
            if (summary) setSummaryOpen(true);
            else void loadSummary();
          }}
        >
          <BookOpenText className="mr-1.5 h-3.5 w-3.5" />
          Summarize paper
        </Button>
        <Button
          variant="secondary"
          size="sm"
          className="h-8 text-xs"
          onClick={(event) => {
            event.stopPropagation();
            void loadArtifacts();
          }}
        >
          <Images className="mr-1.5 h-3.5 w-3.5" />
          Tables & figures
        </Button>
      </div>

      <Dialog open={summaryOpen} onOpenChange={setSummaryOpen}>
        <DialogContent className="h-[88vh] max-w-3xl grid-rows-[auto_minmax(0,1fr)] overflow-hidden">
          <DialogHeader>
            <DialogTitle>Ranked paper #{paper.rank} summary</DialogTitle>
            <DialogDescription className="line-clamp-2">{paper.title}</DialogDescription>
          </DialogHeader>
          <div className="min-h-0 overflow-y-auto overscroll-contain pr-3">
            {summaryLoading && (
              <div className="flex min-h-48 items-center justify-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-5 w-5 animate-spin" />
                Building an evidence-grounded summary…
              </div>
            )}
            {summaryError && (
              <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
                {summaryError}
              </div>
            )}
            {!summaryLoading && summary && (
              <>
                <EvidenceMarkdown>{summary.summary}</EvidenceMarkdown>
                <div className="mt-4 flex items-center justify-between border-t pt-3">
                  <span className="text-xs text-muted-foreground">
                    {summary.cached ? 'Loaded from the indexed-paper summary cache' : 'Generated from indexed evidence'}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => void loadSummary(true)}
                  >
                    <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                    Regenerate
                  </Button>
                </div>
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={artifactsOpen} onOpenChange={setArtifactsOpen}>
        <DialogContent className="max-h-[90vh] max-w-5xl overflow-hidden">
          <DialogHeader>
            <DialogTitle>Tables and figures · Ranked paper #{paper.rank}</DialogTitle>
            <DialogDescription className="line-clamp-2">{paper.title}</DialogDescription>
          </DialogHeader>
          {artifactsLoading && (
            <div className="flex min-h-52 items-center justify-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
              Loading indexed artifacts…
            </div>
          )}
          {artifactsError && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
              {artifactsError}
            </div>
          )}
          {!artifactsLoading && !artifactsError && (
            <Tabs defaultValue={tables.length > 0 ? 'tables' : 'figures'} className="min-h-0">
              <TabsList>
                <TabsTrigger value="tables">
                  <Table2 className="mr-1.5 h-4 w-4" />
                  Tables ({tables.length})
                </TabsTrigger>
                <TabsTrigger value="figures">
                  <ImageIcon className="mr-1.5 h-4 w-4" />
                  Figures ({figures.length})
                </TabsTrigger>
              </TabsList>
              <TabsContent value="tables" className="max-h-[68vh] overflow-y-auto pr-2">
                {tables.length === 0 ? (
                  <p className="py-12 text-center text-sm text-muted-foreground">
                    No tables were extracted from this PDF.
                  </p>
                ) : (
                  <div className="space-y-4">
                    {tables.map((artifact) => (
                      <article key={artifact.artifact_id} className="rounded-xl border bg-muted/20 p-4">
                        <div className="mb-2 flex items-start justify-between gap-3">
                          <div>
                            <h3 className="font-medium">{artifact.label}</h3>
                            <p className="text-xs text-muted-foreground">
                              PDF page {artifact.page_number ?? 'unknown'}
                            </p>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => void openSource(artifact)}
                          >
                            <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
                            Source
                          </Button>
                        </div>
                        <EvidenceMarkdown>{artifact.text}</EvidenceMarkdown>
                      </article>
                    ))}
                  </div>
                )}
              </TabsContent>
              <TabsContent value="figures" className="max-h-[68vh] overflow-y-auto pr-2">
                {figures.length === 0 ? (
                  <p className="py-12 text-center text-sm text-muted-foreground">
                    No figures were extracted from this PDF.
                  </p>
                ) : (
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    {figures.map((artifact) => (
                      <figure key={artifact.artifact_id} className="overflow-hidden rounded-xl border bg-muted/20">
                        {artifact.url && (
                          <img
                            src={artifact.url.startsWith('/') ? `${API_BASE_URL}${artifact.url}` : artifact.url}
                            alt={artifact.label}
                            className="h-72 w-full bg-white object-contain"
                            loading="lazy"
                          />
                        )}
                        <figcaption className="space-y-2 p-3">
                          <p className="text-sm font-medium">{artifact.label}</p>
                          <div className="flex items-center justify-between">
                            <span className="text-xs text-muted-foreground">
                              PDF page {artifact.page_number ?? 'unknown'}
                            </span>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => void openSource(artifact)}
                            >
                              <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
                              Source
                            </Button>
                          </div>
                        </figcaption>
                      </figure>
                    ))}
                  </div>
                )}
              </TabsContent>
            </Tabs>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={sourceOpen} onOpenChange={setSourceOpen}>
        <DialogContent className="h-[90vh] max-w-6xl grid-rows-[auto_minmax(0,1fr)] gap-0 overflow-hidden p-0">
          <DialogHeader className="border-b px-6 pb-4 pt-6">
            <DialogTitle>Source evidence · Ranked paper #{paper.rank}</DialogTitle>
            <DialogDescription className="line-clamp-2">
              {paper.title}
            </DialogDescription>
          </DialogHeader>
          {sourceLoading && (
            <div className="flex h-full items-center justify-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-5 w-5 animate-spin" />
              Loading the indexed PDF and evidence…
            </div>
          )}
          {sourceError && (
            <div className="m-6 rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
              {sourceError}
            </div>
          )}
          {!sourceLoading && sourceEvidence && (
            <div className="grid min-h-0 flex-1 grid-cols-1 overflow-hidden lg:grid-cols-[minmax(0,2fr)_minmax(20rem,1fr)]">
              <section className="min-h-[45vh] border-r bg-muted/20">
                {sourcePdfUrl ? (
                  <iframe
                    src={`${sourcePdfUrl}#page=${sourceEvidence.page_number || 1}&zoom=page-width`}
                    title={`Paper ${paper.pubmed_id}, page ${sourceEvidence.page_number || 1}`}
                    className="h-full min-h-[45vh] w-full bg-white"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center p-8 text-center text-sm text-muted-foreground">
                    Re-index this paper once to retain its PDF for exact-page viewing.
                  </div>
                )}
              </section>
              <aside className="min-h-0 overflow-y-auto p-5">
                <p className="text-xs font-medium uppercase tracking-wide text-primary">
                  Highlighted retrieved evidence
                </p>
                <p className="mb-4 mt-1 text-xs text-muted-foreground">
                  PDF page {sourceEvidence.page_number ?? 'not available'} · {sourceEvidence.content_type}
                </p>
                <mark className="block whitespace-pre-wrap rounded-xl border border-amber-300/70 bg-amber-100/90 p-4 text-sm leading-7 text-slate-900">
                  {sourceEvidence.text}
                </mark>
              </aside>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
