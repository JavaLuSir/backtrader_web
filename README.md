# Backtrader Web 版本（最小可用原型）

满足 `Web版本Backtrader测试.md`：
- 左侧策略列表（每个策略一个 `.py` 文件，点击切换）
- 右侧输入股票代码 / 资金 / 开始结束日期，点击开始回测
- 底部展示回测资金曲线（日期-金额），并标注买/卖点
- 回测完成后可导出交易CSV（买卖点、现金、总资产）
- 后端使用 MySQL（默认按文档：`192.168.1.10:3306`，数据库 `stock`）

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

## 3) 采集数据（示例：AAPL 近10年日K）

```powershell
python .\scripts\ingest_yfinance.py --symbol AAPL --years 10
```

## 4) 启动网站

```powershell
uvicorn btweb.main:app --reload --port 8000
```

浏览器打开：
- http://127.0.0.1:8000

## 5) 添加/切换策略

把策略文件放到 `strategies/` 目录。
- 已内置示例：`strategies/sma_crossover.py`
- 已从桌面复制：`strategies/策略1.py`

策略加载规则：
- 优先读取 `STRATEGY_CLASS`；否则自动寻找第一个 `bt.Strategy` 子类。

---

如果你希望“策略参数也能在网页上编辑/保存”，告诉我你想暴露哪些参数（如均线周期、手续费、仓位等），我可以把策略 `params` 自动生成表单。