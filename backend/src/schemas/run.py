from pydantic import BaseModel,Field,ConfigDict
from datetime import datetime

class RunInput(BaseModel):
    name:str=Field(min_length=2,max_length=140)
    study_id:int
    alpha:float=Field(default=.05,gt=0,lt=1,allow_inf_nan=False,strict=True)

class RunOut(BaseModel):
    id:int
    name:str
    study_id:int
    alpha:float
    status:str
    snapshot:dict
    result:dict
    error:str
    created_at:datetime
    quality:dict=Field(default_factory=dict)
    exclusions:list[dict]=Field(default_factory=list)
    model_config=ConfigDict(from_attributes=True)
