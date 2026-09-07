# 轻量六门控

这套门控借鉴 `math-modeling-skills` 的可追溯思想，压缩为三人队伍在 7-10 天内能真正执行的版本。原则是：每一关都留下文件证据；前一关没过，不把问题推给下一位队员。

## G1 题目已拆解

负责人：队长/建模。

通过条件：每一问已写清输入、输出、目标、约束、评价指标和前后依赖；三道候选题完成六维评分；最终选题和放弃理由有记录；赛题附件已生成数据契约并人工核对单位和口径。

证据：`templates/problem_decomposition.md`、`templates/problem_selection_scorecard.csv`、`state/data_contract.json`。

## G2 方法已验证

负责人：队长和主程序。

通过条件：每问至少有基准方案和主方案；主方案有最小 PoC 或小样本试跑；已明确验证方法和失败条件；关键假设有编号和检验办法。复杂模型不能只凭名称入选。

证据：`templates/model_contract.md`、`templates/assumption_register.csv`、`templates/experiment_plan.csv`、PoC 代码及输出。

## G3 代码已复现

负责人：主程序，主论文交叉运行。

通过条件：固定随机种子；输入输出路径明确；非作者按 README 能完整运行；关键表格和图片由脚本生成；异常、单位和缺失值处理有记录。

证据：代码、清洗后数据、结果表、绘图源数据、`experiments/*/manifest.json` 和运行日志。

## G4 结果已冻结

负责人：主程序，队长确认。

通过条件：最终数字、表格和图片已确认，并生成 SHA-256 清单。冻结后如果代码、参数或数据变化，必须从受影响的最早门控重新检查。

```powershell
python scripts/result_freeze.py freeze
python scripts/result_freeze.py check
```

证据：`state/frozen_results.json`。

## G5 论文证据链已闭合

负责人：主论文，队长和主程序逐项签字。

通过条件：论文每个关键结论都能指向结果文件、表格或图片；图表采用“描述-分析-结论”三步解释；每个主模型都有变量、假设、公式、求解、结果、验证和局限。

证据：`templates/claim_evidence_map.csv`、论文草稿、图表契约。

## G6 终稿已审计

负责人：三人换位检查。

通过条件：数据来源、公式与代码、数值与图表、正文引用、匿名、AI 声明、文件大小、压缩包和可运行性全部通过；`scripts/audit_project.py` 返回 PASS；发现问题已修复或在论文中如实限定。

证据：`state/audit_report.json`、`templates/reviewer_scorecard.csv`、提交检查输出、最终 PDF 和支撑材料包。

## 门控命令

查看状态：

```powershell
python scripts/gatekeeper.py status
```

通过一关时必须提供说明和至少一个真实证据文件：

```powershell
python scripts/gatekeeper.py pass G1 --note "C 题已拆解，队长确认" --artifact templates/problem_decomposition.md
```

模型、数据或代码变化时，从受影响的最早一关重新打开，下游自动重置：

```powershell
python scripts/gatekeeper.py reopen G3 --reason "修复缺失值处理后结果发生变化"
```
