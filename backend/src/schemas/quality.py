from pydantic import BaseModel,Field,ConfigDict
from datetime import datetime
from src.constants.enums import NoticeStatus


class NoticeItemInput(BaseModel):
    study_id:int
    specimen_code:str=Field(min_length=1,max_length=60)


class NoticeInput(BaseModel):
    title:str=Field(min_length=2,max_length=160)
    reason:str=Field(min_length=10,max_length=1000)
    items:list[NoticeItemInput]=Field(min_length=1,max_length=2000)


class RevokeInput(BaseModel):
    reason:str=Field(min_length=5,max_length=1000)


class NoticeOut(BaseModel):
    id:int
    title:str
    reason:str
    items:list[dict]
    status:str
    issued_by:str
    created_at:datetime
    revoked_by:str
    revocation_reason:str
    revoked_at:datetime|None
    affected_run_ids:list[int]=Field(default_factory=list)
    model_config=ConfigDict(from_attributes=True)
