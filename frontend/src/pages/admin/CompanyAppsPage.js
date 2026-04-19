import { useState, useEffect } from 'react';
import api from '@/lib/api';
import { useAdmin } from '@/context/AdminContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { toast } from 'sonner';
import { 
  Package, 
  Plus, 
  Trash2, 
  Building2,
  LayoutGrid,
  Loader2,
  CheckCircle,
  XCircle
} from 'lucide-react';

const CompanyAppsPage = () => {
  const { companies, selectedCompanyId } = useAdmin();
  const [allocations, setAllocations] = useState([]);
  const [apps, setApps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [allocationToDelete, setAllocationToDelete] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  
  const [formData, setFormData] = useState({
    company_id: '',
    app_id: '',
  });

  useEffect(() => {
    fetchAllocations();
    fetchApps();
  }, [selectedCompanyId]);

  const fetchAllocations = async () => {
    try {
      const params = selectedCompanyId ? { company_id: selectedCompanyId } : {};
      const response = await api.get('/company-apps', { params });
      setAllocations(response.data);
    } catch (error) {
      toast.error('Failed to load app allocations');
    } finally {
      setLoading(false);
    }
  };

  const fetchApps = async () => {
    try {
      const response = await api.get('/apps');
      setApps(response.data);
    } catch (error) {
      console.error('Failed to load apps');
    }
  };

  const handleCreate = async () => {
    if (!formData.company_id || !formData.app_id) {
      toast.error('Please select both a company and an app');
      return;
    }

    setSubmitting(true);
    try {
      await api.post('/company-apps', formData);
      setDialogOpen(false);
      setFormData({ company_id: '', app_id: '' });
      fetchAllocations();
      toast.success('App allocated to company');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to allocate app');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!allocationToDelete) return;

    try {
      await api.delete(`/company-apps/${allocationToDelete.id}`);
      fetchAllocations();
      toast.success('App allocation removed');
    } catch (error) {
      toast.error('Failed to remove allocation');
    } finally {
      setDeleteDialogOpen(false);
      setAllocationToDelete(null);
    }
  };

  const toggleActive = async (allocation) => {
    try {
      await api.put(`/company-apps/${allocation.id}`, {
        is_active: !allocation.is_active
      });
      fetchAllocations();
      toast.success(allocation.is_active ? 'App deactivated' : 'App activated');
    } catch (error) {
      toast.error('Failed to update allocation');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div data-testid="company-apps-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">App Allocations</h1>
          <p className="text-gray-500 mt-1">
            Manage which apps are available to each company
          </p>
        </div>
        <Button
          onClick={() => setDialogOpen(true)}
          className="bg-gray-900 hover:bg-gray-800"
          data-testid="allocate-app-button"
        >
          <Plus className="w-4 h-4 mr-2" />
          Allocate App
        </Button>
      </div>

      {/* Info Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6 flex items-start gap-3">
        <Package className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-blue-800">
          <p className="font-medium">About App Allocations</p>
          <p className="mt-1 text-blue-700">
            Companies must have an app allocated before their users can access it.
            Global apps are available to all companies automatically.
          </p>
        </div>
      </div>

      {/* Allocations List */}
      {allocations.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Package className="w-6 h-6 text-gray-400" />
          </div>
          <h3 className="text-lg font-medium text-gray-900 mb-1">No app allocations</h3>
          <p className="text-gray-500 mb-4">Allocate apps to companies to enable access</p>
          <Button onClick={() => setDialogOpen(true)} variant="outline">
            <Plus className="w-4 h-4 mr-2" />
            Allocate first app
          </Button>
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-6 py-3">
                    Company
                  </th>
                  <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-6 py-3">
                    App
                  </th>
                  <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-6 py-3">
                    Status
                  </th>
                  <th className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider px-6 py-3">
                    Allocated
                  </th>
                  <th className="text-right text-xs font-medium text-gray-500 uppercase tracking-wider px-6 py-3">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {allocations.map((allocation) => (
                  <tr key={allocation.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center">
                          <Building2 className="w-4 h-4 text-blue-600" />
                        </div>
                        <span className="font-medium text-gray-900">{allocation.company_name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        {allocation.app_icon ? (
                          <img src={allocation.app_icon} alt="" className="w-8 h-8 rounded-lg object-cover" />
                        ) : (
                          <div className="w-8 h-8 bg-gray-100 rounded-lg flex items-center justify-center">
                            <LayoutGrid className="w-4 h-4 text-gray-600" />
                          </div>
                        )}
                        <span className="text-gray-900">{allocation.app_name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <button
                        onClick={() => toggleActive(allocation)}
                        className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
                          allocation.is_active
                            ? 'bg-green-100 text-green-700 hover:bg-green-200'
                            : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                        }`}
                      >
                        {allocation.is_active ? (
                          <>
                            <CheckCircle className="w-3 h-3" />
                            Active
                          </>
                        ) : (
                          <>
                            <XCircle className="w-3 h-3" />
                            Inactive
                          </>
                        )}
                      </button>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      {new Date(allocation.purchased_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        onClick={() => {
                          setAllocationToDelete(allocation);
                          setDeleteDialogOpen(true);
                        }}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Allocate App Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Allocate App to Company</DialogTitle>
            <DialogDescription>
              Select a company and an app to create an allocation
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Company</Label>
              <Select
                value={formData.company_id}
                onValueChange={(value) => setFormData({ ...formData, company_id: value })}
              >
                <SelectTrigger data-testid="select-company">
                  <SelectValue placeholder="Select a company" />
                </SelectTrigger>
                <SelectContent>
                  {companies.map((company) => (
                    <SelectItem key={company.id} value={company.id}>
                      {company.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            
            <div className="space-y-2">
              <Label>App</Label>
              <Select
                value={formData.app_id}
                onValueChange={(value) => setFormData({ ...formData, app_id: value })}
              >
                <SelectTrigger data-testid="select-app">
                  <SelectValue placeholder="Select an app" />
                </SelectTrigger>
                <SelectContent>
                  {apps.filter(app => !app.is_global).map((app) => (
                    <SelectItem key={app.id} value={app.id}>
                      {app.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-gray-500">Global apps are automatically available to all companies</p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={submitting}
              className="bg-gray-900 hover:bg-gray-800"
            >
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Allocate'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Remove App Allocation</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove "{allocationToDelete?.app_name}" from "{allocationToDelete?.company_name}"? 
              Users in this company will lose access to the app.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} className="bg-red-600 hover:bg-red-700">
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

export default CompanyAppsPage;
