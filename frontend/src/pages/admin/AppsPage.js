import { useState, useEffect } from 'react';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import { Plus, Pencil, Trash2, Loader2, ExternalLink, LayoutGrid } from 'lucide-react';

const iconOptions = [
  'LayoutDashboard', 'Users', 'Shield', 'FileText', 'Settings',
  'Boxes', 'ClipboardCheck', 'BarChart3', 'Calendar', 'MessageSquare', 'Briefcase'
];

const AppsPage = () => {
  const [apps, setApps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingApp, setEditingApp] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    url: '',
    icon: 'LayoutDashboard',
    description: '',
    is_active: true,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchApps();
  }, []);

  const fetchApps = async () => {
    try {
      const response = await api.get('/apps?include_inactive=true');
      setApps(response.data);
    } catch (error) {
      toast.error('Failed to load apps');
    } finally {
      setLoading(false);
    }
  };

  const openCreateDialog = () => {
    setEditingApp(null);
    setFormData({ name: '', url: '', icon: 'LayoutDashboard', description: '', is_active: true });
    setDialogOpen(true);
  };

  const openEditDialog = (app) => {
    setEditingApp(app);
    setFormData({
      name: app.name,
      url: app.url,
      icon: app.icon || 'LayoutDashboard',
      description: app.description || '',
      is_active: app.is_active,
    });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!formData.name || !formData.url) {
      toast.error('Name and URL are required');
      return;
    }

    setSaving(true);
    try {
      if (editingApp) {
        await api.put(`/apps/${editingApp.id}`, formData);
        toast.success('App updated successfully');
      } else {
        await api.post('/apps', formData);
        toast.success('App created successfully');
      }
      setDialogOpen(false);
      fetchApps();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save app');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (app) => {
    if (!window.confirm(`Are you sure you want to delete "${app.name}"?`)) return;

    try {
      await api.delete(`/apps/${app.id}`);
      toast.success('App deleted successfully');
      fetchApps();
    } catch (error) {
      toast.error('Failed to delete app');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div data-testid="apps-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Apps</h1>
          <p className="text-sm text-gray-500 mt-1">Manage registered applications</p>
        </div>
        <Button onClick={openCreateDialog} className="bg-gray-900 hover:bg-gray-800" data-testid="add-app-button">
          <Plus className="w-4 h-4 mr-2" />
          Add App
        </Button>
      </div>

      <div className="bg-white border border-gray-200 rounded-md overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-gray-50">
              <TableHead className="font-semibold">Name</TableHead>
              <TableHead className="font-semibold">URL</TableHead>
              <TableHead className="font-semibold">Status</TableHead>
              <TableHead className="font-semibold text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {apps.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="text-center py-12 text-gray-500">
                  <LayoutGrid className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                  No apps registered yet
                </TableCell>
              </TableRow>
            ) : (
              apps.map((app, index) => (
                <TableRow key={app.id} className={index % 2 === 1 ? 'bg-gray-50/50' : ''}>
                  <TableCell className="font-medium">{app.name}</TableCell>
                  <TableCell>
                    <a
                      href={app.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-blue-600 hover:text-blue-800"
                    >
                      {app.url.length > 40 ? `${app.url.substring(0, 40)}...` : app.url}
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </TableCell>
                  <TableCell>
                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                      app.is_active ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-600'
                    }`}>
                      {app.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEditDialog(app)}
                      data-testid={`edit-app-${app.id}`}
                    >
                      <Pencil className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(app)}
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      data-testid={`delete-app-${app.id}`}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editingApp ? 'Edit App' : 'Add New App'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., WorkAssess"
                data-testid="app-name-input"
              />
            </div>
            <div>
              <Label htmlFor="url">URL</Label>
              <Input
                id="url"
                value={formData.url}
                onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                placeholder="https://workassess.company.com"
                data-testid="app-url-input"
              />
            </div>
            <div>
              <Label htmlFor="icon">Icon</Label>
              <Select
                value={formData.icon}
                onValueChange={(value) => setFormData({ ...formData, icon: value })}
              >
                <SelectTrigger data-testid="app-icon-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {iconOptions.map((icon) => (
                    <SelectItem key={icon} value={icon}>{icon}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Brief description of the app"
                rows={3}
                data-testid="app-description-input"
              />
            </div>
            <div className="flex items-center justify-between">
              <Label htmlFor="is_active">Active</Label>
              <Switch
                id="is_active"
                checked={formData.is_active}
                onCheckedChange={(checked) => setFormData({ ...formData, is_active: checked })}
                data-testid="app-active-switch"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving} className="bg-gray-900 hover:bg-gray-800" data-testid="save-app-button">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AppsPage;
