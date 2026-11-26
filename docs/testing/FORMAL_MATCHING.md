# FP-MATCH-1 匹配公式的形式化验证

本文件记录 `formal` 模式（`python tests/advanced/run.py formal`）的方法、结果和局限。
验收命令为 `python tests/advanced/run.py formal` 与 `python tests/run_tests.py`，
本模式**不需要数据库**（没有 `NEEDS_DB`）。

## 1. 结论与方法

- 用 Z3 对 [FP-MATCH-1](../REQUIREMENTS.md#5-matching-contract) 的**规格公式**证明
  7 条性质（T1–T7）：把每条性质取反后求解，结果全部为 `unsat`，即不存在满足前置
  条件却违反后置条件的赋值。
- 用真实 `match_score` 在 5 元素全集 `{a,b,c,d,e}` 的**全部 1024 个子集对**上与 Z3
  编码逐一比对：1024/1024 一致，0 个不一致。
- 在同一批 1024 对上用真实实现重放 T1–T7：全部成立（有界穷举，不是证明）。

方法上，每个测试把 Hoare 三元组 `{P} C {Q}` 的否定 `P ∧ ¬Q` 交给
`z3.Solver`：`unsat` 表示 `{P} C {Q}` 在规格层面成立。耗时是单次
`Solver.check()`，另设 2 秒/查询上限并由测试断言（本机多次运行实测均低于 0.05 秒）。

**必须说清楚的边界**：证明对象是 `tests/advanced/formal/encoding.py` 里的
**规格公式**，不是 `backend/app/employer/matching.py` 的 Python 代码。SMT 证明
不会执行 Python；规格与代码的联系来自第 5 节的**有界穷举对拍**。因此本文所有
"证明"都应读作"规格公式的证明"，不能读作"实现已被证明正确"。

## 2. 编码

文件：[`encoding.py`](../../tests/advanced/formal/encoding.py)。

- **算术层**：`n = |R|`、`k = |C ∩ R|` 是 Z3 `Int` 变量。前置条件为
  `n >= 1`、`0 <= k <= n`；`score := (100*k) div n`。Z3Py 在 `Int` 上用 `/`
  生成 SMT-LIB `div`（欧几里得整数除法）；这里分子非负、分母为正，所以它等于
  `floor`。`total_score` 额外编码需求里的 `n = 0 -> 100` 特例。
- **集合层**：有界全集 `U` 取 6 个元素，`C`、`R` 各用 6 个布尔成员变量表示；
  `k`、`n` 用 `Sum(If(flag, 1, 0))` 定义；`R ⊆ C` 逐元素编码为蕴含。
- **有界性**：集合层命题对 `|U| = 6` 的**所有**集合成立（穷尽布尔赋值），但它是
  有界命题，不是无界集合论命题。
- 编码不导入 `app.*`。Z3 一侧与 Python 一侧是同一需求文字的两份独立描述。

## 3. 条款 → 性质 → Hoare 三元组 → 结果 → 耗时

| 条款（FP-MATCH-1） | 性质 | Hoare 三元组 | SMT 结果 | 实现侧有界穷举 | 耗时 |
|---|---|---|---|---|---|
| 结果必须是 0–100 的整数 | T1 | `{n >= 1 ∧ 0 <= k <= n} score := (100*k) div n {0 <= score <= 100}` | `unsat` | 1024/1024 对满足 | 0.0044 s |
| 示例行 1、3 | T2 | `{n >= 1 ∧ 0 <= k <= n} score := (100*k) div n {k = n -> score = 100 ∧ k = 0 -> score = 0}` | `unsat` | 992/992 对满足（`n = 0` 的 32 对不适用，跳过） | 0.0030 s |
| `floor(100*\|C∩R\|/\|R\|)` | T3 | `{n >= 1 ∧ 0 <= k <= n} score := (100*k) div n {score*n <= 100*k ∧ 100*k < (score+1)*n}` | `unsat` | 992/992 对满足 | 0.0053 s |
| 按分数排序（重合度单调） | T4 | `{n >= 1 ∧ 0 <= k1 <= k2 <= n} score1 := (100*k1) div n; score2 := (100*k2) div n {score1 <= score2}` | `unsat` | 992 对归并为 20 个 `(n,k)` 组合，55 次单调比较全部成立 | 0.0144 s |
| 满分语义 | T5 | `{\|R\| >= 1} score := score_of_sets(C,R) {score = 100 ↔ R ⊆ C}` | `unsat` | 992/992 对满足 | 0.0040 s |
| 只有 `C ∩ R` 贡献分数 | T6 | `{\|R\| = n ∧ x ∉ R ∧ x ∉ C} score := score_of_sets(C,R); score' := score_of_sets(C ∪ {x}, R) {score' = score}` | `unsat` | 1024 对上的 1280 次"添加无关技能"全部未改变分数 | 0.0117 s |
| 示例行 2 | T7 | `{n = 2 ∧ k = 1} score := (100*k) div n {score = 50}` | `unsat` | 160/160 对满足 | 0.0005 s |

- T2/T3/T5 的 `n = 0` 对（即 `R` 为空，共 32 对）按定理前置条件 `n >= 1` 排除；
  空需求列表的 100 分由示例行 4 与 1024 对主对拍覆盖。
- T1–T7 全部由 [`test_matching_theory.py`](../../tests/advanced/formal/test_matching_theory.py)
  中的独立测试证明，表内耗时取自本机一次运行，全部远低于 2 秒上限。

## 4. 负向测试（编码非平凡性）

两个**故意为假**的性质必须返回 `sat` 并给出反例；如果返回 `unsat`，说明编码是
平凡真或除法语义不对，T1–T7 的证明就失去意义。

| ID | 假性质 | 结果 | 反例（求解器模型） |
|---|---|---|---|
| N1 | `floor(100k/n) = round_half_up(100k/n)` | `sat` | `n = 6, k = 4`：floor = 66，round-half-up = 67 |
| N2 | `score = floor(100*\|C∩R\| / \|C\|)`（分母误用候选人数） | `sat` | 6 元全集中 `C = {0,2,4,5}`、`R = {4}`：规格分 100，错误公式 25 |

N1 同时验证了编码用的是整数 floor 而不是实数除法：若 `/` 是实数除法，这个假性质
会变成恒真并得到 `unsat`，测试即失败。N2 说明"分母是 `|R|` 而不是 `|C|`"不是
文字游戏，编码能把它与规格区分开。反例只断言"存在且违反对应性质"，不固定具体
模型值，因此不依赖 Z3 版本的反例选择。

## 5. 规格到代码：有界穷举对拍

文件：[`test_spec_to_code.py`](../../tests/advanced/formal/test_spec_to_code.py)。

- 全集 `U = {a,b,c,d,e}`，32 个子集，枚举全部 `32 × 32 = 1024` 个 `(C, R)` 对。
- 对每一对同时得到三个值：
  1. 真实 `app.employer.matching.match_score` 的返回值；
  2. Z3 编码在该具体赋值下的值（1024 个等式放进一个 solver，从模型读出）；
  3. 由需求文字独立写出的 `100 if |R| = 0 else (100*|C∩R|)//|R|`。
- 结果：**1024/1024** 三方一致，0 个不一致；不一致断言会打印
  `candidate`、`required`、`n`、`k` 与两侧取值。
- 需求示例行（`Python, SQL` vs `Python, SQL` → 100；`Python` vs `Python, SQL` → 50；
  `Rust` vs `Python, SQL` → 0；任意技能 vs 空列表 → 100）另由真实实现单独断言，
  期望值按需求手算。

分数分布（1024 对）：100 分 243 对、0 分 211 对、50 分 220 对，其余为
20/25/33/40/60/66/75/80；所有取值都在 0–100 内。

**这不是证明**：它只覆盖 `|U| = 5` 的具体集合，不能排除 `|R| > 5` 或归一化路径上
的实现错误；它的作用是给第 3 节的规格证明提供"实现与规格在这些输入上一致"的
经验证据。

## 6. 自检

1. **负向测试本身**：第 4 节两个 `sat` 查询就是"求解器能判出错误"的自检。
2. **规格侧变异**：把 `encoding.py::int_div` 临时从
   `numerator / denominator` 改为乘法近似 `numerator * denominator`，再运行
   `python tests/advanced/run.py formal`，结果 `1`（失败）：
   - T1、T2、T3、T5、T7 由 `unsat` 变为 `sat`（性质被破坏）；
   - 1024 对主对拍报告真实反例：`candidate=['a'], required=['a','b']`，
     真实实现 50，变异编码 200；
   - T4 仍为 `unsat`（乘法在 `k1 <= k2` 下仍单调），符合预期；
   - 实现侧的 7 个有界穷举测试全部通过——它们只调用真实 `match_score`，不受
     编码变异影响。这正好展示了"规格测试"与"代码测试"的分工。
   恢复为整数除法后重新运行，18 个测试全部通过。生产代码未改动。
3. **实现侧变异**：用一个仓库外的 pytest 插件把 `test_spec_to_code` 里的
   `match_score` 引用替换成分母误用 `|C|` 的错误实现（生产代码与仓库文件均未
   改动），再运行同目录测试，结果 `8 failed, 10 passed`：需求示例、1024 对主对拍
   以及 T2–T7 全部变红（如 `candidate=['a'], required=['a','b']`，错误实现 100，
   规格 50）；只有 T1 的 0–100 范围检查仍然通过（错误分母的结果仍落在 0–100），
   这也说明各性质检查的分工与覆盖边界。

## 7. 局限

- **未证明 Python 代码本身**。证明对象是规格公式；代码只通过 5 元素全集的
  1024 对有界穷举与规格关联。实现若只在 `|R| > 5` 时出错，本模式发现不了。
- **归一化不在 SMT 模型内**。`match_score` 先做 trim/lower/去空/去重，这部分
  由 P1 的属性测试覆盖；本模式只比较归一化后的集合语义。
- **集合证明有界**：T5、T6 的 `unsat` 是对 `|U| = 6` 的布尔编码穷尽得到的；算术
  性质 T1–T4、T7 的 `n` 无界，但只在前置条件 `n >= 1` 下成立。
- **Hoare 三元组是语义层面的**：SMT 公式描述前后条件，不是经过证明助手检查的
  程序逻辑；没有对 `match_score` 做符号执行或最弱前置条件演算。
- **耗时与反例依赖运行环境**：耗时是本机实测值；不同 Z3 版本可能给出不同反例，
  测试不固定反例的具体数值，只固定"是反例"。
- 排序键、API 视图等 FP-MATCH-1 的其余条款不在本模式范围内（分别由单元/集成
  测试覆盖）。

## 8. 复现

```powershell
# 仓库根目录，项目虚拟环境（见 tests/advanced/README.md）
python tests/advanced/run.py formal --out "$env:TEMP\csc4801-formal"
python tests/run_tests.py
```

```sh
python tests/advanced/run.py formal --out "$TMPDIR/csc4801-formal"
python tests/run_tests.py
```

`--out` 必须在 checkout 之外且为新目录。产物结构：

```text
<out>/formal/run.log                # pytest 汇总
<out>/formal/junit.xml
<out>/formal/result.json            # 命令、退出码、耗时
<out>/formal/matching_theory.json   # T1–T7、N1–N2 的结果与单次耗时
<out>/formal/spec_to_code_pairs.json
<out>/formal/bounded_T1..T7.json    # 每条的检查数与耗时
<out>/formal/requirement_examples.json
```
