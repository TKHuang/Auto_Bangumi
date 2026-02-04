import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { MoreVertical, RefreshCw, Trash2, RotateCcw, AlertCircle } from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu';

export interface RSS {
  id: number;
  name: string | null;
  url: string;
  enabled: boolean;
  aggregate: boolean;
  parser: string;
  last_update: string | null;
  last_status: string | null;
  last_error: string | null;
}

interface RSSFeedCardProps {
  feed: RSS;
  pendingCount: number;
  onToggle: (enabled: boolean) => void;
  onDelete: () => void;
  onRefresh: () => void;
  onRecreate: () => void;
}

export const RSSFeedCard: React.FC<RSSFeedCardProps> = ({
  feed,
  pendingCount,
  onToggle,
  onDelete,
  onRefresh,
  onRecreate,
}) => {
  return (
    <Card className="overflow-hidden">
      <CardContent className="p-4 flex items-center gap-4">
        {/* Selection/Icon placeholder if needed, skipping for now based on requirements */}
        
        {/* Main Info */}
        <div className="flex-1 min-w-0 grid gap-1">
          <div className="flex items-center gap-2">
            <h3 className="font-semibold text-lg truncate leading-none">
              {feed.name || 'Unnamed Feed'}
            </h3>
            {feed.aggregate && (
              <Badge variant="secondary" className="text-[10px] px-1 h-5">
                Agg
              </Badge>
            )}
          </div>
          <p className="text-sm text-muted-foreground truncate" title={feed.url}>
            {feed.url}
          </p>
        </div>

        {/* Status & Metadata */}
        <div className="flex items-center gap-4 text-sm">
          {/* Last Update */}
          <div className="text-right hidden md:block">
            <p className="text-xs text-muted-foreground">Last Update</p>
            <p className="font-medium">{feed.last_update || '-'}</p>
          </div>

          {/* Status Indicators */}
          <div className="flex flex-col items-end gap-1 w-[140px]">
            <div className="flex items-center gap-2">
              {pendingCount > 0 && (
                <Badge 
                  className="bg-amber-500 hover:bg-amber-600 gap-1 px-2 h-6"
                  title={`${pendingCount} pending reviews`}
                >
                  <AlertCircle className="w-3 h-3" />
                  {pendingCount}
                </Badge>
              )}
              
              {feed.last_status === 'Success' ? (
                <Badge variant="default" className="bg-green-500 hover:bg-green-600 h-6">Success</Badge>
              ) : feed.last_status === 'Error' ? (
                 <Badge variant="destructive" className="h-6" title={feed.last_error || 'Unknown error'}>Error</Badge>
              ) : (
                <Badge variant="outline" className="h-6">-</Badge>
              )}
            </div>
            
            <div className="flex items-center gap-2">
               <Badge variant="outline" className="h-5 text-[10px]">{feed.parser}</Badge>
               <Switch 
                 checked={feed.enabled}
                 onCheckedChange={onToggle}
                 className="scale-75 origin-right"
               />
            </div>
          </div>
        </div>

        {/* Actions */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <MoreVertical className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={onRefresh}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </DropdownMenuItem>
            <DropdownMenuItem onClick={onRecreate}>
              <RotateCcw className="mr-2 h-4 w-4" />
              Recreate
            </DropdownMenuItem>
            {/* Edit is not in top requirements for card actions but usually exists. 
                Requirements say: Refresh, Delete, Recreate. 
                I'll stick to those. */}
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={onDelete} className="text-destructive focus:text-destructive">
              <Trash2 className="mr-2 h-4 w-4" />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </CardContent>
    </Card>
  );
};
