import { useState, useEffect } from 'react';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
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
import { Checkbox } from '@/components/ui/checkbox';
import { toast } from 'sonner';
import { Plus, Pencil, Trash2, Loader2, Users, Shield, LayoutGrid } from 'lucide-react';

const UsersPage = () => {
  const [users, setUsers] = useState([]);
  const [apps, setApps] = useState([]);
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [assignDialogOpen, setAssignDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [editingUser, setEditingUser] = useState(null);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    role: 'user',
  });
  const [saving, setSaving] = useState(false);
  const [userApps, setUserApps] = useState([]);
  const [userRoles, setUserRoles] = useState([]);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [usersRes, appsRes, rolesRes] = await Promise.all([
        api.get('/users'),
        api.get('/apps?include_inactive=true'),
        api.get('/roles'),
      ]);
      setUsers(usersRes.data);
      setApps(appsRes.data);
      setRoles(rolesRes.data);
    } catch (error) {
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const openCreateDialog = () => {
    setEditingUser(null);
    setFormData({ email: '', password: '', first_name: '', last_name: '', role: 'user' });
    setDialogOpen(true);
  };

  const openEditDialog = (user) => {
    setEditingUser(user);
    setFormData({
      email: user.email,
      password: '',
      first_name: user.first_name || '',
      last_name: user.last_name || '',
      role: user.role,
    });
    setDialogOpen(true);
  };

  const openAssignDialog = async (user) => {
    setSelectedUser(user);
    try {
      const response = await api.get(`/users/${user.id}`);
      setUserApps(response.data.apps.map(a => a.id));
      setUserRoles(response.data.roles.map(r => r.id));
      setAssignDialogOpen(true);
    } catch (error) {
      toast.error('Failed to load user details');
    }
  };

  const handleSave = async () => {
    if (!formData.email) {
      toast.error('Email is required');
      return;
    }

    setSaving(true);
    try {
      if (editingUser) {
        const updateData = { ...formData };
        if (!updateData.password) delete updateData.password;
        await api.put(`/users/${editingUser.id}`, updateData);
        toast.success('User updated successfully');
      } else {
        if (!formData.password) {
          toast.error('Password is required for new users');
          setSaving(false);
          return;
        }
        await api.post('/users', formData);
        toast.success('User created successfully');
      }
      setDialogOpen(false);
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save user');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (user) => {
    if (!window.confirm(`Are you sure you want to delete "${user.email}"?`)) return;

    try {
      await api.delete(`/users/${user.id}`);
      toast.success('User deleted successfully');
      fetchData();
    } catch (error) {
      toast.error('Failed to delete user');
    }
  };

  const toggleAppAssignment = async (appId, isAssigned) => {
    try {
      if (isAssigned) {
        await api.post(`/users/${selectedUser.id}/apps?app_id=${appId}&is_granted=true`);
        setUserApps([...userApps, appId]);
      } else {
        await api.delete(`/users/${selectedUser.id}/apps/${appId}`);
        setUserApps(userApps.filter(id => id !== appId));
      }
      toast.success('App assignment updated');
    } catch (error) {
      toast.error('Failed to update app assignment');
    }
  };

  const toggleRoleAssignment = async (roleId, isAssigned) => {
    try {
      if (isAssigned) {
        await api.post(`/users/${selectedUser.id}/roles?role_id=${roleId}`);
        setUserRoles([...userRoles, roleId]);
      } else {
        await api.delete(`/users/${selectedUser.id}/roles/${roleId}`);
        setUserRoles(userRoles.filter(id => id !== roleId));
      }
      toast.success('Role assignment updated');
    } catch (error) {
      toast.error('Failed to update role assignment');
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
    <div data-testid="users-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Users</h1>
          <p className="text-sm text-gray-500 mt-1">Manage user accounts and access</p>
        </div>
        <Button onClick={openCreateDialog} className="bg-gray-900 hover:bg-gray-800" data-testid="add-user-button">
          <Plus className="w-4 h-4 mr-2" />
          Add User
        </Button>
      </div>

      <div className="bg-white border border-gray-200 rounded-md overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-gray-50">
              <TableHead className="font-semibold">User</TableHead>
              <TableHead className="font-semibold">Role</TableHead>
              <TableHead className="font-semibold">Status</TableHead>
              <TableHead className="font-semibold">Last Login</TableHead>
              <TableHead className="font-semibold text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-12 text-gray-500">
                  <Users className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                  No users found
                </TableCell>
              </TableRow>
            ) : (
              users.map((user, index) => (
                <TableRow key={user.id} className={index % 2 === 1 ? 'bg-gray-50/50' : ''}>
                  <TableCell>
                    <div>
                      <div className="font-medium">{user.first_name} {user.last_name}</div>
                      <div className="text-sm text-gray-500">{user.email}</div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant={user.role === 'admin' ? 'default' : 'secondary'}>
                      {user.role}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                      user.status === 'active' ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-600'
                    }`}>
                      {user.status}
                    </span>
                  </TableCell>
                  <TableCell className="text-sm text-gray-500">
                    {user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never'}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openAssignDialog(user)}
                      data-testid={`assign-user-${user.id}`}
                    >
                      <Shield className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEditDialog(user)}
                      data-testid={`edit-user-${user.id}`}
                    >
                      <Pencil className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(user)}
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      data-testid={`delete-user-${user.id}`}
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

      {/* Create/Edit User Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editingUser ? 'Edit User' : 'Add New User'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="first_name">First Name</Label>
                <Input
                  id="first_name"
                  value={formData.first_name}
                  onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                  data-testid="user-first-name-input"
                />
              </div>
              <div>
                <Label htmlFor="last_name">Last Name</Label>
                <Input
                  id="last_name"
                  value={formData.last_name}
                  onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                  data-testid="user-last-name-input"
                />
              </div>
            </div>
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                data-testid="user-email-input"
              />
            </div>
            <div>
              <Label htmlFor="password">
                Password {editingUser && <span className="text-gray-400">(leave blank to keep current)</span>}
              </Label>
              <Input
                id="password"
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                data-testid="user-password-input"
              />
            </div>
            <div>
              <Label htmlFor="role">Role</Label>
              <Select
                value={formData.role}
                onValueChange={(value) => setFormData({ ...formData, role: value })}
              >
                <SelectTrigger data-testid="user-role-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="user">User</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving} className="bg-gray-900 hover:bg-gray-800" data-testid="save-user-button">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Assign Apps/Roles Dialog */}
      <Dialog open={assignDialogOpen} onOpenChange={setAssignDialogOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Manage Access: {selectedUser?.email}</DialogTitle>
          </DialogHeader>
          <div className="space-y-6 py-4">
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                <Shield className="w-4 h-4" /> Roles
              </h3>
              <div className="space-y-2">
                {roles.length === 0 ? (
                  <p className="text-sm text-gray-500">No roles available</p>
                ) : (
                  roles.map((role) => (
                    <div key={role.id} className="flex items-center gap-3 p-2 rounded hover:bg-gray-50">
                      <Checkbox
                        id={`role-${role.id}`}
                        checked={userRoles.includes(role.id)}
                        onCheckedChange={(checked) => toggleRoleAssignment(role.id, checked)}
                      />
                      <label htmlFor={`role-${role.id}`} className="text-sm cursor-pointer flex-1">
                        <span className="font-medium">{role.name}</span>
                        {role.description && (
                          <span className="text-gray-500 ml-2">- {role.description}</span>
                        )}
                      </label>
                    </div>
                  ))
                )}
              </div>
            </div>
            
            <div>
              <h3 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                <LayoutGrid className="w-4 h-4" /> Direct App Access (Overrides)
              </h3>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {apps.length === 0 ? (
                  <p className="text-sm text-gray-500">No apps available</p>
                ) : (
                  apps.map((app) => (
                    <div key={app.id} className="flex items-center gap-3 p-2 rounded hover:bg-gray-50">
                      <Checkbox
                        id={`app-${app.id}`}
                        checked={userApps.includes(app.id)}
                        onCheckedChange={(checked) => toggleAppAssignment(app.id, checked)}
                      />
                      <label htmlFor={`app-${app.id}`} className="text-sm cursor-pointer flex-1">
                        <span className="font-medium">{app.name}</span>
                        {!app.is_active && <Badge variant="secondary" className="ml-2">Inactive</Badge>}
                      </label>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAssignDialogOpen(false)}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default UsersPage;
