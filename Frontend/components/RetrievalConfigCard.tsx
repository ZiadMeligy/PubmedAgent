import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Sliders } from 'lucide-react';

export interface RetrievalParam {
  key: string;
  label: string;
  value: number;
  colorClass: string;
}

interface RetrievalConfigCardProps {
  params: RetrievalParam[];
  journalQualityEnabled?: boolean;
  minimumSjr?: number;
}

export function RetrievalConfigCard({ params, journalQualityEnabled, minimumSjr }: RetrievalConfigCardProps) {
  return (
    <Card className="mb-4 bg-muted/30 border-muted">
      <CardHeader className="py-3 px-4 pb-0">
        <CardTitle className="text-sm flex items-center gap-2">
          <Sliders className="h-4 w-4" />
          Retrieval Configuration
        </CardTitle>
        <CardDescription className="text-xs">Ranking weights used for this search</CardDescription>
      </CardHeader>
      <CardContent className="py-3 px-4 space-y-3">
        {params.map((param) => (
          <div key={param.key} className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="font-medium text-muted-foreground">{param.label}</span>
              <span className="font-mono text-muted-foreground">{param.value.toFixed(2)}</span>
            </div>
            <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
              <div 
                className={`h-full ${param.colorClass} transition-all duration-300`} 
                style={{ width: `${Math.min(100, Math.max(0, param.value * 100))}%` }} 
              />
            </div>
          </div>
        ))}

        {journalQualityEnabled && (
          <div className="mt-3 pt-3 border-t border-muted">
            <div className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Journal Quality</span>
              <div className="flex items-center gap-2">
                <span className="text-xs">🟢 Enabled</span>
                {minimumSjr !== undefined && (
                  <span className="text-xs text-muted-foreground">- Minimum SJR ≥ {minimumSjr}</span>
                )}
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
