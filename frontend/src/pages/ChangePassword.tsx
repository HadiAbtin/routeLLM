import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { authApi } from '../lib/api';
import { Key, ArrowRight } from 'lucide-react';
import { cn } from '../lib/utils';

export function ChangePassword() {
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const { token } = useAuthStore();
  const navigate = useNavigate();

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (newPassword !== confirmPassword) {
      setError('New passwords do not match');
      return;
    }

    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters');
      return;
    }

    if (!token) {
      setError('Not authenticated');
      return;
    }

    setLoading(true);
    try {
      await authApi.changePassword({ old_password: oldPassword, new_password: newPassword });
      setSuccess(true);
      setTimeout(() => {
        navigate('/dashboard');
      }, 2000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Password change failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-4">
      <div className="max-w-md w-full">
        <div className="bg-slate-800/90 backdrop-blur-sm rounded-2xl shadow-2xl border border-slate-700/50 p-8">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-indigo-500 via-purple-500 to-pink-500 rounded-2xl mb-4 shadow-lg shadow-indigo-500/50">
              <Key className="w-8 h-8 text-white" strokeWidth={2.5} />
            </div>
            <h2 className="text-2xl font-bold text-white mb-2">Change Password</h2>
            <p className="text-sm text-slate-400">You must change your password before continuing</p>
          </div>

          <form className="space-y-5" onSubmit={onSubmit}>
            {error && (
              <div className="rounded-xl bg-red-500/10 border border-red-500/20 p-4 backdrop-blur-sm">
                <p className="text-sm text-red-300">{error}</p>
              </div>
            )}
            {success && (
              <div className="rounded-xl bg-green-500/10 border border-green-500/20 p-4 backdrop-blur-sm">
                <p className="text-sm text-green-300">Password changed successfully! Redirecting...</p>
              </div>
            )}

            <div>
              <label htmlFor="old_password" className="block text-sm font-medium text-slate-300 mb-2">
                Old Password
              </label>
              <input
                id="old_password"
                name="old_password"
                type="password"
                required
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                className={cn(
                  "block w-full px-4 py-3 bg-slate-700/50 border border-slate-600/50 rounded-xl",
                  "text-white placeholder-slate-400",
                  "focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50",
                  "transition-all duration-200 backdrop-blur-sm"
                )}
              />
            </div>

            <div>
              <label htmlFor="new_password" className="block text-sm font-medium text-slate-300 mb-2">
                New Password
              </label>
              <input
                id="new_password"
                name="new_password"
                type="password"
                required
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className={cn(
                  "block w-full px-4 py-3 bg-slate-700/50 border border-slate-600/50 rounded-xl",
                  "text-white placeholder-slate-400",
                  "focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50",
                  "transition-all duration-200 backdrop-blur-sm"
                )}
              />
            </div>

            <div>
              <label htmlFor="confirm_password" className="block text-sm font-medium text-slate-300 mb-2">
                Confirm New Password
              </label>
              <input
                id="confirm_password"
                name="confirm_password"
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className={cn(
                  "block w-full px-4 py-3 bg-slate-700/50 border border-slate-600/50 rounded-xl",
                  "text-white placeholder-slate-400",
                  "focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50",
                  "transition-all duration-200 backdrop-blur-sm"
                )}
              />
            </div>

            <button
              type="submit"
              disabled={loading || success}
              className={cn(
                "w-full flex items-center justify-center gap-2 py-3.5 px-4 rounded-xl",
                "text-sm font-semibold text-white",
                "bg-gradient-to-r from-indigo-600 to-purple-600",
                "hover:from-indigo-500 hover:to-purple-500",
                "focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:ring-offset-2 focus:ring-offset-slate-800",
                "disabled:opacity-50 disabled:cursor-not-allowed",
                "transition-all duration-200",
                "shadow-lg shadow-indigo-500/25 hover:shadow-indigo-500/40"
              )}
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>Changing...</span>
                </>
              ) : (
                <>
                  <span>Change Password</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
