# 股票自动补全功能使用说明

## 功能概述

在股票代码输入框中，当您输入股票代码或名称时，系统会自动搜索并显示匹配的股票列表供选择。

## 使用步骤

### 1. 初始化股票数据库

首次使用前，需要导入股票信息到数据库：

```powershell
# 导入预定义的常用股票（美股、港股、A 股示例）
python scripts\init_stocks.py
```

### 2. 添加更多股票

#### 方法一：从 yfinance 自动获取

```powershell
# 导入单个股票
python scripts\import_stock_info.py --symbol AAPL

# 导入多个股票
python scripts\import_stock_info.py --symbols AAPL,GOOGL,MSFT,TSLA

# 导入 A 股（需要使用 Yahoo Finance 的后缀格式）
python scripts\import_stock_info.py --symbols 600000.SS,000001.SZ,600519.SS
```

#### 方法二：从 CSV 文件批量导入

创建 CSV 文件（例如 `stocks.csv`）：

```csv
symbol,name,exchange,market
600000.SS,浦发银行，SSE,
000001.SZ,平安银行，SZSE,
AAPL,Apple Inc,NASDAQ,
0700.HK，腾讯控股，HKEX,
```

然后执行：

```powershell
python scripts\import_stock_info.py --csv stocks.csv
```

### 3. 查看已导入的股票

```powershell
python scripts\import_stock_info.py --list
```

### 4. 使用自动补全功能

1. 启动网站：
   ```powershell
   uvicorn btweb.main:app --reload --port 8000
   ```

2. 浏览器访问：http://127.0.0.1:8000

3. 在"股票代码"输入框中输入：
   - 股票代码（如 `AAPL`、`600`）
   - 股票名称（如 `Apple`、`腾讯`）

4. 系统会自动显示匹配的股票列表（300ms 防抖）

5. 使用方式：
   - 鼠标点击选择
   - 键盘 `↑` `↓` 方向键选择，`Enter` 确认
   - `Esc` 关闭下拉列表
   - 点击外部区域关闭

## API 接口

### 获取股票列表

```
GET /api/stocks?q={搜索关键词}&limit={返回数量}
```

参数：
- `q`: 搜索关键词，支持代码或名称模糊匹配（可选）
- `limit`: 返回结果数量，默认 20（可选）

返回示例：

```json
[
  {
    "symbol": "AAPL",
    "name": "Apple Inc",
    "exchange": "NASDAQ",
    "market": null
  },
  {
    "symbol": "AAPL.L",
    "name": "Apple Inc (London)",
    "exchange": "LSE",
    "market": null
  }
]
```

## 数据库表结构

### stock_info 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 主键 |
| symbol | VARCHAR(16) | 股票代码（唯一） |
| name | VARCHAR(64) | 股票名称 |
| exchange | VARCHAR(16) | 交易所（NYSE, NASDAQ, SSE, SZSE, HKEX 等） |
| market | VARCHAR(16) | 市场类型 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

## 注意事项

1. **股票代码格式**：
   - 美股：直接代码，如 `AAPL`
   - A 股：需要后缀，如 `600000.SS`（上交所）、`000001.SZ`（深交所）
   - 港股：需要 `.HK` 后缀，如 `0700.HK`

2. **数据来源**：
   - yfinance 自动获取：信息可能不完整，但方便快捷
   - CSV 手动导入：适合批量导入 A 股等特定市场股票

3. **性能优化**：
   - 输入时有 300ms 防抖，避免频繁请求
   - 数据库已为 `symbol` 和 `name` 字段添加索引
   - 默认最多返回 20 条结果

## 扩展数据源

如果需要更完整的 A 股数据，可以：

1. 从聚宽、Tushare 等平台获取股票列表
2. 导出为 CSV 格式
3. 使用 `--csv` 参数批量导入

示例 CSV 格式：

```csv
symbol,name,exchange,market
600000.SS，浦发银行，SSE,主板
600036.SS，招商银行，SSE,主板
300750.SZ，宁德时代，SZSE,创业板
```
