export interface RSS {
  id: number;
  name: string;
  url: string;
  aggregate: boolean;
  parser: string;
  enabled: boolean;
  last_update: string | null;
  last_status: string | null;
  last_error: string | null;
}

export const rssTemplate: RSS = {
  id: 0,
  name: '',
  url: '',
  aggregate: false,
  parser: '',
  enabled: false,
  last_update: null,
  last_status: null,
  last_error: null,
};
