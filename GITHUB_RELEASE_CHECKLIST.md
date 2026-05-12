# GitHub 发布检查清单

本清单用于把本地附件仓库发布到 GitHub。当前仓库已发布到 <https://github.com/ginsonko/Artificial-PsyArch-test->，远端分支为 `main`，发布锚点提交为 `3b60865733d620ddfe75eacb603f985f49e5fa84`。

## 1. 发布前检查

- 确认当前目录为 `Artificial-PsyArch-test实验论文数据集附件`。
- 运行 `git status --short --branch`，应只显示当前分支且无未提交变更。
- 运行 `python scripts/verify_release_integrity.py`，确认 tracked 文件、`manifest.json`、顶层文件哈希和补丁哈希一致。
- 确认 `README.md`、`REPRODUCE.md`、`MANIFEST.md`、`LICENSE`、`CITATION.cff` 均存在。

## 2. 推荐仓库名称

当前 GitHub 仓库名：

```text
Artificial-PsyArch-test-
```

中文说明可以放在仓库 description 中：

```text
Artificial PsyArch paper reproducible experiment appendix / 人工心智架构实验论文数据集附件
```

## 3. 使用 GitHub CLI 发布

如果已安装并登录 GitHub CLI，可在本仓库目录运行：

```powershell
gh auth status
gh repo view ginsonko/Artificial-PsyArch-test-
git ls-remote --heads origin main
```

## 4. 使用网页手动发布

如果不使用 GitHub CLI：

1. 在 GitHub 网页确认仓库 `https://github.com/ginsonko/Artificial-PsyArch-test-` 存在。
2. 在本仓库目录运行：

```powershell
git remote -v
git push origin master:main
git ls-remote --heads origin main
```

3. 确认 GitHub 页面显示最新提交。

## 5. 发布后建议

- 在 GitHub release 中上传论文总发布包 `AP-paper-v3.34-public-review-release-2026-05-12.zip`。
- 在 release notes 中粘贴总发布包 manifest 的 `package_sha256`。
- 如果仓库 URL 后续发生变化，发布后请同步更新 `README.md`、`manifest.json` 与本清单。
