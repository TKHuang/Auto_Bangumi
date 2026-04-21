import { omit } from 'radash';
import type { BangumiAPI, BangumiRule } from '#/bangumi';
import type { ApiSuccess } from '#/api';

export const apiBangumi = {
  /**
   * 获取所有 bangumi 数据
   * @returns 所有 bangumi 数据
   */
  async getAll() {
    const { data } = await axios.get<BangumiAPI[]>('api/v1/bangumi/get/all');
    const result: BangumiRule[] = data.map((bangumi) => ({
      ...bangumi,
      filter: bangumi.filter.split(','),
      rss_link: bangumi.rss_link.split(','),
    }));
    return result;
  },

  /**
   * 获取指定 bangumiId 的规则
   * @param bangumiId  bangumi id
   * @returns 指定 bangumi 的规则
   */
  async getRule(bangumiId: number) {
    const { data } = await axios.get<BangumiAPI>(
      `api/v1/bangumi/get/${bangumiId}`
    );
    const result: BangumiRule = {
      ...data,
      filter: data.filter.split(','),
      rss_link: data.rss_link.split(','),
    };
    return result;
  },

  /**
   * 更新指定 bangumiId 的规则
   * @param bangumiId - 需要更新的 bangumi 的 id
   * @param bangumiRule
   * @returns axios 请求返回的数据
   */
  async updateRule(bangumiId: number, bangumiRule: BangumiRule) {
    const rule: BangumiAPI = {
      ...bangumiRule,
      filter: bangumiRule.filter.join(','),
      rss_link: bangumiRule.rss_link.join(','),
    };
    const post = omit(rule, ['id']);
    const { data } = await axios.patch<ApiSuccess>(
      `api/v1/bangumi/update/${bangumiId}`,
      post,
      { suppressErrorMessage: true } as any
    );
    return data;
  },

  /**
   * 删除指定 bangumiId 的数据库规则，会在重新匹配到后重建
   * @param bangumiId - 需要删除的 bangumi 的 id
   * @param file - 是否同时删除关联文件。
   * @returns axios 请求返回的数据
   */
  async deleteRule(bangumiId: number | number[], file: boolean) {
    const url = 'api/v1/bangumi/delete';

    if (typeof bangumiId === 'number') {
      const { data } = await axios.delete<ApiSuccess>(`${url}/${bangumiId}`, {
        params: { file },
      });
      return data;
    } else {
      // DELETE /bangumi/delete with body containing array of IDs
      const { data } = await axios.delete<ApiSuccess>(url, {
        data: bangumiId,
        params: { file },
      });
      return data;
    }
  },

  /**
   * 删除指定 bangumiId 的规则。如果 file 为 true，则同时删除关联文件。
   * @param bangumiId - 需要删除规则的 bangumi 的 id。
   * @param file - 是否同时删除关联文件。
   * @returns axios 请求返回的数据
   */
  async disableRule(bangumiId: number | number[], file: boolean) {
    const url = 'api/v1/bangumi/disable';

    if (typeof bangumiId === 'number') {
      const { data } = await axios.delete<ApiSuccess>(`${url}/${bangumiId}`, {
        params: { file },
      });
      return data;
    } else {
      // DELETE /bangumi/disable with body containing array of IDs
      const { data } = await axios.delete<ApiSuccess>(url, {
        data: bangumiId,
        params: { file },
      });
      return data;
    }
  },

  /**
   * 启用指定 bangumiId 的规则
   * @param bangumiId - 需要启用的 bangumi 的 id
   */
  async enableRule(bangumiId: number) {
    const { data } = await axios.patch<ApiSuccess>(
      `api/v1/bangumi/enable/${bangumiId}`
    );
    return data;
  },

  /**
   * 重置所有 bangumi 数据
   */
  async resetAll() {
    const { data } = await axios.delete<ApiSuccess>('api/v1/bangumi/reset/all');
    return data;
  },

  /**
   * 刷新所有没有海报的 bangumi 海报
   */
  async refreshPoster() {
    const { data } = await axios.post<ApiSuccess>(
      'api/v1/bangumi/refresh/poster/all'
    );
    return data;
  },

  /**
   * 获取指定 bangumiId 的种子状态
   * @param bangumiId
   */
  async getTorrentStatus(bangumiId: number) {
    const { data } = await axios.get<any[]>(
      `api/v1/bangumi/torrent/${bangumiId}`
    );
    return data;
  },

  /**
   * 重新下载指定 torrentId 的种子
   * @param torrentId
   */
  async downloadTorrent(torrent_id: number) {
    const { data } = await axios.post<ApiSuccess>(
      `api/v1/bangumi/torrent/download`,
      null,
      {
        params: {
          torrent_id,
        },
      }
    );
    return data;
  },

  /**
   * 激活待审核的 bangumi
   * @param bangumiId - 需要激活的 bangumi 的 id
   * @param filter - 可选的过滤器字符串
   * @returns axios 请求返回的数据
   */
  async activatePending(
    bangumiId: number,
    filter?: string,
    includedHashes?: string[],
    excludedHashes?: string[]
  ) {
    const body: Record<string, unknown> = {};
    if (filter !== undefined) body.filter = filter;
    if (includedHashes?.length) body.included_hashes = includedHashes;
    if (excludedHashes?.length) body.excluded_hashes = excludedHashes;
    const { data } = await axios.post<ApiSuccess>(
      `api/v1/bangumi/${bangumiId}/activate`,
      body
    );
    return data;
  },

  /**
   * 重新触发指定 bangumiId 的重命名流程
   * @param bangumiId - 需要重新命名的 bangumi 的 id
   * @returns axios 请求返回的数据
   */
  async retriggerRename(bangumiId: number) {
    const { data } = await axios.post<ApiSuccess>(
      `api/v1/bangumi/${bangumiId}/retrigger-rename`,
      null,
      { suppressErrorMessage: true } as any
    );
    return data;
  },
};
