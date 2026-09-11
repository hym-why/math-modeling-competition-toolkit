# 数学建模国赛省奖冲刺包

这套材料面向 3 名 CST/计算机背景学生，目标是在 7-10 天内建立一套能稳定产出“完整、可信、规范、可复现”论文的工作流，优先冲省三/省二。

## 快速使用

1. 先读 `docs/01_training_schedule.md`，按天执行赛前训练。
2. 再读 `docs/02_contest_runbook.md`，把赛中每个时间段要做什么固定下来。
3. 读 `docs/07_data_and_experiment_protocol.md`，跑通数据契约与可复现实验。
4. 读 `docs/08_official_five_year_benchmark.md`，用五年官方 C 题验证模型选择。
5. 城市绿色物流 A 题复盘读 `docs/09_green_logistics_official_comparison.md`。
6. 用 `templates/paper_template.md` 开论文骨架，正式数字只从冻结结果填写。
7. 按 `docs/05_quality_gates.md` 通过 G1-G6，并执行最终机器审计。
8. 提交前逐项过 `docs/03_submission_checklist.md`，并把 AI 使用记录整理到 `templates/ai_usage_record.md`。

## C题数据预处理专题

本仓库已整理 C 题的完整数据预处理方案、与 26c 论文方法的对比、论文可直接使用的文字，以及配套可视化图表：

- [C题数据预处理方案](docs/C题数据预处理方案.md)
- [C题数据预处理图总览](output/C题_数据预处理图/C题_数据预处理图总览.png)

## 本机运行命令

如果已经安装并配置 Python：

```powershell
python code/example_pipeline.py
```

当前这台机器可以使用 Codex 自带 Python：

```powershell
C:\Users\HUAWEI\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe code\example_pipeline.py
```

项目已建立 `.venv` 并安装核心数据与绘图库。PowerShell 中可激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

只有选定题型后才安装可选算法库：

```powershell
python -m pip install -r code/requirements_optional.txt
```

提交前基础检查：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/check_submission.ps1
```

赛前环境与工具自检：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/preflight.ps1
```

结果冻结与门控：

```powershell
python scripts/score_problems.py
python scripts/data_contract.py create data/附件.xlsx
python scripts/run_experiment.py --name q1_baseline --entry code/main.py --seed 42
python scripts/result_freeze.py freeze
python scripts/result_freeze.py check
python scripts/audit_project.py --forbidden "学校全名" --forbidden "队员姓名"
python scripts/gatekeeper.py status
```

最终一键检查：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/final_check.ps1 -ForbiddenTerms "学校全名","队员姓名"
```

下载并回归近五年官方 C 题：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/fetch_official_benchmarks.ps1
python scripts/benchmark_suite.py
python scripts/model_benchmarks.py --case all
```

封闭试运行城市绿色物流 A 题：

```powershell
python scripts/data_contract.py check --contract state/green_logistics_data_contract.json
python scripts/run_experiment.py --name green_logistics_final --entry code/green_logistics_trial.py --seed 2026 -- --starts 6 --mc-trials 100
```

输入只取自 `data/green_logistics_A/` 的四个题面附件。报告、路径、到达时间、成本拆分、
动态事件与路线图写入 `outputs/green_logistics_trial/`。代码不访问网络。

用官网优秀论文对照审计已保存的封闭试运行结果：

```powershell
python code/audit_green_logistics_comparison.py
```

审计不会重新优化或覆盖原路线，结果写入
`outputs/green_logistics_official_audit.json`。

## 推荐目录

```text
data/          # 赛题数据、外部公开数据；不要放身份信息
code/          # 可运行源程序和复现实验脚本
outputs/       # 结果表、图片、中间文件
experiments/   # 每次正式运行的命令、日志、哈希和依赖版本
templates/     # 论文、选题、AI 使用、支撑材料模板
docs/          # 训练计划、赛中流程、检查清单
submission/    # 最终论文和支撑材料压缩包
scripts/       # 提交前辅助检查脚本
state/         # 门控、数据契约、环境、结果冻结和审计状态
```

## 三人固定分工

- 队长/建模：选题、假设、指标、模型结构、结果解释、最终拍板。
- 主程序：数据清洗、算法实现、图表导出、结果复现、支撑材料整理。
- 主论文：摘要、正文结构、图表标题、格式、引用、匿名和提交清单。

三人都必须能读懂核心代码和论文主线，避免任一成员掉线导致整队停摆。

## 官方规则提醒

- 2026 年竞赛开始时间以官方发布为准；赛题发布、报名和提交请走官方渠道。
- 竞赛期间必须独立完成，不得与队外人员讨论赛题。
- 可以使用 AI 工具辅助，但要透明声明、人工核验，并保留使用记录。
- 电子论文、纸质论文、附录和支撑材料必须一致；支撑材料中的程序要能运行，且不能出现学校、姓名、赛区等身份信息。

参考：

- https://www.mcm.edu.cn/
- https://www.mcm.edu.cn/html_cn/node/9d8e511fe7a1447b35f53a82c908e2e0.html
- https://www.mcm.edu.cn/html_cn/node/4cd596519c9eb9fbd866398f6df0caa3.html

## 设计参考

本冲刺包采用独立实现，综合参考多个开源竞赛工作流与成熟算法项目。详细筛选、许可证情况、采用与放弃理由见 `docs/06_github_research_and_upgrade.md`。定位仍然是让三名新手在 7-10 天内掌握并真正执行，不用工具数量制造虚假完备感。
