import { useState, useEffect } from 'react';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Checkbox } from '@/components/ui/checkbox';
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
import { toast } from 'sonner';
import { Plus, Pencil, Trash2, Loader2, Shield, LayoutGrid } from 'lucide-react';

const RolesPage = () => {
  const [roles, setRoles] = useState([]);
  const [apps, setApps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [appsDialogOpen, setAppsDialogOpen] = useState(false);
  const [editingRole, setEditingRole] = useState(null);
  const [selectedRole, setSelectedRole] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
  });
  const [roleApps, setRoleApps] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [rolesRes, appsRes] = await Promise.all([
        api.get('/roles'),
        api.get('/apps?include_inactive=true'),
      ]);
      setRoles(rolesRes.data);
      setApps(appsRes.data);
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const openCreateDialog = () => {
    setEditingRole(null);
    setFormData({ name: '', description: '' });
    setDialogOpen(true);
  };

  const openEditDialog = (role) => {
    setEditingRole(role);
    setFormData({
      name: role.name,
      description: role.description || '',
    });
    setDialogOpen(true);
  };

  const openAppsDialog = async (role) => {
    setSelectedRole(role);
    try {
      const response = await api.get(`/roles/${role.id}`);
      setRoleApps(response.data.apps.map(a => a.id));
      setAppsDialogOpen(true);
    } catch (error) {
      toast.error('Failed to load role details');
    }
  };

  const handleSave = async () => {
    if (!formData.name) {
      toast.error('Name is required');
      return;
    }

    setSaving(true);
    try {
      if (editingRole) {
        await api.put(`/roles/${editingRole.id}`, formData);
        toast.success('Role updated successfully');
      } else {
        await api.post('/roles', formData);
        toast.success('Role created successfully');
      }
      setDialogOpen(false);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save role');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (role) => {
    if (!window.confirm(`Are you sure you want to delete "${role.name}"?`)) return;

    try {
      await api.delete(`/roles/${role.id}`);
      toast.success('Role deleted successfully');
      fetchData();
    } catch (error) {
      toast.error('Failed to delete role');
    }
  };

  const toggleAppAssignment = async (appId, isAssigned) => {
    try {
      if (isAssigned) {
        await api.post(`/roles/${selectedRole.id}/apps?app_id=${appId}`);
        setRoleApps([...roleApps, appId]);
      } else {
        await api.delete(`/roles/${selectedRole.id}/apps/${appId}`);
        setRoleApps(roleApps.filter(id => id !== appId));
      }
      toast.success('App assignment updated');
    } catch (error) {
      toast.error('Failed to update app assignment');
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
    <div data-testid="roles-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Roles</h1>
          <p className="text-sm text-gray-500 mt-1">Manage roles and their default app access</p>
        </div>
        <Button onClick={openCreateDialog} className="bg-gray-900 hover:bg-gray-800" data-testid="add-role-button">
          <Plus className="w-4 h-4 mr-2" />
          Add Role
        </Button>
      </div>

      <div className="bg-white border border-gray-200 rounded-md overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-gray-50">
              <TableHead className="font-semibold">Name</TableHead>
              <TableHead className="font-semibold">Description</TableHead>
              <TableHead className="font-semibold">Created</TableHead>
              <TableHead className="font-semibold text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {roles.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="text-center py-12 text-gray-500">
                  <Shield className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                  No roles created yet
                </TableCell>
              </TableRow>
            ) : (
              roles.map((role, index) => (
                <TableRow key={role.id} className={index % 2 === 1 ? 'bg-gray-50/50' : ''}>
                  <TableCell className="font-medium">{role.name}</TableCell>
                  <TableCell className="text-gray-500">{role.description || '-'}</TableCell>
                  <TableCell className="text-sm text-gray-500">
                    {new Date(role.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openAppsDialog(role)}
                      data-testid={`manage-role-apps-${role.id}`}
                    >
                      <LayoutGrid className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEditDialog(role)}
                      data-testid={`edit-role-${role.id}`}
                    >
                      <Pencil className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(role)}
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      data-testid={`delete-role-${role.id}`}
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

      {/* Create/Edit Role Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editingRole ? 'Edit Role' : 'Add New Role'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="e.g., Safety Team"
                data-testid="role-name-input"
              />
            </div>
            <div>
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                placeholder="Brief description of this role"
                rows={3}
                data-testid="role-description-input"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving} className="bg-gray-900 hover:bg-gray-800" data-testid="save-role-button">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Manage Role Apps Dialog */}
      <Dialog open={appsDialogOpen} onOpenChange={setAppsDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Default Apps for: {selectedRole?.name}</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p className="text-sm text-gray-500 mb-4">
              Users with this role will automatically have access to the selected apps.
            </p>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {apps.length === 0 ? (
                <p className="text-sm text-gray-500">No apps available</p>
              ) : (
                apps.map((app) => (
                  <div key={app.id} className="flex items-center gap-3 p-2 rounded hover:bg-gray-50">
                    <Checkbox
                      id={`role-app-${app.id}`}
                      checked={roleApps.includes(app.id)}
                      onCheckedChange={(checked) => toggleAppAssignment(app.id, checked)}
                    />
                    <label htmlFor={`role-app-${app.id}`} className="text-sm cursor-pointer flex-1">
                      <span className="font-medium">{app.name}</span>
                      {app.description && (
                        <span className="text-gray-500 block text-xs">{app.description}</span>
                      )}
                    </label>
                  </div>
                ))
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAppsDialogOpen(false)}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default RolesPage;
