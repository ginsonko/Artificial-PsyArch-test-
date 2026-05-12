# GitHub 发布检查清单

本清单用于把本地附件仓库发布到 GitHub。当前仓库已经准备到可上传状态；由于本机未安装 GitHub CLI（`gh`）且没有配置 remote，本轮没有直接推送。

## 1. 发布前检查

- 确认当前目录为 `Artificial-PsyArch-test实验论文数据集附件`。
- 运行 `git status --short --branch`，应只显示当前分支且无未提交变更。
- 运行 `python scripts/verify_release_integrity.py`，确认 tracked 文件、`manifest.json`、顶层文件哈希和补丁哈希一致。
- 确认 `README.md`、`REPRODUCE.md`、`MANIFEST.md`、`LICENSE`、`CITATION.cff` 均存在。

## 2. 推荐仓库名称

GitHub 仓库名建议使用 ASCII：

```text
Artificial-PsyArch-test
```

中文说明可以放在仓库 description 中：

```text
Artificial PsyArch paper reproducible experiment appendix / 人工心智架构实验论文数据集附件
```

## 3. 使用 GitHub CLI 发布

如果已安装并登录 GitHub CLI，可在本仓库目录运行：

```powershell
gh auth status
gh repo create Artificial-PsyArch-test --public --source . --remote origin --push --description "Artificial PsyArch paper reproducible experiment appendix"
git ls-remote --heads origin master
```

## 4. 使用网页手动发布

如果不使用 GitHub CLI：

1. 在 GitHub 网页新建空仓库 `Artificial-PsyArch-test`，不要勾选自动创建 README、LICENSE 或 `.gitignore`。
2. 在本仓库目录运行：

```powershell
git remote add origin https://github.com/<your-account>/Artificial-PsyArch-test.git
git push -u origin master
git ls-remote --heads origin master
```

3. 确认 GitHub 页面显示最新提交。

## 5. 发布后建议

- 在 GitHub release 中上传论文总发布包 `AP-paper-v3.31-public-review-release-2026-05-12.zip`。
- 在 release notes 中粘贴总发布包 manifest 的 `package_sha256`。
- 如果仓库 URL 与 `CITATION.cff` 中的占位 URL 不同，发布后请更新 `repository-code` 并重新提交。
