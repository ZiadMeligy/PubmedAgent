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
}

export function RetrievalConfigCard({ params }: RetrievalConfigCardProps) {
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
      </CardContent>
    </Card>
  );
}
