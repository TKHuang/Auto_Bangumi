import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { FileImage } from 'lucide-react';

export interface Bangumi {
  id: number;
  official_title: string;
  poster_link: string | null;
  year: string;
  season: number;
  season_raw?: string;
  group_name: string;
  deleted: boolean;
  pending_review: boolean;
  // Additional fields for detail dialog
  filter?: string;
  offset?: number;
  dpi?: string;
  source?: string;
  subtitle?: string;
  added_at?: string;
  updated_at?: string;
  version?: number;
}

interface BangumiCardProps {
  bangumi: Bangumi;
  onClick: () => void;
}

export function BangumiCard({ bangumi, onClick }: BangumiCardProps) {
  const [imgError, setImgError] = useState(false);

  return (
    <Card 
      className="group relative cursor-pointer overflow-hidden rounded-xl border-border/50 bg-card/50 shadow-sm transition-all hover:-translate-y-1 hover:shadow-xl hover:shadow-primary/20 hover:border-primary/50"
      onClick={onClick}
    >
      <div className="aspect-[2/3] w-full overflow-hidden relative bg-muted">
        {!imgError && bangumi.poster_link ? (
          <img
            src={bangumi.poster_link}
            alt={bangumi.official_title}
            className="h-full w-full object-cover transition-transform duration-700 ease-out group-hover:scale-110"
            onError={() => setImgError(true)}
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center bg-muted text-muted-foreground p-4 text-center">
            <FileImage className="h-12 w-12 mb-2 opacity-50" />
            <span className="text-xs font-medium">No Poster</span>
          </div>
        )}
        
        {/* Status Badges */}
        <div className="absolute top-2 right-2 z-10 flex flex-col gap-1 items-end">
          {bangumi.deleted && (
            <Badge variant="destructive" className="shadow-sm backdrop-blur-md">Deleted</Badge>
          )}
          {bangumi.pending_review && (
            <Badge className="bg-amber-500 hover:bg-amber-600 text-white shadow-sm backdrop-blur-md">Pending</Badge>
          )}
          {!bangumi.deleted && !bangumi.pending_review && (
             <Badge className="bg-emerald-500 hover:bg-emerald-600 text-white shadow-sm backdrop-blur-md">Active</Badge>
          )}
        </div>
        
        {/* Content Overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent opacity-60 transition-opacity duration-300 group-hover:opacity-80" />
        <div className="absolute inset-0 flex flex-col justify-end p-4 text-white">
          <h3 className="font-bold text-lg leading-tight line-clamp-2 mb-1 text-white drop-shadow-sm group-hover:text-primary-foreground transition-colors">
            {bangumi.official_title}
          </h3>
          
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-white/90 font-medium mb-1">
            <span className="bg-white/20 px-1.5 py-0.5 rounded backdrop-blur-sm">{bangumi.year}</span>
            <span className="bg-white/20 px-1.5 py-0.5 rounded backdrop-blur-sm">Season {bangumi.season}</span>
          </div>
          
          <div className="text-xs text-white/70 truncate flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-primary inline-block" />
            {bangumi.group_name}
          </div>
        </div>
      </div>
    </Card>
  );
}
