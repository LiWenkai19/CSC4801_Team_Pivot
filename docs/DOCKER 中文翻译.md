---
title: 在期末项目中使用 Docker
source: DOCKER.md
translator: AI 翻译稿，已经二次对照原文复查修订
---

# 在期末项目中使用 Docker

每个团队仓库**必须**（MUST）包含一个 `Dockerfile`，使任何人都能从 `main` 上的任一提交构建并运行完整环境。镜像从源码重建：**无需上传任何镜像 tar 包**。评分者与审计者直接从仓库构建，且每次缺陷修复后都要重新构建。

## What your repository must provide（仓库必须提供的内容）

- 一个位于 `INSTALL.md` 所写明位置的 `Dockerfile`。
- 已提交到仓库的入口脚本、迁移脚本和种子脚本。
- `INSTALL.md` 中确切的构建、启动、迁移、种子数据和单元测试命令。
- 为任何依赖写入文档的镜像、配置和启动命令。

构建**必须**在干净检出（clean checkout）上成功，不依赖任何未写入文档的命令或机密。运行中的环境**必须**复现确定性种子数据。

## Build and run（构建与运行）

示例命令（将镜像名、端口和应用命令替换为该团队写入文档的对应内容）：

```bash
docker build -t team-example .
docker run -d --name team-example -p 127.0.0.1:8080:8080 team-example
docker exec team-example <migration-command>
docker exec team-example <seed-command>
docker exec team-example <unit-test-command>
```

`INSTALL.md` 还必须写明如何启动任何所需的依赖，以及如何持久化或重置本地数据。评分者必须能够依照该文档操作，而无需猜测任何命令、镜像或机密。

## Auditing another team（审计其他团队）

审计者从**目标团队 `main` 分支上的最新提交**构建。目标团队上的所有开发者都将各自的变更与修复发布到 `main`。审计者只负责发现并报告缺陷；修复由目标团队负责。审计前务必更新到最新提交，以免报告已过时的缺陷：

```bash
git clone <target-repo>
cd <target-repo>
git checkout main
git pull
docker build -t audit-target .
```

然后按照该团队的 `INSTALL.md` 启动、迁移、灌入种子数据并运行单元测试。在每份报告中记录确切的提交 SHA。不得修改目标团队的源码或仓库；安全边界参见 [`PEER_REVIEW.md`](PEER_REVIEW.md)。
