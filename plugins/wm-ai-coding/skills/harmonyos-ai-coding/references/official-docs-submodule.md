# Official Docs Submodule — harmonyos-ai-coding

## Submodule Structure

```
skills/harmonyos-ai-coding/
├── docs/          ← OpenHarmony 官方文档（git submodule）
├── references/    ← 本 skill 参考文档
└── SKILL.md
```

官方文档仓库：`git@gitcode.com:openharmony/docs.git`

添加方式：
```bash
cd skills/harmonyos-ai-coding
git submodule add git@gitcode.com:openharmony/docs.git docs
```

## ⚠️ 常见陷阱：Orphan Gitlink

### 症状

`git submodule add` 报错：
```
fatal: Pathspec 'skills/harmonyos-ai-coding/docs' is in submodule 'skills/harmonyos-ai-coding'
```

但 `.gitmodules` 中实际上没有 `skills/harmonyos-ai-coding` 条目。

### 根因

`skills/harmonyos-ai-coding` 目录已在父仓库 git index 中注册为 **orphan gitlink**（mode `160000`），但没有对应的 `.gitmodules` 条目。这通常发生在：
- 之前用 `git add` 错误地 staged 了一个目录但没有完成 submodule 注册
- 从其他仓库迁移时带来了 gitlink

### 检测

```bash
# 检查是否有 orphan gitlink
git ls-files --stage | grep "160000"

# 示例输出（orphan — 无 .gitmodules 对应）：
# 160000 5bcba226986611afb6c606ffa48f8ac35d495735 0  skills/harmonyos-ai-coding
```

### 修复

```bash
# 移除 orphan gitlink（不是删除文件）
git rm --cached skills/harmonyos-ai-coding

# 然后重新添加 submodule
cd skills/harmonyos-ai-coding
git submodule add git@gitcode.com:openharmony/docs.git docs
```

**注意**：`git rm --cached` 只从 index 移除引用，**不删除工作目录中的文件**。

## 日常使用

### 保持官方文档更新

```bash
cd skills/harmonyos-ai-coding/docs
git fetch origin
git checkout master   # 或指定分支
```

### 父仓库提交 submodule 引用变更

```bash
# 在父仓库（sexual）更新 submodule 指针
cd /path/to/sexual
git add skills/harmonyos-ai-coding
git commit -m "chore: sync harmonyos-ai-coding/docs to <hash>"
git push origin master
```

## 参考

- `git-branch-hygiene` skill — 通用 submodule 管理规范（含 gitlink drift、staged-index 问题）
