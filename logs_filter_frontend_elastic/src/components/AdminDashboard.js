import React, { useState, useEffect, useCallback } from 'react';
import BrandMark from './BrandMark';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const ADMIN_TOKEN_KEY = 'logviewer_admin_token';

function authHeaders(token) {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };
}

export default function AdminDashboard() {
  const [token, setToken] = useState(() => localStorage.getItem(ADMIN_TOKEN_KEY));
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);

  const [users, setUsers] = useState([]);
  const [listError, setListError] = useState('');
  const [listLoading, setListLoading] = useState(false);

  const [showAdd, setShowAdd] = useState(false);
  const [addEmail, setAddEmail] = useState('');
  const [addPassword, setAddPassword] = useState('');
  const [addRole, setAddRole] = useState('N1');
  const [addError, setAddError] = useState('');

  const [editUser, setEditUser] = useState(null);
  const [editEmail, setEditEmail] = useState('');
  const [editRole, setEditRole] = useState('N1');
  const [editPassword, setEditPassword] = useState('');
  const [editError, setEditError] = useState('');

  const loadUsers = useCallback(async () => {
    if (!token) return;
    setListLoading(true);
    setListError('');
    try {
      const res = await fetch(`${API_BASE}/api/admin/users`, { headers: authHeaders(token) });
      if (res.status === 401 || res.status === 403) {
        localStorage.removeItem(ADMIN_TOKEN_KEY);
        setToken(null);
        setListError('Session expired. Sign in again.');
        return;
      }
      const data = await res.json();
      if (!res.ok) {
        setListError(data.detail || 'Failed to load users');
        return;
      }
      setUsers(data.users || []);
    } catch (e) {
      setListError(e.message || 'Cannot reach server');
    } finally {
      setListLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (token) loadUsers();
  }, [token, loadUsers]);

  const handleAdminLogin = async (e) => {
    e.preventDefault();
    setLoginError('');
    setLoginLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/admin/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const data = await res.json();
      if (!data.ok) {
        setLoginError(data.error || 'Login failed');
        return;
      }
      localStorage.setItem(ADMIN_TOKEN_KEY, data.token);
      setToken(data.token);
      setPassword('');
    } catch (err) {
      setLoginError(err.message || 'Cannot reach server');
    } finally {
      setLoginLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    setToken(null);
    setUsers([]);
  };

  const handleAddUser = async (e) => {
    e.preventDefault();
    setAddError('');
    try {
      const res = await fetch(`${API_BASE}/api/admin/users`, {
        method: 'POST',
        headers: authHeaders(token),
        body: JSON.stringify({
          email: addEmail.trim(),
          password: addPassword,
          role: addRole,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setAddError(typeof data.detail === 'string' ? data.detail : 'Create failed');
        return;
      }
      setShowAdd(false);
      setAddEmail('');
      setAddPassword('');
      setAddRole('N1');
      loadUsers();
    } catch (err) {
      setAddError(err.message || 'Request failed');
    }
  };

  const openEdit = (u) => {
    setEditUser(u);
    setEditEmail(u.email);
    setEditRole(u.role);
    setEditPassword('');
    setEditError('');
  };

  const handleEditSave = async (e) => {
    e.preventDefault();
    if (!editUser) return;
    setEditError('');
    const body = { email: editEmail.trim(), role: editRole };
    if (editPassword.trim()) body.password = editPassword;
    try {
      const res = await fetch(`${API_BASE}/api/admin/users/${editUser.id}`, {
        method: 'PATCH',
        headers: authHeaders(token),
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        setEditError(typeof data.detail === 'string' ? data.detail : 'Update failed');
        return;
      }
      setEditUser(null);
      loadUsers();
    } catch (err) {
      setEditError(err.message || 'Request failed');
    }
  };

  const handleDelete = async (u) => {
    if (!window.confirm(`Delete user ${u.email} (id ${u.id})? This cannot be undone.`)) return;
    try {
      const res = await fetch(`${API_BASE}/api/admin/users/${u.id}`, {
        method: 'DELETE',
        headers: authHeaders(token),
      });
      const data = await res.json();
      if (!res.ok) {
        alert(typeof data.detail === 'string' ? data.detail : 'Delete failed');
        return;
      }
      loadUsers();
    } catch (err) {
      alert(err.message || 'Request failed');
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-slate-900 to-slate-800 px-4">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <div className="flex justify-center mb-4">
              <BrandMark className="h-14 w-14 sm:h-16 sm:w-16" />
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-white">Admin</h1>
            <p className="text-slate-400 mt-2">User management (static credentials)</p>
          </div>
          <div className="bg-slate-800/90 rounded-2xl shadow-xl border border-slate-600 p-8">
            <form onSubmit={handleAdminLogin} className="space-y-5">
              <label className="block">
                <span className="block text-sm font-medium text-slate-300 mb-1.5">Username</span>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full px-4 py-3 rounded-lg border border-slate-600 bg-slate-900 text-white focus:ring-2 focus:ring-orange-500 focus:border-orange-500 outline-none"
                  autoComplete="username"
                  required
                />
              </label>
              <label className="block">
                <span className="block text-sm font-medium text-slate-300 mb-1.5">Password</span>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-4 py-3 rounded-lg border border-slate-600 bg-slate-900 text-white focus:ring-2 focus:ring-orange-500 focus:border-orange-500 outline-none"
                  autoComplete="current-password"
                  required
                />
              </label>
              {loginError && (
                <div className="text-red-400 text-sm bg-red-950/50 px-3 py-2 rounded-lg">{loginError}</div>
              )}
              <button
                type="submit"
                disabled={loginLoading}
                className="w-full py-3 px-4 rounded-lg bg-orange-600 text-white font-semibold hover:bg-orange-700 focus:ring-2 focus:ring-orange-500 transition disabled:opacity-70"
              >
                {loginLoading ? 'Signing in…' : 'Sign in'}
              </button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  const roleHelp = (
    <p className="text-xs text-slate-500 mt-1">
      N1 / N2: standard access. N3: receives DNSBL change alerts (Bcc) in addition to the operator inbox.
    </p>
  );

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-900 to-slate-800 text-slate-100 px-4 py-8">
      <div className="max-w-5xl mx-auto">
        <header className="flex flex-wrap items-center justify-between gap-4 mb-8">
          <div className="flex items-center gap-3">
            <BrandMark className="h-10 w-10" />
            <div>
              <h1 className="text-xl font-bold text-white">Admin dashboard</h1>
              <p className="text-sm text-slate-400">Users & roles (N1, N2, N3)</p>
            </div>
          </div>
          <button
            type="button"
            onClick={logout}
            className="px-4 py-2 rounded-lg border border-slate-500 text-slate-200 hover:bg-slate-700 text-sm font-medium"
          >
            Log out
          </button>
        </header>

        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-semibold text-white">Users</h2>
          <button
            type="button"
            onClick={() => {
              setShowAdd(true);
              setAddError('');
            }}
            className="px-4 py-2 rounded-lg bg-orange-600 text-white text-sm font-semibold hover:bg-orange-700"
          >
            Add user
          </button>
        </div>

        {listError && (
          <div className="mb-4 text-red-400 text-sm bg-red-950/40 px-3 py-2 rounded-lg border border-red-900">
            {listError}
          </div>
        )}

        <div className="rounded-xl border border-slate-600 overflow-hidden bg-slate-800/50">
          {listLoading ? (
            <div className="p-8 text-center text-slate-400">Loading…</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-800 text-left text-slate-300 border-b border-slate-600">
                    <th className="px-4 py-3 font-medium">ID</th>
                    <th className="px-4 py-3 font-medium">Email</th>
                    <th className="px-4 py-3 font-medium">Role</th>
                    <th className="px-4 py-3 font-medium">Created</th>
                    <th className="px-4 py-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-b border-slate-700/80 hover:bg-slate-800/80">
                      <td className="px-4 py-3 text-slate-400">{u.id}</td>
                      <td className="px-4 py-3 text-white">{u.email}</td>
                      <td className="px-4 py-3">
                        <span className="inline-flex px-2 py-0.5 rounded bg-slate-700 text-orange-300 font-mono text-xs">
                          {u.role}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-400 whitespace-nowrap">{u.created_at}</td>
                      <td className="px-4 py-3 text-right space-x-2">
                        <button
                          type="button"
                          onClick={() => openEdit(u)}
                          className="text-orange-400 hover:text-orange-300 font-medium"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(u)}
                          className="text-red-400 hover:text-red-300 font-medium"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {users.length === 0 && (
                <div className="p-8 text-center text-slate-500">No users yet.</div>
              )}
            </div>
          )}
        </div>

        {showAdd && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
            <div className="bg-slate-800 border border-slate-600 rounded-xl p-6 w-full max-w-md shadow-xl">
              <h3 className="text-lg font-semibold text-white mb-4">Add user</h3>
              <form onSubmit={handleAddUser} className="space-y-4">
                <label className="block">
                  <span className="text-sm text-slate-300">Email</span>
                  <input
                    type="email"
                    required
                    value={addEmail}
                    onChange={(e) => setAddEmail(e.target.value)}
                    className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white"
                  />
                </label>
                <label className="block">
                  <span className="text-sm text-slate-300">Password (min 6)</span>
                  <input
                    type="password"
                    required
                    minLength={6}
                    value={addPassword}
                    onChange={(e) => setAddPassword(e.target.value)}
                    className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white"
                  />
                </label>
                <label className="block">
                  <span className="text-sm text-slate-300">Role</span>
                  <select
                    value={addRole}
                    onChange={(e) => setAddRole(e.target.value)}
                    className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white"
                  >
                    <option value="N1">N1</option>
                    <option value="N2">N2</option>
                    <option value="N3">N3</option>
                  </select>
                  {roleHelp}
                </label>
                {addError && <div className="text-red-400 text-sm">{addError}</div>}
                <div className="flex gap-2 justify-end pt-2">
                  <button
                    type="button"
                    onClick={() => setShowAdd(false)}
                    className="px-4 py-2 rounded-lg border border-slate-500 text-slate-300"
                  >
                    Cancel
                  </button>
                  <button type="submit" className="px-4 py-2 rounded-lg bg-orange-600 text-white font-semibold">
                    Create
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {editUser && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50">
            <div className="bg-slate-800 border border-slate-600 rounded-xl p-6 w-full max-w-md shadow-xl">
              <h3 className="text-lg font-semibold text-white mb-1">Edit user</h3>
              <p className="text-sm text-slate-400 mb-4">ID {editUser.id}</p>
              <form onSubmit={handleEditSave} className="space-y-4">
                <label className="block">
                  <span className="text-sm text-slate-300">Email</span>
                  <input
                    type="email"
                    required
                    value={editEmail}
                    onChange={(e) => setEditEmail(e.target.value)}
                    className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white"
                  />
                </label>
                <label className="block">
                  <span className="text-sm text-slate-300">New password (leave blank to keep)</span>
                  <input
                    type="password"
                    minLength={6}
                    value={editPassword}
                    onChange={(e) => setEditPassword(e.target.value)}
                    className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white"
                    placeholder="••••••••"
                  />
                </label>
                <label className="block">
                  <span className="text-sm text-slate-300">Role</span>
                  <select
                    value={editRole}
                    onChange={(e) => setEditRole(e.target.value)}
                    className="mt-1 w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-600 text-white"
                  >
                    <option value="N1">N1</option>
                    <option value="N2">N2</option>
                    <option value="N3">N3</option>
                  </select>
                  {roleHelp}
                </label>
                {editError && <div className="text-red-400 text-sm">{editError}</div>}
                <div className="flex gap-2 justify-end pt-2">
                  <button
                    type="button"
                    onClick={() => setEditUser(null)}
                    className="px-4 py-2 rounded-lg border border-slate-500 text-slate-300"
                  >
                    Cancel
                  </button>
                  <button type="submit" className="px-4 py-2 rounded-lg bg-orange-600 text-white font-semibold">
                    Save
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
