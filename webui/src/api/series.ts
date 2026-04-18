export interface SeriesItem {
  id: number;
  canonical_title: string;
  normalized_title: string;
  season: number;
  cour_part: number | null;
  year: number | null;
  root_path: string;
  poster_url: string | null;
  default_filter: string | null;
  default_offset: number | null;
  pending_review: boolean;
}

export interface SeriesList {
  items: SeriesItem[];
  total: number;
}

export interface SeriesPatch {
  canonical_title?: string;
  root_path?: string;
  default_filter?: string;
  default_offset?: number;
  poster_url?: string;
}

export const apiSeries = {
  async list(limit = 50, offset = 0) {
    const { data } = await axios.get<SeriesList>(
      `api/v1/series/?limit=${limit}&offset=${offset}`
    );
    return data;
  },
  async get(id: number) {
    const { data } = await axios.get<SeriesItem>(`api/v1/series/${id}`);
    return data;
  },
  async patch(id: number, body: SeriesPatch) {
    const { data } = await axios.patch<SeriesItem>(`api/v1/series/${id}`, body);
    return data;
  },
};
