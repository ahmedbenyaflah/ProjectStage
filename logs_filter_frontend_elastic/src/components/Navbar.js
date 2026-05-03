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
  const { email, logout, token, role } = useAuth();
  const showDnsbl = role === 'N3';
  const navigate = useNavigate();
  const location = useLocation();
  const [loadingBlacklist, setLoadingBlacklist] = useState(false);
  const [blacklistError, setBlacklistError] = useState('');
  const [blacklistOpen, setBlacklistOpen] = useState(false);
  const [blacklisted, setBlacklisted] = useState([]);
  const [sendingEmail, setSendingEmail] = useState(false);
  const [emailStatus, setEmailStatus] = useState('');
  const [intervalMinutesStr, setIntervalMinutesStr] = useState('5');
  const [savingInterval, setSavingInterval] = useState(false);
  const [scanningNow, setScanningNow] = useState(false);
  const [intervalStatus, setIntervalStatus] = useState('');

  const active = useMemo(() => {
    if (location.pathname.startsWith('/search')) return 'search';
    if (location.pathname.startsWith('/dashboard')) return 'dashboard';
    return '';
  }, [location.pathname]);

  const loadBlacklist = async () => {
    setBlacklistError('');
    setLoadingBlacklist(true);
    try {
      const headers = token ? { Authorization: `Bearer ${token}` } : undefined;
      const [listedRes, intervalRes] = await Promise.all([
        fetch(`${API_BASE}/api/blacklist/listed`, { method: 'GET', headers }),
        fetch(`${API_BASE}/api/blacklist/interval`, { method: 'GET', headers }),
      ]);
      const listedData = await listedRes.json();
      if (!listedRes.ok) throw new Error(listedData.detail || 'Failed to load blacklist');
      setBlacklisted(Array.isArray(listedData.listed) ? listedData.listed : []);
      if (intervalRes.ok) {
        const idata = await intervalRes.json();
        const sec = Number(idata.interval_seconds);
        if (Number.isFinite(sec) && sec > 0) {
          setIntervalMinutesStr(String(Math.max(1, Math.round(sec / 60))));
        }
      }
      setBlacklistOpen(true);
    } catch (e) {
      setBlacklistError(e.message || 'Failed to load blacklist');
      setBlacklistOpen(true);
    } finally {
      setLoadingBlacklist(false);
    }
  };

  const saveScanInterval = async () => {
    setIntervalStatus('');
    const minutes = parseInt(intervalMinutesStr, 10);
    if (!Number.isFinite(minutes) || minutes < 1 || minutes > 10080) {
      setIntervalStatus('Interval must be 1–10080 minutes (7 days max).');
      setTimeout(() => setIntervalStatus(''), 4000);
      return;
    }
    setSavingInterval(true);
    try {
      const res = await fetch(`${API_BASE}/api/blacklist/interval`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ interval_seconds: Math.round(minutes * 60) }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to save interval');
      const sec = Number(data.interval_seconds);
      if (Number.isFinite(sec) && sec > 0) {
        setIntervalMinutesStr(String(Math.max(1, Math.round(sec / 60))));
      }
      setIntervalStatus('Saved.');
      setTimeout(() => setIntervalStatus(''), 3000);
    } catch (e) {
      setIntervalStatus(e.message || 'Save failed');
      setTimeout(() => setIntervalStatus(''), 5000);
    } finally {
      setSavingInterval(false);
    }
  };

  const runBlacklistScanNow = async () => {
    setBlacklistError('');
    setScanningNow(true);
    try {
      const res = await fetch(`${API_BASE}/api/blacklist/scan`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Scan failed');
      setBlacklisted(Array.isArray(data.listed) ? data.listed : []);
    } catch (e) {
      setBlacklistError(e.message || 'Scan failed');
    } finally {
      setScanningNow(false);
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
              {showDnsbl && (
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
              )}
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

        {showDnsbl && blacklistOpen && (
          <div className="mt-3 bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
            <div className="px-4 py-3 flex flex-col gap-3 border-b border-gray-100 sm:flex-row sm:items-center sm:justify-between">
              <div className="text-sm font-semibold text-gray-900">
                Currently blacklisted ({blacklisted.length})
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <span className="whitespace-nowrap">Auto-scan every</span>
                  <input
                    type="number"
                    min={1}
                    max={10080}
                    step={1}
                    value={intervalMinutesStr}
                    onChange={(e) => setIntervalMinutesStr(e.target.value)}
                    className="w-20 rounded-md border border-gray-300 px-2 py-1 text-sm font-mono"
                  />
                  <span className="text-gray-600">min</span>
                </label>
                <button
                  type="button"
                  onClick={saveScanInterval}
                  disabled={savingInterval}
                  className="text-sm px-3 py-1 rounded-md border border-gray-300 bg-white text-gray-800 hover:bg-gray-50 transition disabled:opacity-60"
                >
                  {savingInterval ? 'Saving…' : 'Save interval'}
                </button>
                <button
                  type="button"
                  onClick={runBlacklistScanNow}
                  disabled={scanningNow}
                  className="text-sm px-3 py-1 rounded-md border border-orange-500 bg-orange-600 text-white hover:bg-orange-700 transition disabled:opacity-60"
                >
                  {scanningNow ? 'Scanning…' : 'Check now'}
                </button>
                {intervalStatus && (
                  <span
                    className={`text-xs px-2 py-1 rounded-md ${
                      intervalStatus.startsWith('Saved')
                        ? 'bg-green-50 text-green-800'
                        : intervalStatus.includes('must be')
                          ? 'bg-amber-50 text-amber-900'
                          : 'bg-red-50 text-red-700'
                    }`}
                  >
                    {intervalStatus}
                  </span>
                )}
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

