import type { RSS } from '#/rss';
import type { Torrent } from '#/torrent';
import type { ApiSuccess } from '#/api';
import type { BangumiAPI } from '#/bangumi';

export const apiRSS = {
  async get() {
    const { data } = await axios.get<RSS[]>('api/v1/rss');
    return data!;
  },

  async add(
    rss: RSS,
    manualOverride?: { officialTitle?: string; season?: number; groupName?: string }
  ) {
    // Build query params for manual override
    const params = new URLSearchParams();
    if (manualOverride?.officialTitle) {
      params.append('official_title', manualOverride.officialTitle);
    }
    if (manualOverride?.season !== undefined) {
      params.append('season', String(manualOverride.season));
    }
    if (manualOverride?.groupName) {
      params.append('group_name', manualOverride.groupName);
    }

    const queryString = params.toString();
    const url = queryString
      ? `api/v1/rss/add?${queryString}`
      : 'api/v1/rss/add';

    const { data } = await axios.post<ApiSuccess>(url, rss);
    return data;
  },

  async delete(rss_id: number) {
    const { data } = await axios.delete<ApiSuccess>(
      `api/v1/rss/delete/${rss_id}`
    );
    return data!;
  },

  async deleteMany(rss_list: number[]) {
    const { data } = await axios.post<ApiSuccess>(
      `api/v1/rss/delete/many`,
      rss_list
    );
    return data!;
  },

  async disable(rss_id: number) {
    const { data } = await axios.patch<ApiSuccess>(
      `api/v1/rss/disable/${rss_id}`
    );
    return data!;
  },

  async disableMany(rss_list: number[]) {
    const { data } = await axios.post<ApiSuccess>(
      `api/v1/rss/disable/many`,
      rss_list
    );
    return data!;
  },

  async update(rss_id: number, rss: RSS) {
    const { data } = await axios.patch<ApiSuccess>(
      `api/v1/rss/update/${rss_id}`,
      rss
    );
    return data!;
  },

  async enableMany(rss_list: number[]) {
    const { data } = await axios.post<ApiSuccess>(
      `api/v1/rss/enable/many`,
      rss_list
    );
    return data!;
  },

  async refreshAll() {
    const { data } = await axios.get<ApiSuccess>('api/v1/rss/refresh/all');
    return data!;
  },

  async refresh(rss_id: number) {
    const { data } = await axios.get<ApiSuccess>(
      `api/v1/rss/refresh/${rss_id}`
    );
    return data!;
  },

  async getTorrent(rss_id: number) {
    const { data } = await axios.get<Torrent[]>(
      `api/v1/rss/torrent?rss_id=${rss_id}`
    );
    return data!;
  },

  async recreate(
    rss_id: number,
    manualOverride?: { officialTitle?: string; season?: number; groupName?: string }
  ) {
    // Build query params for manual override
    const params = new URLSearchParams();
    if (manualOverride?.officialTitle) {
      params.append('official_title', manualOverride.officialTitle);
    }
    if (manualOverride?.season !== undefined) {
      params.append('season', String(manualOverride.season));
    }
    if (manualOverride?.groupName) {
      params.append('group_name', manualOverride.groupName);
    }

    const queryString = params.toString();
    const url = queryString
      ? `api/v1/rss/recreate/${rss_id}?${queryString}`
      : `api/v1/rss/recreate/${rss_id}`;

    const { data } = await axios.post<BangumiAPI[]>(url);
    return data!;
  },

  async getPendingCount(rss_id: number) {
    const { data } = await axios.get<{ pending_count: number }>(
      `api/v1/rss/${rss_id}/pending-count`
    );
    return data!;
  },

  async getPendingBangumi(rss_id: number) {
    const { data } = await axios.get<BangumiAPI[]>(
      `api/v1/rss/${rss_id}/pending`
    );
    return data!;
  },
};
