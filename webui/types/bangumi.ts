/**
 * @type `Bangumi` in backend/src/module/models/bangumi.py
 */
export interface BangumiRule {
  added: boolean;
  deleted: boolean;
  dpi: string;
  eps_collect: boolean;
  filter: string[];
  group_name: string;
  id: number;
  official_title: string;
  offset: number;
  poster_link: string | null;
  pending_review: boolean;
  rss_link: string[];
  rss_id: number | null;
  rule_name: string;
  save_path: string;
  season: number;
  season_raw: string;
  source: string | null;
  subtitle: string;
  title_raw: string;
  year: string | null;
  torrent_count: number;
  // null = downloader state not yet fetched (UI shows loading). The
  // /bangumi/get/all endpoint returns null; the slow /completion-status
  // call patches in real numbers when it resolves.
  completed_count: number | null;
}

export interface BangumiAPI extends Omit<BangumiRule, 'filter' | 'rss_link'> {
  filter: string;
  rss_link: string;
}

export interface SearchResult {
  order: number;
  value: BangumiRule;
}

export type BangumiUpdate = Omit<BangumiAPI, 'id'>;

export const ruleTemplate: BangumiRule = {
  added: false,
  deleted: false,
  dpi: '',
  eps_collect: false,
  filter: [],
  group_name: '',
  id: 0,
  official_title: '',
  offset: 0,
  poster_link: '',
  pending_review: false,
  rss_link: [],
  rss_id: null,
  rule_name: '',
  save_path: '',
  season: 1,
  season_raw: '',
  source: null,
  subtitle: '',
  title_raw: '',
  year: null,
  torrent_count: 0,
  completed_count: 0,
};
