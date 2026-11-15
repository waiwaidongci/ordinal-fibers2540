import json
from pathlib import Path
from sqlalchemy import select,func
from fastapi import HTTPException
from redis import Redis
from src.config.settings import REDIS_URL,ARTIFACTS_DIR
from src.models import RankTestRun,RunQualityBasis,SpecimenExclusion
from src.services.study_service import get_study
from src.services.treatment_service import list_treatments
from src.services.quality_service import lock_quality,build_exclusions,exclusion_fingerprint,basis_for_run,exclusions_for_run
from src.services.rank_inference import analyze_study
from src.constants.enums import RunStatus
redis=Redis.from_url(REDIS_URL)
def list_runs(db):return db.scalars(select(RankTestRun).order_by(RankTestRun.id.desc())).all()
def get_run(db,id):
    r=db.get(RankTestRun,id)
    if not r:raise HTTPException(404,'秩检验任务不存在')
    return r

def create_run(db,data,user=None):
    """新建检验：冻结排除依据、全部工艺与剩余等级；排除后不足5份/组立即失败。"""
    lock_quality(db)
    s=get_study(db,data.study_id)
    if db.scalar(select(RankTestRun).where(RankTestRun.name==data.name)):raise HTTPException(409,'任务名称重复')
    if db.scalar(select(func.count()).select_from(RankTestRun).where(RankTestRun.status.in_(['queued','running'])))>=3:raise HTTPException(429,'已有3项活动任务，请等待')
    kept,excluded,applied_notice_ids=build_exclusions(db,s.id)
    treatments=list_treatments(db,s.id)
    snapshot={'study':{k:getattr(s,k) for k in ('id','code','name','protocol','source_file')},
              'treatments':[{k:getattr(t,k) for k in ('id','code','name','process_note')} for t in treatments],
              'readings':[{k:getattr(r,k) for k in ('id','specimen_code','treatment_id','grade','source_note')} for r in kept],
              'exclusions':excluded,'applied_notice_ids':applied_notice_ids}
    fp=exclusion_fingerprint(s.id,excluded)
    short=[(t,sum(1 for r in kept if r.treatment_id==t.id)) for t in treatments]
    short=[(t,n) for t,n in short if n<5]
    status=RunStatus.QUEUED;error=''
    if short:
        status=RunStatus.FAILED
        error=('排除失效试样后样本不足：'+'；'.join(f'{t.code} {t.name} 仅 {n} 份（至少5份）' for t,n in short)+'。全部工艺与冻结排除依据已保留；请补充独立试样，或撤销通告后新建检验。')[:600]
    r=RankTestRun(**data.model_dump(),status=status,snapshot=snapshot,error=error);db.add(r);db.flush()
    db.add(RunQualityBasis(run_id=r.id,study_id=s.id,basis_status='current',exclusion_count=len(excluded),exclusion_fingerprint=fp,applied_notice_ids=applied_notice_ids))
    for e in excluded:db.add(SpecimenExclusion(run_id=r.id,study_id=s.id,**e))
    db.commit()
    if status==RunStatus.QUEUED:
        try:redis.lpush('ordinal:runs',str(r.id))
        except Exception:pass
    return r

def execute_run(db,id):
    """worker 执行；完成计算既不恢复已停用依据，也不改写冻结排除。

    计算开始时持有质量锁直到结果落库：若此刻有通告发布或撤销，两者只能
    先后发生，不会在“读完快照”和“写入完成”之间漏掉一次停用。
    """
    r=get_run(db,id)
    if r.status not in (RunStatus.QUEUED,RunStatus.RUNNING):return
    r.status=RunStatus.RUNNING;db.commit()
    lock_quality(db)
    if not db.scalar(select(RunQualityBasis).where(RunQualityBasis.run_id==id)):
        db.add(RunQualityBasis(run_id=id,study_id=r.study_id,basis_status='current',exclusion_count=len((r.snapshot or {}).get('exclusions',[]))))
        db.flush()
    try:
        result=analyze_study(r.snapshot,r.alpha);Path(ARTIFACTS_DIR).mkdir(exist_ok=True);Path(ARTIFACTS_DIR,f'run-{id}.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False));r.result=result;r.error='';r.status=RunStatus.COMPLETED
    except Exception as exc:
        db.rollback();r=get_run(db,id);r.status=RunStatus.FAILED;r.error=str(exc)[:600]
    else:
        from src.services.quality_service import revalidate_basis_against_active
        revalidate_basis_against_active(db,r,'worker')
    db.commit()

def run_trace(db,run):
    """来源/结果页共用的追溯信息：依据状态、冻结排除与命中通告。"""
    info=basis_for_run(db,run)
    rows=exclusions_for_run(db,run.id)
    return {'quality':info,'exclusions':[{'specimen_code':e.specimen_code,'treatment_code':e.treatment_code,'treatment_name':e.treatment_name,'grade':e.grade,'notice_ids':e.notice_ids,'notice_titles':e.notice_titles,'reason':e.reason} for e in rows]}
