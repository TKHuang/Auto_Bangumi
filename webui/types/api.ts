export type AuthError = 'Not authenticated';

export type LoginError = 'Password error' | 'User not found';

export type ApiErrorMessage = AuthError | LoginError;

/**
 * 401 Token 过期
 * 404 Not Found
 * 406 Not Acceptable
 * 409 Conflict (重复订阅)
 * 422 Unprocessable Entity (解析失败需要手动输入)
 * 500 Internal Server Error
 * 502 Bad Gateway
 * 503 Service Unavailable
 * 504 Gateway Timeout
 */
export type StatusCode = 401 | 404 | 406 | 409 | 422 | 500 | 502 | 503 | 504;

export interface ApiError {
  status: StatusCode;
  msg_en: string;
  msg_zh: string;
}

export interface ApiSuccess {
  msg_en: string;
  msg_zh: string;
}
