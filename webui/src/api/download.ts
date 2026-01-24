import type { BangumiAPI, BangumiRule } from '#/bangumi';
import type { RSS } from '#/rss';
import type { ApiSuccess } from '#/api';

export const apiDownload = {
  /**
   * 解析 RSS 链接
   * @param rss_item - RSS 链接
   */
  async analysis(rss_item: RSS) {
    const { data } = await axios.post<BangumiAPI>(
      'api/v1/rss/analysis',
      rss_item
    );

    const result: BangumiRule = {
      ...data,
      filter: data.filter.split(','),
      rss_link: data.rss_link.split(','),
    };
    return result;
  },

  /**
   * 分析 RSS 种子
   * @param rss_item - RSS 链接
   * @param filter - 过滤器
   * @param titleRaw - 可选，仅返回解析后title_raw匹配的种子（用于聚合RSS）
   */
  async analysisTorrents(rss_item: RSS, filter: string, titleRaw?: string) {
    const params = new URLSearchParams();
    params.set('_filter', filter);
    if (titleRaw) {
      params.set('title_raw', titleRaw);
    }
    const { data } = await axios.post<
      { name: string; url: string; homepage: string; filter: boolean }[]
    >(`api/v1/rss/analysis/torrents?${params.toString()}`, rss_item);
    return data;
  },

  /**
   * 旧番
   * @param bangumiData - Bangumi 数据
   */
  async collection(bangumiData: BangumiRule) {
    const { id: _, ...rest } = bangumiData;
    const postData = {
      ...rest,
      filter: bangumiData.filter.join(','),
      rss_link: bangumiData.rss_link.join(','),
    };
    const { data } = await axios.post<ApiSuccess>(
      'api/v1/rss/collect',
      postData
    );
    return data;
  },

  /**
   * 新番
   * @param bangumiData - Bangumi 数据
   */
  async subscribe(bangumiData: BangumiRule, rss: RSS) {
    const { id: _, ...rest } = bangumiData;
    const bangumi = {
      ...rest,
      filter: bangumiData.filter.join(','),
      rss_link: bangumiData.rss_link.join(','),
    };
    const postData = {
      data: bangumi,
      rss,
    };
    const { data } = await axios.post<ApiSuccess>(
      'api/v1/rss/subscribe',
      postData
    );
    return data;
  },
};
