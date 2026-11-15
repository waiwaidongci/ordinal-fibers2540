# 青蘖纸浆等级比较簿

以全体独立试样的合并平均秩，比较纸浆形成等级的组间分布；保留并列修正、全部Dunn组对和人工复检说明。

## 研究场景

青蘖纸材研究组有14位检验分析员。上游按同一盲评口径记录独立纸浆试样的1–9形成等级，1为粗散、9为均整。过去分析员在工作表算等级均值、把1级差理解成固定性能增量，忽略大量并列，又只把事后显著的两组抄进纪要。本册替代来源核对、统一排秩、完整家族比较及复检讨论的一段，下游是负责人批准后的独立制备与盲评安排。

输入文件名 `QN-SHIFT_独立纸浆试样.csv` 用于溯源元数据；试样可逐份录入/编辑或API写入，没有任意CSV解析器。输入有序、非等距，结果不是工艺质量概率或因果结论。拒绝可以由分布形状变化产生，不能无条件解释为纯中位数差。

| 角色 | 页面 | 权限 | 典型动作 |
|---|---|---|---|
| admin 复检负责人 | 六页全部 | 写入、排队、说明、批准/退回、分发、发布/撤销质量通告 | 批注新批独立取样与盲评设计 |
| analyst 检验分析员 | 六页全部 | 来源/工艺/等级写入、排队、提出说明、下载已批准说明；只读质量通告 | 核对并列项及所有组对 |
| viewer 纸材观察员 | 六页全部 | 只读与已批准CSV下载，写入/审批403 | 阅读边界与分发复检依据 |

演示账号 `admin@qingnie.local`、`analyst@qingnie.local`、`viewer@qingnie.local`；共同密码 `Qingnie2026!`。

## 一天的工作剧本

1. 09:00 林蘖用analyst登录，打开 `QN-SHIFT 形成错位 · 四工艺复检研究`。
2. 09:05 核对清水参照、温和酶解、低剪切打浆、复合处理四个预定义工艺，每组30份独立试样，共120份；每份只评一次，编号在本研究内唯一。
3. 09:15 观察真实等级点阵，确认等级只表示顺序。另两份研究为相近分布、全同等级，合计3研究/12工艺/360份试样。
4. 09:20 提前设α=.05，命名“形成错位 · 全组秩比较”，冻结全部工艺/试样/等级与说明，再排队由worker计算。
5. 09:22 阅读总体：H=58.403116，渐近p=1.28925e-12，C=0.9798354。同时查看Dunn方差基数1185.600840和全部6组对；当前Holm拒绝5项。未拒绝组对不会隐藏。
6. 09:25 在并列与平均秩页核对Σ(t³−t)=34842，逐份检查合并平均秩。下/上中位位置保留原等级，不把偶数样本插值成3.5级。
7. 09:35 提出“四工艺独立复检说明”，同时说明拒绝/未拒绝组对、可能的分布形状差异与下一批独立盲评设计。
8. 10:00 宋槐用admin留批注并同意复检；周予用viewer下载 `followup-note-<id>.csv`，含完整总体、四组摘要与六组对。新数据另建快照，旧结果不回写。

以上数值来自固定seed真实API/worker结果。seed不预置检验结果，用户需实际排队。污染确认后由admin在来源页按试样清单发布质量通告；新检验自动排除失效试样，旧依据立即停用，撤销只影响新检验。

## 快速启动

```bash
cp .env.example .env
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose exec -T backend python -m scripts.seed_demo
```

前端 http://localhost:18231，API文档 http://localhost:19231/docs，MySQL localhost:17731，库/用户ordinal；本地密码见.env.example。健康接口/health检查数据库SELECT1与Redis ping。

SEED_DEMO=true启动尝试插入演示输入，失败记日志不阻塞应用。自然键为账号email、研究code、工艺study_id+code、试样study_id+specimen_code；只插入缺项，不覆盖人工说明/工艺/等级/来源。固定seed20261112；3研究×4工艺×30独立试样=360。seed不自动提交任务，也不预置质量通告或失效试样。

## 五服务与配置

| 服务 | 栈与职责 | 健康条件 |
|---|---|---|
| frontend | Vue3.5.45、Pinia、Vue Router、TypeScript、Vite6.4.6，Nginx1.27 | HTTP 127.0.0.1 |
| backend | Python3.11、FastAPI、SQLAlchemy2、PyJWT、NumPy/SciPy | DB SELECT1 + Redis ping |
| worker | 同后端镜像，持久队列扫描及Redis唤醒 | 30秒内心跳文件 |
| db | MySQL8，命名数据卷 | TCP mysqladmin ping |
| redis | Redis7 AOF，唤醒与登录限流 | redis-cli ping |

Compose恰好5服务、健康依赖、数据库/Redis/共享artifacts命名卷。等级虽是整数编码，MySQL存储仍显式DOUBLE(asdecimal=False)，alpha同样使用DOUBLE；输入必须为1–9整数，合并秩及统计量在JSON保留Python双精度。Nginx剥离一次/api/，Python路由不带重复前缀。

| 变量 | 默认与用途 |
|---|---|
| COMPOSE_PROJECT_NAME | ordinal-fibers，容器前缀 |
| FRONTEND_PORT/BACKEND_PORT/DB_PORT | 18231/19231/17731 |
| DB_PASSWORD | ordinal-demo-local，仅本地示例 |
| JWT_SECRET | 本地示例，部署前用独立随机键 |
| SEED_DEMO | true，启动补齐缺失seed |
| DATABASE_URL/REDIS_URL | Compose内部地址，本地可覆盖 |
| OMP_NUM_THREADS/OPENBLAS_NUM_THREADS | 1，数值线程限制 |

JWT8小时，PBKDF2-SHA256存储密码。角色授权、审计、统一错误与Redis每IP每分钟30次登录限流。验证失败仅输出loc/msg，不回显NaN/Inf非法输入造成JSON编码500。单研究2–5工艺，每组至少5份、总计≤2000份；活动任务最多3项。数据库是任务状态权威，Redis唤醒失败仍扫描；单worker中断任务按冻结快照重算。

## 质量通告与失效试样

上游确认污染后，按“研究+试样编号”清单发布质量通告（`POST /notices`，仅admin）。一份通告的 `items` 可跨多个研究，同一试样可被多份重叠通告覆盖。通告不删除、不改写等级或工艺，来源台账仍逐份显示原等级与命中的通告。

- **新检验**：`POST /runs` 在质量锁内读取当前全部有效通告，把失效试样从合并排秩中排除，并把每份试样的原等级、命中通告与原因冻结为 `specimen_exclusions`；`snapshot.exclusions` 与 `exclusion_fingerprint` 一并留档。全部预定义工艺保留；排除后任一工艺少于5份时任务直接进入 `failed`，错误写明不足组别，不输出成功结果。
- **旧依据**：发布通告时，任何冻结输入包含清单试样的既有任务（queued/running/completed）立即把 `run_quality_bases.basis_status` 置为 `invalidated`；worker 完成计算只会再复核一次，绝不恢复。已批准说明可继续阅读、批注与批准记录仍可查，但批准草稿、新建说明与 CSV 分发均返回 409。
- **撤销**：`POST /notices/{id}/revoke` 只追加撤销人/原因/时间并保留原通告行；**只有新建检验**才会重新纳入试样。旧检验依据即使其命中的通告全部撤销也保持停用，不会因时间流逝或撤销而恢复资格。
- **重叠撤销**：有效通告集合实时计算；只要还有一份重叠通告为 active，试样就保持失效。全部重叠通告撤销后，下一次新建检验才会纳入该试样。
- **并发**：发布/撤销通告、新建检验、worker 写出完成结果、批准/分发说明都在同一事务内 `SELECT ... FOR UPDATE` `quality_locks` 单行（SQLite 下同时取得写锁）。因此并发只会有一种先后：要么新检验已排除试样，要么旧依据已停用；不会出现两者都未发生的窗口。分发与通告并发时，先完成的分发合法，但依据一旦命中即永久停用，后续分发被拒。
- **追溯**：`GET /runs?` / `GET /runs/{id}` 返回 `quality`（依据状态、命中通告、停用原因、排除指纹）与 `exclusions`；`GET /runs/{id}/trace` 为同样的只读视图。`GET /notices` 返回每份通告的 `affected_run_ids`。来源页显示逐份失效状态与通告清单，结果页显示冻结排除依据与停用横幅，说明页显示依据状态及不可分发原因。

所有读者（来源、结果、说明、导出）共用 `quality_service` 的同一判定；不在页面复制规则。质量锁、通告、依据状态与排除行由 `Base.metadata.create_all` 创建，DDL 见 `migrations/001_initial.sql`。

## 公式与解释

全部N合并一次排秩，并列取平均秩。若某等级全体出现t次，则T=Σ(t³−t)，C=1−T/(N³−N)。KW未修正统计量等价为 `12/[N(N+1)] Σ n_g (Rbar_g−(N+1)/2)²`，H=H_raw/C，df=k−1，p=chi2.sf(H,df)。使用中心化表达式减少抵消误差，C与Dunn方差的分子用整数并列项计算。

Dunn对全部k(k−1)/2组对，使用同一合并秩：`V=N(N+1)/12−T/[12(N−1)]`，`SE_ij=sqrt(V(1/n_i+1/n_j))`，`z=(Rbar_i−Rbar_j)/SE`，双侧p=2 norm.sf(abs(z))。Holm对完整家族原始p排序、乘剩余家族数、取累积最大值并截至1，按调整p≤预设alpha判拒绝。无论KW是否拒绝，全家族都保留。

H的p是χ²渐近，Dunn是正态渐近，不是exact。Holm依赖单项p的适用性，不能把名义alpha说成有限样本无条件保证。等级分布差异可能来自形状；只有额外位置移动/同形状假设才可聚焦中位位置。平均秩差不是等级单位的效应。未拒绝不证明相等/等效。重复测量或配对设计不适用；ID唯一不证明样本独立，批次相关需设计控制。

全同值时C=0，KW与Dunn未定义，任务失败，不输出p=1来假称无差异。非法等级、外部工艺、重复试样、少于5份/组、空组均明确拒绝或留下worker失败态。公式参见 [SciPy Kruskal](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.kruskal.html) 与 [Dunn原论文](https://www.stat.cmu.edu/technometrics/59-69/VOL-06-03/v0603241.pdf)。

快照按工艺/试样代码规范排序，SHA256覆盖版本、完整输入、alpha；同环境完整复算一致，输入列表顺序不改变整份计算结果。指纹含数据库ID和说明元数据，重建库/修改来源不保证相同指纹。结果同时存数据库和/artifacts/run-<id>.json，全部原始等级、平均秩、并列项与组对可核查。

## 代码与本地开发

五个实体GradeStudy、Treatment、GradeReading、RankTestRun、FollowupNote各自贯穿model/schema/service/controller/route/API；质量通告扩展QualityNotice、RunQualityBasis、SpecimenExclusion与QualityLock，集中在services/quality_service.py并共用routes/notices.py与runs trace。studyStore、measurementsStore、researchStore、qualityStore承接对应状态；六页为总览、来源、配置、结果、说明、审计，登录另计。GradeDots复用于总览/结果，PairFamilyTable复用于结果/说明；共享PageHeading、StatusBadge、ErrorNotice、StudySelect、RunSelect，hooks useTask/usePolling、format工具。所有宽图/表局部滚动，grid显式minmax(0,1fr)/min-width:0；结果工艺选择按真实已加载组同步。

目录：backend/src/{models,schemas,services,controllers,routes,config,constants,middlewares,utils}；数学services/{rank_pool,dunn,rank_inference}.py；backend/scripts/seed_demo.py与migrations/001_initial.sql。frontend/src/{api,stores,types,constants,components/common,hooks,pages,router,utils}。

Role/RunStatus/NoteStatus/NoticeStatus/BasisStatus前后端分别定义于backend/src/constants/enums.py和frontend/src/constants/enums.ts，角色类型在types/domain.ts；RunStatus用于运行service/worker，NoteStatus用于schema/service，NoticeStatus与BasisStatus用于质量依据与分发判定，前端用于状态与账户/页面。等级枚举1–9在前端constants/enums.ts，后端schemas/reading.py与rank_inference.py严格校验。

```bash
docker compose up -d db redis
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL='mysql+pymysql://ordinal:ordinal-demo-local@localhost:17731/ordinal?charset=utf8mb4'
export REDIS_URL='redis://localhost:6379/0'
export SEED_DEMO=true
uvicorn src.main:app --host 0.0.0.0 --port 19231
# 另一终端同backend环境
python -m src.worker
# frontend另一终端
npm ci
npm run dev -- --port 18231
```

本地worker需可写/artifacts，推荐Compose共享卷。初始DDL供审阅，metadata.create_all只建缺表，没有生产版本升级器。字体Google Fonts Barlow/Noto Serif SC，离线回退Georgia/serif。真实测试、截图和已知差异在批次独立test-artifacts/gb-0027；收尾docker compose down -v --remove-orphans会删本题数据库/Redis/结果卷。MIT License。
