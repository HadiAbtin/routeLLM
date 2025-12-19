import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { AppLayout } from '../components/AppLayout';
import { Button } from '../components/Button';
import { useAuthStore } from '../store/authStore';
import { statsApi } from '../lib/api.js';
import { CheckCircle2, XCircle, Clock, Activity } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export function Runs() {
  const { token } = useAuthStore();
  const navigate = useNavigate();

  const { data: stats, isLoading: loading } = useQuery({
    queryKey: ['runs-stats', 60],
    queryFn: () => statsApi.getRunsStats(60).then((res: any) => res.data),
    enabled: !!token,
    refetchInterval: 10000,
  });

  if (loading) {
    return (
      <AppLayout title="Runs">
        <div className="flex items-center justify-center h-64">
          <div className="text-slate-500">Loading...</div>
        </div>
      </AppLayout>
    );
  }

  if (!stats) {
    return (
      <AppLayout title="Runs">
        <div className="text-slate-500">No data available</div>
      </AppLayout>
    );
  }

  return (
    <AppLayout 
      title="Runs"
      subtitle="Monitor async agent runs and worker performance"
    >
      <div className="w-full space-y-6">
        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-slate-600 dark:text-slate-400">Total Runs</h3>
              <Activity className="w-5 h-5 text-slate-400" />
            </div>
            <p className="text-3xl font-bold text-slate-900 dark:text-white">{stats.total_runs}</p>
          </div>
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-slate-600 dark:text-slate-400">Succeeded</h3>
              <CheckCircle2 className="w-5 h-5 text-green-500" />
            </div>
            <p className="text-3xl font-bold text-green-600">{stats.by_status.succeeded}</p>
          </div>
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-slate-600 dark:text-slate-400">Failed</h3>
              <XCircle className="w-5 h-5 text-red-500" />
            </div>
            <p className="text-3xl font-bold text-red-600">{stats.by_status.failed}</p>
          </div>
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 flex flex-col">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-slate-600 dark:text-slate-400">Running</h3>
              <Clock className="w-5 h-5 text-blue-500" />
            </div>
            <p className="text-3xl font-bold text-blue-600 mb-4">{stats.by_status.running}</p>
            {stats.by_status.running > 0 && (
              <div className="flex justify-center mt-auto">
                <Button
                  variant="primary"
                  onClick={() => navigate('/runs')}
                  className="w-full"
                >
                  View Progress
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* Status Distribution */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Runs by Status</h3>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">Distribution of run statuses</p>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={Object.entries(stats.by_status).map(([status, count]) => ({ status, count }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" className="dark:stroke-slate-700" />
              <XAxis dataKey="status" stroke="#6b7280" className="dark:stroke-slate-400" />
              <YAxis stroke="#6b7280" className="dark:stroke-slate-400" />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#1f2937', 
                  border: '1px solid #374151', 
                  borderRadius: '12px', 
                  color: '#f3f4f6',
                  padding: '12px'
                }}
              />
              <Bar dataKey="count" fill="#6366f1" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Retry Histogram */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Retry Distribution</h3>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">Number of retries per run</p>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={stats.retry_histogram}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" className="dark:stroke-slate-700" />
              <XAxis dataKey="retry_count" stroke="#6b7280" className="dark:stroke-slate-400" />
              <YAxis stroke="#6b7280" className="dark:stroke-slate-400" />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#1f2937', 
                  border: '1px solid #374151', 
                  borderRadius: '12px', 
                  color: '#f3f4f6',
                  padding: '12px'
                }}
              />
              <Bar dataKey="runs" fill="#8b5cf6" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </AppLayout>
  );
}
