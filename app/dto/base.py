from typing import Generic, TypeVar, Optional
from pydantic import BaseModel
from pydantic.generics import GenericModel

T = TypeVar('T')

class ReponseWrapper(GenericModel, Generic[T]):
    message: str
    data: Optional[T] = None