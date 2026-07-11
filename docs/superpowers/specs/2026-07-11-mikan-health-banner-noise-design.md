# Mikan health banner 降噪設計

## 問題

Dashboard 目前只要 Mikan 最後一次成功解析超過一小時，就把狀態判為
`degraded`。這段時間可能完全沒有新的 Mikan 請求，因此即使沒有失敗且
`pending_count` 為 0，UI 仍會常駐顯示警告。這不是可採取行動的異常訊號。

## 方案比較

1. **只顯示可採取行動的狀態（採用）**：有待處理項目或實際連續失敗時才顯示。
   保留既有診斷 API，但避免無流量造成假警報。
2. **完全移除 banner**：最安靜，但使用者也會失去真正異常及待處理項目的入口。
3. **延長時間門檻**：只能延後假警報，無法修正「沒有請求不代表異常」的語意問題。

## 顯示契約

- `pending_count > 0`：顯示警告、待處理數量，以及前往 pending resolution 的連結。
- `consecutive_failures > 0`：顯示警告；若後端狀態為 `down`，沿用較高嚴重度樣式。
- `pending_count === 0` 且 `consecutive_failures === 0`：不顯示 banner，無論
  `hours_since_last_success` 多久。
- API 回應欄位與後端健康度計算維持相容；本次只調整 UI 是否顯示，避免影響其他
  可能使用 `/api/v1/health/mikan` 的診斷功能。

## 元件與資料流

`useHealthStore` 繼續每 30 秒取得 Mikan health。`MikanHealthBanner.vue` 根據
`pending_count` 與 `consecutive_failures` 決定是否渲染，並根據後端 `status`
選擇 degraded 或 down 樣式。Pending resolution 頁面與 API 不變。

## 錯誤處理

沿用 health store 現有的請求錯誤處理。本次不把 health API 本身的網路錯誤轉成
Mikan 服務異常，避免把 AutoBangumi API 問題誤報為 Mikan 問題。

## 測試

新增或調整 WebUI 元件測試，至少覆蓋：

- `degraded`、0 pending、0 failures 時不顯示。
- pending 大於 0 時顯示數量與詳情連結。
- failures 大於 0 時顯示；`down` 狀態使用 down 樣式。
- `ok`、0 pending、0 failures 時不顯示。
