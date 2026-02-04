export interface ProgramConfig {
  rss_time: number;
  rename_time: number;
  webui_port: number;
}

export interface DownloaderConfig {
  type: string;
  host: string;
  username: string;
  password: string;
  path: string;
  ssl: boolean;
}

export interface ParserConfig {
  enable: boolean;
  filter: string[];
  language: string;
}

export interface ManageConfig {
  enable: boolean;
  eps_complete: boolean;
  rename_method: string;
  group_tag: boolean;
  remove_bad_torrent: boolean;
}

export interface ProxyConfig {
  enable: boolean;
  type: string;
  host: string;
  port: number;
  username: string;
  password: string;
}

export interface NotificationConfig {
  enable: boolean;
  type: string;
  token: string;
  chat_id: string;
}

export interface Config {
  program: ProgramConfig;
  downloader: DownloaderConfig;
  rss_parser: ParserConfig;
  bangumi_manage: ManageConfig;
  proxy: ProxyConfig;
  notification: NotificationConfig;
}
