import { useState, useEffect } from 'react';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { toast } from 'sonner';
import { Loader2, RefreshCw, ExternalLink, AlertCircle, CheckCircle2, XCircle } from 'lucide-react';

const SettingsPage = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [testing, setTesting] = useState(false);
  const [syncResult, setSyncResult] = useState(null);
  const [testResult, setTestResult] = useState(null);
  
  const [bambooSettings, setBambooSettings] = useState({
    api_key: '',
    subdomain: '',
    enabled: false,
  });
  
  const [azureSettings, setAzureSettings] = useState({
    tenant_id: '',
    client_id: '',
    client_secret: '',
    enabled: false,
  });

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const [bambooRes, azureRes] = await Promise.all([
        api.get('/settings/bamboohr'),
        api.get('/settings/azure-sso'),
      ]);
      setBambooSettings({
        api_key: bambooRes.data.api_key || '',
        subdomain: bambooRes.data.subdomain || '',
        enabled: bambooRes.data.enabled || false,
      });
      setAzureSettings({
        tenant_id: azureRes.data.tenant_id || '',
        client_id: azureRes.data.client_id || '',
        client_secret: azureRes.data.client_secret || '',
        enabled: azureRes.data.enabled || false,
      });
    } catch (error) {
      toast.error('Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  const saveBambooSettings = async () => {
    setSaving(true);
    try {
      await api.put('/settings/bamboohr', bambooSettings);
      toast.success('BambooHR settings saved');
      setTestResult(null); // Clear test result after save
    } catch (error) {
      toast.error('Failed to save BambooHR settings');
    } finally {
      setSaving(false);
    }
  };

  const testBambooConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const response = await api.post('/settings/bamboohr/test');
      setTestResult(response.data);
      if (response.data.success) {
        toast.success(`Connection successful! Found ${response.data.total_employees || 0} employees`);
      } else {
        toast.error(response.data.message || 'Connection failed');
      }
    } catch (error) {
      const msg = error.response?.data?.detail || error.response?.data?.message || 'Connection test failed';
      setTestResult({ success: false, message: msg });
      toast.error(msg);
    } finally {
      setTesting(false);
    }
  };

  const saveAzureSettings = async () => {
    setSaving(true);
    try {
      await api.put('/settings/azure-sso', azureSettings);
      toast.success('Azure SSO settings saved');
    } catch (error) {
      toast.error('Failed to save Azure SSO settings');
    } finally {
      setSaving(false);
    }
  };

  const triggerBambooSync = async () => {
    setSyncing(true);
    setSyncResult(null);
    try {
      const response = await api.post('/settings/bamboohr/sync');
      setSyncResult(response.data);
      if (response.data.success) {
        toast.success(`Sync completed! ${response.data.created} created, ${response.data.updated} updated`);
      } else {
        toast.error(response.data.message || 'Sync failed');
      }
    } catch (error) {
      const msg = error.response?.data?.detail || 'Failed to trigger sync';
      setSyncResult({ success: false, message: msg });
      toast.error(msg);
    } finally {
      setSyncing(false);
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
    <div className="max-w-3xl" data-testid="settings-page">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500 mt-1">Configure integrations and system settings</p>
      </div>

      {/* BambooHR Settings */}
      <Card className="mb-6">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">BambooHR Integration</CardTitle>
              <CardDescription>Sync employee data from BambooHR</CardDescription>
            </div>
            <Switch
              checked={bambooSettings.enabled}
              onCheckedChange={(checked) => setBambooSettings({ ...bambooSettings, enabled: checked })}
              data-testid="bamboo-sync-enabled-switch"
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <Label htmlFor="bamboo_subdomain">Subdomain</Label>
            <Input
              id="bamboo_subdomain"
              value={bambooSettings.subdomain}
              onChange={(e) => setBambooSettings({ ...bambooSettings, subdomain: e.target.value })}
              placeholder="yourcompany"
              className="max-w-md"
              data-testid="bamboo-subdomain-input"
            />
            <p className="text-xs text-gray-500 mt-1">Your BambooHR subdomain (e.g., yourcompany from yourcompany.bamboohr.com)</p>
          </div>
          
          <div>
            <Label htmlFor="bamboo_api_key">API Key</Label>
            <Input
              id="bamboo_api_key"
              type="password"
              value={bambooSettings.api_key}
              onChange={(e) => setBambooSettings({ ...bambooSettings, api_key: e.target.value })}
              placeholder="Enter your BambooHR API key"
              className="max-w-md"
              data-testid="bamboo-api-key-input"
            />
            <p className="text-xs text-gray-500 mt-1">
              Get your API key from BambooHR: Account &gt; API Keys
            </p>
          </div>

          {/* Test Result */}
          {testResult && (
            <div className={`p-3 rounded-md flex items-start gap-2 ${testResult.success ? 'bg-green-50 border border-green-200' : 'bg-red-50 border border-red-200'}`}>
              {testResult.success ? (
                <CheckCircle2 className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
              ) : (
                <XCircle className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" />
              )}
              <div>
                <p className={`text-sm ${testResult.success ? 'text-green-800' : 'text-red-800'}`}>
                  {testResult.message}
                </p>
                {testResult.total_employees !== undefined && (
                  <p className="text-xs text-green-600 mt-1">
                    Total employees: {testResult.total_employees}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Sync Result */}
          {syncResult && (
            <div className={`p-3 rounded-md ${syncResult.success ? 'bg-blue-50 border border-blue-200' : 'bg-red-50 border border-red-200'}`}>
              <div className="flex items-start gap-2">
                {syncResult.success ? (
                  <CheckCircle2 className="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0" />
                ) : (
                  <XCircle className="w-4 h-4 text-red-600 mt-0.5 flex-shrink-0" />
                )}
                <div>
                  <p className={`text-sm ${syncResult.success ? 'text-blue-800' : 'text-red-800'}`}>
                    {syncResult.message}
                  </p>
                  {syncResult.success && (
                    <div className="text-xs text-blue-600 mt-1 space-y-0.5">
                      <p>Fetched: {syncResult.total_fetched} employees</p>
                      <p>Created: {syncResult.created} | Updated: {syncResult.updated}</p>
                      {syncResult.sync_time && <p>Sync time: {new Date(syncResult.sync_time).toLocaleString()}</p>}
                    </div>
                  )}
                  {syncResult.errors && syncResult.errors.length > 0 && (
                    <div className="text-xs text-red-600 mt-2">
                      <p className="font-medium">Errors:</p>
                      {syncResult.errors.map((err, i) => <p key={i}>• {err}</p>)}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          <div className="flex items-center gap-3 pt-2">
            <Button onClick={saveBambooSettings} disabled={saving} className="bg-gray-900 hover:bg-gray-800" data-testid="save-bamboo-settings-button">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Save Settings
            </Button>
            <Button
              variant="outline"
              onClick={testBambooConnection}
              disabled={testing || !bambooSettings.api_key || !bambooSettings.subdomain}
              data-testid="test-bamboo-button"
            >
              {testing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <CheckCircle2 className="w-4 h-4 mr-2" />}
              Test Connection
            </Button>
            <Button
              variant="outline"
              onClick={triggerBambooSync}
              disabled={syncing || !bambooSettings.api_key || !bambooSettings.subdomain || !bambooSettings.enabled}
              data-testid="sync-bamboo-button"
            >
              {syncing ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <RefreshCw className="w-4 h-4 mr-2" />}
              Sync Now
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Azure SSO Settings */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">Azure AD SSO</CardTitle>
              <CardDescription>Configure Microsoft Entra ID (Azure AD) single sign-on</CardDescription>
            </div>
            <Switch
              checked={azureSettings.enabled}
              onCheckedChange={(checked) => setAzureSettings({ ...azureSettings, enabled: checked })}
              data-testid="azure-sso-enabled-switch"
            />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="bg-amber-50 border border-amber-200 rounded-md p-3 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-amber-800">
              Azure AD credentials are not yet available. Configure them here when ready.
            </p>
          </div>
          
          <div>
            <Label htmlFor="azure_tenant">Tenant ID</Label>
            <Input
              id="azure_tenant"
              value={azureSettings.tenant_id}
              onChange={(e) => setAzureSettings({ ...azureSettings, tenant_id: e.target.value })}
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              className="max-w-md font-mono text-sm"
              data-testid="azure-tenant-input"
            />
          </div>
          
          <div>
            <Label htmlFor="azure_client">Client ID (Application ID)</Label>
            <Input
              id="azure_client"
              value={azureSettings.client_id}
              onChange={(e) => setAzureSettings({ ...azureSettings, client_id: e.target.value })}
              placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              className="max-w-md font-mono text-sm"
              data-testid="azure-client-input"
            />
          </div>
          
          <div>
            <Label htmlFor="azure_secret">Client Secret</Label>
            <Input
              id="azure_secret"
              type="password"
              value={azureSettings.client_secret}
              onChange={(e) => setAzureSettings({ ...azureSettings, client_secret: e.target.value })}
              placeholder="Enter your client secret"
              className="max-w-md"
              data-testid="azure-secret-input"
            />
          </div>

          <Separator />

          <div>
            <h4 className="text-sm font-medium text-gray-900 mb-2">Setup Instructions</h4>
            <ol className="text-sm text-gray-600 space-y-2 list-decimal list-inside">
              <li>Go to <a href="https://portal.azure.com" target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">Azure Portal</a> → Microsoft Entra ID → App registrations</li>
              <li>Create a new registration or select existing app</li>
              <li>Copy the Application (client) ID and Directory (tenant) ID</li>
              <li>Under Certificates & secrets, create a new client secret</li>
              <li>Add redirect URI: <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">{window.location.origin}/auth/callback</code></li>
            </ol>
          </div>

          <div className="pt-2">
            <Button onClick={saveAzureSettings} disabled={saving} className="bg-gray-900 hover:bg-gray-800" data-testid="save-azure-settings-button">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Save Settings
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default SettingsPage;
