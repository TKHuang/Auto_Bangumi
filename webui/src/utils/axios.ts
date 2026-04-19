import Axios from 'axios';
import type { AxiosError, AxiosResponse } from 'axios';
import type { ApiSuccess, StatusCode } from '#/api';

export const axios = Axios.create({
  withCredentials: true,
});

axios.interceptors.response.use(
  (res: AxiosResponse) => res,
  (err: AxiosError<ApiSuccess>) => {
    const status = err.response?.status as StatusCode;
    const msg_en = err.response?.data.msg_en ?? '';
    const msg_zh = err.response?.data.msg_zh ?? '';

    const message = useMessage();
    const { returnUserLangText } = useMyI18n();

    const errorMsg = returnUserLangText({
      en: msg_en,
      'zh-CN': msg_zh,
    });

    const { isLoggedIn } = useAuth();

    switch (status) {
      /** token 过期 */
      case 401:
        isLoggedIn.value = false;
        if (errorMsg) message.error(errorMsg);
        break;
      /** 资源未找到 */
      case 404:
        if (errorMsg) message.error(errorMsg);
        break;
      /** 执行失败 */
      case 406:
        if (errorMsg) message.error(errorMsg);
        break;
      /** 冲突 (如重复订阅) */
      case 409:
        if (errorMsg) message.error(errorMsg);
        break;
      /** 验证失败 (如解析失败需要手动输入) */
      case 422:
        // Pass full response data for special error types (e.g., bangumi_parsing_failed)
        // Don't show generic error message - let the caller handle it
        return Promise.reject(err.response?.data);
      case 500:
      case 502:
      case 503:
      case 504:
        // Don't logout on server errors — they don't invalidate the session.
        // Prefer the structured msg_en / msg_zh the API may surface (e.g. for
        // downloader-unreachable cases) over the generic fallback.
        message.error(
          errorMsg ||
            returnUserLangText({
              en: 'Server error!',
              'zh-CN': '服务器错误！',
            })
        );
        break;
    }

    const error = {
      status,
      msg_en,
      msg_zh,
    };

    return Promise.reject(error);
  }
);
