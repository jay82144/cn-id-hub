import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { toast } from 'sonner';
import {
  LayoutDashboard,
  Users,
  Shield,
  FileText,
  Settings,
  ExternalLink,
  LogOut,
  User,
  ChevronDown,
  Loader2,
  Boxes,
  ClipboardCheck,
  BarChart3,
  Calendar,
  MessageSquare,
  Briefcase,
} from 'lucide-react';

// Icon mapping for apps
const iconMap = {
  'LayoutDashboard': LayoutDashboard,
  'Users': Users,
  'Shield': Shield,
  'FileText': FileText,
  'Settings': Settings,
  'Boxes': Boxes,
  'ClipboardCheck': ClipboardCheck,
  'BarChart3': BarChart3,
  'Calendar': Calendar,
  'MessageSquare': MessageSquare,
  'Briefcase': Briefcase,
};

const AppCard = ({ app, index }) => {
  const IconComponent = iconMap[app.icon] || LayoutDashboard;
  
  return (
    <a
      href={app.url}
      target="_blank"
      rel="noopener noreferrer"
      className={`group block bg-white border border-gray-200 p-6 transition-all duration-200 hover:border-blue-600 hover:shadow-[0_8px_30px_rgb(0,0,0,0.04)] rounded-md animate-fade-in opacity-0`}
      style={{ animationDelay: `${index * 0.05}s`, animationFillMode: 'forwards' }}
      data-testid={`app-card-${app.id}`}
    >
      <div className="flex items-start justify-between">
        <div className="w-12 h-12 rounded-lg bg-gray-50 border border-gray-100 flex items-center justify-center text-gray-700 group-hover:scale-105 transition-transform">
          <IconComponent className="w-6 h-6" />
        </div>
        <ExternalLink className="w-4 h-4 text-gray-300 group-hover:text-blue-600 transition-colors" />
      </div>
      <h3 className="text-lg font-semibold text-gray-900 mt-4">
        {app.name}
      </h3>
      <p className="text-sm text-gray-500 mt-1 line-clamp-2">
        {app.description || 'No description available'}
      </p>
    </a>
  );
};

const LaunchpadPage = () => {
  const navigate = useNavigate();
  const { user, logout, isAdmin } = useAuth();
  const [apps, setApps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [shouldRedirect, setShouldRedirect] = useState(false);
  const [redirectUrl, setRedirectUrl] = useState(null);

  useEffect(() => {
    fetchLaunchpad();
  }, []);

  const fetchLaunchpad = async () => {
    try {
      const response = await api.get('/launchpad');
      setApps(response.data.apps);
      setShouldRedirect(response.data.should_redirect);
      setRedirectUrl(response.data.redirect_url);
      
      // Auto-redirect if only one app
      if (response.data.should_redirect && response.data.redirect_url) {
        toast.info('Redirecting to your app...');
        setTimeout(() => {
          window.location.href = response.data.redirect_url;
        }, 1500);
      }
    } catch (error) {
      toast.error('Failed to load apps');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
    toast.success('Logged out successfully');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  if (shouldRedirect && redirectUrl) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-white">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600 mb-4" />
        <p className="text-gray-600">Redirecting to your app...</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white" data-testid="launchpad-page">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white/70 backdrop-blur-xl border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-6 md:px-12 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gray-900 rounded-md flex items-center justify-center">
              <Boxes className="w-4 h-4 text-white" />
            </div>
            <span className="font-semibold text-gray-900">Identity Hub</span>
          </div>
          
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="flex items-center gap-2 hover:bg-gray-100" data-testid="user-menu-button">
                <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center">
                  <User className="w-4 h-4 text-gray-600" />
                </div>
                <span className="hidden sm:inline text-sm font-medium text-gray-700">
                  {user?.first_name || user?.email?.split('@')[0]}
                </span>
                <ChevronDown className="w-4 h-4 text-gray-400" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <div className="px-3 py-2">
                <p className="text-sm font-medium text-gray-900">{user?.first_name} {user?.last_name}</p>
                <p className="text-xs text-gray-500">{user?.email}</p>
              </div>
              <DropdownMenuSeparator />
              {isAdmin && (
                <>
                  <DropdownMenuItem onClick={() => navigate('/admin')} data-testid="admin-panel-link">
                    <Settings className="w-4 h-4 mr-2" />
                    Admin Panel
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                </>
              )}
              <DropdownMenuItem onClick={handleLogout} className="text-red-600" data-testid="logout-button">
                <LogOut className="w-4 h-4 mr-2" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-6 md:px-12 py-12">
        <div className="mb-10">
          <span className="text-xs tracking-[0.2em] uppercase font-semibold text-gray-400">
            Your Applications
          </span>
          <h1 className="font-heading text-3xl sm:text-4xl tracking-tighter text-gray-900 mt-2">
            Choose an app to launch
          </h1>
        </div>

        {apps.length === 0 ? (
          <div className="text-center py-16 bg-gray-50 rounded-lg border border-gray-200">
            <Boxes className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No apps assigned</h3>
            <p className="text-gray-500">Contact your administrator to get access to applications.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6" data-testid="apps-grid">
            {apps.map((app, index) => (
              <AppCard key={app.id} app={app} index={index} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
};

export default LaunchpadPage;
