# 数据与实验协议

## 赛前一次性环境体检

```powershell
python scripts/project_doctor.py
```

必须安装项缺失时脚本返回失败；`statsmodels`、PuLP、Scikit-Criteria 是按题型选装项。报告写入 `state/environment_report.json`，不要把含本机信息的报告放进支撑材料。

## G1：建立数据契约

拿到附件后，为所有 CSV、Excel 或 JSON 建立数据契约：

```powershell
python scripts/data_contract.py create data/附件1.xlsx data/附件2.csv
```

脚本记录文件哈希、工作表、行列数、重复行、字段类型、缺失率、唯一值和数值摘要，并提示高缺失、常量列和疑似 ID。建模前必须人工补查：单位、业务口径、时间顺序、标签泄漏、不同表的连接键。

数据或附件变化后运行：

```powershell
python scripts/data_contract.py check
```

检查失败时重新生成契约，并从受影响的最早门控回退。

## G2：冻结假设和实验计划

- 在 `templates/assumption_register.csv` 给假设编号，写清不成立时的影响和验证方法。
- 在 `templates/experiment_plan.csv` 先登记基准、主模型、指标和接受规则。
- 主模型必须回答“比基准改善多少、增加的复杂度是否值得”。

## G3：通过实验包装器运行

```powershell
python scripts/run_experiment.py --name q1_baseline --entry code/main.py --seed 42 --parameter method=baseline
```

传递给主程序的参数放在最后一个 `--` 后：

```powershell
python scripts/run_experiment.py --name q2_main --entry code/q2.py --seed 42 --parameter alpha=0.2 -- --folds 5
```

每次运行在 `experiments/<时间_名称>/` 留下：

- `manifest.json`：命令、种子、参数、代码与输入哈希、依赖版本、输出哈希、返回码。
- `stdout.log` 和 `stderr.log`：运行记录。

如果实验过程中修改了 `data/` 或 `code/`，或者没有产生新结果，脚本会警告。警告不能自动证明错误，但必须由主程序解释。

## G4-G6：冻结与审计

```powershell
python scripts/result_freeze.py freeze
python scripts/audit_project.py --forbidden "学校全名" --forbidden "队员姓名"
python scripts/gatekeeper.py pass G6 --note "终审通过" --artifact state/audit_report.json
```

完整审计要求：数据契约未过期、至少一次成功实验、冻结结果未变化、关键结论和图表证据完备、G1-G5 已通过。比赛中途可用 `--skip-gates` 查看其余缺口，但这不能放行 G6。

人工审稿表按 100 权重折算为 5 分制，内部放行线为 3.50；任一维度不高于 2 分直接阻断。这只是队内质量门槛，不代表奖项预测。
