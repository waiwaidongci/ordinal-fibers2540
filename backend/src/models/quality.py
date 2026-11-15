from datetime import datetime
from sqlalchemy import String,ForeignKey,DateTime,JSON,UniqueConstraint,Index
from sqlalchemy.dialects.mysql import DOUBLE
from sqlalchemy.orm import Mapped,mapped_column
from src.config.database import Base


class QualityLock(Base):
    """串行化点：发布/撤销通告、新建检验、worker 完工与说明分发共用一行。

    这些写入都在同一事务内 SELECT ... FOR UPDATE 这一行，使“通告与排队、计算
    完成、复检分发并发”只有一种先后顺序：要么新检验已排除失效试样，要么旧依据
    已停用，不会出现两者都没发生的窗口。
    """
    __tablename__='quality_locks'
    id:Mapped[int]=mapped_column(primary_key=True)
    note:Mapped[str]=mapped_column(String(80),default='quality-basis-serialization')


class QualityNotice(Base):
    """跨研究、按试样清单发布的质量通告。

    items 为 [{study_id,study_code,specimen_code,treatment_code,treatment_name}]，
    一次通告可覆盖多个研究。通告不写回等级、工艺或既有结果；撤销采用追加撤销
    信息、保留原通告行的方式。任一重叠通告仍有效时，清单内试样保持失效。
    """
    __tablename__='quality_notices'
    id:Mapped[int]=mapped_column(primary_key=True)
    title:Mapped[str]=mapped_column(String(160))
    reason:Mapped[str]=mapped_column(String(1000))
    items:Mapped[list]=mapped_column(JSON,default=list)
    status:Mapped[str]=mapped_column(String(20),default='active')
    issued_by:Mapped[str]=mapped_column(String(140),default='')
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    revoked_by:Mapped[str]=mapped_column(String(140),default='')
    revocation_reason:Mapped[str]=mapped_column(String(1000),default='')
    revoked_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    __table_args__=(Index('ix_quality_notices_status','status'),)


class RunQualityBasis(Base):
    """检验依据的质量状态。

    创建任务时是 current，并记录冻结的排除依据摘要；一旦冻结输入包含后来发布
    的失效试样，立即变为 invalidated。撤销通告、worker 迟到完成或复算都不能
    把它改回 current；需要恢复证据只能新建检验。
    """
    __tablename__='run_quality_bases'
    id:Mapped[int]=mapped_column(primary_key=True)
    run_id:Mapped[int]=mapped_column(ForeignKey('rank_test_runs.id'))
    study_id:Mapped[int]=mapped_column(ForeignKey('grade_studies.id'))
    basis_status:Mapped[str]=mapped_column(String(20),default='current')
    exclusion_count:Mapped[int]=mapped_column(default=0)
    exclusion_fingerprint:Mapped[str]=mapped_column(String(64),default='')
    applied_notice_ids:Mapped[list]=mapped_column(JSON,default=list)
    invalidated_by_notice_ids:Mapped[list]=mapped_column(JSON,default=list)
    invalidated_reason:Mapped[str]=mapped_column(String(1000),default='')
    invalidated_by:Mapped[str]=mapped_column(String(140),default='')
    invalidated_at:Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    __table_args__=(UniqueConstraint('run_id'),Index('ix_run_quality_bases_study','study_id'))


class SpecimenExclusion(Base):
    """新建检验时冻结的排除依据：每份被排除试样的原始等级与命中通告。

    任务创建后这些行不再变化；之后撤销通告只影响新检验，不改写旧任务的排除
    依据，也不会让旧任务恢复可分发资格。
    """
    __tablename__='specimen_exclusions'
    id:Mapped[int]=mapped_column(primary_key=True)
    run_id:Mapped[int]=mapped_column(ForeignKey('rank_test_runs.id'))
    study_id:Mapped[int]=mapped_column(ForeignKey('grade_studies.id'))
    specimen_code:Mapped[str]=mapped_column(String(60))
    treatment_code:Mapped[str]=mapped_column(String(40))
    treatment_name:Mapped[str]=mapped_column(String(100))
    grade:Mapped[float]=mapped_column(DOUBLE(asdecimal=False))
    notice_ids:Mapped[list]=mapped_column(JSON,default=list)
    notice_titles:Mapped[list]=mapped_column(JSON,default=list)
    reason:Mapped[str]=mapped_column(String(1000),default='')
    created_at:Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    __table_args__=(UniqueConstraint('run_id','specimen_code'),Index('ix_specimen_exclusions_run','run_id'))
