import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
// @ts-ignore
import { AppLayout } from '../components/AppLayout';
import { useAuthStore } from '../store/authStore';
import { statsApi } from '../lib/api.js';
import { TrendingUp, AlertCircle, CheckCircle2 } from 'lucide-react';
import { useState } from 'react';


interface ProviderStat {
  provider: string;
  total_requests_last_15m: number;
  total_requests_last_1h: number;
  success_count_last_15m: number;
  error_count_last_15m: number;
  active_keys: number;
  cooling_keys: number;
  disabled_keys: number;
}

interface KeyStat {
  id: string;
  provider: string;
  display_name: string;
  status: string;
  cooling_until: string | null;
  last_used_at: string | null;
  last_error_at: string | null;
  error_count_recent: number;
  success_count_last_1h: number;
  error_count_last_1h: number;
  requests_last_1h: number;
  max_rpm: number | null;
  max_tpm: number | null;
}

export function Dashboard() {
  const { token } = useAuthStore();
  const [tokenPeriod, setTokenPeriod] = useState<'hour' | 'day' | 'week' | 'month'>('hour');

  const { data: statsData, isLoading: statsLoading, error: statsError } = useQuery({
    queryKey: ['providers-stats'],
    queryFn: async () => {
      try {
        const response = await statsApi.getProvidersStats();
        // Ensure data structure is correct
        const data = response.data;
        if (data && typeof data === 'object') {
          // If data.providers exists, ensure it's an array
          if (data.providers && !Array.isArray(data.providers)) {
            return { ...data, providers: [] };
          }
          // Ensure providers array contains only valid objects
          if (Array.isArray(data.providers)) {
            data.providers = data.providers.filter((item: any) =>
              item && typeof item === 'object' && 'provider' in item && typeof item.provider === 'string'
            );
          }
        }
        return data;
      } catch (error: any) {
        throw error;
      }
    },
    enabled: !!token,
    refetchInterval: 10000,
    retry: 2,
  });


  const { data: keysData } = useQuery({
    queryKey: ['key-stats'],
    queryFn: async () => {
      try {
        const response = await statsApi.getKeyStats();
        const data = response.data;
        // Ensure data structure is correct
        if (data && typeof data === 'object') {
          // If data.keys exists, ensure it's an array
          if (data.keys && !Array.isArray(data.keys)) {
            return { ...data, keys: [] };
          }
        }
        return data;
      } catch (error: any) {
        throw error;
      }
    },
    enabled: !!token,
    refetchInterval: 10000,
  });

  const { data: recentErrorsData } = useQuery({
    queryKey: ['recent-errors'],
    queryFn: async () => {
      try {
        const response = await statsApi.getRecentErrors(20);
        return response.data;
      } catch (error: any) {
        return { errors: [] };
      }
    },
    enabled: !!token,
    refetchInterval: 10000,
  });

  const { data: tokensData, isLoading: tokensLoading } = useQuery({
    queryKey: ['provider-tokens', tokenPeriod],
    queryFn: async () => {
      try {
        const response = await statsApi.getProviderTokens(tokenPeriod);

        // Always ensure we have a valid response structure
        if (!response || !response.data) {
          return { providers: [] };
        }

        const data = response.data;

        // Force to object if needed
        if (typeof data !== 'object' || data === null) {
          return { providers: [] };
        }

        // Extract providers array safely
        let providersArray: any[] = [];

        if (Array.isArray(data)) {
          // If data is directly an array, wrap it
          providersArray = data;
        } else if (data && typeof data === 'object' && 'providers' in data) {
          // Normal case: data.providers
          if (Array.isArray(data.providers)) {
            providersArray = data.providers;
          }
        }

        // Validate and sanitize each provider entry
        const validProviders = providersArray
          .filter((item: any) => {
            // Must be an object
            if (!item || typeof item !== 'object' || Array.isArray(item)) {
              return false;
            }
            // Must have provider as string
            if (!('provider' in item) || typeof item.provider !== 'string') {
              return false;
            }
            return true;
          })
          .map((item: any) => {
            // Sanitize each field to ensure proper types
            return {
              provider: String(item.provider || ''),
              total_tokens: Number(item.total_tokens || 0),
              period: String(item.period || tokenPeriod)
            };
          });

        return { providers: validProviders };
      } catch (error: any) {
        // On error, return empty array
        return { providers: [] };
      }
    },
    enabled: !!token,
    refetchInterval: 10000,
  });

  // Ensure we always have arrays, not objects - with strict validation
  const providerStats: ProviderStat[] = (() => {
    try {
      if (!statsData) {
        return [];
      }
      if (typeof statsData !== 'object') {
        return [];
      }
      if (Array.isArray(statsData.providers)) {
        const filtered = statsData.providers
          .filter((item: any) => {
            if (!item || typeof item !== 'object') {
              return false;
            }
            if (!('provider' in item)) {
              return false;
            }
            if (typeof item.provider !== 'string') {
              return false;
            }
            // Ensure all numeric fields are numbers
            const numericFields = ['total_requests_last_15m', 'total_requests_last_1h', 'success_count_last_15m', 'error_count_last_15m', 'active_keys', 'cooling_keys', 'disabled_keys'];
            for (const field of numericFields) {
              if (field in item && typeof item[field] !== 'number') {
                item[field] = Number(item[field]) || 0;
              }
            }
            return true;
          });
        return filtered;
      }
      if (Array.isArray(statsData)) {
        return statsData.filter((item: any) => item && typeof item === 'object' && 'provider' in item);
      }
    } catch (e) {
      // Silent error handling
    }
    return [];
  })();

  const keys = (() => {
    try {
      if (!keysData || typeof keysData !== 'object') return [];
      if (Array.isArray(keysData.keys)) {
        return keysData.keys.filter((item: any) => {
          if (!item || typeof item !== 'object') return false;
          if (!('id' in item) || typeof item.id !== 'string') return false;
          return true;
        });
      }
      if (Array.isArray(keysData)) {
        return keysData.filter((item: any) => item && typeof item === 'object' && 'id' in item);
      }
    } catch (e) {
      // Silent error handling
    }
    return [];
  })();

  // Extract tokens providers - simplified and safe
  const tokensProviders: Array<{ provider: string; total_tokens: number }> = (() => {
    // Default to empty array
    if (!tokensData || typeof tokensData !== 'object') {
      return [];
    }

    // Get providers array
    const providers = Array.isArray(tokensData)
      ? tokensData
      : (tokensData.providers && Array.isArray(tokensData.providers)
        ? tokensData.providers
        : []);

    // Map to safe format
    return providers
      .filter((item: any) => item && typeof item === 'object' && !Array.isArray(item))
      .map((item: any) => ({
        provider: String(item.provider || ''),
        total_tokens: Number(item.total_tokens || 0)
      }))
      .filter((item) => item.provider.length > 0);
  })();

  const getProviderColor = (provider: string): string => {
    const colors: Record<string, string> = {
      openai: '#10a37f',
      anthropic: '#d97757',
      deepseek: '#6366f1',
      gemini: '#4285f4',
    };
    return colors[provider.toLowerCase()] || '#6366f1';
  };

  // Debug logging before render
  return (
    <AppLayout
      title="Route LLM Gateway Dashboard"
      subtitle="Real-time monitoring of provider health and key usage"
      autoRefresh={true}
      onAutoRefreshToggle={() => { }}
    >
      <div className="w-full space-y-6">
        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 w-full">
          {providerStats.length === 0 && !statsLoading ? (
            <div className="col-span-full bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-8 text-center">
              <p className="text-slate-600 dark:text-slate-400 mb-2">No providers configured</p>
              <p className="text-sm text-slate-500 dark:text-slate-500">Add provider keys via the Admin API to see statistics</p>
            </div>
          ) : (
            providerStats
              .map((stat: any) => {
                if (!stat || typeof stat !== 'object' || !stat.provider) {
                  return null;
                }
                // Ensure all stat properties are valid
                if (typeof stat.provider !== 'string') {
                  return null;
                }
                const totalRequests = Number(stat.total_requests_last_15m || 0);
                const errorCount = Number(stat.error_count_last_15m || 0);
                const errorRate = totalRequests > 0
                  ? (errorCount / totalRequests) * 100
                  : 0;

                const providerName = String(stat.provider || '');
                return (
                  <div
                    key={providerName}
                    className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6 hover:shadow-md transition-shadow"
                  >
                    {/* Card Header */}
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-xl flex items-center justify-center shadow-lg shadow-indigo-500/25">
                          <span className="text-white text-lg font-bold">{String(stat.provider || '').charAt(0).toUpperCase()}</span>
                        </div>
                        <div>
                          <h3 className="text-lg font-bold text-slate-900 dark:text-white">{String(stat.provider || '').toUpperCase()}</h3>
                          <p className="text-xs text-slate-500 dark:text-slate-400">Provider</p>
                        </div>
                      </div>
                      {errorRate < 5 ? (
                        <CheckCircle2 className="w-5 h-5 text-green-500" />
                      ) : (
                        <AlertCircle className="w-5 h-5 text-yellow-500" />
                      )}
                    </div>

                    {/* Main Metric */}
                    <div className="mb-4">
                      <div className="flex items-baseline gap-2">
                        <p className="text-3xl font-bold text-slate-900 dark:text-white">
                          {Number(stat.total_requests_last_15m || 0).toLocaleString()}
                        </p>
                        {Number(stat.total_requests_last_15m || 0) > 0 && (
                          <TrendingUp className="w-4 h-4 text-green-500" />
                        )}
                      </div>
                      <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">requests / 15m</p>
                    </div>

                    {/* Key Status */}
                    <div className="flex items-center gap-4 mb-4 pb-4 border-b border-slate-200 dark:border-slate-700">
                      <div className="flex items-center gap-1.5">
                        <div className="w-2 h-2 rounded-full bg-green-500"></div>
                        <span className="text-xs font-medium text-slate-600 dark:text-slate-400">{Number(stat.active_keys || 0)} active keys</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <div className="w-2 h-2 rounded-full bg-yellow-500"></div>
                        <span className="text-xs font-medium text-slate-600 dark:text-slate-400">{Number(stat.cooling_keys || 0)} cooling</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <div className="w-2 h-2 rounded-full bg-slate-400"></div>
                        <span className="text-xs font-medium text-slate-600 dark:text-slate-400">{Number(stat.disabled_keys || 0)} disabled</span>
                      </div>
                    </div>

                    {/* Keys List */}
                    {(() => {
                      const providerKeys = Array.isArray(keys)
                        ? keys.filter((k: any) => k && typeof k === 'object' && 'provider' in k && k.provider === stat.provider)
                        : [];
                      if (providerKeys.length === 0) return null;
                      return (
                        <div className="mb-4">
                          <p className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-2">Keys:</p>
                          <div className="space-y-1">
                            {providerKeys.slice(0, 3).map((key: any) => {
                              if (!key || !key.id || typeof key !== 'object') return null;
                              return (
                                <div key={String(key.id)} className="flex items-center justify-between text-xs">
                                  <span className="text-slate-600 dark:text-slate-400 truncate">{String(key.display_name || '')}</span>
                                  <span className={`px-2 py-0.5 rounded-full text-xs ${key.status === 'active' ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300' :
                                    key.status === 'cooling_down' ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300' :
                                      'bg-slate-100 dark:bg-slate-700 text-slate-800 dark:text-slate-300'
                                    }`}>
                                    {String(key.status || '')}
                                  </span>
                                </div>
                              );
                            })}
                            {providerKeys.length > 3 && (
                              <p className="text-xs text-slate-500 dark:text-slate-500">
                                +{providerKeys.length - 3} more
                              </p>
                            )}
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                );
              })
              .filter((item: any) => item !== null)
          )}
        </div>

        {/* Token Usage Cards */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Token Usage per Provider</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">Total tokens consumed</p>
            </div>
            <select
              value={tokenPeriod}
              onChange={(e) => setTokenPeriod(e.target.value as 'hour' | 'day' | 'week' | 'month')}
              className="px-3 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            >
              <option value="hour">Last Hour</option>
              <option value="day">Last Day</option>
              <option value="week">Last Week</option>
              <option value="month">Last Month</option>
            </select>
          </div>
          {tokensLoading ? (
            <div className="h-32 flex items-center justify-center text-slate-500 dark:text-slate-400">
              <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto mb-2"></div>
                <p>Loading...</p>
              </div>
            </div>
          ) : tokensProviders.length === 0 ? (
            <div className="h-32 flex items-center justify-center text-slate-400 border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-lg">
              <div className="text-center">
                <p className="text-sm">No token usage data</p>
                <p className="text-xs mt-1">Make some requests to see token statistics</p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {tokensProviders.map((item) => {
                const providerName = item.provider;
                const totalTokens = item.total_tokens;
                const color = getProviderColor(providerName) || '#6366f1';

                return (
                  <div
                    key={providerName}
                    className="bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-700 dark:to-slate-800 rounded-lg p-4 border border-slate-200 dark:border-slate-600"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-slate-600 dark:text-slate-400 uppercase">
                        {providerName}
                      </span>
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: color }}
                      />
                    </div>
                    <div className="flex items-baseline gap-2">
                      <p className="text-2xl font-bold text-slate-900 dark:text-white">
                        {totalTokens.toLocaleString()}
                      </p>
                      <span className="text-xs text-slate-500 dark:text-slate-400">tokens</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Error Rates Chart */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Error Rates</h3>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">Last 1 hour</p>
          </div>
          {statsLoading ? (
            <div className="h-64 flex items-center justify-center text-slate-500 dark:text-slate-400">
              <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto mb-2"></div>
                <p>Loading...</p>
              </div>
            </div>
          ) : statsError ? (
            <div className="h-64 flex items-center justify-center text-red-500">
              <div className="text-center">
                <AlertCircle className="w-8 h-8 mx-auto mb-2" />
                <p>Error loading data</p>
                <p className="text-xs mt-1">
                  {statsError instanceof Error
                    ? statsError.message
                    : typeof statsError === 'object' && statsError !== null && 'message' in statsError
                      ? String((statsError as any).message || 'Unknown error')
                      : 'Unknown error'}
                </p>
              </div>
            </div>
          ) : providerStats.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-slate-400 border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-lg">
              <div className="text-center">
                <p className="text-sm">No providers configured</p>
                <p className="text-xs mt-1">Add provider keys to see statistics</p>
              </div>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={300}>
              {(() => {
                const chartData = Array.isArray(providerStats) ? providerStats : [];
                if (!Array.isArray(chartData)) {
                  return <div className="text-center text-slate-500 p-4">Invalid chart data</div>;
                }
                return (
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" className="dark:stroke-slate-700" />
                    <XAxis dataKey="provider" stroke="#6b7280" className="dark:stroke-slate-400" />
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
                    <Bar dataKey="error_count_last_15m" fill="#ef4444" name="Errors" radius={[8, 8, 0, 0]} />
                    <Bar dataKey="success_count_last_15m" fill="#10b981" name="Success" radius={[8, 8, 0, 0]} />
                  </BarChart>
                );
              })()}
            </ResponsiveContainer>
          )}
        </div>

        {/* Keys Section */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">All Keys</h3>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">Provider keys status and health</p>
          </div>
          {keys.length === 0 ? (
            <div className="h-32 flex items-center justify-center text-slate-400 border-2 border-dashed border-slate-300 dark:border-slate-600 rounded-lg">
              <div className="text-center">
                <p className="text-sm">No keys configured</p>
                <p className="text-xs mt-1">Add provider keys via the Admin API</p>
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {keys.map((key: KeyStat) => {
                if (!key || typeof key !== 'object' || !key.id) {
                  return null;
                }
                const keyId = String(key.id || '');
                const statusColors: Record<string, { bg: string; text: string; dot: string }> = {
                  active: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-800 dark:text-green-300', dot: 'bg-green-500' },
                  cooling_down: { bg: 'bg-yellow-100 dark:bg-yellow-900/30', text: 'text-yellow-800 dark:text-yellow-300', dot: 'bg-yellow-500' },
                  disabled: { bg: 'bg-slate-100 dark:bg-slate-700', text: 'text-slate-800 dark:text-slate-300', dot: 'bg-slate-400' },
                };
                const statusStyle = statusColors[String(key.status || 'disabled')] || statusColors.disabled;
                if (!statusStyle || typeof statusStyle !== 'object') {
                  return null;
                }
                return (
                  <div key={keyId} className="border border-slate-200 dark:border-slate-700 rounded-lg p-4 hover:shadow-md transition-shadow">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-sm font-semibold text-slate-900 dark:text-white truncate">{String(key.display_name || '')}</h4>
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium rounded-full ${statusStyle.bg} ${statusStyle.text}`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${statusStyle.dot}`}></span>
                        {String(key.status || '')}
                      </span>
                    </div>
                    <div className="text-xs text-slate-600 dark:text-slate-400">
                      <p>Provider: <span className="font-medium">{String(key.provider || '').toUpperCase()}</span></p>
                      <p className="font-mono text-slate-500 dark:text-slate-500 mt-1">{String(key.id || '').substring(0, 8)}...</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Recent Errors */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Recent Errors</h3>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">Last 20 failed runs</p>
          </div>
          {recentErrorsData?.errors && Array.isArray(recentErrorsData.errors) && recentErrorsData.errors.length > 0 ? (
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {recentErrorsData.errors.map((error: any, idx: number) => {
                if (!error || typeof error !== 'object') return null;
                const errorKind = String(error.kind || 'transient');
                const kindColors: Record<string, string> = {
                  rate_limit: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-300',
                  client: 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300',
                  authentication: 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300',
                  transient: 'bg-orange-100 dark:bg-orange-900/30 text-orange-800 dark:text-orange-300',
                };
                const kindColor = kindColors[errorKind] || kindColors.transient;
                return (
                  <div key={idx} className="border border-slate-200 dark:border-slate-700 rounded-lg p-4">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`text-xs font-medium px-2 py-0.5 rounded ${kindColor}`}>
                            {errorKind.toUpperCase()}
                          </span>
                          <span className="text-sm font-semibold text-slate-900 dark:text-white">
                            {String(error.provider || '').toUpperCase()}
                          </span>
                          {error.key_display_name && (
                            <span className="text-xs text-slate-600 dark:text-slate-400">
                              ({String(error.key_display_name)})
                            </span>
                          )}
                        </div>
                        <p className="text-sm text-slate-700 dark:text-slate-300 mt-1">
                          {String(error.message || 'Unknown error')}
                        </p>
                      </div>
                      <span className="text-xs text-slate-500 dark:text-slate-400 ml-4">
                        {error.timestamp ? new Date(error.timestamp).toLocaleString() : 'Unknown time'}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-8 text-slate-500 dark:text-slate-400">
              <CheckCircle2 className="w-12 h-12 mx-auto mb-2 text-green-500 opacity-50" />
              <p>No recent errors</p>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
