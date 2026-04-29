import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import api from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';
import { Mail, Lock, ArrowRight, Loader2, ExternalLink } from 'lucide-react';

const LoginPage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { login, requestMagicLink, loginWithMagicLink, loginWithToken, user, isAuthenticated } = useAuth();
  
  const [mode, setMode] = useState('password'); // 'password' | 'magic-link' | 'magic-link-sent'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [azureSSOEnabled, setAzureSSOEnabled] = useState(false);
  const [checkingSSO, setCheckingSSO] = useState(true);
  const [redirectUrl, setRedirectUrl] = useState(null);
  const [redirectAppName, setRedirectAppName] = useState(null);
  const [redirectValidated, setRedirectValidated] = useState(null); // null = pending, true = valid, false = invalid
  const [ssoCheckDone, setSsoCheckDone] = useState(false);

  // Check for redirect parameter (external app SSO)
  useEffect(() => {
    const redirect = searchParams.get('redirect');
    if (redirect) {
      try {
        const decodedUrl = decodeURIComponent(redirect);
        // Validate URL format
        const url = new URL(decodedUrl);
        setRedirectUrl(decodedUrl);
        // Extract app name from hostname
        const hostname = url.hostname;
        const appName = hostname.split('.')[0];
        setRedirectAppName(appName.charAt(0).toUpperCase() + appName.slice(1));
        setRedirectValidated(null); // Will be validated below
      } catch (e) {
        console.error('Invalid redirect URL:', e);
        toast.error('Invalid redirect URL');
      }
    }
  }, [searchParams]);

  // If user is already authenticated and there's a redirect, validate and redirect immediately
  useEffect(() => {
    const checkExistingAuth = async () => {
      if (ssoCheckDone) return; // Prevent multiple checks
      
      const token = localStorage.getItem('token');
      if (token && redirectUrl) {
        try {
          // Validate token is still valid
          const response = await api.get('/auth/verify', {
            headers: { Authorization: `Bearer ${token}` }
          });
          
          if (response.data.valid) {
            // Validate redirect URL against allowed callbacks
            const validateResponse = await api.post('/auth/validate-redirect', {
              redirect_url: redirectUrl
            }, {
              headers: { Authorization: `Bearer ${token}` }
            });
            
            setSsoCheckDone(true);
            
            if (validateResponse.data.allowed) {
              setRedirectValidated(true);
              // Redirect to external app with token
              performRedirect(token);
              return; // Prevent further execution
            } else {
              setRedirectValidated(false);
              toast.error(validateResponse.data.reason || 'This application is not authorized for SSO');
              // Don't clear redirectUrl - just mark as invalid
            }
          }
        } catch (error) {
          // Token invalid or validation failed, continue with normal login
          console.log('Auth check failed, showing login form');
          setSsoCheckDone(true);
        }
      }
    };
    
    if (redirectUrl && !ssoCheckDone) {
      checkExistingAuth();
    }
  }, [redirectUrl, isAuthenticated, ssoCheckDone]);

  // Perform redirect to external app with token
  const performRedirect = (token) => {
    if (!redirectUrl) return;
    
    try {
      const url = new URL(redirectUrl);
      url.searchParams.set('token', token);
      window.location.href = url.toString();
    } catch (e) {
      console.error('Failed to redirect:', e);
      toast.error('Failed to redirect to application');
    }
  };

  // Check for token or error in URL (from Azure SSO callback)
  useEffect(() => {
    const token = searchParams.get('token');
    const error = searchParams.get('error');
    
    if (token && !redirectUrl) {
      handleTokenLogin(token);
    } else if (error) {
      toast.error(decodeURIComponent(error));
      // Clear the URL params but keep redirect if present
      const newUrl = redirectUrl ? `/login?redirect=${encodeURIComponent(redirectUrl)}` : '/login';
      window.history.replaceState({}, '', newUrl);
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
      
      // If there's a redirect URL, validate and redirect
      if (redirectUrl) {
        try {
          const validateResponse = await api.post('/auth/validate-redirect', {
            redirect_url: redirectUrl
          });
          
          if (validateResponse.data.allowed) {
            performRedirect(token);
            return;
          } else {
            toast.error('This application is not authorized for SSO');
          }
        } catch (e) {
          toast.error('Failed to validate redirect');
        }
      }
      
      toast.success('Logged in successfully');
      navigate('/launchpad');
    } catch (error) {
      toast.error('Login failed');
      localStorage.removeItem('token');
      delete api.defaults.headers.common['Authorization'];
      const newUrl = redirectUrl ? `/login?redirect=${encodeURIComponent(redirectUrl)}` : '/login';
      window.history.replaceState({}, '', newUrl);
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
      
      // If there's a redirect URL, validate and redirect to external app
      if (redirectUrl) {
        try {
          const validateResponse = await api.post('/auth/validate-redirect', {
            redirect_url: redirectUrl
          });
          
          if (validateResponse.data.allowed) {
            toast.success('Redirecting to application...');
            performRedirect(access_token);
            return;
          } else {
            toast.error(validateResponse.data.reason || 'This application is not authorized for SSO');
            // Clear redirect and go to launchpad
            setRedirectUrl(null);
          }
        } catch (e) {
          console.error('Redirect validation failed:', e);
          toast.error('Failed to validate redirect');
          setRedirectUrl(null);
        }
      }
      
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
      if (response.data.auth_url) {
        // Store redirect URL in session storage for after SSO callback
        if (redirectUrl) {
          sessionStorage.setItem('sso_redirect', redirectUrl);
        }
        window.location.href = response.data.auth_url;
      }
    } catch (error) {
      toast.error('Failed to initiate SSO');
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex" data-testid="login-page">
      {/* Left side - Login Form */}
      <div className="flex-1 flex items-center justify-center p-8 lg:p-12">
        <div className="w-full max-w-md space-y-8">
          {/* Header */}
          <div className="space-y-2">
            <span className="text-sm font-medium text-gray-500 tracking-wide uppercase">
              Identity Hub
            </span>
            <h1 className="text-4xl font-bold text-gray-900">
              Welcome back
            </h1>
            <p className="text-gray-600">
              {redirectUrl ? (
                <>Sign in to continue to <span className="font-medium text-gray-900">{redirectAppName}</span></>
              ) : (
                'Sign in to access your applications'
              )}
            </p>
          </div>

          {/* External App Indicator */}
          {redirectUrl && (
            <div className="flex items-center gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg" data-testid="redirect-indicator">
              <ExternalLink className="w-4 h-4 text-blue-600" />
              <span className="text-sm text-blue-800">
                You'll be redirected to <span className="font-medium">{redirectAppName}</span> after signing in
              </span>
            </div>
          )}

          {/* Azure SSO Button */}
          <div>
            <Button
              type="button"
              variant="outline"
              className="w-full h-12 justify-center gap-2 font-medium"
              onClick={handleAzureSSO}
              disabled={loading || checkingSSO || !azureSSOEnabled}
              data-testid="azure-sso-button"
            >
              <svg className="w-5 h-5" viewBox="0 0 21 21" xmlns="http://www.w3.org/2000/svg">
                <rect x="1" y="1" width="9" height="9" fill="#f25022"/>
                <rect x="11" y="1" width="9" height="9" fill="#7fba00"/>
                <rect x="1" y="11" width="9" height="9" fill="#00a4ef"/>
                <rect x="11" y="11" width="9" height="9" fill="#ffb900"/>
              </svg>
              Continue with Microsoft
              {!azureSSOEnabled && !checkingSSO && (
                <span className="text-xs text-gray-400">(not configured)</span>
              )}
            </Button>
          </div>

          {/* Divider */}
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-white px-2 text-gray-500">Or</span>
            </div>
          </div>

          {/* Login Form */}
          {mode === 'magic-link-sent' ? (
            <div className="text-center space-y-4 p-6 bg-gray-50 rounded-lg">
              <Mail className="w-12 h-12 mx-auto text-gray-400" />
              <h3 className="text-lg font-medium">Check your email</h3>
              <p className="text-sm text-gray-600">
                We've sent a magic link to <strong>{email}</strong>
              </p>
              <Button
                variant="link"
                onClick={() => setMode('password')}
                className="text-sm"
              >
                Back to login
              </Button>
            </div>
          ) : (
            <form onSubmit={mode === 'password' ? handlePasswordLogin : handleMagicLinkRequest} className="space-y-5">
              {/* Email field */}
              <div className="space-y-2">
                <Label htmlFor="email">Email address</Label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    className="pl-10 h-12"
                    disabled={loading}
                    data-testid="email-input"
                  />
                </div>
              </div>

              {/* Password field (only for password mode) */}
              {mode === 'password' && (
                <div className="space-y-2">
                  <Label htmlFor="password">Password</Label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                    <Input
                      id="password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter your password"
                      className="pl-10 h-12"
                      disabled={loading}
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

              {/* Toggle mode - HIDDEN: Magic link email delivery not yet configured
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
              */}
            </form>
          )}
          
          {/* Version indicator */}
          <div className="mt-8 text-center">
            <span className="text-xs text-gray-400">v3.1.0</span>
          </div>
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
