import type { ReactNode } from 'react';
import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom';
import AppLayout from '@/components/layout/AppLayout';
import LoginPage from '@/pages/LoginPage';
import BangumiPage from '@/pages/BangumiPage';
import RSSPage from '@/pages/RSSPage';
import ConfigPage from '@/pages/ConfigPage';
import LogPage from '@/pages/LogPage';
import CalendarPage from '@/pages/CalendarPage';
import DownloaderPage from '@/pages/DownloaderPage';
import SearchPage from '@/pages/SearchPage';
import { useAuthStore } from '@/stores/authStore';

const ProtectedRoute = ({ children }: { children: ReactNode }) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return children;
};

const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <BangumiPage />,
      },
      {
        path: 'rss',
        element: <RSSPage />,
      },
      {
        path: 'config',
        element: <ConfigPage />,
      },
      {
        path: 'log',
        element: <LogPage />,
      },
      {
        path: 'calendar',
        element: <CalendarPage />,
      },
      {
        path: 'downloader',
        element: <DownloaderPage />,
      },
      {
        path: 'search',
        element: <SearchPage />,
      },
    ],
  },
]);

function App() {
  return <RouterProvider router={router} />;
}

export default App;
