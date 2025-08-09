from pydantic import BaseModel, HttpUrl
from typing import List, Optional


class ResponseData(BaseModel):
    taskId: str
    resultUrls: List[HttpUrl]
    originUrls: List[HttpUrl]


class VeoData(BaseModel):
    taskId: str
    paramJson: str
    completeTime: str
    response: ResponseData
    successFlag: int
    errorCode: Optional[str]
    errorMessage: str
    createTime: str
    fallbackFlag: bool


class VeoResponse(BaseModel):
    code: int
    msg: str
    data: VeoData