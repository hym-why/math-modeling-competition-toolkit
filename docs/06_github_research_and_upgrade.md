# GitHub 项目调研与升级取舍

调研时间：2026-09-06。筛选标准不是宣传语或 Star 数，而是：能否降低结果错误、能否在 72 小时内执行、是否有真实脚本和测试、是否适合三人 CST 队伍、许可证是否清楚。

## 竞赛工作流项目

| 项目 | 值得借鉴 | 本项目采用 | 未直接采用 |
|---|---|---|---|
| [xuec699-sudo/math-modeling-skills](https://github.com/xuec699-sudo/math-modeling-skills) | 三角色、G1-G6、结果冻结、Claim-Evidence | 已实现轻量六门控和结果哈希 | 60+ 脚本、五人评审、固定 9000 字下限 |
| [Y-love-han/math-modeling-skill](https://github.com/Y-love-han/math-modeling-skill) | fail-closed、数据谱系、复现、反证、隐私扫描；MIT | 输入契约、最终机器审计、G6 必须由审计报告放行 | 12 阶段状态机、哈希链账本、38 个 CLI，短训成本过高 |
| [XiaoMaColtAI/math-modeling-skill](https://github.com/XiaoMaColtAI/math-modeling-skill) | 输入哈希、随机种子、依赖版本、唯一复现命令、图表源数据契约 | `run_experiment.py` 和增强图表契约 | 固定图片数量和双格式论文交付；最终格式仍以当届官方要求为准 |
| [ciyuan1234/MCM_skills](https://github.com/ciyuan1234/MCM_skills) | 数据契约、黄金题回归、假设闭环、时间降级 | 数据侧写与哈希、假设登记表、模拟赛回归思路 | 仓库当前未提供 LICENSE；只参考公开思想，不复制代码或文本；不采用自定义摘要字数等非官方阈值 |
| [han69611/math-modeling-skills](https://github.com/han69611/math-modeling-skills) | 实验管理、创新评分、独立评委视角；MIT | 实验计划表、八维审稿表 | 37 个 Skills 的重复编排层 |
| [SatakaGintoki/MathSkill](https://github.com/SatakaGintoki/MathSkill) | 盲解基线、先查优化可行域、证据覆盖率 | 训练中先盲做再读优秀论文；审稿表强调可行性和证据 | 多 Agent 固定编排，三人短训没有必要 |

## 成熟算法项目

| 项目 | 推荐用途 | 使用原则 |
|---|---|---|
| [statsmodels](https://github.com/statsmodels/statsmodels) | ARIMA/SARIMAX、Holt-Winters、统计检验、残差诊断 | 预测题优先用成熟实现，必须保留朴素预测基线和时间顺序验证 |
| [PuLP](https://github.com/coin-or/pulp) | 线性规划、整数规划、调度与分配 | 先验证可行域和求解器可用，再讨论最优值；赛前完成 solver 冒烟测试 |
| [Scikit-Criteria](https://github.com/quatrope/scikit-criteria) | TOPSIS、ELECTRE 等多准则决策 | 可作为手写 TOPSIS 的交叉验证，不以“换算法名称”冒充创新 |
| [pyDecision](https://github.com/Valdecy/pyDecision) | AHP、熵权、TOPSIS 等大量 MCDA 方法对照 | 仅在确有决策含义时使用，优先少模型、强解释和权重敏感性 |

## 最终结论

本项目继续保持“小而硬”的定位：六门控不扩张为十二阶段；新增数据契约、环境体检、可复现实验、假设登记和机器审计。算法库作为可选依赖，不在不知道赛题时预装一大批包，也不把模型堆叠当创新。

任何外部项目关于论文页数、摘要字数、图片数量和获奖等级的说法，都不能替代 CUMCM 当届官方规则。
