import { useNavigate } from 'react-router-dom';
import { AppLayout } from '../components/AppLayout';
import { useAuthStore } from '../store/authStore';
import { User, Key, Shield } from 'lucide-react';

export function Settings() {
  const { user } = useAuthStore();
  const navigate = useNavigate();

  return (
    <AppLayout 
      title="Settings"
      subtitle="Manage your account settings"
    >
      <div className="w-full max-w-2xl space-y-6">
        {/* Profile Card */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-lg flex items-center justify-center">
              <User className="w-5 h-5 text-white" />
            </div>
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Profile</h3>
          </div>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Email</label>
              <div className="text-sm text-slate-900 dark:text-white font-mono bg-slate-50 dark:bg-slate-700/50 px-3 py-2 rounded-lg border border-slate-200 dark:border-slate-600">
                {user?.email}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Role</label>
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-slate-500" />
                <span className="text-sm text-slate-900 dark:text-white">{user?.is_admin ? 'Admin' : 'User'}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Password Card */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-lg flex items-center justify-center">
              <Key className="w-5 h-5 text-white" />
            </div>
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Password</h3>
          </div>
          <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
            Change your password to keep your account secure.
          </p>
          <button
            onClick={() => navigate('/change-password')}
            className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 hover:from-indigo-500 hover:to-purple-500 transition-all duration-200"
          >
            <Key className="w-4 h-4" />
            Change Password
          </button>
        </div>
      </div>
    </AppLayout>
  );
}
