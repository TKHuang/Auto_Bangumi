import React from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Play, Trash2, Filter, Edit } from 'lucide-react';
import type { RSS } from './RSSFeedCard';

export interface Bangumi {
  id: number;
  official_title: string;
  season: number;
  group_name: string;
  filter: string;
  rss_link: string;
  title_raw: string;
  deleted: boolean;
}

interface PendingBangumiListProps {
  bangumis: Bangumi[];
  feeds: RSS[];
  onActivate: (bangumi: Bangumi) => void;
  onEditFilter: (bangumi: Bangumi) => void;
  onDelete: (bangumi: Bangumi) => void;
  onBatchActivate: () => void;
}

export const PendingBangumiList: React.FC<PendingBangumiListProps> = ({
  bangumis,
  feeds,
  onActivate,
  onEditFilter,
  onDelete,
  onBatchActivate,
}) => {
  if (bangumis.length === 0) {
    return null;
  }

  const groupedBangumis = React.useMemo(() => {
    const groups: Record<string, Bangumi[]> = {};
    bangumis.forEach((b) => {
      const key = b.rss_link || 'Other';
      if (!groups[key]) groups[key] = [];
      groups[key].push(b);
    });
    return groups;
  }, [bangumis]);

  const getFeedName = (url: string) => {
    const feed = feeds.find((f) => f.url === url);
    return feed?.name || url;
  };

  return (
    <Card className="mt-8 border-amber-200 dark:border-amber-900 bg-amber-50/50 dark:bg-amber-900/10">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <div className="flex flex-col gap-1">
            <CardTitle className="text-xl font-bold text-amber-900 dark:text-amber-100">
            Pending Reviews
            </CardTitle>
            <p className="text-sm text-muted-foreground">
                These bangumi matched your filters but need confirmation.
            </p>
        </div>
        <Button onClick={onBatchActivate} variant="outline" className="border-amber-500 text-amber-600 hover:bg-amber-100">
          <Play className="mr-2 h-4 w-4" />
          Batch Activate
        </Button>
      </CardHeader>
      <CardContent className="space-y-6">
        {Object.entries(groupedBangumis).map(([rssUrl, items]) => (
          <div key={rssUrl} className="space-y-3">
            <div className="flex items-center gap-2 border-b border-amber-200 dark:border-amber-800 pb-1">
              <h3 className="font-semibold text-lg text-amber-800 dark:text-amber-200">
                {getFeedName(rssUrl)}
              </h3>
              <Badge variant="outline" className="text-xs">
                {items.length} pending
              </Badge>
            </div>
            
            <div className="grid gap-3">
              {items.map((bangumi) => (
                <div
                  key={bangumi.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-white dark:bg-zinc-900 border shadow-sm"
                >
                  <div className="flex-1 min-w-0 grid gap-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium truncate">
                        {bangumi.official_title}
                      </span>
                      <Badge variant="secondary" className="text-[10px]">
                        S{bangumi.season}
                      </Badge>
                      {bangumi.group_name && (
                         <Badge variant="outline" className="text-[10px]">
                            {bangumi.group_name}
                         </Badge>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground truncate" title={bangumi.title_raw}>
                       {bangumi.title_raw}
                    </div>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <Filter className="w-3 h-3" />
                        <code className="bg-muted px-1 rounded">{bangumi.filter}</code>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 ml-4">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => onActivate(bangumi)}
                      title="Activate"
                    >
                      <Play className="w-4 h-4 text-green-600" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => onEditFilter(bangumi)}
                      title="Edit Filter"
                    >
                      <Edit className="w-4 h-4 text-blue-600" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => onDelete(bangumi)}
                      title="Delete"
                    >
                      <Trash2 className="w-4 h-4 text-red-600" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
};
