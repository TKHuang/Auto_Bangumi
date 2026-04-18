export interface MikanPendingItem {
  info_hash: string;
  raw_name: string;
  homepage: string | null;
  attempts: number;
  last_error: string | null;
  first_seen_at: string | null;
}

export interface MikanHealth {
  status: 'ok' | 'degraded' | 'down';
  pending_count: number;
  last_success_at: string | null;
  hours_since_last_success: number | null;
  consecutive_failures: number;
  pending_items: MikanPendingItem[];
}

export interface ConcurrencyHealth {
  rss_locks: Array<{ rss_id: number; held: boolean; held_duration_s: number }>;
  rate_limiters: Record<
    string,
    { queue: number; in_flight: number; req_per_min: number; error_rate_5m: number; degraded: boolean }
  >;
}

export const apiHealth = {
  async mikan() {
    const { data } = await axios.get<MikanHealth>('api/v1/health/mikan');
    return data;
  },
  async concurrency() {
    const { data } = await axios.get<ConcurrencyHealth>('api/v1/health/concurrency');
    return data;
  },
};
