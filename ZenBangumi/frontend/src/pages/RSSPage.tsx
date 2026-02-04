import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';
import { Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { AddRSSDialog } from '@/components/AddRSSDialog';
import type { AddRSSPayload } from '@/components/AddRSSDialog';
import { RSSFeedCard } from '@/components/RSSFeedCard';
import type { RSS } from '@/components/RSSFeedCard';
import { PendingBangumiList } from '@/components/PendingBangumiList';
import type { Bangumi } from '@/components/PendingBangumiList';

export default function RSSPage() {
  const queryClient = useQueryClient();
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

  // --- Queries ---

  const { data: feeds = [], isLoading: isLoadingFeeds } = useQuery<RSS[]>({
    queryKey: ['rss'],
    queryFn: async () => {
      const res = await api.get('/rss/');
      return res.data;
    },
  });

  const { data: allBangumis = [] } = useQuery<Bangumi[]>({
    queryKey: ['bangumi'],
    queryFn: async () => {
      const res = await api.get('/bangumi/');
      return res.data;
    },
  });

  // --- Derived State ---

  const pendingBangumis = useMemo(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return allBangumis.filter((b: any) => b.pending_review === true || b.pending_review === 1);
  }, [allBangumis]);

  const pendingCounts = useMemo(() => {
    const counts: Record<number, number> = {};
    if (!feeds.length) return {};
    
    const urlToId: Record<string, number> = {};
    feeds.forEach(f => {
      if (f.url) urlToId[f.url] = f.id;
    });

    pendingBangumis.forEach((b: Bangumi) => {
        const rssId = urlToId[b.rss_link];
        if (rssId) {
            counts[rssId] = (counts[rssId] || 0) + 1;
        }
    });
    
    return counts;
  }, [feeds, pendingBangumis]);

  // --- Mutations ---

  const addRSSMutation = useMutation({
    mutationFn: async (payload: AddRSSPayload) => {
      await api.post('/rss/', payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rss'] });
    },
  });

  const deleteRSSMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/rss/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rss'] });
    },
  });

  const toggleRSSMutation = useMutation({
    mutationFn: async ({ id, enabled }: { id: number; enabled: boolean }) => {
      await api.put(`/rss/${id}`, { enabled });
    },
    onMutate: async ({ id, enabled }) => {
      await queryClient.cancelQueries({ queryKey: ['rss'] });
      const previousFeeds = queryClient.getQueryData<RSS[]>(['rss']);
      
      queryClient.setQueryData<RSS[]>(['rss'], (old) => {
        if (!old) return [];
        return old.map((f) => (f.id === id ? { ...f, enabled } : f));
      });
      
      return { previousFeeds };
    },
    onError: (_err, _variables, context) => {
      if (context?.previousFeeds) {
        queryClient.setQueryData(['rss'], context.previousFeeds);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['rss'] });
    },
  });

  const deleteBangumiMutation = useMutation({
    mutationFn: async (id: number) => {
      await api.delete(`/bangumi/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bangumi'] });
    },
  });

  const updateBangumiFilterMutation = useMutation({
    mutationFn: async ({ id, filter }: { id: number; filter: string }) => {
       await api.patch(`/bangumi/${id}`, { filter });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bangumi'] });
    }
  });

  // --- Handlers ---

  const handleAddRSS = async (data: AddRSSPayload) => {
    await addRSSMutation.mutateAsync(data);
  };

  const handleToggleRSS = (feed: RSS) => {
    toggleRSSMutation.mutate({ id: feed.id, enabled: !feed.enabled });
  };

  const handleDeleteRSS = (feed: RSS) => {
    if (confirm(`Are you sure you want to delete "${feed.name || feed.url}"?`)) {
      deleteRSSMutation.mutate(feed.id);
    }
  };

  const handleRefresh = (_feed: RSS) => {
    alert("Refresh functionality is not yet implemented (501).");
  };

  const handleRecreate = (_feed: RSS) => {
    alert("Recreate functionality is not yet implemented (501).");
  };
  
  const handleActivateBangumi = (_bangumi: Bangumi) => {
      alert("Activate Bangumi is not yet implemented (501).");
  };

  const handleBatchActivate = () => {
      alert("Batch Activate is not yet implemented (501).");
  };
  
  const handleEditFilter = (bangumi: Bangumi) => {
      const newFilter = prompt("Edit Filter Regex:", bangumi.filter);
      if (newFilter !== null && newFilter !== bangumi.filter) {
          updateBangumiFilterMutation.mutate({ id: bangumi.id, filter: newFilter });
      }
  };

  const handleDeleteBangumi = (bangumi: Bangumi) => {
      if (confirm(`Delete pending bangumi "${bangumi.official_title}"?`)) {
          deleteBangumiMutation.mutate(bangumi.id);
      }
  };

  return (
    <div className="container mx-auto py-6 space-y-8 max-w-5xl">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">RSS Management</h1>
          <p className="text-muted-foreground mt-1">
            Manage your RSS subscriptions and pending bangumi reviews.
          </p>
        </div>
        <Button onClick={() => setIsAddDialogOpen(true)} className="w-full sm:w-auto">
          <Plus className="mr-2 h-4 w-4" /> Add RSS Feed
        </Button>
      </div>

      <div className="space-y-4">
        {isLoadingFeeds ? (
          <div className="text-center py-12 text-muted-foreground">Loading feeds...</div>
        ) : feeds.length === 0 ? (
          <div className="text-center py-12 border rounded-lg bg-muted/20">
            <p className="text-muted-foreground">No RSS feeds found.</p>
            <Button variant="link" onClick={() => setIsAddDialogOpen(true)}>
              Add your first feed
            </Button>
          </div>
        ) : (
          <div className="grid gap-4">
            {feeds.map((feed) => (
              <RSSFeedCard
                key={feed.id}
                feed={feed}
                pendingCount={pendingCounts[feed.id] || 0}
                onToggle={(_enabled) => handleToggleRSS(feed)}
                onDelete={() => handleDeleteRSS(feed)}
                onRefresh={() => handleRefresh(feed)}
                onRecreate={() => handleRecreate(feed)}
              />
            ))}
          </div>
        )}
      </div>

      {pendingBangumis.length > 0 && (
          <PendingBangumiList 
            bangumis={pendingBangumis}
            feeds={feeds}
            onActivate={handleActivateBangumi}
            onEditFilter={handleEditFilter}
            onDelete={handleDeleteBangumi}
            onBatchActivate={handleBatchActivate}
          />
      )}

      <AddRSSDialog 
        open={isAddDialogOpen} 
        onOpenChange={setIsAddDialogOpen} 
        onSubmit={handleAddRSS} 
      />
    </div>
  );
}
