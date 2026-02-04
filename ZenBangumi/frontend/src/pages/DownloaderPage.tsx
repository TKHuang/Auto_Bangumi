import { useQuery } from '@tanstack/react-query';
import api from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { CheckCircle2, XCircle, Download, Activity } from 'lucide-react';

export default function DownloaderPage() {
  const { data: config } = useQuery({
    queryKey: ['config'],
    queryFn: async () => {
      const res = await api.get('/config/');
      return res.data;
    },
  });

  const downloaderType = config?.downloader?.type || 'qBittorrent';
  const downloaderHost = config?.downloader?.host || '127.0.0.1:8080';
  const isConnected = true;

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl font-bold flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Downloader Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="flex flex-col space-y-2">
              <span className="text-sm text-muted-foreground">Type</span>
              <span className="font-semibold text-lg">{downloaderType}</span>
            </div>
            
            <div className="flex flex-col space-y-2">
              <span className="text-sm text-muted-foreground">Host</span>
              <span className="font-semibold text-lg">{downloaderHost}</span>
            </div>
            
            <div className="flex flex-col space-y-2">
              <span className="text-sm text-muted-foreground">Status</span>
              <div className="flex items-center gap-2">
                {isConnected ? (
                  <Badge variant="default" className="bg-green-600 hover:bg-green-700">
                    <CheckCircle2 className="h-3 w-3 mr-1" /> Connected
                  </Badge>
                ) : (
                  <Badge variant="destructive">
                    <XCircle className="h-3 w-3 mr-1" /> Disconnected
                  </Badge>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-xl font-bold flex items-center gap-2">
            <Download className="h-5 w-5" />
            Active Downloads (Placeholder)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <table className="w-full text-sm text-left">
              <thead className="bg-muted/50 text-muted-foreground">
                <tr>
                  <th className="p-4 font-medium">Name</th>
                  <th className="p-4 font-medium w-32">Size</th>
                  <th className="p-4 font-medium w-32">Progress</th>
                  <th className="p-4 font-medium w-32">Speed</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-t hover:bg-muted/50">
                  <td className="p-4 font-medium">[Lilith-Raws] Kakkou no Iinazuke - 07.mp4</td>
                  <td className="p-4">1.2 GB</td>
                  <td className="p-4">
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                        <div className="h-full bg-primary w-[45%]" />
                      </div>
                      <span className="text-xs">45%</span>
                    </div>
                  </td>
                  <td className="p-4 text-green-500">2.5 MB/s</td>
                </tr>
                <tr className="border-t hover:bg-muted/50">
                  <td className="p-4 font-medium text-muted-foreground text-center py-8" colSpan={4}>
                    No other active downloads
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
