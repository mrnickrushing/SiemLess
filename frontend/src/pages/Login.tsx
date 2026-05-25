import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck, Eye, EyeOff } from 'lucide-react';
import { login } from '../api/auth';
import { checkBackendHealth } from '../api/stats';

interface Props {
  onSuccess?: (username: string) => void;
}

export default function Login({ onSuccess }: Props) {
  const navigate = useNavigate();
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [backendOk, setBackendOk] = useState<boolean | null>(null);

  useEffect(() => {
    checkBackendHealth().then(setBackendOk);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const user = await login(username, password);
      onSuccess?.(user);
      navigate('/');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0f1117] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-3">
            <ShieldCheck className="text-[#2dd4aa]" size={40} />
            <span className="text-3xl font-bold text-white tracking-wide">SiemLess</span>
          </div>
          <p className="text-gray-400 text-sm mb-3">Security Information &amp; Event Management</p>
          {/* Backend status indicator */}
          <div className="flex items-center justify-center gap-1.5">
            <span
              className={`w-2 h-2 rounded-full ${
                backendOk === null
                  ? 'bg-yellow-400 animate-pulse'
                  : backendOk
                  ? 'bg-[#2dd4aa]'
                  : 'bg-red-500'
              }`}
            />
            <span className="text-xs text-gray-500">
              {backendOk === null ? 'Connecting…' : backendOk ? 'Backend reachable' : 'Backend unreachable'}
            </span>
          </div>
        </div>

        <div className="bg-[#1a1f2e] border border-gray-800 rounded-xl p-8 shadow-2xl">
          <h2 className="text-white text-xl font-semibold mb-6">Sign in</h2>

          {error && (
            <div className="mb-4 px-4 py-3 bg-red-900/30 border border-red-700 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-gray-400 text-sm mb-1.5">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoComplete="username"
                className="w-full bg-[#0f1117] border border-gray-700 rounded-lg px-4 py-2.5 text-white text-sm focus:outline-none focus:border-[#2dd4aa] transition-colors"
              />
            </div>

            <div>
              <label className="block text-gray-400 text-sm mb-1.5">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  className="w-full bg-[#0f1117] border border-gray-700 rounded-lg px-4 py-2.5 pr-10 text-white text-sm focus:outline-none focus:border-[#2dd4aa] transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-[#2dd4aa] hover:bg-[#1ab894] disabled:opacity-50 disabled:cursor-not-allowed text-black font-semibold py-2.5 rounded-lg transition-colors text-sm"
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
