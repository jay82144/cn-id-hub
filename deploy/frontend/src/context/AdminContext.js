import { createContext, useContext, useState, useEffect } from 'react';
import { useAuth } from './AuthContext';
import api from '@/lib/api';

const AdminContext = createContext(null);

export const useAdmin = () => {
  const context = useContext(AdminContext);
  if (!context) {
    throw new Error('useAdmin must be used within AdminProvider');
  }
  return context;
};

export const AdminProvider = ({ children }) => {
  const { user, isSysadmin } = useAuth();
  const [companies, setCompanies] = useState([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState(null);
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [loading, setLoading] = useState(true);

  // Fetch companies for sysadmin
  useEffect(() => {
    if (isSysadmin) {
      fetchCompanies();
    } else {
      setLoading(false);
    }
  }, [isSysadmin]);

  // Set selected company when selection changes
  useEffect(() => {
    if (selectedCompanyId && companies.length > 0) {
      const company = companies.find(c => c.id === selectedCompanyId);
      setSelectedCompany(company || null);
    } else {
      setSelectedCompany(null);
    }
  }, [selectedCompanyId, companies]);

  const fetchCompanies = async () => {
    try {
      const response = await api.get('/companies');
      setCompanies(response.data);
    } catch (error) {
      console.error('Failed to fetch companies:', error);
    } finally {
      setLoading(false);
    }
  };

  const selectCompany = (companyId) => {
    setSelectedCompanyId(companyId);
  };

  const clearCompanyFilter = () => {
    setSelectedCompanyId(null);
    setSelectedCompany(null);
  };

  // Get query params for API calls
  const getCompanyFilter = () => {
    if (isSysadmin && selectedCompanyId) {
      return { company_id: selectedCompanyId };
    }
    return {};
  };

  const value = {
    companies,
    selectedCompanyId,
    selectedCompany,
    loading,
    selectCompany,
    clearCompanyFilter,
    getCompanyFilter,
    isSysadmin,
  };

  return (
    <AdminContext.Provider value={value}>
      {children}
    </AdminContext.Provider>
  );
};
