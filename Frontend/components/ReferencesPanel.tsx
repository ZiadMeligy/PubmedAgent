"use client";

import { Reference } from '@/types';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ExternalLink, FileText } from 'lucide-react';

interface ReferencesPanelProps {
  references: Reference[];
}

export function ReferencesPanel({ references }: ReferencesPanelProps) {
  if (references.length === 0) return null;

  return (
    <div className="mt-4 space-y-3">
      <h4 className="text-sm font-semibold text-muted-foreground flex items-center gap-2">
        <FileText className="h-4 w-4" />
        References
      </h4>
      <div className="space-y-2">
        {references.map((ref, index) => (
          <Card key={ref.pmid || index} className="hover:shadow-sm transition-shadow">
            <CardHeader className="pb-2 pt-4">
              <CardTitle className="text-sm font-medium leading-snug line-clamp-2">
                {ref.title}
              </CardTitle>
            </CardHeader>
            <CardContent className="pb-2">
              <p className="text-xs text-muted-foreground">
                {ref.rank ? (
                  <>
                    Ranked paper <span className="font-semibold">#{ref.rank}</span>
                    {' · '}
                  </>
                ) : null}
                PMID: <span className="font-mono">{ref.pmid}</span>
              </p>
            </CardContent>
            <CardFooter className="pt-0 pb-3">
              <Button
                variant="ghost"
                size="sm"
                className="h-8 text-xs"
                onClick={() => window.open(ref.url, '_blank', 'noopener,noreferrer')}
              >
                <ExternalLink className="h-3 w-3 mr-1" />
                Open PubMed
              </Button>
            </CardFooter>
          </Card>
        ))}
      </div>
    </div>
  );
}
