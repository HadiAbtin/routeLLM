import { useState, type FormEvent } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { AppLayout } from '../components/AppLayout';
import { useAuthStore } from '../store/authStore';
import { adminKeysApi, statsApi, type ProviderKeyCreate } from '../lib/api.js';
import { ChevronUp, ChevronsUpDown, Plus, X, Trash2 } from 'lucide-react';
import { cn } from '../lib/utils.js';
import { useNavigate } from 'react-router-dom';

interface KeyStat {
  id: string;
  provider: string;
  display_name: string;
  status: string;
  environment?: string;
  priority?: number;
  cooling_until: string | null;
  last_used_at: string | null;
  last_error_at: string | null;
  error_count_recent: number;
  success_count_last_1h: number;
  error_count_last_1h: number;
  requests_last_1h: number;
  max_rpm: number | null;
  max_tpm: number | null;
  created_at?: string | null;
  updated_at?: string | null;
}

const AVAILABLE_PROVIDERS = ['openai', 'anthropic', 'deepseek', 'gemini'] as const;

export function Keys() {
  const { token } = useAuthStore();
  const navigate = useNavigate();
  const [selectedProvider, setSelectedProvider] = useState<string>('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [deleteKeyId, setDeleteKeyId] = useState<string | null>(null);
  const [createForm, setCreateForm] = useState({
    provider: 'openai',
    display_name: '',
    api_key: '',
    priority: '10',
    max_rpm: '',
    max_tpm: '',
  });

  const queryClient = useQueryClient();

  const { data: keysData } = useQuery({
    queryKey: ['key-stats'],
    queryFn: async () => {
      try {
        const response = await statsApi.getKeyStats();
        console.log('Keys API Response:', response);
        return response.data;
      } catch (error: any) {
        console.error('Keys API Error:', error);
        throw error;
      }
    },
    enabled: !!token,
    refetchInterval: 10000,
  });

  const { data: errorsData } = useQuery({
    queryKey: ['key-errors'],
    queryFn: async () => {
      try {
        const response = await statsApi.getKeyErrors();
        console.log('Key Errors API Response:', response);
        return response.data;
      } catch (error: any) {
        console.error('Key Errors API Error:', error);
        throw error;
      }
    },
    enabled: !!token,
    refetchInterval: 10000,
  });

  const keys: KeyStat[] = keysData?.keys || [];
  const keyErrors = errorsData?.keys || [];

  // Debug logging
  console.log('Keys Data:', {
    keysData,
    errorsData,
    keys,
    keyErrors,
  });

  const createKeyMutation = useMutation({
    mutationFn: async (payload: ProviderKeyCreate) => {
      return adminKeysApi.createKey(payload);
    },
    onSuccess: () => {
      // Refresh stats after successful creation
      queryClient.invalidateQueries({ queryKey: ['key-stats'] });
      queryClient.invalidateQueries({ queryKey: ['key-errors'] });
      setIsCreateModalOpen(false);
      setCreateForm({
        provider: 'openai',
        display_name: '',
        api_key: '',
        priority: '10',
        max_rpm: '',
        max_tpm: '',
      });
    },
  });

  const deleteKeyMutation = useMutation({
    mutationFn: async (keyId: string) => {
      return adminKeysApi.deleteKey(keyId);
    },
    onSuccess: () => {
      // Refresh stats after successful deletion
      queryClient.invalidateQueries({ queryKey: ['key-stats'] });
      queryClient.invalidateQueries({ queryKey: ['key-errors'] });
      setDeleteKeyId(null);
    },
  });

  const handleCreateSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!createForm.display_name.trim() || !createForm.api_key.trim()) {
      return;
    }

    const payload: ProviderKeyCreate = {
      provider: createForm.provider,
      display_name: createForm.display_name.trim(),
      api_key: createForm.api_key.trim(),
      status: 'active',
      priority: createForm.priority ? Number(createForm.priority) : undefined,
      max_rpm: createForm.max_rpm ? Number(createForm.max_rpm) : undefined,
      max_tpm: createForm.max_tpm ? Number(createForm.max_tpm) : undefined,
    };

    createKeyMutation.mutate(payload);
  };

  const isSubmitting = createKeyMutation.isPending;
  const createError = (createKeyMutation.error as any)?.message as string | undefined;

  if (!selectedProvider && keys.length > 0) {
    setSelectedProvider(keys[0].provider);
  }

  const filteredKeys = keys.filter((k: KeyStat) => !selectedProvider || k.provider === selectedProvider);
  const filteredErrors = keyErrors.filter((k: any) => !selectedProvider || k.provider === selectedProvider);

  const statusColors: Record<string, { bg: string; text: string; dot: string }> = {
    active: { bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-800 dark:text-green-300', dot: 'bg-green-500' },
    cooling_down: { bg: 'bg-yellow-100 dark:bg-yellow-900/30', text: 'text-yellow-800 dark:text-yellow-300', dot: 'bg-yellow-500' },
    disabled: { bg: 'bg-slate-100 dark:bg-slate-700', text: 'text-slate-800 dark:text-slate-300', dot: 'bg-slate-400' },
  };

  return (
    <AppLayout
      title="Keys"
      subtitle="Manage and monitor your provider keys"
    >
      <div className="w-full space-y-6">
        {/* Header / Filter + Create */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <label className="text-sm font-medium text-slate-700 dark:text-slate-300">Filter by Provider:</label>
            <select
              value={selectedProvider}
              onChange={(e) => setSelectedProvider(e.target.value)}
              className="rounded-lg border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm focus:border-indigo-500 focus:ring-indigo-500 px-4 py-2 text-sm"
            >
              <option value="">All Providers</option>
              {Array.from(new Set(keys.map((k) => k.provider))).map((provider) => (
                <option key={provider} value={provider}>
                  {provider.toUpperCase()}
                </option>
              ))}
            </select>
          </div>

          <button
            type="button"
            onClick={() => setIsCreateModalOpen(true)}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-indigo-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-50 dark:focus-visible:ring-offset-slate-900 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Key
          </button>
        </div>

        {/* Key Health Table */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 flex items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Key Health</h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Monitor status and usage of your provider keys
              </p>
            </div>
          </div>
          <div className="overflow-x-auto scrollbar-thin">
            <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700">
              <thead className="bg-slate-50 dark:bg-slate-800/50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                    <div className="flex items-center gap-1">
                      Display Name
                      <ChevronUp className="w-4 h-4" />
                    </div>
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                    <div className="flex items-center gap-1">
                      Key ID
                      <ChevronsUpDown className="w-4 h-4" />
                    </div>
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Provider</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">STATUS</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Environment</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Priority</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Last Used</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Errors</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Requests (1h)</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Max RPM</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Max TPM</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">Created</th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">ACTIONS</th>
                </tr>
              </thead>
              <tbody className="bg-white dark:bg-slate-800 divide-y divide-slate-200 dark:divide-slate-700">
                {filteredKeys.map((key) => {
                  const statusStyle = statusColors[key.status] || statusColors.disabled;
                  return (
                    <tr
                      key={key.id}
                      className="hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors cursor-pointer"
                      onClick={() => navigate(`/keys/${key.id}`)}
                    >
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-slate-900 dark:text-white">{key.display_name}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600 dark:text-slate-400 font-mono">{key.id.substring(0, 8)}...</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600 dark:text-slate-400 font-medium uppercase">{key.provider}</td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={cn("inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-full", statusStyle.bg, statusStyle.text)}>
                          <span className={cn("w-1.5 h-1.5 rounded-full", statusStyle.dot)}></span>
                          {key.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600 dark:text-slate-400">{key.environment || 'prod'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600 dark:text-slate-400">{key.priority ?? 'N/A'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600 dark:text-slate-400">
                        {key.last_used_at ? new Date(key.last_used_at).toLocaleString() : <span className="text-slate-400">Never</span>}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900 dark:text-white font-medium">{key.error_count_recent}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900 dark:text-white font-medium">{key.requests_last_1h}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600 dark:text-slate-400">{key.max_rpm ?? 'N/A'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600 dark:text-slate-400">{key.max_tpm ?? 'N/A'}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600 dark:text-slate-400">
                        {key.created_at ? new Date(key.created_at).toLocaleDateString() : <span className="text-slate-400">N/A</span>}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setDeleteKeyId(key.id);
                            }}
                            className="inline-flex items-center gap-1.5 text-red-600 dark:text-red-400 hover:text-red-700 dark:hover:text-red-300 font-medium transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="px-6 py-3 bg-slate-50 dark:bg-slate-800/50 border-t border-slate-200 dark:border-slate-700">
            <p className="text-sm text-slate-600 dark:text-slate-400">Showing {filteredKeys.length} of {keys.length} keys</p>
          </div>
        </div>

        {/* Error Chart */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 p-6">
          <div className="mb-4">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Errors per Key</h3>
            <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">Last 1 hour</p>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={filteredErrors}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" className="dark:stroke-slate-700" />
              <XAxis dataKey="display_name" angle={-45} textAnchor="end" height={100} stroke="#6b7280" className="dark:stroke-slate-400" />
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
              <Bar dataKey="rate_limit_errors_last_1h" stackId="a" fill="#f59e0b" name="Rate Limit" radius={[8, 8, 0, 0]} />
              <Bar dataKey="transient_errors_last_1h" stackId="a" fill="#ef4444" name="Transient" radius={[8, 8, 0, 0]} />
              <Bar dataKey="client_errors_last_1h" stackId="a" fill="#dc2626" name="Client" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Create Key Modal */}
        {isCreateModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm">
            <div className="w-full max-w-lg rounded-2xl bg-white dark:bg-slate-900 shadow-2xl border border-slate-200 dark:border-slate-700">
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Create New Key</h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Keys are stored securely on the backend. The UI never persists keys in the browser.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => !isSubmitting && setIsCreateModalOpen(false)}
                  className="rounded-full p-1.5 text-slate-400 hover:text-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleCreateSubmit} className="px-6 py-5 space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                      Provider
                    </label>
                    <select
                      value={createForm.provider}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, provider: e.target.value }))}
                      className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white px-3 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    >
                      {AVAILABLE_PROVIDERS.map((provider) => (
                        <option key={provider} value={provider}>
                          {provider.toUpperCase()}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                      Display Name
                    </label>
                    <input
                      type="text"
                      value={createForm.display_name}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, display_name: e.target.value }))}
                      placeholder="e.g. OpenAI Primary Key"
                      className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white px-3 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      required
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                    API Key
                  </label>
                  <input
                    type="password"
                    value={createForm.api_key}
                    onChange={(e) => setCreateForm((prev) => ({ ...prev, api_key: e.target.value }))}
                    placeholder="sk-..."
                    className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white px-3 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 font-mono"
                    required
                  />
                  <p className="text-[11px] text-slate-500 dark:text-slate-500">
                    The key is sent once to the backend over HTTPS and never stored in the browser.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                      Priority
                    </label>
                    <input
                      type="number"
                      value={createForm.priority}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, priority: e.target.value }))}
                      className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white px-3 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                      Max RPM
                    </label>
                    <input
                      type="number"
                      value={createForm.max_rpm}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, max_rpm: e.target.value }))}
                      className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white px-3 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      placeholder="optional"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                      Max TPM
                    </label>
                    <input
                      type="number"
                      value={createForm.max_tpm}
                      onChange={(e) => setCreateForm((prev) => ({ ...prev, max_tpm: e.target.value }))}
                      className="w-full rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 text-sm text-slate-900 dark:text-white px-3 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      placeholder="optional"
                    />
                  </div>
                </div>

                {createError && (
                  <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300">
                    {createError}
                  </div>
                )}

                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => !isSubmitting && setIsCreateModalOpen(false)}
                    className="inline-flex items-center justify-center rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={
                      isSubmitting ||
                      !createForm.display_name.trim() ||
                      !createForm.api_key.trim()
                    }
                    className={cn(
                      'inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-semibold shadow-sm transition-colors',
                      isSubmitting || !createForm.display_name.trim() || !createForm.api_key.trim()
                        ? 'bg-indigo-300 text-white cursor-not-allowed'
                        : 'bg-indigo-600 text-white hover:bg-indigo-500'
                    )}
                  >
                    {isSubmitting ? 'Creating…' : 'Create Key'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Delete Confirmation Modal */}
        {deleteKeyId && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm">
            <div className="w-full max-w-md rounded-2xl bg-white dark:bg-slate-900 shadow-2xl border border-slate-200 dark:border-slate-700">
              <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800">
                <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Delete Key</h2>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  This action cannot be undone
                </p>
              </div>

              <div className="px-6 py-5">
                <p className="text-sm text-slate-700 dark:text-slate-300">
                  Are you sure you want to delete this key? This will permanently remove the key from the system.
                </p>
                {deleteKeyId && (
                  <div className="mt-4 p-3 rounded-lg bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
                    <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">Key ID:</p>
                    <p className="text-sm font-mono text-slate-900 dark:text-white">{deleteKeyId.substring(0, 8)}...</p>
                  </div>
                )}
              </div>

              <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-200 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setDeleteKeyId(null)}
                  disabled={deleteKeyMutation.isPending}
                  className="inline-flex items-center justify-center rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 px-4 py-2 text-sm font-medium text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => deleteKeyMutation.mutate(deleteKeyId)}
                  disabled={deleteKeyMutation.isPending}
                  className={cn(
                    'inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-semibold shadow-sm transition-colors',
                    deleteKeyMutation.isPending
                      ? 'bg-red-300 text-white cursor-not-allowed'
                      : 'bg-red-600 text-white hover:bg-red-500'
                  )}
                >
                  {deleteKeyMutation.isPending ? 'Deleting…' : 'Delete Key'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
