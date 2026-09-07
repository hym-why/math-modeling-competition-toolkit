# 选题评分说明

使用 `templates/problem_selection_scorecard.csv` 时，先填题型，再对六个评分项按 1-5 分打分。三人独立评分后取平均值，避免由最先发言的人带偏全队。

## 评分项

- `problem_type`：优化、预测、评价、分类、仿真、机理或混合类型，只分类不计分。
- `data_score`（20%）：数据是否可获取、可读懂、可清洗。没有核心数据给 1 分。
- `coding_score`（15%）：8 小时内能否完成基准代码，是否有可靠库可用。
- `metric_score`（20%）：是否存在客观评价指标，能否做误差、对比或稳定性检验。
- `writing_score`（15%）：能否清楚讲出假设、方法、图表、结论和局限。
- `team_score`（15%）：是否匹配三名 CST 学生的数据处理、编程和工程协作优势。
- `innovation_score`（15%）：基准模型之外，是否存在一个可解释、可验证的改进点。

加权总分：

```text
weighted_score = 0.20*data + 0.15*coding + 0.20*metric
               + 0.15*writing + 0.15*team + 0.15*innovation
```

填完 CSV 后自动计算并排序：

```powershell
python scripts/score_problems.py
```

结果写入 `outputs/problem_selection_ranked.csv`。被一票否决的题会排在所有可选题之后。

## 决策规则

- 加权总分最高且没有致命风险的题优先。
- 如果 C 题和 B 题的加权分差小于 0.30，优先选择风险更低者；风险相当时优先 C 题。
- `data_score=1`、`team_score=1`、核心结果无法验证或 30 行以内 PoC 跑不通，均在 `veto` 填 `yes` 并放弃。
- 选题最迟在开赛后 2 小时内冻结，除非发现硬性不可做。

## 两小时内的最小产物

- 填完六维评分表并记录放弃理由。
- 用 `templates/problem_decomposition.md` 拆清每一问及依赖。
- 每个候选主模型写出最小 PoC；只允许验证可行性，不追求最终精度。
- 完成后通过 G1，再进入正式建模。详见 `docs/05_quality_gates.md`。
