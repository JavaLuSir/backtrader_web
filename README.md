# Backtrader Web 版本（最小可用原型）

满足 `Web 版本 Backtrader 测试.md`：
- 左侧策略列表（每个策略一个 `.py` 文件，点击切换）
- 右侧输入股票代码 / 资金 / 开始结束日期，点击开始回测
- 底部展示回测资金曲线（日期 - 金额），并标注买/卖点
- 回测完成后可导出交易 CSV（买卖点、现金、总资产）
- 后端使用 MySQL（默认按文档：`192.168.1.10:3306`，数据库 `stock`）
- **股票代码自动补全**：输入代码或名称时自动提示匹配的股票

## 0) MySQL 准备

需要先创建数据库（脚本只会建表，不会建库）：

```sql
CREATE DATABASE IF NOT EXISTS stock CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

然后把连接信息写入 `.env`（可从 `.env.example` 复制）。

> 说明：网站启动时即使 DB 不通也能打开页面，但回测/健康检查会报错。

## 1) 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

## 2) 初始化数据库表

```powershell
python -m btweb.init_db
```

## 3) 导入股票信息（用于自动补全）

```powershell
python -m scripts.init_stocks
```

导入常用股票（美股、港股、A 股示例），之后在输入股票代码时会自动提示补全。

更多股票可使用以下命令添加：
```powershell
# 导入多个股票
python scripts\import_stock_info.py --symbols AAPL,GOOGL,MSFT,TSLA

# 从 CSV 批量导入
python scripts\import_stock_info.py --csv stocks.csv

# 查看已导入的股票
python scripts\import_stock_info.py --list
```

详细说明请查看：[AUTO_COMPLETE_README.md](AUTO_COMPLETE_README.md)

## 4) 采集数据（示例：AAPL 近 10 年日 K）

```powershell
python .\scripts\ingest_yfinance.py --symbol AAPL --years 10
```

## 5) 启动网站

```powershell
uvicorn btweb.main:app --reload --port 8000
```

浏览器打开：
- http://127.0.0.1:8000

## 6) 添加/切换策略

把策略文件放到 `strategies/` 目录。
- 已内置示例：`strategies/sma_crossover.py`
- 已从桌面复制：`strategies/策略 1.py`

策略加载规则：
- 优先读取 `STRATEGY_CLASS`；否则自动寻找第一个 `bt.Strategy` 子类。

---

如果你希望"策略参数也能在网页上编辑/保存"，告诉我你想暴露哪些参数（如均线周期、手续费、仓位等），我可以把策略 `params` 自动生成表单。

指标说明：页面会显示年化收益率、夏普比率、最大回撤、胜率、盈亏比 (平均盈利/平均亏损)、卡尔马比率、索提诺比率。
