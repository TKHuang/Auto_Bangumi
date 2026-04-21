export interface PendingItem {
  info_hash: string;
  raw_name: string;
  homepage: string | null;
  url: string;
  rss_id: number;
  first_seen_at: string | null;
  attempt_count: number;
  last_error: string | null;
  last_attempt_at: string | null;
}

export interface RetryResult {
  info_hash: string;
  resolved: boolean;
  mikan_bangumi_id?: number;
  mikan_subgroup_id?: number;
  error?: string;
}

export interface ResolveRequest {
  mikan_bangumi_url: string;
  title: string;
  season?: number;
}

export interface ResolveResult {
  info_hash: string;
  bangumi_id: number;
  mikan_bangumi_url: string;
  short_circuited: boolean;
}

export const apiPendingResolution = {
  async list(limit = 50, offset = 0) {
    const { data } = await axios.get<{
      items: PendingItem[];
      total: number;
    }>(`api/v1/pending-resolution/?limit=${limit}&offset=${offset}`);
    return data;
  },
  async retry(infoHash: string) {
    const { data } = await axios.post<RetryResult>(
      `api/v1/pending-resolution/${infoHash}/retry`
    );
    return data;
  },
  async resolve(infoHash: string, body: ResolveRequest) {
    const { data } = await axios.post<ResolveResult>(
      `api/v1/pending-resolution/${infoHash}/resolve`,
      body
    );
    return data;
  },
};
