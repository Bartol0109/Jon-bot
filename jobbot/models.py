from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Job:
    source: str
    title: str
    company: str
    url: str
    location: str = ""
    remote: bool = False
    posted: Optional[datetime] = None   # timezone-aware UTC
    tags: list = field(default_factory=list)
    description: str = ""
    scope: str = "remote"               # "remote" | "hr"
    score: float = 0.0
    reason: str = ""

    @property
    def key(self) -> str:
        return (self.url or f"{self.source}:{self.company}:{self.title}").split("?")[0].lower()
