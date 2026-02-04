import { CheckCircle2, Circle } from 'lucide-react';

export interface Torrent {
  id: number;
  name: string;
  downloaded: boolean;
  renamed_at: string | null;
}

interface TorrentListProps {
  torrents: Torrent[];
  isLoading?: boolean;
}

export function TorrentList({ torrents, isLoading }: TorrentListProps) {
  if (isLoading) {
    return <div className="p-8 text-center text-muted-foreground animate-pulse">Loading torrents...</div>;
  }

  if (!torrents || torrents.length === 0) {
    return <div className="p-8 text-center text-muted-foreground border rounded-md border-dashed">No torrents found.</div>;
  }

  return (
    <div className="w-full overflow-auto rounded-md border shadow-sm">
      <table className="w-full caption-bottom text-sm">
        <thead className="[&_tr]:border-b bg-muted/30">
          <tr className="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted">
            <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0">
              Name
            </th>
            <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0 w-[120px]">
              Status
            </th>
            <th className="h-12 px-4 text-left align-middle font-medium text-muted-foreground [&:has([role=checkbox])]:pr-0 w-[160px]">
              Renamed
            </th>
          </tr>
        </thead>
        <tbody className="[&_tr:last-child]:border-0">
          {torrents.map((torrent) => (
            <tr
              key={torrent.id}
              className="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted"
            >
              <td className="p-4 align-middle [&:has([role=checkbox])]:pr-0 font-mono text-xs">
                <div className="line-clamp-2 break-all" title={torrent.name}>
                    {torrent.name}
                </div>
              </td>
              <td className="p-4 align-middle [&:has([role=checkbox])]:pr-0">
                {torrent.downloaded ? (
                    <div className="flex items-center gap-2 text-emerald-600 font-medium">
                        <CheckCircle2 className="h-4 w-4" />
                        <span>Done</span>
                    </div>
                ) : (
                    <div className="flex items-center gap-2 text-muted-foreground">
                        <Circle className="h-4 w-4" />
                        <span>Pending</span>
                    </div>
                )}
              </td>
              <td className="p-4 align-middle [&:has([role=checkbox])]:pr-0 text-muted-foreground">
                {torrent.renamed_at ? (
                    <div className="flex flex-col text-xs">
                        <span className="font-medium text-foreground">
                            {new Date(torrent.renamed_at).toLocaleDateString()}
                        </span>
                        <span className="text-[10px] opacity-70">
                            {new Date(torrent.renamed_at).toLocaleTimeString()}
                        </span>
                    </div>
                ) : (
                    <span className="text-xs italic opacity-50">Not renamed</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
