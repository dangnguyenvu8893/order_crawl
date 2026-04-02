# Order Crawl

Service Node duy nhất để backend gửi 1 URL sản phẩm từ `1688`, `taobao`, `tmall` và nhận về payload đúng contract backend import.

## Endpoints

`GET /health`

`POST /transform-product-from-url`

```json
{
  "url": "https://detail.1688.com/offer/892407994374.html",
  "debug": false
}
```

Response success mặc định chỉ gồm:

```json
{
  "name": "string",
  "maxPrice": "string",
  "sourceId": "string",
  "sourceType": "1688|taobao|tmall",
  "url": "https://...",
  "images": ["https://..."],
  "rangePrices": [
    {
      "beginAmount": 1,
      "endAmount": 9,
      "price": 10.5,
      "discountPrice": 10.5
    }
  ],
  "skuProperty": [
    {
      "name": "Màu",
      "sourcePropertyId": "123",
      "values": [
        {
          "name": "Đỏ",
          "sourceValueId": "456",
          "image": "https://..."
        }
      ]
    }
  ],
  "sku": [
    {
      "canBookCount": "5",
      "price": "10.50",
      "specAttrs": "Đỏ|M",
      "skuId": "789"
    }
  ]
}
```

Khi `debug=true`, response thêm `_meta` để xem provider fallback và latency.

## Provider Priority

- `1688`: `gianghuy -> vipomall -> hangve -> pandamall`
- `taobao`: `gianghuy -> vipomall -> hangve -> pandamall`
- `tmall`: `vipomall -> hangve -> pandamall`

`pandamall` luôn là fallback cuối.

## Chạy Local

```bash
npm test
npm run test:providers
npm start
```

Service mặc định chạy ở `http://localhost:3000`.

`npm test` là suite unit/integration local không gọi network thật.

`npm run test:providers` là live smoke test để biết provider nào còn hoạt động thực tế với credential hiện có. Script sẽ trả JSON theo từng marketplace/provider và exit code `1` nếu có provider fail hoặc trả payload không đủ contract.

## Cấu hình

Ưu tiên đọc credential từ `./config/*.json`.

Để không làm gãy máy đang dùng credential cũ, service vẫn fallback đọc từ `./crawl_new/config/*.json` nếu file mới chưa tồn tại.

Các file hỗ trợ:

- `config/gianghuy.credentials.json`
- `config/hangve.credentials.json`
- `config/hangve.accounts.json`
- `config/pandamall.credentials.json`
- `config/pandamall.accounts.json`

Ví dụ PandaMall:

```json
{
  "phone": "0900000000",
  "password": "secret"
}
```

Ví dụ Hangve accounts:

```json
{
  "accounts": [
    {
      "username": "0900000000",
      "password": "secret"
    }
  ]
}
```

## Provider Guard

Lớp chống spam/chống block được đặt riêng ở orchestrator runtime, không nằm trong provider:

- `src/core/provider-guard.js`
- `src/core/orchestrator.js`

Provider chỉ biết `resolveProduct(context, { signal })`. Nếu muốn bỏ hẳn anti-block solution hoặc thay bằng strategy khác, chỉ cần:

- đổi `CRAWL_PROVIDER_GUARD_MODE=off`
- hoặc truyền `providerExecutionGuard` khác vào `transformProductFromUrl(...)`

Env chính:

- `CRAWL_PROVIDER_GUARD_MODE=adaptive|off`
- `CRAWL_GUARD_GIANGHUY_MAX_INFLIGHT`
- `CRAWL_GUARD_VIPOMALL_MAX_INFLIGHT`
- `CRAWL_GUARD_HANGVE_MAX_INFLIGHT`
- `CRAWL_GUARD_PANDAMALL_MAX_INFLIGHT`
- `CRAWL_GUARD_HANGVE_MIN_INTERVAL_MS`
- `CRAWL_GUARD_PANDAMALL_MIN_INTERVAL_MS`
- `CRAWL_GUARD_<PROVIDER>_FAILURE_THRESHOLD`
- `CRAWL_GUARD_<PROVIDER>_COOLDOWN_MS`

Ngoài guard, orchestrator còn có:

- `CRAWL_RESULT_CACHE_TTL_MS`
- `CRAWL_REQUEST_DEADLINE_MS`
