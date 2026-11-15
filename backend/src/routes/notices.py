from fastapi import APIRouter,Depends,Query
from fastapi.encoders import jsonable_encoder
from src.config.database import get_db
from src.utils.auth import current_user,admin
from src.schemas.quality import NoticeInput,RevokeInput,NoticeOut
from src.controllers import quality_controller as controller
router=APIRouter(prefix='/notices',tags=['quality-notices'])

@router.get('',response_model=list[NoticeOut])
def index(study_id:int|None=Query(default=None),db=Depends(get_db),user=Depends(current_user)):
    return controller.index(db,study_id)

@router.post('',status_code=201)
def create(data:NoticeInput,db=Depends(get_db),user=Depends(admin)):
    return controller.create(db,data,user)

@router.post('/{id}/revoke',response_model=NoticeOut)
def revoke(id:int,data:RevokeInput,db=Depends(get_db),user=Depends(admin)):
    return controller.revoke(db,id,data,user)
