from src.services import quality_service as service

FIELDS=('id','title','reason','items','status','issued_by','created_at','revoked_by','revocation_reason','revoked_at')

def serialize(notice,db=None):
    data={k:getattr(notice,k) for k in FIELDS}
    if db is not None:data['affected_run_ids']=service.affected_run_ids(db,notice.id)
    return data

def index(db,study_id=None):
    return [serialize(n,db) for n in service.list_notices(db,study_id)]

def create(db,data,user):
    notice,invalidated=service.create_notice(db,data,user)
    return {'notice':serialize(notice,db),'invalidated_run_ids':invalidated}

def revoke(db,id,data,user):
    return serialize(service.revoke_notice(db,id,data.reason,user),db)
