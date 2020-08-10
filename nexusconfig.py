from dataclasses import dataclass


@dataclass
class NexusConfig:
    registry: str
    nexus: str
    username: str
    password: str
