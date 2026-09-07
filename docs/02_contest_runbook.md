# 赛中执行手册

## 0-2 小时：选题

三人独立读题 40 分钟，然后用 `templates/problem_selection_scorecard.csv` 打分。队长按总分和风险拍板。

同时填写 `templates/problem_decomposition.md`，通过 G1 后冻结选题。

附件落盘后立即运行 `scripts/data_contract.py create`，先发现缺失、重复、字段类型和工作表问题。

选题优先级：

1. 本科组优先看 C 题。
2. B 题如果数据结构清楚、优化目标清楚，可以优先于 C 题。
3. A 题只有在模型非常直观、参数可估计、仿真能落地时才选。

硬性放弃条件：

- 2 小时内说不清输入、输出、评价指标、基准模型、改进模型、验证方式。
- 核心数据不可获得，且无法构造合理替代。
- 需要大量专业背景才能解释结果。

## 2-8 小时：先拿基准结果

- 主程序先做数据读取、清洗、描述性统计和可视化。
- 队长写问题重述、变量定义、模型假设、基准模型公式。
- 队长和主程序共同填写 `templates/model_contract.md`，先跑最小 PoC，再决定主模型。
- 给关键假设编号并填写 `templates/assumption_register.csv`；先登记 `templates/experiment_plan.csv`，再跑正式实验。
- 主论文把 `templates/paper_template.md` 填成真实论文骨架。
- 第 8 小时验收：至少 1 个基准模型、2 张图、1 张结果表、完整目录。
- 验收完成后通过 G2；没有 PoC 数字的复杂模型不进入主线。

## 8-30 小时：核心模型

- 在基准模型上做一个明确改进，例如加入权重、约束、非线性项、时间因素或鲁棒处理。
- 每个模型都要有输入、输出、参数含义、求解步骤、结果解释。
- 至少做一个验证：留出集、交叉验证、误差分析、对比基准、敏感性分析或稳定性检验。
- 每张图先填写 `templates/figure_contract.csv`：它支持什么结论、源数据和生成脚本在哪里。
- 每天固定同步 4 次，每次不超过 20 分钟，只讨论本队内容。
- 由非作者复现主程序并通过 G3。
- 正式结果通过 `scripts/run_experiment.py` 运行，留下种子、参数、版本、输入和输出哈希。

## 30-55 小时：论文优先

- 主结果确认后运行 `python scripts/result_freeze.py freeze`，通过 G4，再把数字写入摘要和结论。
- 所有图表必须有编号、标题、单位和解释。
- 公式不求多，求变量清楚、逻辑闭合。
- 主论文维护 `templates/claim_evidence_map.csv`，确保关键数字能追溯到文件和脚本。
- 支撑材料同步整理，不要最后才找文件。
- 论文证据链闭合后通过 G5。

## 最后 10-12 小时：冻结模型

- 停止大改模型，只修明显 bug 和文字。
- 运行 `python scripts/result_freeze.py check`；若失败，重新冻结并复核所有受影响的论文数字。
- 按 `docs/03_submission_checklist.md` 逐项检查。
- 运行 `scripts/check_submission.ps1` 做文件大小和基础命名检查。
- 确认论文、附录、代码、支撑材料结果一致。
- AI 使用按 `templates/ai_usage_record.md` 整理，论文中按官方要求声明。
- 三人换位审计并通过 G6 后才上传。
- 机器审计先运行 `scripts/audit_project.py`，人工审稿使用 `templates/reviewer_scorecard.csv`。

## 最小可交付标准

- 论文结构完整，摘要能独立说明方案。
- 至少一个基准模型和一个改进模型。
- 至少一种验证或敏感性分析。
- 代码可运行，输出与论文一致。
- 无身份信息，无引用缺失，无支撑材料缺失。
