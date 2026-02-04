import { useQuery } from '@tanstack/react-query';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { ProgramTab } from '../components/config/ProgramTab';
import { DownloaderTab } from '../components/config/DownloaderTab';
import { ParserTab } from '../components/config/ParserTab';
import { ManageTab } from '../components/config/ManageTab';
import { ProxyTab } from '../components/config/ProxyTab';
import { NotificationTab } from '../components/config/NotificationTab';
import type { Config } from '../types/config';
import api from '../lib/api';
import { Loader2, AlertCircle } from 'lucide-react';
import { Card, CardContent } from '../components/ui/card';

export default function ConfigPage() {
  const { data: config, isLoading, isError, error } = useQuery<Config>({
    queryKey: ['config'],
    queryFn: async () => {
      const res = await api.get('/config/');
      return res.data;
    },
  });

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-8">
        <Card className="border-destructive/50 bg-destructive/10">
          <CardContent className="flex items-center gap-4 p-6 text-destructive">
            <AlertCircle className="h-5 w-5" />
            <div>
              <h5 className="font-medium leading-none tracking-tight">Error</h5>
              <div className="text-sm opacity-90 mt-1">
                Failed to load configuration: {error instanceof Error ? error.message : 'Unknown error'}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!config) {
    return null;
  }

  return (
    <div className="container mx-auto max-w-4xl p-6 space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Configuration</h1>
        <p className="text-muted-foreground mt-2">
          Manage your AutoBangumi settings and preferences.
        </p>
      </div>

      <Tabs defaultValue="program" className="space-y-6">
        <TabsList className="grid w-full grid-cols-2 lg:grid-cols-6 h-auto">
          <TabsTrigger value="program">Program</TabsTrigger>
          <TabsTrigger value="downloader">Downloader</TabsTrigger>
          <TabsTrigger value="parser">Parser</TabsTrigger>
          <TabsTrigger value="manage">Manage</TabsTrigger>
          <TabsTrigger value="proxy">Proxy</TabsTrigger>
          <TabsTrigger value="notification">Notification</TabsTrigger>
        </TabsList>

        <TabsContent value="program">
          <ProgramTab config={config.program} />
        </TabsContent>

        <TabsContent value="downloader">
          <DownloaderTab config={config.downloader} />
        </TabsContent>

        <TabsContent value="parser">
          <ParserTab config={config.rss_parser} />
        </TabsContent>

        <TabsContent value="manage">
          <ManageTab config={config.bangumi_manage} />
        </TabsContent>

        <TabsContent value="proxy">
          <ProxyTab config={config.proxy} />
        </TabsContent>

        <TabsContent value="notification">
          <NotificationTab config={config.notification} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
