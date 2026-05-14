# 信用风控评分平台 MVP

这是基于 `credit_risk_scoring_platform_prd.md` 实现的 Streamlit MVP。平台使用 Home Credit 已训练模型产物，演示“申请接入 -> 模型评分 -> 策略决策 -> 人工复核 -> 标签回流 -> 监控报表”的最小业务闭环。

## 范围

已实现：

- 风控总览：KPI、经营趋势、风险结构、待复核和策略摘要。
- 风控总览预警：待复核积压、策略分流、模型稳定性三类轻量规则提示。
- 申请审批：6 类样例客户、四步式可编辑表单、字段校验、真实预测结果展示。
- 申请详情：客户快照、评分结果、原因码、状态流转、标签回流和审计记录。
- 人工复核：待复核列表、复核通过/拒绝、幂等处理。
- 策略中心：`t1/t2`、成本矩阵试算和策略版本发布。
- 模型中心：AUC、KS、LogLoss、Brier、Lift、Calibration、SHAP Top20。
- 报表中心：日/周/月经营趋势、风险分布、标签回流、Lift 摘要、审计日志。
- 平台教程：5 分钟使用路径、页面说明和低/中/高风险案例。

未实现：

- 批量评分、完整 REST API、复杂权限、A/B 策略实验、自动重训。
- 任意手工输入的 438 特征实时评分。MVP 表单允许编辑业务字段并保存快照，但评分仍严格绑定样例客户和已有模型预测产物。

## 本地运行

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m streamlit run app.py --server.address 0.0.0.0 --server.headless true --server.port 8503
```

访问地址：

```text
本地调试地址：http://localhost:8503
远程访问地址：http://<ECS公网IP>:8503
```

说明：

- 页面顶部会同时显示本地调试地址和远程访问地址。
- 未设置 `CREDIT_PLATFORM_PUBLIC_HOST` 时，页面会默认显示 `http://<ECS公网IP>:8503` 占位地址，本地调试仍然直接使用 `http://localhost:8503`。
- 如需在本地预演 ECS 访问地址，可先设置 `CREDIT_PLATFORM_PUBLIC_HOST`，再启动应用。

可选环境变量示例：

```powershell
$env:CREDIT_PLATFORM_PUBLIC_HOST = "203.0.113.10"
$env:CREDIT_PLATFORM_PUBLIC_PORT = "8503"
python -m streamlit run app.py --server.address 0.0.0.0 --server.headless true --server.port 8503
```

快速健康检查：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8503/_stcore/health
```

## 阿里云 ECS 部署

以下步骤以 Linux ECS + systemd 为例；如果你的 ECS 是 Windows，或未使用 systemd，服务托管步骤需要改成对应平台的方式。

1. 将项目上传到 ECS，并进入项目目录。
2. 安装 Python 3.12+、`venv` 和基础编译依赖。
3. 创建虚拟环境并安装依赖：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

4. 确认模型产物目录存在于 `data/model_artifacts/home-credit-gpu-full`，并且运行态数据库目录 `data/runtime/` 具备写权限。
5. 设置公网访问环境变量。这里必须把 `<ECS公网IP>` 替换为 ECS 的真实公网 IP，不要保留占位符：

```bash
export CREDIT_PLATFORM_PUBLIC_HOST="<ECS公网IP>"
export CREDIT_PLATFORM_PUBLIC_PORT="8503"
```

6. 在阿里云安全组中放通入方向 TCP `8503`；如果操作系统启用了防火墙，也要同步放通 `8503/tcp`。
7. 先以前台方式启动服务，确认应用可正常启动：

```bash
source .venv/bin/activate
python -m streamlit run app.py --server.address 0.0.0.0 --server.headless true --server.port 8503
```

8. 做健康检查：

```bash
curl http://127.0.0.1:8503/_stcore/health
curl http://<ECS公网IP>:8503/_stcore/health
```

9. 远程访问地址为：

```text
http://<ECS公网IP>:8503
```

### systemd 常驻运行示例

将下面的服务文件保存为 `/etc/systemd/system/credit-risk-platform.service`，并把 `User`、`Group`、`WorkingDirectory`、`ExecStart` 里的路径替换成你在 ECS 上的真实值。同时，`CREDIT_PLATFORM_PUBLIC_HOST` 必须替换为真实公网 IP。

```ini
[Unit]
Description=Credit Risk Scoring Platform
After=network.target

[Service]
Type=simple
User=ecs-user
Group=ecs-user
WorkingDirectory=/opt/credit-risk-scoring-platform
Environment=CREDIT_PLATFORM_PUBLIC_HOST=<ECS公网IP>
Environment=CREDIT_PLATFORM_PUBLIC_PORT=8503
ExecStart=/opt/credit-risk-scoring-platform/.venv/bin/python -m streamlit run app.py --server.address 0.0.0.0 --server.headless true --server.port 8503
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

加载并启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now credit-risk-platform.service
sudo systemctl status credit-risk-platform.service
```

查看日志：

```bash
sudo journalctl -u credit-risk-platform.service -f
```

## 数据与产物

模型产物位于：

```text
data/model_artifacts/home-credit-gpu-full
```

来源为 sibling 项目：

```text
../kaggle-Home-Credit-Default-Risk/artifacts/home-credit-gpu-full
```

当前 MVP 读取以下产物：

- `reports/metrics.json`
- `reports/thresholds.json`
- `reports/lift_table.csv`
- `reports/shap_top20.csv`
- `reports/calibration_curve.png`
- `predictions/holdout_predictions.csv`
- `features/feature_matrix.parquet`

运行态 SQLite 数据库位于：

```text
data/runtime/credit_platform.sqlite3
```

删除该文件后重新启动应用会重新生成演示申请数据。

## 验收路径

1. 进入“风控总览”，查看 KPI、工作台和三类轻量预警。
2. 进入“申请审批”，选择低风险客户，编辑业务字段并提交评分，结果为自动通过；在申请详情中查看快照、原因码和审计记录。
3. 选择中风险客户提交评分，进入“人工复核”，提交复核通过，再回到申请详情确认状态流转。
4. 选择高风险客户提交评分，结果为自动拒绝。
5. 进入“策略中心”，调整阈值和成本矩阵，查看通过/复核/拒绝率与总成本。
6. 进入“报表中心”，切换日/周/月趋势，模拟标签回流后查看回流指标、Lift 摘要和模型效果。
