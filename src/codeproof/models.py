from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
class Status(str,Enum):
    passed="passed"; failed="failed"; unavailable="unavailable"; error="error"; skipped="skipped"
class Finding(BaseModel):
    level:str="info"; message:str; path:str|None=None; line:int|None=None; rule:str|None=None
class CheckResult(BaseModel):
    name:str; status:Status; command:list[str]=Field(default_factory=list); duration_seconds:float=0; exit_code:int|None=None; summary:str=""; findings:list[Finding]=Field(default_factory=list); evidence:dict[str,Any]=Field(default_factory=dict); raw_output:str|None=None; weight:float=0; required:bool=False
class ScanReport(BaseModel):
    schema_version:str="1.0"; project:str; target:str; generated_at:str; codeproof_version:str; score:float; grade:str; policy_passed:bool; fail_under:float; results:list[CheckResult]; limitations:list[str]=Field(default_factory=list)
