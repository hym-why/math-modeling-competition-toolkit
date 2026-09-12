# C题参考文献精读：Parra & Patel (2016) 光伏-储能系统与电价机制

> 用途：全国大学生数学建模竞赛 C 题建模与论文写作参考
>
> 文献：David Parra, Martin K. Patel. *Effect of tariffs on the performance and economic benefits of PV-coupled battery systems*. Applied Energy, 2016, 164: 175–187.
>
> DOI: `10.1016/j.apenergy.2015.11.037`

## 1. 文献基本信息

- **题名**：Effect of tariffs on the performance and economic benefits of PV-coupled battery systems
- **作者**：David Parra；Martin K. Patel
- **期刊**：Applied Energy
- **年份**：2016
- **卷**：164
- **页码**：175–187
- **DOI**：10.1016/j.apenergy.2015.11.037
- **关键词方向**：PV-battery、Li-ion、Pb-acid、retail tariff、levelised cost、break-even analysis、IRR、battery ageing

## 2. 研究问题

论文研究单户住宅中“已有光伏 + 新增电池储能”的技术经济表现，重点回答两个问题：

1. 在不同零售电价机制下，最优电池技术和容量如何变化？
2. 不同监管环境和价值实现方式，会怎样改变储能系统的经济收益？

其核心思想是：**储能系统的经济性不能只由电池价格或效率决定，还受到电价结构、充放电时机、循环频率、电池衰减和当地售电/购电规则共同影响。**

## 3. 系统结构

研究对象可抽象为：

`光伏发电 → 本地负荷 / 电池充电 / 向电网输出`

`电网 → 本地负荷（必要时购电）`

`电池 → 本地负荷（在经济上合适的时段放电）`

论文只评价在既有 PV 系统基础上增加储能的增量价值，而不是重新评价 PV 本体投资。

## 4. 关键变量与符号建议

为了在国赛模型中复用，可统一定义：

| 符号 | 含义 |
|---|---|
| $P_{pv,t}$ | 时刻 $t$ 的光伏发电功率 |
| $P_{load,t}$ | 时刻 $t$ 的负荷功率 |
| $P_{ch,t}$ | 电池充电功率 |
| $P_{dis,t}$ | 电池放电功率 |
| $P_{grid,t}^{in}$ | 从电网购电功率 |
| $P_{grid,t}^{out}$ | 向电网售电功率 |
| $E_t$ | 电池在时刻 $t$ 的储能量 / SOC 对应能量 |
| $E_{max,t}$ | 考虑老化后的可用容量 |
| $\eta_c,\eta_d$ | 充、放电效率 |
| $c_t^{buy}$ | 时刻 $t$ 的购电价格 |
| $c_t^{sell}$ | 时刻 $t$ 的上网/售电价格 |
| $C_{bat}$ | 电池投资成本 |
| $N_{EFC}$ | 等效满循环次数 |
| $r$ | 折现率 |

## 5. 可复用的能量平衡模型

### 5.1 节点功率平衡

对每个离散时刻 $t$：

$$
P_{pv,t}+P_{grid,t}^{in}+P_{dis,t}
=
P_{load,t}+P_{ch,t}+P_{grid,t}^{out}
$$

这是光储优化模型最基本的约束。

### 5.2 电池状态转移

$$
E_{t+1}=E_t+\eta_cP_{ch,t}\Delta t-\frac{P_{dis,t}\Delta t}{\eta_d}
$$

并满足：

$$
E_{min,t}\le E_t\le E_{max,t}
$$

以及充放电功率边界：

$$
0\le P_{ch,t}\le P_{ch}^{max}
$$

$$
0\le P_{dis,t}\le P_{dis}^{max}
$$

如需避免同一时刻同时充放电，可增加二进制变量：

$$
P_{ch,t}\le u_tP_{ch}^{max}
$$

$$
P_{dis,t}\le (1-u_t)P_{dis}^{max},\quad u_t\in\{0,1\}
$$

## 6. 三类电价机制

论文对比三类零售电价：

### 6.1 Flat tariff（固定电价）

全天购电价格基本不随时间变化：

$$
c_t^{buy}=c_0
$$

这种机制下，储能更多承担“提高 PV 自发自用率”的作用。

### 6.2 Time-of-use tariff（分时电价）

论文采用双时段形式，可抽象为：

$$
c_t^{buy}=\begin{cases}
c_{peak}, & t\in T_{peak}\\
c_{off}, & t\in T_{off}\end{cases}
$$

此时电池不仅能存储光伏富余电量，还具有明显的峰谷套利价值。

### 6.3 Dynamic tariff（动态电价）

论文采用与批发市场关联、**每小时一个价格**的动态电价：

$$
c_t^{buy}=f(p_t^{wholesale})
$$

优化器需要根据未来时段电价差决定是否保留电量到更高价值时段再放电。

## 7. 优化目标的建模方式

国赛中可将论文思想转写为“最小化年度总用能成本”：

$$
\min J=\sum_t
\left(
 c_t^{buy}P_{grid,t}^{in}
-c_t^{sell}P_{grid,t}^{out}
\right)\Delta t
+C_{deg}
$$

其中 $C_{deg}$ 为电池衰减成本。

若题目要求系统选型，可进一步加入年化投资成本：

$$
\min J_{annual}
=
C_{energy}+C_{battery,annual}+C_{deg}+C_{O\&M}
$$

也可以做多目标优化：

$$
\min \left(J_{annual},\ E_{grid},\ P_{peak}\right)
$$

分别对应经济成本、对电网依赖和最大需量。

## 8. 电池老化与等效满循环

论文的重要贡献之一是没有把电池视为“寿命期内性能不变”的理想设备，而是模拟了容量与年放电量随使用年限的下降。

在竞赛模型中，可先采用简化的等效满循环 EFC：

$$
N_{EFC}=\frac{\sum_t E_{dis,t}}{E_{nom}}
$$

再构造容量退化关系，例如：

$$
E_{max,y}=E_{nom}(1-\alpha y-\beta N_{EFC,y})
$$

其中：

- $\alpha$：日历老化系数；
- $\beta$：循环老化系数；
- $y$：服役年数。

更高精度模型可把温度、DOD、SOC 区间和倍率加入衰减函数。

## 9. 论文评价指标

### 9.1 自发自用率

$$
SCR=\frac{E_{PV\rightarrow load}+E_{PV\rightarrow battery\rightarrow load}}{E_{PV}}
$$

用于衡量光伏发电有多少在用户侧被实际利用。

### 9.2 等效满循环数

$$
EFC=\frac{E_{annual\ discharge}}{E_{battery,nom}}
$$

循环次数越高，电池资产使用越充分，但也会加快循环老化。

### 9.3 Levelised Cost / Levelised Value

可将寿命周期内成本与累计有效放电量折现后相除：

$$
LCOS=\frac{\sum_{y=0}^{Y}\frac{C_y}{(1+r)^y}}
{\sum_{y=0}^{Y}\frac{E_{dis,y}}{(1+r)^y}}
$$

对应的储能价值可理解为“每单位放电电量避免的购电成本或带来的电价套利收益”。

### 9.4 内部收益率 IRR

令净现值为 0：

$$
0=-I_0+\sum_{y=1}^{Y}\frac{CF_y}{(1+IRR)^y}
$$

论文用 IRR 衡量不同地区和电价机制下增加电池投资的吸引力。

## 10. 论文的关键实验设计

论文对 Pb-acid 和 Li-ion 两类电池进行比较，并测试多个容量。公开页面显示，其容量范围为：

- **2 kWh–20 kWh**；
- 共比较 **10 个容量档位**；
- 最大容量约对应一年中最大 PV 富余能量储存需求。

这种“容量扫描 + 技术类型扫描 + 电价机制扫描”的实验设计非常适合国赛：

$$
Technology\times Capacity\times Tariff\times Scenario
$$

每种组合都计算成本、收益、循环次数、自发自用率、峰值功率等指标，然后寻找 Pareto 最优或综合评分最优方案。

## 11. 论文的关键结论

根据 Applied Energy 官方页面可核实的结果：

1. **动态电价可使电池的 levelised value 相对固定电价提高最多约 28%。**
2. 但动态电价情景下 **levelised cost 可提高约 94%**，因此总体盈利能力反而可能下降。
3. 原因之一是动态电价优化会减少电池的等效满循环次数，使昂贵的储能资产利用率下降。
4. 分时电价的技术、经济表现通常处在固定电价与动态电价之间。
5. Li-ion 的经济性强烈依赖当地零售电价和监管环境。
6. 论文公开摘要报告的最大 IRR：
   - Geneva：约 **−0.2%**；
   - Jura：约 **0.8%**；
   - Germany：约 **4.3%**。
7. 对应的零售电价约为：
   - Geneva：0.22 CHF/kWh；
   - Jura：0.25 CHF/kWh；
   - Germany：0.35 CHF/kWh。
8. 论文 highlights 给出的 Geneva Li-ion 成本门槛：
   - 仅做 PV energy time-shift：约 **375 CHF/kWh**；
   - 若同时进行 demand peak-shaving：约 **500 CHF/kWh**。

## 12. 一个很重要、容易误判的结论

这篇论文最值得借鉴的不是“动态电价一定更好”，而是：

> **单次放电的边际价值更高，不代表整个储能项目的生命周期收益更高。**

动态电价会诱导系统只在少数高价时段放电。虽然每 kWh 的价值上升，但电池利用率下降，固定投资成本要由更少的累计放电量承担，因此 LCOS 上升，最终 IRR 可能变差。

国赛论文中可将这一现象概括为：

$$
\text{高单位收益}\not\Rightarrow\text{高全寿命收益}
$$

因此不能只比较峰谷价差，应同时考察：

- 年放电量；
- 等效满循环次数；
- 容量利用率；
- 电池衰减；
- 全寿命现金流。

## 13. 对当前 C 题建模的可迁移框架

若当前赛题涉及新能源、电力系统、储能或电价优化，推荐采用以下四层模型。

### 第一层：时序能量流模型

输入：

- 光伏/新能源出力；
- 负荷；
- 电价；
- 储能参数。

输出：

- 每时段购电、售电；
- 充放电；
- SOC；
- 弃电量。

### 第二层：调度优化模型

目标：

- 最小用能成本；
- 或最大储能收益；
- 或多目标权衡。

方法候选：

- 线性规划 LP；
- 混合整数线性规划 MILP；
- 动态规划；
- 滚动优化 / MPC。

若约束基本线性，**MILP 是国赛中兼具解释性和可实现性的首选方法**。

### 第三层：寿命与经济模型

对每一年更新：

$$
Capacity_y=f(Age,EFC,DOD,Temperature)
$$

并重新计算下一年度运行收益。

最终计算：

- NPV；
- IRR；
- LCOS；
- 投资回收期；
- 盈亏平衡电池价格。

### 第四层：情景与敏感性分析

至少分析：

- 电池成本 ±10%、±20%、±30%；
- 电价水平；
- 峰谷价差；
- 光伏装机规模；
- 电池容量；
- 循环寿命；
- 充放电效率；
- 折现率；
- 不同地区/政策情景。

## 14. 可以直接放入国赛论文的表达思路

### 14.1 模型动机

> 由于储能设备的经济收益不仅与峰谷电价差有关，还受到循环次数、容量衰减与资产利用率的共同影响，本文建立时序能量流—储能衰减—全寿命经济评价一体化模型，对不同储能容量和调度策略进行联合优化。

### 14.2 模型评价

> 与仅基于单日典型曲线或静态峰谷套利的评价方法相比，时序模型能够同时反映可再生能源出力波动、电价变化和电池 SOC 约束，从而避免高估储能系统的经济收益。

### 14.3 敏感性分析

> 参考 Parra 和 Patel 对不同电价制度与电池成本情景的比较思想，本文通过参数扰动分析关键参数对最优配置及经济指标的影响，从而检验模型结论的稳健性。

> 注意：正式参赛论文中应根据本队模型和实际结果重新组织语言，不建议原样照搬。

## 15. 建议绘制的图表

为了增强论文表现力，建议复现/扩展以下类型图表：

1. **电池容量—年成本曲线**：横轴容量，纵轴总成本/收益。
2. **容量—IRR 曲线**：比较不同电价机制。
3. **容量—EFC 曲线**：解释为何大容量未必更经济。
4. **SOC 时序图**：选典型日展示调度逻辑。
5. **电价 + 充放电联合时序图**：证明策略会在高价时段释放电量。
6. **敏感性 Tornado 图**：比较电池成本、电价、效率、寿命等参数影响。
7. **二维热力图**：电池容量 × 电价差 → NPV/IRR。
8. **Pareto 前沿**：经济成本 vs 峰值削减 / 新能源消纳。

## 16. 对建模实现的建议

推荐代码结构：

```text
load_data.py
battery_model.py
tariff_model.py
optimizer.py
economics.py
sensitivity.py
visualize.py
```

核心流程：

```text
读取时序数据
  ↓
构造 PV / 负荷 / 电价序列
  ↓
遍历电池技术与容量
  ↓
执行逐时调度优化
  ↓
统计 EFC 与衰减
  ↓
更新下一年电池参数
  ↓
计算 NPV / IRR / LCOS
  ↓
情景分析与敏感性分析
  ↓
输出最优容量与策略
```

## 17. 引用格式

### GB/T 7714 风格

> PARRA D, PATEL M K. Effect of tariffs on the performance and economic benefits of PV-coupled battery systems[J]. Applied Energy, 2016, 164: 175-187. DOI:10.1016/j.apenergy.2015.11.037.

### BibTeX

```bibtex
@article{Parra2016Tariffs,
  title   = {Effect of tariffs on the performance and economic benefits of PV-coupled battery systems},
  author  = {Parra, David and Patel, Martin K.},
  journal = {Applied Energy},
  volume  = {164},
  pages   = {175--187},
  year    = {2016},
  doi     = {10.1016/j.apenergy.2015.11.037}
}
```

## 18. 信息来源与使用边界

本文档依据 Applied Energy / ScienceDirect 公开页面中可访问的题录、摘要、Highlights、方法与结果页面信息进行整理，并结合数学建模常用储能优化框架进行了“可迁移建模”重构。

其中：

- 文献题录、容量范围、三种电价类型、主要实验结论与 IRR 数值属于原文公开信息；
- 本文档中的统一符号、MILP 约束、目标函数、EFC 简化表达式、国赛写作模板和代码结构属于面向竞赛的二次建模建议，并非逐字摘录原论文公式；
- 若最终论文需要复现作者精确参数、老化方程或图中数值，应以原始 PDF 正文为准。

## 19. 原始来源

- ScienceDirect / Applied Energy: https://www.sciencedirect.com/science/article/pii/S0306261915014877
- DOI: https://doi.org/10.1016/j.apenergy.2015.11.037

---

**建议下一步**：结合当前 C 题实际附件数据，把本文框架映射到题目的变量、约束与目标函数，并建立一个可运行的 MILP/时序仿真基线模型。