# gb-0027 · 质量通告 / 失效试样 / 依据停用 验证批次

验证日期：2026-11-15。运行环境：SQLite（`DATABASE_URL=sqlite:///...`）+ fakeredis，
后端 FastAPI TestClient 与真实 uvicorn 两种通路；前端 Vite 6.4.6 + Chromium
（Playwright，1440×1000 与 390×844）。

## 结论

| 验证项 | 结果 |
|---|---|
| 按试样清单跨研究发布通告 | 通过：单份通告 items 覆盖 QN-NEAR 与 QN-CONST 两份试样，`study_code/treatment_code` 被补齐并显示 |
| 撤销通告只允许新建检验恢复 | 通过：撤销后旧 run 仍 invalidated，新 run 重新纳入试样 |
| 重叠通告全部撤销才恢复 | 通过：两份重叠通告覆盖同一试样，撤销一份后新检验仍排除；两份都撤销后恢复 |
| 新检验排除失效试样并冻结排除依据 | 通过：`snapshot.exclusions` + `specimen_exclusions` 行 + `exclusion_fingerprint`；原等级保留 |
| 保留全部工艺、样本不足明确失败 | 通过：排除 26/30 后 T1 仅 4 份，run 直接 `failed`，错误写明组别，4 个工艺仍在快照中 |
| 通告与排队并发 | 通过：两种交错下均为“已排除”或“已停用”，无空窗 |
| 通告与计算完成并发 | 通过：worker 完成不恢复停用；撤销后仍停用 |
| 通告与复检分发并发 | 通过：并发中先完成的分发可成功，随后依据命中永久停用，后续导出 409 |
| 撤销只允许新建检验，旧结果/批准说明可查不再分发 | 通过：说明列表仍返回 `status=approved`，export 返回 409 |
| 来源页追查通告/排除/受影响依据 | 通过：逐份“失效·不入新检验”+ 通告编号；通告表显示 `affected_run_ids` |
| 结果页追查通告/排除/受影响依据 | 通过：停用横幅、冻结排除表、排除指纹、应用通告编号 |
| 说明页显示依据状态 | 通过：停用横幅、禁止新建/批准、禁止下载并说明原因 |
| 旧任务无 `RunQualityBasis` 行 | 通过：发布通告时补建并持久化停用，撤销不恢复 |

## 自动化脚本（本目录 tools/）

- `api_tests.py` — 端到端 HTTP 流程（登录、建 run、说明批准、导出 409、重叠撤销、跨研究、样本不足、迟到结果、trace、审计）。
- `concurrency_test.py` — 双线程交错：发布 vs 新建、撤销 vs 新建、通告 vs worker 完成、撤销后 worker、通告 vs 分发、旧任务无依据行。
- `serve_only.py` / `work_once.py` — 本地 SQLite 服务与单次 worker（用于截图）。
- `ui_flow.py`、`ui_results.py`、`ui_cross.py`、`ui_final.py`、`ui_failed_result.py` — 浏览器流程与截图。

运行（需先启动 backend 与 vite，按 README 的 18231/19231）：

```bash
cd test-artifacts/gb-0027/tools
python3.11 api_tests.py
python3.11 concurrency_test.py
```

## 截图

| 文件 | 内容 |
|---|---|
| 01-data-notices.png | 来源页：质量通告区、失效行、通告表单 |
| 02-data-overlap.png | 发布第二份重叠通告后的通告表 |
| 03-runs-queued.png | 通告后新建检验进入队列 |
| 04-results-valid.png | 有效依据结果：冻结排除依据表 + 指纹 |
| 05-results-invalidated.png | 停用依据结果：红色横幅、只作留档 |
| 06-notes.png | 说明页（viewer）：可读、不可下载状态 |
| 07-runs.png | 运行队列：停用依据 + 排除份数 |
| 08-data-final.png | 来源页最终布局（通告区整行） |
| 09-data-cross-study.png | 跨研究通告（QN-SHIFT + QN-NEAR） |
| 10-data-revoked.png | 撤销一份重叠通告后的历史与撤销原因 |
| 11-notes-admin.png | 负责人视角：停用说明禁止审批/下载 |
| 12-overview.png | 总览页未被改动 |
| 13-runs-shortage.png | 样本不足失败任务与约束说明 |
| 14-data-mobile.png | 390px 移动端来源页 |
| 15-results-failed.png | 失败任务仍保留冻结排除依据 |

## 已知差异 / 边界

- 本地验证用 SQLite + fakeredis；未在本机启动 MySQL/Redis/Docker（环境无 docker）。
  质量锁在 MySQL 用 `SELECT ... FOR UPDATE`，SQLite 下额外执行一次无操作 UPDATE 取得写锁。
- 通告发布/撤销与分发都在单行质量锁上串行化；并发验证证明不会出现“既未排除也未停用”的窗口，
  但 SQLite 的真实并发粒度仍弱于 MySQL 行锁，生产环境以 Compose 的 MySQL 为准。
- `.gitignore` 的第 11 行 `*.png` 会忽略本目录截图，但不会忽略脚本与说明；截图仅在本地验证留存，
  需要入库时用 `git add -f`，否则可保留在本地。
