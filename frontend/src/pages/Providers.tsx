import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { AppLayout } from '../components/AppLayout';
import { useAuthStore } from '../store/authStore';
import { statsApi } from '../lib/api';

export function Providers() {
  const { token } = useAuthStore();
  const [selectedProvider, setSelectedProvider] = useState<string>('');

  const { data: statsData } = useQuery({
    queryKey: ['providers-stats'],
    queryFn: () => statsApi.getProvidersStats().then((res: any) => res.data),
    enabled: !!token,
    refetchInterval: 10000,
  });

  const { data: timeseriesData } = useQuery({
    queryKey: ['providers-timeseries', 60, 60],
    queryFn: () => statsApi.getProvidersTimeseries(60, 60).then((res: any) => res.data),
    enabled: !!token,
    refetchInterval: 10000,
  });

  const providerStats = statsData?.providers || [];
  const timeseries = timeseriesData?.points || [];

  if (!selectedProvider && providerStats.length > 0) {
    setSelectedProvider(providerStats[0].provider);
  }

  const filteredTimeseries = timeseries.filter((p: any) => p.provider === selectedProvider);

  return (
    <AppLayout
      title="Providers"
      subtitle="Monitor provider performance and health"
    >
      <div className="w-full space-y-6">
        {/* Provider Selector */}
        <div className="flex items-center gap-4">
          <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Provider:</label>
          <select
            value={selectedProvider}
            onChange={(e) => setSelectedProvider(e.target.value)}
            className="rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500 px-4 py-2 text-sm"
          >
            {providerStats.map((stat: any) => (
              <option key={stat.provider} value={stat.provider}>
                {stat.provider.toUpperCase()}
              </option>
            ))}
          </select>
        </div>

        {selectedProvider && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Requests Chart */}
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
              <div className="mb-4">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Requests over Time</h3>
                <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">Last 1 hour</p>
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={filteredTimeseries}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" className="dark:stroke-slate-700" />
                  <XAxis
                    dataKey="timestamp"
                    tickFormatter={(value) => new Date(value).toLocaleTimeString()}
                    stroke="#6b7280"
                    className="dark:stroke-slate-400"
                  />
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
                  <Line type="monotone" dataKey="requests" stroke="#6366f1" strokeWidth={2} dot={false} name="Requests" />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Errors Chart */}
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
              <div className="mb-4">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Errors over Time</h3>
                <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">Last 1 hour</p>
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={filteredTimeseries}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" className="dark:stroke-slate-700" />
                  <XAxis
                    dataKey="timestamp"
                    tickFormatter={(value) => new Date(value).toLocaleTimeString()}
                    stroke="#6b7280"
                    className="dark:stroke-slate-400"
                  />
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
                  <Legend />
                  <Bar dataKey="rate_limit_errors" stackId="a" fill="#f59e0b" name="Rate Limit" radius={[8, 8, 0, 0]} />
                  <Bar dataKey="transient_errors" stackId="a" fill="#ef4444" name="Transient" radius={[8, 8, 0, 0]} />
                  <Bar dataKey="client_errors" stackId="a" fill="#dc2626" name="Client" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
