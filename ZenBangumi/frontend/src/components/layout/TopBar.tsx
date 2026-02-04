import { useProgramStore } from '@/stores/programStore';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/components/ui/badge';

export default function TopBar() {
  const { status } = useProgramStore();
  const { t } = useTranslation();

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'bg-green-500 hover:bg-green-600';
      case 'stopped':
        return 'bg-yellow-500 hover:bg-yellow-600';
      case 'error':
        return 'bg-red-500 hover:bg-red-600';
      default:
        return 'bg-gray-500';
    }
  };

  return (
    <header className="flex h-14 items-center gap-4 border-b bg-background px-6">
      <div className="flex-1">
        {/* Breadcrumbs or page title could go here */}
      </div>
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Status:</span>
        <Badge className={getStatusColor(status)}>
          {t(`status.${status}`)}
        </Badge>
      </div>
    </header>
  );
}
