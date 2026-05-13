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
python -m streamlit run app.py --server.headless true --server.port 8501
```

访问：

```text
http://127.0.0.1:8501
```

快速健康检查：

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8501/_stcore/health
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
