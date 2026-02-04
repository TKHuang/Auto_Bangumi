import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
import type { Bangumi } from './BangumiCard';
import { TorrentList, type Torrent } from './TorrentList';
import api from '@/lib/api';
import { Trash2, Save, FolderEdit, RefreshCw } from 'lucide-react';

interface BangumiDetailDialogProps {
  bangumi: Bangumi | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function BangumiDetailDialog({ bangumi, open, onOpenChange }: BangumiDetailDialogProps) {
  const queryClient = useQueryClient();
  const [deleteFiles, setDeleteFiles] = useState(false);

  const { register, handleSubmit, formState: { isDirty } } = useForm<Bangumi>({
    values: bangumi || undefined,
  });

  const { data: torrents, isLoading: isLoadingTorrents } = useQuery({
    queryKey: ['torrents', bangumi?.id],
    queryFn: async () => {
      if (!bangumi) return [];
      const res = await api.get<Torrent[]>(`/bangumi/${bangumi.id}/torrents`);
      return res.data;
    },
    enabled: !!bangumi && open,
  });

  const updateMutation = useMutation({
    mutationFn: async (data: Bangumi) => {
      await api.put(`/bangumi/${bangumi!.id}`, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bangumi'] });
      onOpenChange(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      await api.delete(`/bangumi/${bangumi!.id}`, { params: { file: deleteFiles } });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['bangumi'] });
      onOpenChange(false);
    },
  });

  if (!bangumi) return null;

  const onSave = (data: Bangumi) => {
    updateMutation.mutate(data);
  };

  const handleNotImplemented = () => {
      alert("Feature not implemented (501)");
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-start justify-between pr-8">
            <div className="space-y-1">
                <DialogTitle className="text-2xl font-bold">{bangumi.official_title}</DialogTitle>
                <DialogDescription className="flex items-center gap-2">
                    <span>{bangumi.year}</span>
                    <span>•</span>
                    <span>Season {bangumi.season}</span>
                    <span>•</span>
                    <span className="font-mono bg-muted px-1 rounded text-xs">{bangumi.group_name}</span>
                </DialogDescription>
            </div>
            <div className="flex gap-2 shrink-0">
                 {bangumi.deleted && <Badge variant="destructive">Deleted</Badge>}
                 {bangumi.pending_review && <Badge className="bg-amber-500">Pending</Badge>}
                 {!bangumi.deleted && !bangumi.pending_review && <Badge className="bg-emerald-500">Active</Badge>}
            </div>
          </div>
        </DialogHeader>

        <Tabs defaultValue="settings" className="w-full mt-2">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="settings">Settings</TabsTrigger>
            <TabsTrigger value="torrents">Torrents</TabsTrigger>
          </TabsList>
          
          <TabsContent value="settings" className="space-y-6 py-4">
            <form id="bangumi-form" onSubmit={handleSubmit(onSave)} className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
                <div className="space-y-2 col-span-2">
                    <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">Official Title</label>
                    <Input {...register('official_title')} className="font-medium" />
                </div>
                
                <div className="space-y-2">
                    <label className="text-sm font-medium leading-none">Group Name</label>
                    <Input {...register('group_name')} />
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                        <label className="text-sm font-medium leading-none">Year</label>
                        <Input {...register('year')} />
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium leading-none">Season</label>
                        <Input type="number" {...register('season', { valueAsNumber: true })} />
                    </div>
                </div>
                
                <div className="space-y-2 col-span-2">
                    <label className="text-sm font-medium leading-none">Filter (Regex)</label>
                    <Input {...register('filter')} placeholder="Optional regex filter" className="font-mono text-sm" />
                </div>
                
                <div className="space-y-2">
                    <label className="text-sm font-medium leading-none">Offset</label>
                    <Input type="number" {...register('offset', { valueAsNumber: true })} />
                </div>
                
                <div className="space-y-2">
                    <label className="text-sm font-medium leading-none">DPI</label>
                    <Input {...register('dpi')} />
                </div>
            </form>

            <div className="flex flex-col gap-4 border-t pt-6">
                <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
                    <div className="flex gap-2 w-full sm:w-auto">
                        <Button type="button" variant="outline" size="sm" onClick={handleNotImplemented} className="flex-1 sm:flex-none">
                            <FolderEdit className="w-4 h-4 mr-2" /> Rename
                        </Button>
                        <Button type="button" variant="outline" size="sm" onClick={handleNotImplemented} className="flex-1 sm:flex-none">
                            <RefreshCw className="w-4 h-4 mr-2" /> Collect
                        </Button>
                    </div>
                    
                    <div className="flex items-center gap-4 w-full sm:w-auto justify-between sm:justify-end">
                        <div className="flex items-center gap-2">
                             <Switch id="delete-files" checked={deleteFiles} onCheckedChange={setDeleteFiles} />
                             <label htmlFor="delete-files" className="text-sm text-muted-foreground cursor-pointer select-none">Delete files</label>
                        </div>
                        <Button variant="destructive" size="sm" onClick={() => deleteMutation.mutate()} disabled={deleteMutation.isPending}>
                            <Trash2 className="w-4 h-4 mr-2" /> Delete
                        </Button>
                    </div>
                </div>
                
                <div className="flex justify-end pt-2">
                    <Button type="submit" form="bangumi-form" disabled={!isDirty || updateMutation.isPending} className="w-full sm:w-auto">
                        <Save className="w-4 h-4 mr-2" /> 
                        {updateMutation.isPending ? 'Saving...' : 'Save Changes'}
                    </Button>
                </div>
            </div>
          </TabsContent>
          
          <TabsContent value="torrents" className="py-4 min-h-[300px]">
            <TorrentList torrents={torrents || []} isLoading={isLoadingTorrents} />
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
