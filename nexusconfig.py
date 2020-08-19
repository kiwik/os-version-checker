from dataclasses import dataclass


@dataclass
class NexusConfig:
    registry: str
    username: str
    password: str
