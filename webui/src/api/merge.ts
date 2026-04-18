export interface MergeHistoryItem {
  id: number;
  winner_bangumi_id: number;
  loser_bangumi_id: number;
  merge_reason: string;
  merged_at: string | null;
  merged_by: string | null;
  undone_at: string | null;
  undone_by: string | null;
}

export const apiMerge = {
  async merge(winnerId: number, loserId: number, reason = 'manual') {
    const { data } = await axios.post<{
      history_id: number;
      winner_id: number;
      loser_id: number;
    }>('api/v1/bangumi/merge', { winner_id: winnerId, loser_id: loserId, reason });
    return data;
  },
  async listHistory(limit = 50, offset = 0) {
    const { data } = await axios.get<{
      items: MergeHistoryItem[];
      total: number;
    }>(`api/v1/merge-history/?limit=${limit}&offset=${offset}`);
    return data;
  },
  async undo(historyId: number) {
    const { data } = await axios.post<{
      undone: boolean;
      history_id: number;
    }>(`api/v1/merge-history/${historyId}/undo`);
    return data;
  },
};
