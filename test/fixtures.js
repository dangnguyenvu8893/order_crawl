const GIANGHUY_1688_RAW = {
  itemId: 892407994374,
  title: "GiangHuy 1688 title",
  description: "<p>gianghuy</p>",
  maxPrice: 47.98,
  medias: [
    { link: "https://img-1.jpg", isVideo: false },
    { link: "https://img-2.jpg", isVideo: false }
  ],
  properties: [
    {
      name: "Color",
      values: [{ name: "Beige", imageUrl: "https://img-1.jpg" }]
    }
  ],
  skuInfos: [
    {
      id: "sku-1688-1",
      skuPropertyName: "Beige;S;",
      price: 47.98,
      promotionPrice: 47.98,
      amountOnSale: 30,
      imageUrls: "https://img-1.jpg|"
    }
  ],
  priceRanges: [
    { startQuantity: 2, price: 47.98 },
    { startQuantity: 500, price: 46.68 }
  ]
};

const PANDAMALL_TAOBAO_RAW = {
  status: true,
  message: "ok",
  data: {
    id: 1016154115457,
    name: "Pandamall Taobao title",
    description: "<p>pandamall</p>",
    image: "https://pm-main.jpg",
    thumbnails: [
      { type: "image", src: "https://pm-thumb-1.jpg" },
      { type: "image", src: "https://pm-thumb-2.jpg" }
    ],
    price: 151.52,
    promotionPrice: 143.95,
    maxPrice: 151.52,
    url: "https://item.taobao.com/item.htm?id=1016154115457",
    classify: {
      skuImages: {
        "1627207:380848629": "https://pm-color.jpg"
      },
      skuProperties: [
        {
          propID: 1627207,
          propName: "Phân loại màu sắc",
          propValues: [{ valueID: 380848629, valueName: "Milkshake White - Còn hàng" }]
        },
        {
          propID: 20509,
          propName: "kích cỡ",
          propValues: [
            { valueID: 28314, valueName: "S" },
            { valueID: 28315, valueName: "M" }
          ]
        }
      ],
      skuMappings: {
        "1627207:380848629@20509:28314": {
          skuID: "6025255024005",
          sName: "1627207:Milkshake White - Còn hàng@20509:S",
          price: 151.52,
          promotionPrice: 143.95,
          quantity: 129,
          imageURL: "https://pm-color.jpg"
        }
      }
    },
    priceRanges: {
      "1-9": 151.52,
      "10+": 143.95
    }
  }
};

const HANGVE_TMALL_NORMALIZED = {
  source: "taobao",
  itemId: 2508970,
  numIid: "1013307248141",
  title: "Hangve Tmall title",
  sellerNick: "Hangve seller",
  detailUrl: "https://item.taobao.com/item.htm?id=1013307248141",
  price: 118.6,
  promotionPrice: 118.6,
  images: ["https://hv-main.jpg", "https://hv-2.jpg"],
  variantGroups: [
    {
      name: "Color",
      values: ["Red"]
    },
    {
      name: "Size",
      values: ["S", "M"]
    }
  ],
  skus: [
    {
      skuId: "6179390398393",
      classification: "Red;S",
      price: 118.6,
      promotionPrice: 118.6,
      quantity: 5,
      image: "https://hv-main.jpg"
    }
  ],
  priceRanges: [],
  descriptionHtml: "<p>hangve</p>"
};

const VIPOMALL_TAOBAO_RAW = {
  status: "01",
  message: "Successful!",
  data: {
    product_id: "1010925503027",
    product_name:
      "Thẻ thành viên Sam's Club, thẻ chính và thẻ phụ, thẻ thường niên, thẻ trải nghiệm thành viên điện tử Sam's Club một năm, cửa hàng vật lý của Sam's Club.",
    original_product_name: "山姆会员卡主副卡年卡一年Sam山姆超市电子卡會員体验卡sam实体店",
    original_product_url: "https://item.taobao.com/item.htm?id=1010925503027",
    description: '<img src="//img.alicdn.com/example-desc.jpg">',
    main_img_url_list: [
      "https://img.alicdn.com/bao/uploaded/i1/example-1.jpg",
      "https://img.alicdn.com/bao/uploaded/i4/example-2.jpg"
    ],
    price_ranges: [
      { price: 107.22, start_quantity: 1 },
      { price: 161.35, start_quantity: 1 },
      { price: 93.69, start_quantity: 1 }
    ],
    sku_price_ranges: {
      min_price: 93.69,
      max_price: 161.35
    },
    product_prop_list: [
      {
        prop_id: 144160005,
        prop_name: "Tên album",
        original_prop_name: "专辑名称",
        value_list: [
          {
            value_id: 42730477369,
            value_name: "Thẻ phụ cấp 1 năm",
            original_value_name: "副卡一年（秒发新用户）",
            img_url: "//img.alicdn.com/bao/uploaded/i4/example-color.jpg"
          }
        ]
      }
    ],
    product_sku_info_list: [
      {
        sku_id: "6179097222149",
        price: 107.22,
        stock: 200,
        img_url: "//img.alicdn.com/bao/uploaded/i4/example-sku.jpg",
        sku_prop_list: [
          {
            prop_id: 144160005,
            prop_name: "Tên album",
            value_id: 42730477369,
            value_name: "Thẻ phụ cấp 1 năm",
            original_value_name: "副卡一年（秒发新用户）"
          }
        ]
      }
    ]
  }
};

module.exports = {
  GIANGHUY_1688_RAW,
  HANGVE_TMALL_NORMALIZED,
  PANDAMALL_TAOBAO_RAW,
  VIPOMALL_TAOBAO_RAW
};
