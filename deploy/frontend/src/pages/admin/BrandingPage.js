import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { Palette, Save, Loader2, Image, Building2 } from 'lucide-react';

const BrandingPage = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [branding, setBranding] = useState({
    logo_url: '',
    primary_color: '#1f2937',
    secondary_color: '#3b82f6',
  });
  const [companyName, setCompanyName] = useState('');

  useEffect(() => {
    fetchBranding();
  }, []);

  const fetchBranding = async () => {
    try {
      if (user?.company_id) {
        const response = await api.get(`/companies/${user.company_id}/branding`);
        setBranding({
          logo_url: response.data.logo_url || '',
          primary_color: response.data.primary_color || '#1f2937',
          secondary_color: response.data.secondary_color || '#3b82f6',
        });
        setCompanyName(response.data.name || '');
      }
    } catch (error) {
      console.error('Failed to fetch branding');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.put('/companies/my/branding', {
        logo_url: branding.logo_url || null,
        primary_color: branding.primary_color,
        secondary_color: branding.secondary_color,
      });
      toast.success('Branding updated successfully');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to update branding');
    } finally {
      setSaving(false);
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
    <div data-testid="branding-page" className="max-w-2xl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">Company Branding</h1>
        <p className="text-gray-500 mt-1">
          Customize your company's appearance in the Identity Hub
        </p>
      </div>

      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-6">
        {/* Company Name (read-only) */}
        <div className="flex items-center gap-4 pb-6 border-b border-gray-200">
          <div className="w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center">
            <Building2 className="w-6 h-6 text-gray-600" />
          </div>
          <div>
            <p className="text-sm text-gray-500">Company</p>
            <p className="text-lg font-medium text-gray-900">{companyName}</p>
          </div>
        </div>

        {/* Logo URL */}
        <div className="space-y-2">
          <Label htmlFor="logo_url">Logo URL</Label>
          <div className="flex gap-4">
            <Input
              id="logo_url"
              value={branding.logo_url}
              onChange={(e) => setBranding({ ...branding, logo_url: e.target.value })}
              placeholder="https://example.com/logo.png"
              className="flex-1"
              data-testid="logo-url-input"
            />
            {branding.logo_url && (
              <div className="w-12 h-12 bg-gray-100 rounded-lg overflow-hidden flex-shrink-0">
                <img 
                  src={branding.logo_url} 
                  alt="Logo preview" 
                  className="w-full h-full object-contain"
                  onError={(e) => e.target.style.display = 'none'}
                />
              </div>
            )}
          </div>
          <p className="text-xs text-gray-500">Enter a URL to your company logo (recommended size: 200x200px)</p>
        </div>

        {/* Colors */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="primary_color">Primary Color</Label>
            <div className="flex gap-2">
              <input
                type="color"
                id="primary_color"
                value={branding.primary_color}
                onChange={(e) => setBranding({ ...branding, primary_color: e.target.value })}
                className="w-12 h-10 rounded border border-gray-200 cursor-pointer"
                data-testid="primary-color-input"
              />
              <Input
                value={branding.primary_color}
                onChange={(e) => setBranding({ ...branding, primary_color: e.target.value })}
                placeholder="#1f2937"
                className="flex-1"
              />
            </div>
          </div>
          
          <div className="space-y-2">
            <Label htmlFor="secondary_color">Secondary Color</Label>
            <div className="flex gap-2">
              <input
                type="color"
                id="secondary_color"
                value={branding.secondary_color}
                onChange={(e) => setBranding({ ...branding, secondary_color: e.target.value })}
                className="w-12 h-10 rounded border border-gray-200 cursor-pointer"
                data-testid="secondary-color-input"
              />
              <Input
                value={branding.secondary_color}
                onChange={(e) => setBranding({ ...branding, secondary_color: e.target.value })}
                placeholder="#3b82f6"
                className="flex-1"
              />
            </div>
          </div>
        </div>

        {/* Preview */}
        <div className="pt-6 border-t border-gray-200">
          <Label className="mb-3 block">Preview</Label>
          <div 
            className="rounded-lg p-6 flex items-center gap-4"
            style={{ backgroundColor: branding.primary_color }}
          >
            {branding.logo_url ? (
              <img 
                src={branding.logo_url} 
                alt="Logo" 
                className="w-12 h-12 rounded-lg object-contain bg-white"
              />
            ) : (
              <div className="w-12 h-12 bg-white/20 rounded-lg flex items-center justify-center">
                <Image className="w-6 h-6 text-white/60" />
              </div>
            )}
            <div>
              <p className="text-white font-semibold">{companyName}</p>
              <p className="text-white/80 text-sm">Identity Hub</p>
            </div>
            <div className="ml-auto">
              <div 
                className="px-4 py-2 rounded-md text-white text-sm font-medium"
                style={{ backgroundColor: branding.secondary_color }}
              >
                Sample Button
              </div>
            </div>
          </div>
        </div>

        {/* Save Button */}
        <div className="pt-4 flex justify-end">
          <Button
            onClick={handleSave}
            disabled={saving}
            className="bg-gray-900 hover:bg-gray-800"
            data-testid="save-branding-button"
          >
            {saving ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <Save className="w-4 h-4 mr-2" />
            )}
            Save Changes
          </Button>
        </div>
      </div>
    </div>
  );
};

export default BrandingPage;
