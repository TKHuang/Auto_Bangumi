import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BangumiCard, type Bangumi } from '@/components/BangumiCard';
import { BangumiDetailDialog } from '@/components/BangumiDetailDialog';
import { Button } from '@/components/ui/button';
import api from '@/lib/api';

type FilterType = 'all' | 'active' | 'deleted' | 'pending';

export default function BangumiPage() {
  const [filter, setFilter] = useState<FilterType>('active');
  const [selectedBangumi, setSelectedBangumi] = useState<Bangumi | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const { data: bangumiList, isLoading } = useQuery({
    queryKey: ['bangumi', filter],
    queryFn: async () => {
      let params = {};
      if (filter === 'active') {
        params = { deleted: false, pending_review: false };
      } else if (filter === 'deleted') {
        params = { deleted: true };
      } else if (filter === 'pending') {
        params = { pending_review: true };
      }
      
      const res = await api.get<Bangumi[]>('/bangumi', { params });
      return res.data;
    }
  });

  const handleCardClick = (bangumi: Bangumi) => {
    setSelectedBangumi(bangumi);
    setDialogOpen(true);
  };

  return (
    <div className="container mx-auto p-4 md:p-8 space-y-8 animate-in fade-in duration-500">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-primary to-primary/50 bg-clip-text text-transparent">
            My Bangumi
          </h1>
          <p className="text-muted-foreground text-sm">Manage your subscriptions and downloads</p>
        </div>
        
        <div className="flex flex-wrap gap-2 p-1 bg-muted/50 rounded-lg">
            {(['all', 'active', 'pending', 'deleted'] as FilterType[]).map((f) => (
                <Button 
                    key={f}
                    variant={filter === f ? 'default' : 'ghost'} 
                    onClick={() => setFilter(f)}
                    size="sm"
                    className="capitalize transition-all"
                >
                    {f}
                </Button>
            ))}
        </div>
      </div>

      {isLoading && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 md:gap-6">
            {[...Array(12)].map((_, i) => (
                <div key={i} className="aspect-[2/3] bg-muted/50 rounded-xl animate-pulse" />
            ))}
        </div>
      )}
      
      {!isLoading && bangumiList?.length === 0 && (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground border-2 border-dashed rounded-xl bg-card/50">
              <p className="text-lg font-medium">No bangumi found</p>
              <p className="text-sm opacity-70">Try changing the filter or add a new one</p>
          </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 md:gap-6">
        {bangumiList?.map((bangumi) => (
          <BangumiCard 
            key={bangumi.id} 
            bangumi={bangumi} 
            onClick={() => handleCardClick(bangumi)} 
          />
        ))}
      </div>

      <BangumiDetailDialog 
        bangumi={selectedBangumi} 
        open={dialogOpen} 
        onOpenChange={setDialogOpen} 
      />
    </div>
  );
}
