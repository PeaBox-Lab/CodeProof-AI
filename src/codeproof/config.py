from pathlib import Path
import yaml
from pydantic import BaseModel,Field
class CheckConfig(BaseModel):
    enabled:bool=True; weight:float=1; config:str|None=None
class Config(BaseModel):
    version:int=1; fail_under:float=70; source_paths:list[str]=Field(default_factory=lambda:["src"]); test_paths:list[str]=Field(default_factory=lambda:["tests"]); timeout_seconds:int=300; required_tools:list[str]=Field(default_factory=lambda:["ruff","pytest"]); checks:dict[str,CheckConfig]=Field(default_factory=dict)
DEFAULT=Config(checks={"imports":CheckConfig(weight=10),"ruff":CheckConfig(weight=15),"mypy":CheckConfig(weight=15),"pytest":CheckConfig(weight=30),"bandit":CheckConfig(weight=15),"semgrep":CheckConfig(weight=15,config="auto")})
def load(root:Path, explicit:Path|None=None)->Config:
    p=explicit or root/".codeproof.yml"
    return DEFAULT.model_copy(deep=True) if not p.exists() else Config.model_validate(yaml.safe_load(p.read_text()) or {})
