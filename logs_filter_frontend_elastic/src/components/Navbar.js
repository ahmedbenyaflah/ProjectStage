import React, { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import BrandMark from './BrandMark';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

function NavButton({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={[
        'text-sm px-3 py-1.5 rounded-lg border transition',
        active
          ? 'bg-orange-600 border-orange-600 text-white'
          : 'bg-white border-orange-200 text-orange-700 hover:bg-orange-50',
      ].join(' ')}
      type="button"
    >
      {children}
    </button>
  );
}

export default function Navbar() {
  const { email, logout, token } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [loadingBlacklist, setLoadingBlacklist] = useState(false);
  const [blacklistError, setBlacklistError] = useState('');
  const [blacklistOpen, setBlacklistOpen] = useState(false);
  const [blacklisted, setBlacklisted] = useState([]);
  const [sendingEmail, setSendingEmail] = useState(false);
  const [emailStatus, setEmailStatus] = useState('');

  const active = useMemo(() => {
    if (location.pathname.startsWith('/search')) return 'search';
    if (location.pathname.startsWith('/dashboard')) return 'dashboard';
    return '';
  }, [location.pathname]);

  const loadBlacklist = async () => {
    setBlacklistError('');
    setLoadingBlacklist(true);
    try {
      const res = await fetch(`${API_BASE}/api/blacklist/listed`, {
        method: 'GET',
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to load blacklist');
      setBlacklisted(Array.isArray(data.listed) ? data.listed : []);
      setBlacklistOpen(true);
    } catch (e) {
      setBlacklistError(e.message || 'Failed to load blacklist');
      setBlacklistOpen(true);
    } finally {
      setLoadingBlacklist(false);
    }
  };

  const sendBlacklistEmail = async () => {
    setEmailStatus('');
    setSendingEmail(true);
    try {
      const res = await fetch(`${API_BASE}/api/blacklist/email`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to send email');
      if (data.sent) {
        setEmailStatus(`Email sent (${data.count} entries)`);
      } else {
        setEmailStatus(data.message || 'No blacklisted servers to report.');
      }
    } catch (e) {
      setEmailStatus(`Error: ${e.message}`);
    } finally {
      setSendingEmail(false);
      setTimeout(() => setEmailStatus(''), 5000);
    }
  };

  return (
    <header className="bg-white border-b border-orange-100 shadow-sm w-full">
      <div className="max-w-[1600px] mx-auto px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <button
              type="button"
              onClick={() => navigate('/dashboard')}
              className="flex items-center gap-2 min-w-0 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2"
              title="Home"
            >
              <BrandMark className="h-9 w-9 sm:h-10 sm:w-10" />
              <span className="font-bold text-gray-800 truncate text-left leading-tight hidden sm:inline">
                <span className="text-orange-600">Orange</span>
                {' '}
                SMTP Log Investigation
              </span>
            </button>
            <nav className="flex items-center gap-2">
              <NavButton active={active === 'search'} onClick={() => navigate('/search')}>
                Search
              </NavButton>
              <NavButton active={active === 'dashboard'} onClick={() => navigate('/dashboard')}>
                Dashboard
              </NavButton>
              <button
                type="button"
                onClick={() => {
                  if (blacklistOpen) {
                    setBlacklistOpen(false);
                    return;
                  }
                  loadBlacklist();
                }}
                disabled={loadingBlacklist}
                className="text-sm px-3 py-1.5 rounded-lg border border-gray-200 bg-white hover:bg-gray-50 transition disabled:opacity-60"
                title="Show currently blacklisted entries"
              >
                {loadingBlacklist ? 'Loading…' : 'Blacklist'}
              </button>
            </nav>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-600 font-medium hidden sm:inline">{email}</span>
            <button
              onClick={() => {
                logout();
                navigate('/login', { replace: true });
              }}
              className="text-sm border border-orange-200 px-3 py-1.5 rounded-lg hover:bg-orange-50 text-orange-600 transition"
              type="button"
            >
              Sign out
            </button>
          </div>
        </div>

        {blacklistOpen && (
          <div className="mt-3 bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-4 py-3 flex items-center justify-between border-b border-gray-100">
              <div className="text-sm font-semibold text-gray-900">
                Currently blacklisted ({blacklisted.length})
              </div>
              <div className="flex items-center gap-2">
                {emailStatus && (
                  <span className={`text-xs px-2 py-1 rounded-md ${emailStatus.startsWith('Error') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
                    {emailStatus}
                  </span>
                )}
                {blacklisted.length > 0 && (
                  <button
                    type="button"
                    onClick={sendBlacklistEmail}
                    disabled={sendingEmail}
                    className="text-sm px-3 py-1 rounded-md border border-orange-300 bg-orange-50 text-orange-700 hover:bg-orange-100 transition disabled:opacity-60"
                  >
                    {sendingEmail ? 'Sending…' : 'Send Email Report'}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setBlacklistOpen(false)}
                  className="text-sm px-2 py-1 rounded-md border border-gray-200 bg-white hover:bg-gray-50"
                >
                  Close
                </button>
              </div>
            </div>

            {!!blacklistError && (
              <div className="px-4 py-3 text-sm text-red-700 bg-red-50 border-b border-red-100">
                {blacklistError}
              </div>
            )}

            {!blacklistError && blacklisted.length === 0 && (
              <div className="px-4 py-4 text-sm text-gray-600">
                No blacklisted entries right now.
              </div>
            )}

            {!blacklistError && blacklisted.length > 0 && (
              <div className="max-h-[320px] overflow-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-gray-50">
                    <tr className="text-left text-gray-600">
                      <th className="px-4 py-2 font-medium">IP</th>
                      <th className="px-4 py-2 font-medium">Blacklist</th>
                      <th className="px-4 py-2 font-medium">Last seen</th>
                    </tr>
                  </thead>
                  <tbody>
                    {blacklisted.map((r, idx) => (
                      <tr key={`${r.ip || 'ip'}-${r.blacklist || 'bl'}-${idx}`} className="border-t border-gray-100">
                        <td className="px-4 py-2 font-mono text-gray-900">{r.ip || '—'}</td>
                        <td className="px-4 py-2 text-gray-800">{r.blacklist || '—'}</td>
                        <td className="px-4 py-2 text-gray-700">
                          {r['@timestamp'] ? new Date(r['@timestamp']).toLocaleString() : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}

