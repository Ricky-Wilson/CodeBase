"""
Vlan main dataclass object.

Contains all attributes and hints about the datatype (some attributes have the
attribute forced when is assigned).
"""
from dataclasses import dataclass, field
from typing import Optional, List, Any
from netapi.metadata import Metadata, EntityCollections


def status_conversion(raw_status):
    """
    Based on a raw (known) status of the vlan, it returns a standard status (UP,
    DOWN) string and its boolean representation.
    """
    if raw_status == "active":
        status = "active"
        status_up = True
    elif raw_status == "suspended":
        status = "suspended"
        status_up = False
    else:
        # For unknown cases
        status = raw_status
        status_up = False

    return status, status_up


@dataclass(unsafe_hash=True)
class VlanBase:
    id: int
    name: Optional[str] = None
    dynamic: Optional[bool] = None
    status: Optional[str] = None
    status_up: Optional[bool] = None
    # TODO: Could create builder methods for populating interfaces of that VLAN
    interfaces: Optional[List[str]] = None
    connector: Optional[Any] = field(default=None, repr=False)

    def __post_init__(self, **_ignore):
        self.metadata = Metadata(name="vlan", type="entity")
        self.id = int(self.id)
        if self.connector:
            if not hasattr(self.connector, "metadata"):
                raise ValueError(
                    f"It does not contain metadata attribute: {self.connector}"
                )
            if self.connector.metadata.name != "device":
                raise ValueError(
                    f"It is not a valid connector object: {self.connector}"
                )


class VlansBase(EntityCollections):
    ENTITY = "vlan"

    def __init__(self, *args, **kwargs):
        super().__init__(entity=self.ENTITY, *args, **kwargs)
        self.metadata = Metadata(name="vlans", type="collection")

    def __setitem__(self, *args, **kwargs):
        super().__setitem__(*args, entity=self.ENTITY, **kwargs)
