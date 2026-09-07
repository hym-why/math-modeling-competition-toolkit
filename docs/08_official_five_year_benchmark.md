# 近五年 C 题官方基准与模型升级

基准范围为 2021-2025 年本科组 C 题。题面和附件来自 CUMCM 官网，优秀案例优先采用全国组委会在中国大学生在线公开展示的论文及赛题讲评。展示论文仅在线阅读和归纳方法，不复制、再发布论文内容。

## 一键复现

```powershell
powershell -ExecutionPolicy Bypass -File scripts/fetch_official_benchmarks.ps1
.\.venv\Scripts\python.exe scripts\benchmark_suite.py
.\.venv\Scripts\python.exe scripts\model_benchmarks.py --case all
```

生成文件位于 `benchmarks/runs/`：

- `summary.md`：五题页数、问题数、工作簿和数据警告总览。
- `<年份>C/problem.txt`：从官方 PDF 提取的题面文本。
- `<年份>C/data_contract.json`：输入文件哈希、表结构和异常提示。
- `model_comparison.md`：基准模型、候选模型、指标、选择结论和限制。

这些是训练回归基准，不是可直接提交的五份竞赛答案。

## 真题结果

| 题目 | 基准与候选 | 实测结论 | 最终选择 |
|---|---|---|---|
| 2021 C 供应商 | 总供货量排名 vs 下行可靠性评分 | 前 50 家平均缺供率从 16.46% 降至 10.62%，活跃周数从 204.74 增至 213.14；Bootstrap Top-50 Jaccard 为 0.892 | 采用可靠性评分筛选，再接整数规划和运输分配 |
| 2022 C 古代玻璃 | 原始比例浅树 vs CLR+逻辑回归 | 按文物编号分组交叉验证，浅树平衡准确率 1.000，CLR 逻辑回归为 0.934 | 分类保留浅树；CLR 用于成分关联、风化比较和亚类解释 |
| 2023 C 蔬菜 | 7 日季节朴素预测 vs 滞后梯度提升 | 最后 28 天留出，WAPE 从 20.79% 降至 17.53%，MAE 从 12.69 降至 10.70 千克 | 采用滞后模型，但定价必须另估价格弹性并做随机优化 |
| 2024 C 种植 | 2023 实际方案 vs 聚合线性规划 | 基准利润 592.63 万元，松弛规划上界 594.65 万元 | 只把 LP 当上界审计；最终方案必须加入地块、轮作、豆类窗口和分散度约束 |
| 2025 C NIPT | 线性/非线性浓度模型；Z 阈值/平衡逻辑分类 | 非线性回归在按孕妇分组的验证中更差；异常分类 F1 从 0.071 升至 0.198，但仍很弱 | 拒绝非线性回归；异常模型标记为未达提交标准 |

## 与官方展示案例对照

### 2021 C

官方展示的 C066 将任务组织为供应商评价与订购、运输规划。公开的[国二代码案例](https://github.com/zz-wolf/CUMCM2021-C)还采用多维供应特征、PCA 和整数线性规划。现项目保留“评价后接规划”的主线，但把稳定性与缺供下行风险直接放入指标，并用周抽样检验榜单稳定性，避免只按总量或 TOPSIS 分数解释重要性。

### 2022 C

官方展示的 C155 对成分数据做定和与 CLR，使用卡方检验、决策树、R/Q 型聚类及扰动敏感性。五年回归说明，分类阶段不需要为了高级感放弃浅树；真正值得吸收的是成分数据几何、按文物分组验证、统计检验前提检查和扰动分析。

### 2023 C

官方展示的 C228 使用时间相关分析、关联规则、价格预测和多目标优化等完整链路。赛题专家解析强调剥离销量时间效应、建立价格与销量关系、预测成本并进行随机优化。项目的轻量预测器已超过季节基线，但不能把销量预测直接当成价格弹性，更不能用随机切分制造虚高精度。

### 2024 C

官方展示的 C038 使用约束种植模型、遗传算法、CVaR 和相关性分析。项目新增的聚合 LP 能快速检查单位、供需上限和目标函数，并给出最终模型不应超过的松弛上界；正式求解仍需混合整数模型或能严格保持可行性的启发式算法，再对不确定参数做情景与 CVaR 比较。

### 2025 C

官方展示的 C132 使用混合效应/非线性关系、达标时间或生存分析思路以及不平衡分类。项目的按孕妇分组验证揭示：普通非线性提升树无法可靠外推到新孕妇；女胎异常分类即使优于简单 Z 阈值，绝对指标仍不足。训练时应优先补混合效应、区间删失生存模型、概率校准、阈值代价和误差敏感性，所有结论仅用于竞赛建模，不能用于临床决策。

## 固化后的模型底线

1. 每题先给出能解释的基准模型，候选模型只有在正确验证集上胜出才能替换。
2. 成分数据先检查总和与未检出值，再决定 closure、CLR/ILR 或原比例模型。
3. 时间序列按时间留出；同一供应商、文物或孕妇的重复记录按主体分组。
4. 优化模型必须同时报告目标值、最大约束违反量、可行解比例和松弛上界。
5. 不确定性不能只做参数上下浮动图；至少报告情景分布、失败概率或 CVaR。
6. 医疗、分类和小样本题同时报告类别不平衡指标，不能只写准确率。

## 参考页面

- CUMCM 历年赛题：https://www.mcm.edu.cn/html_cn/block/8579f5fce999cdc896f78bca5d4f8237.html
- 官方论文展示入口：https://dxs.moe.gov.cn/zx/hd/sxjm/sxjmlw/qkt_sxjm_lw_lwzs.shtml
- 2021 C066：https://dxs.moe.gov.cn/zx/a/hd_sxjm_sxjmlw_2021qgdxssxjmjslwzs_2021ctlw/230613/1843445.shtml
- 2022 C155：https://dxs.moe.gov.cn/zx/a/hd_sxjm_sxjmlw_2022qgdxssxjmjslwzs_2022ctlw/230613/1843443.shtml
- 2023 C228：https://dxs.moe.gov.cn/zx/a/hd_sxjm_sxjmlw_2023qgdxssxjmjslwzs_2023ctlw/231104/1865128.shtml
- 2024 C038：https://dxs.moe.gov.cn/zx/a/hd_sxjm_sxjmlw_2024qgdxssxjmjslwzs_2024ctlw/241104/1977952.shtml
- 2025 C132：https://dxs.moe.gov.cn/zx/a/hd_sxjm_sxjmlw_2025qgdxssxjmjslwzs_2025ctlw/251101/2022740.shtml
- 2022 C 赛题讲评：https://dxs.moe.gov.cn/zx/a/hd_sxjm_sxjmstjp_2022sxjmstjp/230404/1834982.shtml
- 2023 C 赛题讲评：https://dxs.moe.gov.cn/zx/a/hd_sxjm_sxjmstjp_2023sxjmstjp/231207/1869893.shtml
- 2024 C 赛题讲评：https://dxs.moe.gov.cn/zx/a/hd_sxjm_sxjmstjp_2024sxjmstjp/241127/1980958.shtml
- 2025 C 赛题讲评：https://dxs.moe.gov.cn/zx/a/hd_sxjm_sxjmstjp_2025sxjmstjp/251202/2025781.shtml
