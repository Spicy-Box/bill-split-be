from typing import Generic, TypeVar, Optional
from beanie import PydanticObjectId
from pydantic import BaseModel

T = TypeVar('T')

class ReponseWrapper(BaseModel, Generic[T]):
    message: str
    data: Optional[T] = None
    
class Participants(BaseModel):
    name: str
    user_id: Optional[PydanticObjectId] = None
    is_guest: bool = True