"""质量通告、失效试样与检验依据的权威规则。

只有本模块决定“哪些试样失效”和“某次检验的依据是否仍可分发”。所有读者
（来源页、结果页、说明页、导出）都调用同一函数，不各自复制规则。
"""
import hashlib,json
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from src.models import QualityLock,QualityNotice,RunQualityBasis,SpecimenExclusion,GradeStudy,Treatment,GradeReading,RankTestRun
from src.constants.enums import NoticeStatus,BasisStatus


def ensure_quality_lock(db:Session):
    """惰性确保串行化行存在（正常由启动时 insert-only seed 创建）。"""
    row=db.get(QualityLock,1)
    if row is None:
        row=QualityLock(id=1);db.add(row);db.commit()
    return row


def lock_quality(db:Session):
    """串行化质量依据的所有写入；在同一事务内保持到 commit。

    SELECT ... FOR UPDATE 在 MySQL 上是行锁；随后一次“写回自身”的无操作
    UPDATE 让 SQLite 也取得写锁（SQLite 不支持 FOR UPDATE），使本地测试与
    Compose 中的并发顺序一致。必须在读取有效通告/快照之前调用。
    """
    row=db.scalar(select(QualityLock).where(QualityLock.id==1).with_for_update())
    if row is None:
        raise HTTPException(503,'质量依据锁未初始化，请重试')
    from sqlalchemy import update
    db.execute(update(QualityLock).where(QualityLock.id==1).values(note=QualityLock.note))
    return row


def _notice_items(notice):
    return [i for i in (notice.items or []) if isinstance(i,dict) and i.get('study_id') and i.get('specimen_code')]


def list_notices(db:Session,study_id:int|None=None):
    rows=db.scalars(select(QualityNotice).order_by(QualityNotice.id.desc())).all()
    if study_id is None:return rows
    return [n for n in rows if any(int(i['study_id'])==study_id for i in _notice_items(n))]


def affected_run_ids(db:Session,notice_id:int):
    """从通告反查受影响的既有依据（跨研究）。"""
    bases=db.scalars(select(RunQualityBasis)).all()
    return sorted({b.run_id for b in bases if notice_id in (b.invalidated_by_notice_ids or [])})


def active_notices(db:Session,study_id:int|None=None):
    rows=db.scalars(select(QualityNotice).where(QualityNotice.status==NoticeStatus.ACTIVE).order_by(QualityNotice.id)).all()
    if study_id is None:return rows
    return [n for n in rows if any(int(i['study_id'])==study_id for i in _notice_items(n))]


def active_exclusion_map(db:Session,study_id:int|None=None):
    """{(study_id,specimen_code): {'notice_ids','notice_titles','reason'}}，仅有效通告。"""
    result={}
    for n in active_notices(db,study_id):
        for item in _notice_items(n):
            sid=int(item['study_id'])
            if study_id is not None and sid!=study_id:continue
            key=(sid,str(item['specimen_code']))
            entry=result.setdefault(key,{'study_id':sid,'specimen_code':key[1],'notice_ids':[],'notice_titles':[],'reasons':[]})
            entry['notice_ids'].append(n.id);entry['notice_titles'].append(n.title);entry['reasons'].append(n.reason)
    for entry in result.values():entry['reason']='；'.join(r for r in entry['reasons'] if r)
    return result


def normalize_items(db:Session,items:list[dict]):
    """校验通告清单：每个试样必须真实存在；同一研究内试样编号唯一。"""
    if not items:raise HTTPException(422,'质量通告至少需要一份试样')
    if len(items)>2000:raise HTTPException(422,'单次质量通告最多2000份试样')
    seen=set();normalized=[]
    for raw in items:
        if hasattr(raw,'model_dump'):raw=raw.model_dump()
        if not isinstance(raw,dict):raise HTTPException(422,'试样清单格式不正确')
        try:sid=int(raw.get('study_id'));code=str(raw.get('specimen_code','')).strip()
        except (TypeError,ValueError):raise HTTPException(422,'试样清单需包含研究与试样编号')
        if not code:raise HTTPException(422,'试样编号不能为空')
        key=(sid,code)
        if key in seen:raise HTTPException(409,f'试样 {code} 在清单中重复')
        seen.add(key)
        normalized.append({'study_id':sid,'specimen_code':code})
    for sid in {i['study_id'] for i in normalized}:
        study=db.get(GradeStudy,sid)
        if not study:raise HTTPException(422,f'研究 {sid} 不存在')
        codes=[i['specimen_code'] for i in normalized if i['study_id']==sid]
        found={r.specimen_code:r for r in db.scalars(select(GradeReading).where(GradeReading.study_id==sid,GradeReading.specimen_code.in_(codes))).all()}
        missing=[c for c in codes if c not in found]
        if missing:raise HTTPException(422,f'研究 {study.code} 中不存在试样：'+', '.join(missing[:8])+('…' if len(missing)>8 else ''))
        treatments={t.id:t for t in db.scalars(select(Treatment).where(Treatment.study_id==sid)).all()}
        for item in [i for i in normalized if i['study_id']==sid]:
            r=found[item['specimen_code']];t=treatments.get(r.treatment_id)
            item.update({'study_code':study.code,'treatment_code':t.code if t else '','treatment_name':t.name if t else ''})
    return normalized


def create_notice(db:Session,data,user):
    """发布通告：立即停用冻结输入命中这些试样的既有依据。"""
    lock_quality(db)
    items=normalize_items(db,data.items)
    notice=QualityNotice(title=data.title,reason=data.reason,items=items,status=NoticeStatus.ACTIVE,issued_by=user.email)
    db.add(notice);db.flush()
    invalidated=invalidate_runs_hit_by_notice(db,notice,user.email)
    db.commit()
    return notice,invalidated


def revoke_notice(db:Session,id:int,reason:str,user):
    """撤销通告：只影响新检验；旧依据保持停用。"""
    lock_quality(db)
    notice=db.get(QualityNotice,id)
    if not notice:raise HTTPException(404,'质量通告不存在')
    if notice.status!=NoticeStatus.ACTIVE:raise HTTPException(409,'该通告已撤销，不能重复撤销')
    if not reason or len(reason.strip())<5:raise HTTPException(422,'撤销原因至少5字，便于追溯')
    notice.status=NoticeStatus.REVOKED;notice.revoked_by=user.email;notice.revocation_reason=reason.strip();notice.revoked_at=datetime.utcnow()
    db.commit()
    return notice


def invalidate_runs_hit_by_notice(db:Session,notice,actor:str):
    """把冻结输入包含通告试样的既有检验依据标记为停用，返回受影响 run id。

    只改 basis_status 与停用说明，不碰结果、批准说明、快照或运行状态。
    已被先前通告停用的依据也会记录本次命中，便于从任一通告反查受影响依据。
    没有依据行的旧任务在此补建并持久化停用，确保之后撤销通告也不会恢复。
    """
    hit=[]
    by_study={}
    for item in _notice_items(notice):by_study.setdefault(int(item['study_id']),set()).add(str(item['specimen_code']))
    for sid,codes in by_study.items():
        runs=db.scalars(select(RankTestRun).where(RankTestRun.study_id==sid)).all()
        existing={b.run_id:b for b in db.scalars(select(RunQualityBasis).where(RunQualityBasis.study_id==sid)).all()}
        for run in runs:
            frozen={str(r['specimen_code']) for r in (run.snapshot or {}).get('readings',[])}
            overlap=sorted(frozen & codes)
            if not overlap:continue
            basis=existing.get(run.id)
            if basis is None:
                basis=RunQualityBasis(run_id=run.id,study_id=sid,basis_status=BasisStatus.CURRENT,exclusion_count=len((run.snapshot or {}).get('exclusions',[])))
                db.add(basis);db.flush()
            if notice.id in (basis.invalidated_by_notice_ids or []):continue
            shown=', '.join(overlap[:4])+('…' if len(overlap)>4 else '')
            _mark_invalidated(basis,notice,[f'通告 #{notice.id}《{notice.title}》命中冻结试样 {len(overlap)} 份：'+shown],actor)
            hit.append(run.id)
    db.flush()
    return hit


def _mark_invalidated(basis:RunQualityBasis,notice,reasons,actor):
    basis.basis_status=BasisStatus.INVALIDATED
    basis.invalidated_by_notice_ids=sorted(set((basis.invalidated_by_notice_ids or [])+[notice.id]))
    basis.invalidated_reason='；'.join(dict.fromkeys([*( [basis.invalidated_reason] if basis.invalidated_reason else []),*reasons]))[:1000]
    basis.invalidated_by=actor;basis.invalidated_at=datetime.utcnow()


def revalidate_basis_against_active(db:Session,run,actor:str):
    """计算完成/读取时再对一次有效通告，作为发布路径之外的兜底。

    命中即停用；不恢复任何已停用依据。返回是否有新停用。
    """
    basis=db.scalar(select(RunQualityBasis).where(RunQualityBasis.run_id==run.id))
    if basis is None:return False
    study_id=int((run.snapshot or {}).get('study',{}).get('id',run.study_id))
    frozen={str(r['specimen_code']) for r in (run.snapshot or {}).get('readings',[])}
    active=active_exclusion_map(db,study_id)
    hit=sorted(frozen & {code for (sid,code) in active.keys()})
    if not hit:return False
    already=set(basis.invalidated_by_notice_ids or [])
    new_ids=sorted({i for code in hit for i in active[(study_id,code)]['notice_ids'] if i not in already})
    if basis.basis_status==BasisStatus.INVALIDATED and not new_ids:return False
    reasons=[f'当前有效通告 '+','.join('#%d'%i for i in sorted({i for code in hit for i in active[(study_id,code)]['notice_ids']}))+' 命中冻结试样 '+str(len(hit))+' 份']
    basis.basis_status=BasisStatus.INVALIDATED
    basis.invalidated_by_notice_ids=sorted(already|{i for code in hit for i in active[(study_id,code)]['notice_ids']})
    basis.invalidated_reason='；'.join(dict.fromkeys([*([basis.invalidated_reason] if basis.invalidated_reason else []),*reasons]))[:1000]
    basis.invalidated_by=actor;basis.invalidated_at=datetime.utcnow()
    db.flush();return True


def basis_for_run(db:Session,run)->dict:
    """依据状态：数据库冻结结论 + 当前有效通告复核，任一处失效即失效。"""
    basis=db.scalar(select(RunQualityBasis).where(RunQualityBasis.run_id==run.id))
    study_id=int((run.snapshot or {}).get('study',{}).get('id',run.study_id))
    frozen={str(r['specimen_code']) for r in (run.snapshot or {}).get('readings',[])}
    active=active_exclusion_map(db,study_id)
    hit_codes=sorted(frozen & {code for (sid,code) in active.keys()})
    notice_ids=[];reasons=[]
    frozen_reason=basis.invalidated_reason if basis is not None and basis.basis_status==BasisStatus.INVALIDATED else ''
    if frozen_reason:
        notice_ids.extend(basis.invalidated_by_notice_ids or [])
        reasons.append('冻结时依据已停用：'+frozen_reason)
    for code in hit_codes:notice_ids.extend(active[(study_id,code)]['notice_ids'])
    if hit_codes:reasons.append('当前有效通告 '+','.join('#%d'%i for i in sorted(set(notice_ids)))+f' 命中冻结试样 {len(hit_codes)} 份')
    invalidated=bool((basis is not None and basis.basis_status==BasisStatus.INVALIDATED) or hit_codes)
    titles={}
    for nid in set(notice_ids):
        n=db.get(QualityNotice,nid)
        if n:titles[nid]={'id':n.id,'title':n.title,'status':n.status}
    return {
        'run_id':run.id,'basis_status':BasisStatus.INVALIDATED if invalidated else BasisStatus.CURRENT,
        'invalidated':invalidated,
        'invalidated_by_notice_ids':sorted(set(notice_ids)),
        'invalidated_notices':[titles[k] for k in sorted(titles)],
        'invalidated_reason':'；'.join(dict.fromkeys(reasons))[:1000],
        'exclusion_count':basis.exclusion_count if basis else 0,
        'exclusion_fingerprint':basis.exclusion_fingerprint if basis else '',
        'applied_notice_ids':list(basis.applied_notice_ids or []) if basis else [],
        'hit_specimen_codes':hit_codes,
        'frozen_specimen_count':len(frozen),
    }


def assert_basis_dispatchable(db:Session,run):
    """批准或分发前调用；失效依据立即停用。"""
    info=basis_for_run(db,run)
    if info['invalidated']:
        raise HTTPException(409,'该检验依据包含失效试样，已停用；撤销通告不能恢复旧依据，请新建检验。'+(' '+info['invalidated_reason'] if info['invalidated_reason'] else ''))
    return info


def exclusions_for_run(db:Session,run_id:int):
    return db.scalars(select(SpecimenExclusion).where(SpecimenExclusion.run_id==run_id).order_by(SpecimenExclusion.specimen_code)).all()


def build_exclusions(db:Session,study_id:int):
    """新建检验时冻结的排除依据：返回 (kept_readings, excluded_rows, applied_notice_ids)。"""
    active=active_exclusion_map(db,study_id)
    readings=db.scalars(select(GradeReading).where(GradeReading.study_id==study_id).order_by(GradeReading.specimen_code)).all()
    treatments={t.id:t for t in db.scalars(select(Treatment).where(Treatment.study_id==study_id)).all()}
    kept=[];excluded=[];notice_ids=set()
    for r in readings:
        entry=active.get((study_id,str(r.specimen_code)))
        if not entry:
            kept.append(r);continue
        t=treatments.get(r.treatment_id)
        notice_ids.update(entry['notice_ids'])
        excluded.append({'specimen_code':r.specimen_code,'treatment_code':t.code if t else '','treatment_name':t.name if t else '','grade':float(r.grade),'notice_ids':sorted(entry['notice_ids']),'notice_titles':list(entry['notice_titles']),'reason':entry['reason']})
    return kept,excluded,sorted(notice_ids)


def exclusion_fingerprint(study_id:int,excluded:list[dict]):
    canonical=json.dumps({'study_id':study_id,'excluded':sorted([{'specimen_code':e['specimen_code'],'grade':e['grade'],'notice_ids':e['notice_ids']} for e in excluded],key=lambda e:e['specimen_code'])},sort_keys=True,separators=(',',':'),allow_nan=False)
    return hashlib.sha256(canonical.encode()).hexdigest()
