# Giang Huy Node Client

Project Node.js nay tao `sign` va goi cac API cua `mps.monamedia.net` cho Giang Huy.

Project hien co them command de sinh `dpop` va goi API cua PandaMall.

## Luu y quan trong

- Header `url` gui len API la URL day du, vi du: `https://nhaphang.gianghuy.com`
- Chuoi dem di ky **khong** dung protocol, va project nay cung bo dau `/` cuoi neu co
- Cong thuc thuc te:

```txt
sign = MD5(accessKey + monaId + nhaphang.gianghuy.com + accessSecret)
```

Vi du voi:

- `accessKey = 0856e51ae4394aed8229ffdc12fc5f79`
- `accessSecret = f270b8c27d91467b982002eef107fb80`
- `monaId = 1774764141932`
- `url = https://nhaphang.gianghuy.com`

thi `sign` se la:

```txt
8e88a8e186129c8fe91288451865358c
```

## File credential

Credential duoc luu tai:

```txt
config/gianghuy.credentials.json
```

## Chay nhanh

```bash
npm run sign
npm run account:default
npm run detail:1688
npm run detail:taobao
npm run pandamall:login
npm run pandamall:item-details -- --item-id=892407994374 --provider=alibaba
npm run pandamall:item-details -- --item-id=1016154115457 --provider=taobao
npm run pandamall:item-details -- --item-id=1013307248141 --provider=tmall
npm run pandamall:item-details -- --url='https://detail.tmall.com/item.htm?id=1013307248141&skuId=6179390398393'
npm run hangve:login -- --username=0987064673 --password=21731823
npm run hangve:item-search -- --username=0987064673 --password=21731823 --key-search='https://detail.1688.com/offer/892407994374.html?offerId=892407994374&hotSaleSkuId=5758935680751'
npm run hangve:item-search -- --username=0987064673 --password=21731823 --key-search='https://detail.1688.com/offer/892407994374.html?offerId=892407994374&hotSaleSkuId=5758935680751' --include-detail
npm run hangve:item-detail -- --username=0987064673 --password=21731823 --item-id=1471325
npm run hangve:item-full -- --username=0987064673 --password=21731823 --key-search='https://detail.1688.com/offer/892407994374.html?offerId=892407994374&hotSaleSkuId=5758935680751'
```

## Ghi de bang command line

```bash
npm run sign -- --timestamp=1774764141932 --url=https://nhaphang.gianghuy.com
```

```bash
npm run account:default -- --end-user-id=203922
```

```bash
npm run detail:1688 -- --id=946758645543 --language=vi --is-no-cache=false
```

```bash
npm run detail:taobao -- --id=844351996614 --language=vi --is-no-cache=false
```

```bash
npm run pandamall:login
```

```bash
npm run pandamall:item-details -- --item-id=892407994374 --provider=alibaba
```

```bash
npm run pandamall:item-details -- --item-id=1016154115457 --provider=taobao
```

```bash
npm run pandamall:item-details -- --item-id=1013307248141 --provider=tmall
```

```bash
npm run pandamall:item-details -- --url='https://detail.tmall.com/item.htm?id=1013307248141&skuId=6179390398393'
```

## Bien cau hinh ho tro

- `GIANGHUY_ACCESS_KEY`
- `GIANGHUY_ACCESS_SECRET`
- `GIANGHUY_END_USER_ID`
- `GIANGHUY_URL`
- `MONA_API_BASE_URL`
- `PANDAMALL_ITEM_ID`
- `PANDAMALL_PROVIDER`
- `HANGVE_USERNAME`
- `HANGVE_PASSWORD`
- `HANGVE_API_BASE_URL`
- `HANGVE_ORIGIN`
- `HANGVE_REFERER`

Neu khong truyen, project se dung gia tri mac dinh da duoc cai san trong ma nguon.

## PandaMall login

Command PandaMall se:

- Tao cap khoa ECDSA P-256 JWK trong runtime
- Sinh `dpop` JWT dung format frontend cua `pandamall.vn`
- Goi `POST /api/pandamall/auth/login`

Output se gom:

- request URL
- headers da gui, bao gom `dpop`
- payload/header ben trong proof
- JWK key pair de co the tai su dung cho cac request tiep theo neu can
- HTTP status va JSON response cua API

Mac dinh account PandaMall duoc doc tu:

```txt
config/pandamall.credentials.json
```

## PandaMall item details

Command nay goi:

```txt
POST /api/pandamall/v1/item/details
```

Body:

```json
{
  "item_id": 892407994374,
  "provider": "alibaba"
}
```

Ban co 2 cach goi:

- `item_id`
- `provider`

hoac:

- `url` san pham

Command se:

- Tu dong login bang account mac dinh trong `config/pandamall.credentials.json`
- Lay `accessToken`
- Goi `POST /api/pandamall/v1/item/details`
- Tu sinh `dpop` cho ca request login va request item details
- Neu truyen `url`, command se tu detect san va tach `itemId`

Quy uoc `provider`:

- `1688` hoac `alibaba` => gui len API la `alibaba`
- `taobao` => gui len API la `taobao`
- `tmall` => gui len API la `taobao`

Detect URL hien ho tro:

- `https://detail.1688.com/offer/...`
- `https://item.taobao.com/item.htm?...id=...`
- `https://detail.tmall.com/item.htm?...id=...`

## Hangve login

Command Hangve goi:

```txt
POST /auth/sign-in
```

Command co the doc credential tu:

- `--username`, `--password`
- env `HANGVE_USERNAME`, `HANGVE_PASSWORD`
- file tuy chon `config/hangve.credentials.json`

Vi du file:

```json
{
  "username": "0987064673",
  "password": "21731823"
}
```

## Hangve item search

Command nay tu dong:

- login vao `client.hangve.com`
- goi `GET /customer/me` de lay `go_slim`
- sinh `key_facin` dung cong thuc frontend
- goi `POST /item/search`
- co the goi tiep `POST /item/detail/:id` neu them `--include-detail`
- neu `key-search` la URL `1688`, `taobao` hoac `tmall` thi `source` se duoc auto detect theo host

Vi du:

```bash
npm run hangve:item-search -- --username=0987064673 --password=21731823 --key-search='https://detail.1688.com/offer/892407994374.html?offerId=892407994374&hotSaleSkuId=5758935680751'
```

Mac dinh search dung:

- `source=sync_1688`
- `page=1`
- `per_page=30`

Ban co the ghi de bang:

- `--source=sync_taobao`
- `--page=2`
- `--per-page=15`
- `--price-from=10`
- `--price-to=99`
- `--price-order=asc`
- `--sales-order=desc`
- `--include-detail`
- `--detail-limit=3`

Vi du khong can truyen `--source`:

```bash
npm run hangve:item-full -- --username=0987064673 --password=21731823 --key-search='https://item.taobao.com/item.htm?id=1016154115457&skuId=6025255024005'
```

```bash
npm run hangve:item-full -- --username=0987064673 --password=21731823 --key-search='https://detail.tmall.com/item.htm?id=1013307248141&skuId=6179390398393'
```

## Hangve item detail

Command nay goi:

```txt
POST /item/detail/:id
```

Ngoai response raw cua Hangve, command nay con tra them field `normalized` da duoc parse san:

- `images`
- `variantGroups`
- `skus`
- `attributes`
- `priceRanges`
- `descriptionHtml`

Vi du:

```bash
npm run hangve:item-detail -- --username=0987064673 --password=21731823 --item-id=1471325
```

## Hangve item full

Command nay chay tron chuoi:

- login
- customer/me
- item/search
- item/detail cho item tim thay dau tien

Response se co them `normalizedDetails` va moi phan tu trong `details[]` cung co `normalized`.

Vi du:

```bash
npm run hangve:item-full -- --username=0987064673 --password=21731823 --key-search='https://detail.1688.com/offer/892407994374.html?offerId=892407994374&hotSaleSkuId=5758935680751'
```

## API 1688 detail

Project co san command goi:

```txt
GET /Management1688/get-detail-by-id?Id=...&Language=vi&IsNoCache=false
```

Mau sign cua ban:

- `monaId = 1774765232406`
- `url = https://nhaphang.gianghuy.com`

se cho ra:

```txt
802737758dd6fdec0e6a013fefe0d9ed
```

## API Taobao detail

Project co san command goi:

```txt
GET /ManagementTaobao/get-detail-by-id?Id=...&Language=vi&IsNoCache=false
```

Mau sign cua ban:

- `monaId = 1774765636404`
- `url = https://nhaphang.gianghuy.com`

se cho ra:

```txt
a68dfc7fd9739ca27606988a87a7950b
```
