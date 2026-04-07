import { createContext, useContext, useState, useEffect } from 'react';
import api from '@/lib/api';

const AuthContext = createContext(null);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [mustChangeCredentials, setMustChangeCredentials] = useState({
    password: false,
    email: false
  });

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      fetchUser();
    } else {
      setLoading(false);
    }
  }, []);

  const fetchUser = async () => {
    try {
      const response = await api.get('/auth/me');
      setUser(response.data);
      // Check if user needs to change credentials
      setMustChangeCredentials({
        password: response.data.must_change_password || false,
        email: response.data.must_change_email || false
      });
    } catch (error) {
      localStorage.removeItem('token');
      delete api.defaults.headers.common['Authorization'];
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    const response = await api.post('/auth/login', { email, password });
    const { access_token, user: userData, must_change_password, must_change_email } = response.data;
    localStorage.setItem('token', access_token);
    api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    setUser(userData);
    setMustChangeCredentials({
      password: must_change_password || false,
      email: must_change_email || false
    });
    return { user: userData, mustChangePassword: must_change_password, mustChangeEmail: must_change_email };
  };

  const loginWithMagicLink = async (token) => {
    const response = await api.post('/auth/magic-link/verify', { token });
    const { access_token, user: userData, must_change_password, must_change_email } = response.data;
    localStorage.setItem('token', access_token);
    api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    setUser(userData);
    setMustChangeCredentials({
      password: must_change_password || false,
      email: must_change_email || false
    });
    return { user: userData, mustChangePassword: must_change_password, mustChangeEmail: must_change_email };
  };

  const loginWithToken = async (token) => {
    // Direct login with a token (from Azure SSO callback)
    localStorage.setItem('token', token);
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    await fetchUser();
  };

  const requestMagicLink = async (email) => {
    const response = await api.post('/auth/magic-link', { email });
    return response.data;
  };

  const changePassword = async (currentPassword, newPassword) => {
    await api.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword
    });
    setMustChangeCredentials(prev => ({ ...prev, password: false }));
    setUser(prev => prev ? { ...prev, must_change_password: false } : null);
  };

  const changeCredentials = async (newEmail, newPassword) => {
    const response = await api.post('/auth/change-credentials', {
      new_email: newEmail,
      new_password: newPassword
    });
    const { access_token, user: userData } = response.data;
    localStorage.setItem('token', access_token);
    api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
    setUser(userData);
    setMustChangeCredentials({ password: false, email: false });
    return userData;
  };

  const logout = async () => {
    try {
      await api.post('/auth/logout');
    } catch (error) {
      // Continue with local logout even if server request fails
    }
    localStorage.removeItem('token');
    delete api.defaults.headers.common['Authorization'];
    setUser(null);
    setMustChangeCredentials({ password: false, email: false });
  };

  const value = {
    user,
    loading,
    mustChangeCredentials,
    login,
    logout,
    loginWithMagicLink,
    loginWithToken,
    requestMagicLink,
    changePassword,
    changeCredentials,
    isAdmin: ['sysadmin', 'company_admin'].includes(user?.role),
    isSysadmin: user?.role === 'sysadmin',
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
