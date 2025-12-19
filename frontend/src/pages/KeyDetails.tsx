import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { AppLayout } from '../components/AppLayout';
import { statsApi } from '../lib/api.js';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { ArrowLeft, KeyRound } from 'lucide-react';
import { useMemo, useState } from 'react';

interface KeyTimeseriesPoint {
  ts: string;
  tokens: number;
}

export function KeyDetails() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [timePeriod, setTimePeriod] = useState<'hour' | 'day' | 'week' | 'month'>('hour');

  // Calculate window_minutes and step_seconds based on selected period
  const { windowMinutes, stepSeconds } = useMemo(() => {
    switch (timePeriod) {
      case 'hour':
        return { windowMinutes: 60, stepSeconds: 300 }; // 1 hour, 5-minute buckets
      case 'day':
        return { windowMinutes: 1440, stepSeconds: 3600 }; // 24 hours, 1-hour buckets
      case 'week':
        return { windowMinutes: 10080, stepSeconds: 86400 }; // 7 days, 1-day buckets
      case 'month':
        return { windowMinutes: 43200, stepSeconds: 86400 }; // 30 days, 1-day buckets
      default:
        return { windowMinutes: 60, stepSeconds: 300 };
    }
  }, [timePeriod]);

  const { data, isLoading, error } = useQuery({
    queryKey: ['key-timeseries', id, timePeriod, windowMinutes, stepSeconds],
    enabled: !!id,
    queryFn: async () => {
      const response = await statsApi.getKeyTimeseries(id!, windowMinutes, stepSeconds);
      return response.data as { points: KeyTimeseriesPoint[] };
    },
    refetchInterval: 10000,
  });

  const chartData = useMemo(() => {
    const points = data?.points ?? [];
    return points.map((p) => {
      const date = new Date(p.ts);
      let tsLabel: string;
      
      if (timePeriod === 'hour') {
        tsLabel = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      } else if (timePeriod === 'day') {
        tsLabel = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      } else if (timePeriod === 'week' || timePeriod === 'month') {
        tsLabel = date.toLocaleDateString([], { month: 'short', day: 'numeric' });
      } else {
        tsLabel = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      }
      
      return {
        tsLabel,
      tokens: p.tokens,
      };
    });
  }, [data, timePeriod]);

  return (
    <AppLayout
      title="Key Usage"
      subtitle="Token usage over time for selected provider key"
    >
      <div className="w-full space-y-6">
        <div className="flex items-center justify-between gap-3">
          <button
            type="button"
            onClick={() => navigate('/keys')}
            className="inline-flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Keys
          </button>
          <div className="inline-flex items-center gap-2 rounded-full bg-slate-100 dark:bg-slate-800 px-3 py-1 text-xs text-slate-600 dark:text-slate-300">
            <KeyRound className="w-3 h-3" />
            <span className="font-mono">
              {id ? id.substring(0, 8) + '…' : ''}
            </span>
          </div>
        </div>

        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                Token Usage Over Time
              </h2>
              <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">
                Tokens consumed by this key
              </p>
            </div>
            <select
              value={timePeriod}
              onChange={(e) => setTimePeriod(e.target.value as 'hour' | 'day' | 'week' | 'month')}
              className="px-3 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="hour">Last Hour</option>
              <option value="day">Last Day</option>
              <option value="week">Last Week</option>
              <option value="month">Last Month</option>
            </select>
          </div>

          {isLoading ? (
            <div className="h-64 flex items-center justify-center text-sm text-slate-500 dark:text-slate-400">
              Loading timeseries…
            </div>
          ) : error ? (
            <div className="h-64 flex items-center justify-center text-sm text-red-600 dark:text-red-400">
              Failed to load timeseries data
            </div>
          ) : chartData.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-sm text-slate-400">
              No token usage recorded for this key in the selected window.
            </div>
          ) : (
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ left: 0, right: 0, top: 10, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" className="dark:stroke-slate-700" />
                  <XAxis
                    dataKey="tsLabel"
                    stroke="#6b7280"
                    className="dark:stroke-slate-400"
                    tickMargin={8}
                  />
                  <YAxis
                    stroke="#6b7280"
                    className="dark:stroke-slate-400"
                    tickMargin={8}
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      border: '1px solid #1f2937',
                      borderRadius: 12,
                      color: '#e5e7eb',
                      padding: 12,
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="tokens"
                    stroke="#22c55e"
                    strokeWidth={2}
                    fill="#bbf7d0"
                    fillOpacity={0.6}
                    name="Tokens"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}


