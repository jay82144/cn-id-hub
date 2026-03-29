import { useState, useEffect } from 'react';
import api from '@/lib/api';
import { useAuth } from '@/context/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
import { toast } from 'sonner';
import { Plus, Pencil, Trash2, Loader2, Building2, Image } from 'lucide-react';

const CompaniesPage = () => {
  const { user } = useAuth();
  const [companies, setCompanies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingCompany, setEditingCompany] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    slug: '',
    logo_url: '',
    primary_color: '#0A0A0A',
    secondary_color: '#0047FF',
  });
  const [saving, setSaving] = useState(false);

  // Only sysadmins can access this page
  const isSysadmin = user?.role === 'sysadmin';

  useEffect(() => {
    if (isSysadmin) {
      fetchCompanies();
    }
  }, [isSysadmin]);

  const fetchCompanies = async () => {
    try {
      const response = await api.get('/companies');
      setCompanies(response.data);
    } catch (error) {
      toast.error('Failed to load companies');
    } finally {
      setLoading(false);
    }
  };

  const openCreateDialog = () => {
    setEditingCompany(null);
    setFormData({
      name: '',
      slug: '',
      logo_url: '',
      primary_color: '#0A0A0A',
      secondary_color: '#0047FF',
    });
    setDialogOpen(true);
  };

  const openEditDialog = (company) => {
    setEditingCompany(company);
    setFormData({
      name: company.name,
      slug: company.slug,
      logo_url: company.logo_url || '',
      primary_color: company.primary_color,
      secondary_color: company.secondary_color,
    });
    setDialogOpen(true);
  };

  const generateSlug = (name) => {
    return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  };

  const handleNameChange = (e) => {
    const name = e.target.value;
    setFormData({
      ...formData,
      name,
      slug: editingCompany ? formData.slug : generateSlug(name),
    });
  };

  const handleSave = async () => {
    if (!formData.name || !formData.slug) {
      toast.error('Name and slug are required');
      return;
    }

    setSaving(true);
    try {
      if (editingCompany) {
        await api.put(`/companies/${editingCompany.id}`, {
          name: formData.name,
          logo_url: formData.logo_url || null,
          primary_color: formData.primary_color,
          secondary_color: formData.secondary_color,
        });
        toast.success('Company updated successfully');
      } else {
        await api.post('/companies', formData);
        toast.success('Company created successfully');
      }
      setDialogOpen(false);
      fetchCompanies();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to save company');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (company) => {
    if (!window.confirm(`Are you sure you want to delete "${company.name}"? This will also delete all users, employees, and data for this company.`)) return;

    try {
      await api.delete(`/companies/${company.id}`);
      toast.success('Company deleted successfully');
      fetchCompanies();
    } catch (error) {
      toast.error('Failed to delete company');
    }
  };

  if (!isSysadmin) {
    return (
      <div className="text-center py-12 text-gray-500">
        <Building2 className="w-12 h-12 mx-auto mb-4 text-gray-300" />
        <p>Only system administrators can manage companies.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div data-testid="companies-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Companies</h1>
          <p className="text-sm text-gray-500 mt-1">Manage organizations in the system</p>
        </div>
        <Button onClick={openCreateDialog} className="bg-gray-900 hover:bg-gray-800" data-testid="add-company-button">
          <Plus className="w-4 h-4 mr-2" />
          Add Company
        </Button>
      </div>

      <div className="bg-white border border-gray-200 rounded-md overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="bg-gray-50">
              <TableHead className="font-semibold">Company</TableHead>
              <TableHead className="font-semibold">Slug</TableHead>
              <TableHead className="font-semibold">Branding</TableHead>
              <TableHead className="font-semibold">Status</TableHead>
              <TableHead className="font-semibold text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {companies.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="text-center py-12 text-gray-500">
                  <Building2 className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                  No companies yet
                </TableCell>
              </TableRow>
            ) : (
              companies.map((company, index) => (
                <TableRow key={company.id} className={index % 2 === 1 ? 'bg-gray-50/50' : ''}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      {company.logo_url ? (
                        <img src={company.logo_url} alt="" className="w-8 h-8 rounded object-cover" />
                      ) : (
                        <div className="w-8 h-8 rounded bg-gray-100 flex items-center justify-center">
                          <Building2 className="w-4 h-4 text-gray-400" />
                        </div>
                      )}
                      <span className="font-medium">{company.name}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-gray-500 font-mono text-sm">{company.slug}</TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div
                        className="w-6 h-6 rounded border"
                        style={{ backgroundColor: company.primary_color }}
                        title="Primary color"
                      />
                      <div
                        className="w-6 h-6 rounded border"
                        style={{ backgroundColor: company.secondary_color }}
                        title="Secondary color"
                      />
                    </div>
                  </TableCell>
                  <TableCell>
                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                      company.is_active ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-600'
                    }`}>
                      {company.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openEditDialog(company)}
                      data-testid={`edit-company-${company.id}`}
                    >
                      <Pencil className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDelete(company)}
                      className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      data-testid={`delete-company-${company.id}`}
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
            <DialogTitle>{editingCompany ? 'Edit Company' : 'Add New Company'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="name">Company Name</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={handleNameChange}
                placeholder="Acme Corporation"
                data-testid="company-name-input"
              />
            </div>
            <div>
              <Label htmlFor="slug">Slug (URL identifier)</Label>
              <Input
                id="slug"
                value={formData.slug}
                onChange={(e) => setFormData({ ...formData, slug: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') })}
                placeholder="acme-corp"
                disabled={!!editingCompany}
                className={editingCompany ? 'bg-gray-50' : ''}
                data-testid="company-slug-input"
              />
            </div>
            <div>
              <Label htmlFor="logo_url">Logo URL (optional)</Label>
              <Input
                id="logo_url"
                value={formData.logo_url}
                onChange={(e) => setFormData({ ...formData, logo_url: e.target.value })}
                placeholder="https://example.com/logo.png"
                data-testid="company-logo-input"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="primary_color">Primary Color</Label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    id="primary_color"
                    value={formData.primary_color}
                    onChange={(e) => setFormData({ ...formData, primary_color: e.target.value })}
                    className="w-10 h-10 rounded border cursor-pointer"
                  />
                  <Input
                    value={formData.primary_color}
                    onChange={(e) => setFormData({ ...formData, primary_color: e.target.value })}
                    className="font-mono"
                    data-testid="company-primary-color-input"
                  />
                </div>
              </div>
              <div>
                <Label htmlFor="secondary_color">Secondary Color</Label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    id="secondary_color"
                    value={formData.secondary_color}
                    onChange={(e) => setFormData({ ...formData, secondary_color: e.target.value })}
                    className="w-10 h-10 rounded border cursor-pointer"
                  />
                  <Input
                    value={formData.secondary_color}
                    onChange={(e) => setFormData({ ...formData, secondary_color: e.target.value })}
                    className="font-mono"
                    data-testid="company-secondary-color-input"
                  />
                </div>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving} className="bg-gray-900 hover:bg-gray-800" data-testid="save-company-button">
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default CompaniesPage;
