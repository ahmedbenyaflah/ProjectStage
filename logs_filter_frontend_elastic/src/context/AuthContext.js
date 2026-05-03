import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);
const TOKEN_KEY = 'logviewer_token';
const EMAIL_KEY = 'logviewer_email';
const ROLE_KEY = 'logviewer_role';

function normalizeRole(r) {
  const u = String(r || 'N1').trim().toUpperCase();
  if (u === 'N1' || u === 'N2' || u === 'N3') return u;
  return 'N1';
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [email, setEmail] = useState(() => localStorage.getItem(EMAIL_KEY));
  const [role, setRole] = useState(() => normalizeRole(localStorage.getItem(ROLE_KEY)));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(false);
  }, []);

  const login = (t, e, r) => {
    if (t) localStorage.setItem(TOKEN_KEY, t);
    if (e) localStorage.setItem(EMAIL_KEY, e);
    const nr = normalizeRole(r);
    localStorage.setItem(ROLE_KEY, nr);
    setToken(t);
    setEmail(e);
    setRole(nr);
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(EMAIL_KEY);
    localStorage.removeItem(ROLE_KEY);
    setToken(null);
    setEmail(null);
    setRole('N1');
  };

  const isAuthenticated = !!token;

  return (
    <AuthContext.Provider value={{ token, email, role, login, logout, isAuthenticated, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

