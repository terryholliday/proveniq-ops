'use client';

/**
 * OpsDashboard - Real-time Ops asset dashboard with auto-polling
 * 
 * Industrial/Dark theme. Uses useLiveAsset pattern for:
 * - Hash-gated updates (no flicker)
 * - StrictMode safe polling
 * - Pause on hidden/offline
 * - Exponential backoff on error
 */

import React from 'react';
import { WidgetRenderer } from './widgets/WidgetRenderer';

// Types matching the api-client schema
interface AssetProjection {
  schema_version: string;
  requested_view: string;
  identity: {
    paid: string;
    name: string;
    category: string;
  };
  widgets: Array<{
    widget_type: string;
    priority: number;
    data: Record<string, unknown>;
  }>;
  projection_hash: string;
  profile_generated_at: string;
  capabilities?: string[];
}

interface UseLiveAssetResult {
  data: AssetProjection | null;
  isLoading: boolean;
  isPolling: boolean;
  isError: boolean;
  error: Error | null;
  lastHash: string | null;
  pollCount: number;
  refetch: () => Promise<void>;
}

interface OpsDashboardProps {
  assetId: string;
  intervalMs?: number;
  showDebugInfo?: boolean;
}

// Inline useLiveAsset implementation for Ops
// In production, import from '@proveniq/api-client'
function useLiveAsset(
  assetId: string,
  options: { view?: string; intervalMs?: number } = {}
): UseLiveAssetResult {
  const [data, setData] = React.useState<AssetProjection | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [error, setError] = React.useState<Error | null>(null);
  const [pollCount, setPollCount] = React.useState(0);
  const [lastHash, setLastHash] = React.useState<string | null>(null);

  const mountedRef = React.useRef(false);
  const initRef = React.useRef(false);
  const abortRef = React.useRef<AbortController | null>(null);
  const intervalRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const seqRef = React.useRef(0);
  const backoffRef = React.useRef(0);

  const coreUrl = process.env.NEXT_PUBLIC_CORE_API_URL ?? 'http://localhost:3010';
  const view = options.view ?? 'OPS';
  const intervalMs = options.intervalMs ?? 2000;

  const fetchAsset = React.useCallback(async () => {
    if (!assetId) return;

    abortRef.current?.abort();
    abortRef.current = new AbortController();
    const thisSeq = ++seqRef.current;

    try {
      const response = await fetch(
        `${coreUrl}/core/asset/${encodeURIComponent(assetId)}?view=${view}`,
        { signal: abortRef.current.signal }
      );

      if (thisSeq !== seqRef.current) return;
      if (!mountedRef.current) return;

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const json = await response.json();
      const newHash = json.projection_hash ?? json.canonical_hash_hex ?? '';

      // Hash gating - only update if hash changed
      if (newHash !== lastHash) {
        console.log(`[OpsDashboard] Hash changed: ${lastHash?.slice(0, 8) ?? 'null'} → ${newHash.slice(0, 8)}`);
        setData(json);
        setLastHash(newHash);
      } else {
        console.log(`[OpsDashboard] Hash unchanged (${newHash.slice(0, 8)}), skipping update`);
      }

      setError(null);
      setPollCount((c) => c + 1);
      backoffRef.current = 0; // Reset backoff on success
    } catch (err) {
      if (thisSeq !== seqRef.current) return;
      if (!mountedRef.current) return;
      if (err instanceof Error && err.name === 'AbortError') return;

      console.error('[OpsDashboard] Fetch error:', err);
      setError(err instanceof Error ? err : new Error(String(err)));

      // Exponential backoff
      backoffRef.current = Math.min(backoffRef.current === 0 ? 1000 : backoffRef.current * 2, 15000);
    } finally {
      if (mountedRef.current) {
        setIsLoading(false);
      }
    }
  }, [assetId, coreUrl, view, lastHash]);

  React.useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;
    mountedRef.current = true;

    console.log(`[OpsDashboard] Initializing for ${assetId}`);
    fetchAsset();

    const poll = () => {
      if (!mountedRef.current) return;
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return;
      if (typeof navigator !== 'undefined' && !navigator.onLine) return;

      fetchAsset();
    };

    const startPolling = () => {
      const delay = intervalMs + backoffRef.current + Math.random() * 250;
      intervalRef.current = setTimeout(() => {
        poll();
        startPolling();
      }, delay);
    };

    startPolling();

    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        fetchAsset();
      }
    };

    const handleOnline = () => fetchAsset();

    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', handleVisibility);
    }
    if (typeof window !== 'undefined') {
      window.addEventListener('online', handleOnline);
    }

    return () => {
      mountedRef.current = false;
      initRef.current = false;
      abortRef.current?.abort();
      if (intervalRef.current) clearTimeout(intervalRef.current);
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', handleVisibility);
      }
      if (typeof window !== 'undefined') {
        window.removeEventListener('online', handleOnline);
      }
    };
  }, [assetId, intervalMs, fetchAsset]);

  const refetch = React.useCallback(async () => {
    setLastHash(null);
    await fetchAsset();
  }, [fetchAsset]);

  return {
    data,
    isLoading,
    isPolling: intervalRef.current !== null,
    isError: error !== null,
    error,
    lastHash,
    pollCount,
    refetch,
  };
}

export function OpsDashboard({ assetId, intervalMs = 2000, showDebugInfo = false }: OpsDashboardProps) {
  const { data, isLoading, isPolling, isError, error, lastHash, pollCount, refetch } = useLiveAsset(assetId, {
    view: 'OPS',
    intervalMs,
  });

  const [isOnline, setIsOnline] = React.useState(true);

  React.useEffect(() => {
    if (typeof navigator !== 'undefined') {
      setIsOnline(navigator.onLine);
    }
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    if (typeof window !== 'undefined') {
      window.addEventListener('online', handleOnline);
      window.addEventListener('offline', handleOffline);
    }
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('online', handleOnline);
        window.removeEventListener('offline', handleOffline);
      }
    };
  }, []);

  if (isLoading && !data) {
    return (
      <div className="flex items-center justify-center h-48 bg-gray-900">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-500" />
        <span className="ml-3 text-gray-400">Loading asset data...</span>
      </div>
    );
  }

  if (isError && !data) {
    return (
      <div className="flex flex-col items-center justify-center h-48 bg-gray-900 text-red-400">
        <svg className="h-8 w-8 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <p className="font-medium">Failed to load asset</p>
        <p className="text-sm text-gray-500">{error?.message}</p>
        <button
          onClick={refetch}
          className="mt-4 px-4 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-300 hover:bg-gray-700"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 min-h-screen text-white p-6">
      {/* Status Bar */}
      {showDebugInfo && (
        <div className="flex items-center justify-between text-xs text-gray-500 bg-gray-800 px-4 py-2 rounded-lg mb-6 font-mono">
          <div className="flex items-center gap-6">
            <span className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${isOnline ? 'bg-green-500' : 'bg-red-500'}`} />
              {isOnline ? 'ONLINE' : 'OFFLINE'}
            </span>
            <span>
              POLLS: <span className="text-cyan-400">{pollCount}</span>
            </span>
            <span>
              HASH: <code className="bg-gray-700 px-1 rounded text-yellow-400">{lastHash?.slice(0, 8) ?? 'NONE'}</code>
            </span>
            {isPolling && (
              <span className="flex items-center gap-2 text-green-400">
                <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                LIVE
              </span>
            )}
          </div>
          <button
            onClick={refetch}
            disabled={isLoading}
            className="px-3 py-1 bg-gray-700 rounded text-gray-300 hover:bg-gray-600 disabled:opacity-50"
          >
            {isLoading ? '⟳' : '↻'} REFRESH
          </button>
        </div>
      )}

      {/* Asset Header - Industrial Style */}
      {data?.identity && (
        <div className="mb-6 border-l-4 border-cyan-500 pl-4">
          <h1 className="text-2xl font-bold text-white tracking-tight">{data.identity.name}</h1>
          <p className="text-sm text-gray-400 font-mono">
            {data.identity.category} • PAID: {data.identity.paid}
          </p>
          {data.capabilities && data.capabilities.length > 0 && (
            <div className="flex gap-2 mt-2">
              {data.capabilities.map((cap) => (
                <span key={cap} className="px-2 py-0.5 bg-gray-800 rounded text-xs text-cyan-400 font-mono">
                  {cap}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Widgets */}
      <WidgetRenderer widgets={data?.widgets ?? []} />
    </div>
  );
}

export default OpsDashboard;
