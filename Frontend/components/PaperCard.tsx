"use client";

import { Paper } from '@/types';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ExternalLink, Calendar, Quote, TrendingUp, BarChart3 } from 'lucide-react';

interface PaperCardProps {
  paper: Paper;
}

export function PaperCard({ paper }: PaperCardProps) {
  return (
    <Card className="flex flex-col h-full hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-start gap-2">
          <span className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm font-semibold">
            {paper.rank}
          </span>
          <CardTitle className="text-base font-semibold leading-tight line-clamp-3">
            {paper.title}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="flex-grow">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Calendar className="h-4 w-4 flex-shrink-0" />
            <span>Year: <span className="font-medium text-foreground">{paper.publication_year}</span></span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <Quote className="h-4 w-4 flex-shrink-0" />
            <span>Citations: <span className="font-medium text-foreground">{paper.citation_count}</span></span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <TrendingUp className="h-4 w-4 flex-shrink-0" />
            <span>Similarity: <span className="font-medium text-foreground">{paper.similarity_score.toFixed(2)}</span></span>
          </div>
          <div className="flex items-center gap-2 text-muted-foreground">
            <BarChart3 className="h-4 w-4 flex-shrink-0" />
            <span>Score: <span className="font-medium text-foreground">{paper.composite_score.toFixed(2)}</span></span>
          </div>
        </div>
      </CardContent>
      <CardFooter className="pt-0">
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          onClick={() => window.open(paper.url, '_blank', 'noopener,noreferrer')}
        >
          <ExternalLink className="h-4 w-4 mr-2" />
          Open PubMed
        </Button>
      </CardFooter>
    </Card>
  );
}
