from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict
from datetime import datetime

Carrier = Literal["inpost", "dhl"]

class PackageIn(BaseModel):
    carrier: Carrier
    number: str
    label: Optional[str] = None

class Package(BaseModel):
    id: str
    carrier: Carrier
    number: str
    label: Optional[str] = None
    added_at: datetime
    last_update: Optional[datetime] = None
    detailed_status: Optional[str] = None
    summary_status: Optional[str] = None
    history: List[Dict] = Field(default_factory=list)

class MQTTConfig(BaseModel):
    host: str = ""
    port: int = 1883
    username: str = ""
    password: str = ""
    base_topic: str = "package_tracker"

class Settings(BaseModel):
    poll_interval_minutes: int = 7
    mqtt: MQTTConfig = MQTTConfig()
