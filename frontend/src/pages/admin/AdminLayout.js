import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import { AdminProvider, useAdmin } from '@/context/AdminContext';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import {
  Boxes,
  LayoutGrid,
  Users,
  Shield,
  UserCircle,
  Settings,
  LogOut,
  User,
  ChevronDown,
  ArrowLeft,
  Building2,
  Key,
  Palette,
  Package,
  Globe,
} from 'lucide-react';

const AdminLayoutContent = () => {
  const navigate = useNavigate();
  const { user, logout, isSysadmin } = useAuth();
  const { companies, selectedCompanyId, selectCompany, clearCompanyFilter } = useAdmin();
  
  const isCompanyAdmin = user?.role === 'company_admin';

  // Different nav items based on role
  const sysadminNavItems = [
    { path: '/admin/companies', label: 'Companies', icon: Building2 },
    { path: '/admin/company-apps', label: 'App Allocations', icon: Package },
    { path: '/admin/apps', label: 'Apps Catalog', icon: LayoutGrid },
    { path: '/admin/users', label: 'Users', icon: Users },
    { path: '/admin/roles', label: 'Roles', icon: Shield },
    { path: '/admin/employees', label: 'Employees', icon: UserCircle },
    { path: '/admin/api-keys', label: 'API Keys', icon: Key },
    { path: '/admin/settings', label: 'Settings', icon: Settings },
  ];

  const companyAdminNavItems = [
    { path: '/admin/users', label: 'Users', icon: Users },
    { path: '/admin/employees', label: 'Employees', icon: UserCircle },
    { path: '/admin/branding', label: 'Branding', icon: Palette },
    { path: '/admin/settings', label: 'Settings', icon: Settings },
  ];

  const navItems = isSysadmin ? sysadminNavItems : companyAdminNavItems;

  const handleLogout = () => {
    logout();
    navigate('/login');
    toast.success('Logged out successfully');
  };

  return (
    <div className="min-h-screen bg-gray-50" data-testid="admin-layout">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-white border-b border-gray-200">
        <div className="px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/launchpad')}
              className="flex items-center gap-2 text-gray-500 hover:text-gray-900 transition-colors"
              data-testid="back-to-launchpad"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="text-sm">Back to Launchpad</span>
            </button>
            <div className="h-6 w-px bg-gray-200"></div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gray-900 rounded-md flex items-center justify-center">
                <Boxes className="w-4 h-4 text-white" />
              </div>
              <span className="font-semibold text-gray-900">Admin Panel</span>
            </div>
            
            {/* Company Switcher for Sysadmin */}
            {isSysadmin && companies.length > 0 && (
              <>
                <div className="h-6 w-px bg-gray-200"></div>
                <div className="flex items-center gap-2">
                  <Globe className="w-4 h-4 text-gray-400" />
                  <Select
                    value={selectedCompanyId || 'all'}
                    onValueChange={(value) => {
                      if (value === 'all') {
                        clearCompanyFilter();
                      } else {
                        selectCompany(value);
                      }
                    }}
                  >
                    <SelectTrigger className="w-[200px] h-9 text-sm" data-testid="company-switcher">
                      <SelectValue placeholder="All Companies" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">
                        <span className="flex items-center gap-2">
                          <Globe className="w-4 h-4" />
                          All Companies
                        </span>
                      </SelectItem>
                      {companies.map((company) => (
                        <SelectItem key={company.id} value={company.id}>
                          <span className="flex items-center gap-2">
                            <Building2 className="w-4 h-4" />
                            {company.name}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}
          </div>
          
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="flex items-center gap-2 hover:bg-gray-100" data-testid="admin-user-menu">
                <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center">
                  <User className="w-4 h-4 text-gray-600" />
                </div>
                <div className="hidden sm:block text-left">
                  <span className="text-sm font-medium text-gray-700 block">
                    {user?.first_name || user?.email?.split('@')[0]}
                  </span>
                  <span className="text-xs text-gray-500">
                    {isSysadmin ? 'System Admin' : 'Company Admin'}
                  </span>
                </div>
                <ChevronDown className="w-4 h-4 text-gray-400" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <div className="px-3 py-2">
                <p className="text-sm font-medium text-gray-900">{user?.first_name} {user?.last_name}</p>
                <p className="text-xs text-gray-500">{user?.email}</p>
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={handleLogout} className="text-red-600" data-testid="admin-logout">
                <LogOut className="w-4 h-4 mr-2" />
                Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        
        {/* Navigation tabs */}
        <nav className="px-6 flex gap-1 overflow-x-auto">
          {navItems.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                `flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                  isActive
                    ? 'border-gray-900 text-gray-900'
                    : 'border-transparent text-gray-500 hover:text-gray-900 hover:border-gray-300'
                }`
              }
              data-testid={`nav-${label.toLowerCase().replace(' ', '-')}`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>
      </header>

      {/* Main content */}
      <main className="p-6 md:p-8">
        <Outlet />
      </main>
    </div>
  );
};

const AdminLayout = () => {
  return (
    <AdminProvider>
      <AdminLayoutContent />
    </AdminProvider>
  );
};

export default AdminLayout;
