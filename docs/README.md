# 每周关注股票列表

部署在 GitHub Pages 的静态网站，每周更新关注股票列表，表格形式展示，方便程序扫描采集。

## 项目结构

```
docs/
├── index.html                  # 主页面
├── css/
│   └── style.css               # 样式
├── js/
│   └── app.js                  # 前端逻辑
├── data/
│   ├── watchlists.json         # 当周数据 + 历史索引
│   └── history/
│       └── 2026-06-08.json     # 归档周数据
└── README.md                   # 本文档
```

## 数据格式规范

### watchlists.json

```json
{
  "current": {
    "date_start": "YYYY.MM.DD",
    "date_end": "YYYY.MM.DD",
    "updated_at": "YYYY.MM.DD",
    "stocks": [
      {
        "code": "600519",
        "name": "贵州茅台",
        "sector": "白酒",
        "reason": "关注理由",
        "target_price": 1850.00,
        "stop_loss": 1680.00,
        "current_price": 1765.50,
        "rating": 3
      }
    ]
  },
  "history": [
    {
      "date_start": "YYYY.MM.DD",
      "date_end": "YYYY.MM.DD",
      "stocks_count": 8,
      "file": "data/history/YYYY-MM-DD.json"
    }
  ]
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 股票代码，如 "600519" |
| name | string | 是 | 股票名称 |
| sector | string | 是 | 所属板块（见颜色映射表） |
| reason | string | 是 | 关注理由 |
| target_price | float/null | 否 | 目标价，null 表示未设 |
| stop_loss | float/null | 否 | 止损价，null 表示未设 |
| current_price | float/null | 否 | 当前价，null 表示未填 |
| rating | int | 是 | 评级 1-5 星 |

### 历史文件 data/history/YYYY-MM-DD.json

格式与 `current` 相同，但不包含 `current` 和 `history` 外层，直接是：

```json
{
  "date_start": "YYYY.MM.DD",
  "date_end": "YYYY.MM.DD",
  "updated_at": "YYYY.MM.DD",
  "stocks": [...]
}
```

文件名使用周开始日期，连字符格式：`2026-06-08.json`。

## 板块颜色映射

| 板块 | CSS 类名 | 背景色 | 文字色 |
|------|----------|--------|--------|
| 白酒 | sector-白酒 | #FEF3C7 | #92400E |
| 新能源 | sector-新能源 | #DBEAFE | #1E40AF |
| 医药 | sector-医药 | #D1FAE5 | #065F46 |
| 科技 | sector-科技 | #E0E7FF | #3730A3 |
| 金融 | sector-金融 | #FCE7F3 | #9D174D |
| 消费 | sector-消费 | #FEF9C3 | #854D0E |
| 其他 | sector-default | #F3F4F6 | #4B5563 |

新增板块颜色：在 `css/style.css` 中添加 `.sector-XXX` 样式，在 `js/app.js` 的 `SECTOR_CLASSES` 中添加映射。

## 每周更新流程

1. 打开 `docs/data/watchlists.json`
2. 将 `current` 的 stocks 复制到 `docs/data/history/YYYY-MM-DD.json`（用 date_start 日期命名）
3. 在 `history` 数组头部追加旧周条目（date_start, date_end, stocks_count, file）
4. 写入新一周的 `current` 数据
5. 提交并推送：
   ```bash
   cd docs/
   git add .
   git commit -m "更新关注列表 YYYY.MM.DD"
   git push
   ```
6. GitHub Pages 自动更新（约 1 分钟生效）

## GitHub Pages 部署配置

1. 进入仓库 Settings → Pages
2. Source 选择 `master` 分支，目录选 `/docs`
3. 保存，等待部署完成
4. 访问地址：`https://maoxianfei.github.io/strategy/`

## 程序采集数据

程序可通过以下方式获取数据：

1. **直接请求 JSON**（推荐）：
   ```
   https://maoxianfei.github.io/strategy/data/watchlists.json
   https://maoxianfei.github.io/strategy/data/history/2026-06-08.json
   ```

2. **解析 HTML 表格**：页面 `<table id="watchlist-table">` 语义化结构，每行含 `data-code`、`data-sector`、`data-rating` 属性。

## 故障排查

| 问题 | 原因 | 解决 |
|------|------|------|
| 页面空白 | JSON 加载失败 | 检查文件路径是否正确，浏览器控制台查看错误 |
| 表格不显示 | JSON 格式错误 | 用 JSON validator 校验 watchlists.json |
| 历史切换失败 | history 文件不存在 | 检查 file 路径是否与实际文件一致 |
| 样式错乱 | CSS 未加载 | 检查 css/style.css 路径 |
| 手机端表格超出 | 正常，横滚查看 | 已做响应式横滚处理 |
