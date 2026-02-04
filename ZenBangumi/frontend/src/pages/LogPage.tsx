import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { RefreshCw, Trash2, ExternalLink } from 'lucide-react';
import { useEffect, useRef, useMemo } from 'react';

export default function LogPage() {
  const queryClient = useQueryClient();
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: logData, isLoading, refetch } = useQuery({
    queryKey: ['logs'],
    queryFn: async () => {
      const res = await api.get('/log/');
      if (typeof res.data === 'string') return res.data;
      return res.data?.log || '';
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      await api.delete('/log/');
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['logs'] });
    },
  });

  const logs = useMemo(() => {
    if (!logData) return [];
    return logData
      .trim()
      .split('\n')
      .filter((line: string) => line.trim() !== '')
      .map((line: string, index: number) => {
        const dateMatch = line.match(/\[\d+-\d+-\d+\ \d+:\d+:\d+\]/);
        const date = dateMatch ? dateMatch[0] : '';
        
        const typeMatch = line.match(/(INFO)|(WARNING)|(ERROR)|(DEBUG)|(WARN)/);
        const type = typeMatch ? typeMatch[0] : 'INFO';
        
        let content = line.replace(date, '');
        content = content.replace(new RegExp(`^\\s*${type}:?\\s*`), '').trim();

        return { index, date, type, content, original: line };
      });
  }, [logData]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const getLogColor = (type: string) => {
    switch (type) {
      case 'ERROR':
        return 'text-red-500';
      case 'WARNING':
      case 'WARN':
        return 'text-yellow-500';
      case 'INFO':
        return 'text-white';
      case 'DEBUG':
        return 'text-gray-400';
      default:
        return 'text-white';
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex flex-col md:flex-row gap-6">
        <Card className="flex-1 shadow-lg border-border/50">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
            <CardTitle className="text-xl font-bold">System Logs</CardTitle>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => refetch()}
                disabled={isLoading}
                title="Refresh Logs"
              >
                <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={() => {
                  if (confirm('Are you sure you want to clear all logs?')) {
                    deleteMutation.mutate();
                  }
                }}
                disabled={deleteMutation.isPending}
                title="Clear Logs"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div
              ref={scrollRef}
              className="h-[60vh] w-full rounded-md border bg-black/90 p-4 font-mono text-sm shadow-inner overflow-auto"
            >
              {isLoading ? (
                <div className="flex h-full items-center justify-center text-muted-foreground">
                  Loading logs...
                </div>
              ) : logs.length === 0 ? (
                <div className="flex h-full items-center justify-center text-muted-foreground">
                  No logs available.
                </div>
              ) : (
                <div className="flex flex-col space-y-1">
                  {logs.map((log: { index: number; date: string; type: string; content: string }) => (
                    <div key={log.index} className={`flex gap-3 ${getLogColor(log.type)} hover:bg-white/5 p-0.5 rounded transition-colors`}>
                      <span className="text-gray-500 shrink-0 select-none text-xs pt-0.5 w-[140px]">{log.date}</span>
                      <span className={`font-bold shrink-0 w-[60px] ${getLogColor(log.type)}`}>{log.type}</span>
                      <span className="break-all">{log.content}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <div className="w-full md:w-80 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Resources</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button variant="outline" className="w-full justify-between" asChild>
                <a href="https://github.com/EstrellaXD/Auto_Bangumi" target="_blank" rel="noreferrer">
                  GitHub <ExternalLink className="h-4 w-4" />
                </a>
              </Button>
              <Button variant="outline" className="w-full justify-between" asChild>
                <a href="https://autobangumi.org" target="_blank" rel="noreferrer">
                  Official Website <ExternalLink className="h-4 w-4" />
                </a>
              </Button>
              <Button variant="outline" className="w-full justify-between" asChild>
                <a href="https://github.com/EstrellaXD/Auto_Bangumi/issues" target="_blank" rel="noreferrer">
                  Report Issues <ExternalLink className="h-4 w-4" />
                </a>
              </Button>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Contact</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
               <Button variant="ghost" className="w-full justify-start px-0 hover:bg-transparent hover:text-primary">
                Telegram Group
               </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
