import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import BrandMark from './BrandMark';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login: doLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/overview';

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const data = await res.json();
      if (!data.ok) {
        setError(data.error || 'Login failed');
        return;
      }
      doLogin(data.token, data.email);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err.message || 'Cannot reach server');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-orange-50 to-white px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <BrandMark className="h-14 w-14 sm:h-16 sm:w-16" />
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
            <span className="text-orange-600">Orange</span> SMTP Log Investigation
          </h1>
          <p className="text-gray-600 mt-2">Sign in to access search and dashboards</p>
        </div>

        <div className="bg-white rounded-2xl shadow-lg border border-orange-100 p-8">
          <h2 className="text-xl font-semibold text-gray-800 mb-6">Sign in</h2>
          <form onSubmit={handleSubmit} className="space-y-5">
            <label className="block">
              <span className="block text-sm font-medium text-gray-700 mb-1.5">Email</span>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-orange-500 focus:border-orange-500 outline-none transition"
                placeholder="you@example.com"
                required
                autoComplete="email"
              />
            </label>
            <label className="block">
              <span className="block text-sm font-medium text-gray-700 mb-1.5">Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 rounded-lg border border-gray-300 focus:ring-2 focus:ring-orange-500 focus:border-orange-500 outline-none transition"
                placeholder="••••••••"
                required
                autoComplete="current-password"
              />
            </label>
            {error && (
              <div className="text-red-600 text-sm bg-red-50 px-3 py-2 rounded-lg">{error}</div>
            )}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 rounded-lg bg-orange-600 text-white font-semibold hover:bg-orange-700 focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 transition disabled:opacity-70"
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
          <p className="mt-6 text-center text-gray-600 text-sm">
            Don&apos;t have an account?{' '}
            <Link to="/signup" className="font-semibold text-orange-600 hover:text-orange-700">
              Sign up
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}

