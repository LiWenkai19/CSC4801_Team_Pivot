# Agent 任务分发说明（给人类看）

每个任务一个会话、一个 git worktree、一个分支。会话里可以自行调用子代理。

## 分发顺序

```text
第 1 波（串行，先合并）: P0
第 2 波（P0 合并后并行）: P1  P2  P4  P6  P7  P10
第 3 波（依赖第 2 波）:   P3(需 P2)  P5(需 P4)  P8  P9  P12
第 4 波（收口）:          P11（需其余全部合并）
```

P1 只改 `requirements.lock` 和 `tests/unit/`，理论上可与 P0 并行；但 P0 会改 `.gitignore`，
为免冲突仍建议 P0 先合。

## 每个任务怎么开

在主仓库（`app/`）根目录执行，`P2` 替换为任务号：

```sh
git switch main && git pull
git worktree add ../wt-P2 -b test/P2 main
```

然后在 `../wt-P2` 打开一个新会话，**先粘贴 `_PREAMBLE.md` 全文，再粘贴 `P2.md` 全文**。

## 合并流程

1. Agent 交回汇报（模板见 `_PREAMBLE.md`）后，你检查：
   - `git -C ../wt-P2 diff --stat main...` 只出现该任务允许的路径；
   - 汇报中的命令你自己重跑一次（至少是验收命令）。
2. 推送分支开 PR，等 CI 绿后合并到 `main`。
3. 删除工作区：`git worktree remove ../wt-P2 && git branch -d test/P2`。
4. 后续任务开工前，从最新 `main` 建工作区。

## 为什么不会互相冲突

- 每个任务只新增 `tests/advanced/<自己的目录>/` 和 `docs/testing/` 下自己的文件。
- 所有共享文件（`run.py`、`conftest.py`、`requirements.txt`、`.gitignore`、首版 CI）
  只由 P0 修改；README/INSTALL/DOCKER 只由 P11 修改。
- `run.py` 自动发现模式目录，新模式不需要改它或改 CI。
- 业务缺陷各写 `docs/testing/findings/P<n>.md`，不共享一个文件。

## 并行运行时的资源隔离

- 每个工作区的测试都在本机新建临时 PG 集群（随机端口），不会互相抢库。
- 不要让两个会话同时对同一个 `--out` 目录写产物；`run.py` 会拒绝非空目录。
- 本机同时跑 3 个以上 PG 集群时注意内存；mutation（P7）最吃 CPU，尽量错开。

## 汇报给 Claude（我）时

把 Agent 的汇报原文 + 你的重跑结果贴过来即可；遇到阻塞时附上失败命令的完整输出。
