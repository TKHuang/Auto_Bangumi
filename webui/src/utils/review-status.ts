export interface ReviewStatusInput {
  pendingReview?: boolean;
  previewLoaded: boolean;
  previewLoading?: boolean;
  torrents: readonly { filter: boolean }[];
}

export function needsBangumiRuleReview(input: ReviewStatusInput) {
  if (input.pendingReview) return true;
  if (!input.previewLoaded || input.previewLoading) return false;
  return input.torrents.every((torrent) => torrent.filter);
}
