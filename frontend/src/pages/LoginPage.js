import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { Mail, Lock, ArrowRight, Loader2 } from 'lucide-react';

const LoginPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login, requestMagicLink, loginWithMagicLink, loginWithToken } = useAuth();
  
  const [mode, setMode] = useState('password'); // 'password' | 'magic-link' | 'magic-link-sent'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [azureSSOEnabled, setAzureSSOEnabled] = useState(false);
  const [checkingSSO, setCheckingSSO] = useState(true);

  // Check for token or error in URL (from Azure SSO callback)
  useEffect(() => {
    const token = searchParams.get('token');
    const error = searchParams.get('error');
    
    if (token) {
      handleTokenLogin(token);
    } else if (error) {
      toast.error(decodeURIComponent(error));
      // Clear the URL params
      window.history.replaceState({}, '', '/login');
    }
    
    // Check if Azure SSO is configured
    checkAzureSSOConfig();
  }, [searchParams]);

  const checkAzureSSOConfig = async () => {
    try {
      const response = await api.get('/auth/azure/config');
      setAzureSSOEnabled(response.data.enabled && response.data.configured);
    } catch (error) {
      console.error('Failed to check Azure SSO config:', error);
      setAzureSSOEnabled(false);
    } finally {
      setCheckingSSO(false);
    }
  };

  const handleTokenLogin = async (token) => {
    setLoading(true);
    try {
      // Store token temporarily to check for password change requirement
      localStorage.setItem('token', token);
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      
      // Get user info
      const response = await api.get('/auth/me');
      const user = response.data;
      
      // Check if password change is required
      if (user.must_change_password) {
        navigate('/change-password');
        return;
      }
      
      await loginWithToken(token);
      toast.success('Logged in successfully');
      navigate('/launchpad');
    } catch (error) {
      toast.error('Login failed');
      localStorage.removeItem('token');
      delete api.defaults.headers.common['Authorization'];
      window.history.replaceState({}, '', '/login');
    } finally {
      setLoading(false);
    }
  };

  const handleMagicLinkVerify = async (token) => {
    setLoading(true);
    try {
      await loginWithMagicLink(token);
      toast.success('Logged in successfully');
      navigate('/launchpad');
    } catch (error) {
      toast.error('Invalid or expired magic link');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordLogin = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error('Please fill in all fields');
      return;
    }
    
    setLoading(true);
    try {
      const response = await api.post('/auth/login', { email, password });
      const { access_token, user, must_change_password, must_change_email } = response.data;
      
      localStorage.setItem('token', access_token);
      api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
      
      // Check if credential change is required
      if (must_change_email || must_change_password) {
        if (must_change_email && must_change_password) {
          toast.info('Please update your email and password');
          navigate('/change-credentials');
        } else if (must_change_password) {
          toast.info('Please change your password');
          navigate('/change-password');
        }
        return;
      }
      
      await loginWithToken(access_token);
      toast.success('Logged in successfully');
      navigate('/launchpad');
    } catch (error) {
      const detail = error.response?.data?.detail;
      // Handle validation errors from Pydantic
      if (Array.isArray(detail)) {
        toast.error(detail.map(e => e.msg).join(', '));
      } else {
        toast.error(detail || 'Invalid credentials');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleMagicLinkRequest = async (e) => {
    e.preventDefault();
    if (!email) {
      toast.error('Please enter your email');
      return;
    }
    
    setLoading(true);
    try {
      await requestMagicLink(email);
      setMode('magic-link-sent');
      toast.success('Magic link sent to your email');
    } catch (error) {
      toast.error('Failed to send magic link');
    } finally {
      setLoading(false);
    }
  };

  const handleAzureSSO = async () => {
    if (!azureSSOEnabled) {
      toast.info('Azure SSO is not enabled. Please configure it in Admin Settings first.');
      return;
    }
    
    setLoading(true);
    try {
      const response = await api.get('/auth/azure/login');
      // Redirect to Microsoft login
      window.location.href = response.data.auth_url;
    } catch (error) {
      const errorMsg = error.response?.data?.detail || 'Failed to initiate Azure SSO';
      toast.error(errorMsg);
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex" data-testid="login-page">
      {/* Left side - Login form */}
      <div className="w-full lg:w-1/2 flex flex-col justify-center px-8 md:px-16 lg:px-24 py-12">
        <div className="max-w-md w-full mx-auto">
          {/* Logo/Brand */}
          <div className="mb-12">
            <span className="text-xs tracking-[0.2em] uppercase font-semibold text-gray-400">
              Identity Hub
            </span>
            <h1 className="font-heading text-4xl sm:text-5xl tracking-tighter text-gray-900 mt-2">
              Welcome back
            </h1>
            <p className="text-gray-500 mt-3 text-base">
              Sign in to access your applications
            </p>
          </div>

          {/* Azure SSO Button */}
          <Button
            type="button"
            variant="outline"
            className={`w-full h-12 border-gray-200 hover:bg-gray-50 text-gray-900 font-medium mb-6 ${
              !azureSSOEnabled ? 'opacity-60' : ''
            }`}
            onClick={handleAzureSSO}
            disabled={loading || checkingSSO}
            data-testid="azure-sso-button"
          >
            {loading ? (
              <Loader2 className="w-5 h-5 animate-spin mr-3" />
            ) : (
              <svg className="w-5 h-5 mr-3" viewBox="0 0 21 21" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M10 0H0V10H10V0Z" fill="#F25022"/>
                <path d="M21 0H11V10H21V0Z" fill="#7FBA00"/>
                <path d="M10 11H0V21H10V11Z" fill="#00A4EF"/>
                <path d="M21 11H11V21H21V11Z" fill="#FFB900"/>
              </svg>
            )}
            Continue with Microsoft
            {!azureSSOEnabled && !checkingSSO && (
              <span className="ml-2 text-xs text-gray-400">(not configured)</span>
            )}
          </Button>

          {/* Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-200"></div>
            </div>
            <div className="relative flex justify-center">
              <span className="bg-white px-4 text-xs tracking-[0.15em] uppercase text-gray-400">
                Or
              </span>
            </div>
          </div>

          {mode === 'magic-link-sent' ? (
            <div className="text-center py-8 animate-fade-in">
              <div className="w-16 h-16 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-4">
                <Mail className="w-8 h-8 text-blue-600" />
              </div>
              <h2 className="text-xl font-medium text-gray-900 mb-2">Check your email</h2>
              <p className="text-gray-500 mb-6">
                We've sent a magic link to<br />
                <span className="font-medium text-gray-900">{email}</span>
              </p>
              <Button
                variant="ghost"
                onClick={() => setMode('password')}
                className="text-gray-500 hover:text-gray-900"
                data-testid="back-to-login-button"
              >
                Back to login
              </Button>
            </div>
          ) : (
            <form onSubmit={mode === 'password' ? handlePasswordLogin : handleMagicLinkRequest}>
              {/* Email field */}
              <div className="mb-4">
                <Label htmlFor="email" className="text-sm font-medium text-gray-700 mb-1.5 block">
                  Email address
                </Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="pl-10 h-12 border-gray-200 focus:border-blue-500 focus:ring-blue-500"
                    placeholder="you@company.com"
                    data-testid="email-input"
                  />
                </div>
              </div>

              {/* Password field (only in password mode) */}
              {mode === 'password' && (
                <div className="mb-6 animate-fade-in">
                  <Label htmlFor="password" className="text-sm font-medium text-gray-700 mb-1.5 block">
                    Password
                  </Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <Input
                      id="password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="pl-10 h-12 border-gray-200 focus:border-blue-500 focus:ring-blue-500"
                      placeholder="Enter your password"
                      data-testid="password-input"
                    />
                  </div>
                </div>
              )}

              {/* Submit button */}
              <Button
                type="submit"
                disabled={loading}
                className="w-full h-12 bg-gray-900 hover:bg-gray-800 text-white font-medium"
                data-testid="login-submit-button"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    {mode === 'password' ? 'Sign in' : 'Send magic link'}
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </>
                )}
              </Button>

              {/* Toggle mode */}
              <div className="mt-6 text-center">
                <button
                  type="button"
                  onClick={() => setMode(mode === 'password' ? 'magic-link' : 'password')}
                  className="text-sm text-gray-500 hover:text-gray-900 transition-colors"
                  data-testid="toggle-login-mode-button"
                >
                  {mode === 'password' ? 'Sign in with magic link instead' : 'Sign in with password instead'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>

      {/* Right side - Image */}
      <div className="hidden lg:block lg:w-1/2 relative">
        <img
          src="https://images.pexels.com/photos/950241/pexels-photo-950241.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
          alt="Modern architecture"
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-br from-gray-900/20 to-transparent"></div>
      </div>
    </div>
  );
};

export default LoginPage;
