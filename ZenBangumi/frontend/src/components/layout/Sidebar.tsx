import { NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { 
  LayoutDashboard, 
  Rss, 
  Settings, 
  FileText, 
  Calendar, 
  Download, 
  Search,
  LogOut
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { useAuthStore } from '@/stores/authStore';

export default function Sidebar() {
  const { t } = useTranslation();
  const logout = useAuthStore((state) => state.logout);

  const navItems = [
    { to: '/', icon: LayoutDashboard, label: t('nav.dashboard') },
    { to: '/rss', icon: Rss, label: t('nav.rss') },
    { to: '/calendar', icon: Calendar, label: t('nav.calendar') },
    { to: '/downloader', icon: Download, label: t('nav.downloader') },
    { to: '/search', icon: Search, label: t('nav.search') },
    { to: '/log', icon: FileText, label: t('nav.log') },
    { to: '/config', icon: Settings, label: t('nav.config') },
  ];

  return (
    <div className="flex h-full w-64 flex-col border-r bg-card text-card-foreground hidden md:flex">
      <div className="flex h-14 items-center border-b px-4">
        <span className="font-semibold text-lg">{t('app.title')}</span>
      </div>
      <div className="flex-1 overflow-auto py-2">
        <nav className="grid gap-1 px-2">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground",
                  isActive ? "bg-accent text-accent-foreground" : "text-muted-foreground"
                )
              }
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="border-t p-4">
        <Button 
          variant="outline" 
          className="w-full justify-start gap-2" 
          onClick={() => logout()}
        >
          <LogOut className="h-4 w-4" />
          {t('app.logout')}
        </Button>
      </div>
    </div>
  );
}
