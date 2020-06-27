"""
Facts main dataclass object.

Contains all attributes and hints about the datatype (some attributes have the
attribute forced when is assigned).
"""
from dataclasses import field, asdict
from typing import Optional, List, Any
from pydantic import validator
from pydantic.dataclasses import dataclass
from netapi.units import unit_validator
from netapi.metadata import Metadata, DataConfig, HidePrivateAttrs


@dataclass(unsafe_hash=True, config=DataConfig)
class FactsBase:
    """
    Facts object definition.

    Attributes:

    - `hostname`: (str) Hostname of the device
    - `os_version`: (str) Network OS version of the system
    - `model`: (str) Model/platform of the network device appliance
    - `serial_number`: (str) Serial number of the device. Chassis for the modular ones
    - `uptime`: (Duration) object which specifies the device uptime
    - `up_since`: (DateTime) object which has the date since the device was UP
    - `system_mac`: (EUI) MAC address object of the system/chassis
    - `available_memory`: (Byte) object which specifies the system available memory
    - `total_memory`: (Byte) object which specifies the system memory
    - `os_architecture`: (str) System OS architecture
    - `hardware_revision`: (str) Hardware revision of the device
    - `interfaces`: (List) Interfaces available on the device
    - `connector`: Device object used to perform the necessary connection.
    - `metadata`: Metadata object which contains information about the current object.
    - `get_cmd`: Command to retrieve route information out of the device
    """

    hostname: Optional[str] = None
    os_version: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    uptime: Optional[Any] = None
    up_since: Optional[Any] = None
    system_mac: Optional[Any] = None
    available_memory: Optional[Any] = None
    total_memory: Optional[Any] = None
    os_architecture: Optional[str] = None
    hardware_revision: Optional[str] = None
    interfaces: Optional[List[str]] = field(default=None)
    connector: Optional[Any] = field(default=None, repr=False)
    metadata: Optional[Any] = field(default=None, repr=False)
    get_cmd: Optional[Any] = field(default=None, repr=False)

    @validator("system_mac")
    def valid_mac(cls, value):
        return unit_validator("netaddr.eui.EUI", "EUI", value)

    @validator("uptime")
    def valid_duration(cls, value):
        return unit_validator("pendulum.duration.Duration", "Duration", value)

    @validator("up_since")
    def valid_datetime(cls, value):
        return unit_validator("pendulum.datetime.DateTime", "DateTime", value)

    @validator("available_memory")
    def valid_available_mem_byte(cls, value):
        return unit_validator("bitmath.Byte", "Byte", value)

    @validator("total_memory")
    def valid_total_mem_byte(cls, value):
        return unit_validator("bitmath.Byte", "Byte", value)

    def __post_init__(self, **_ignore):
        self.metadata = Metadata(name="facts", type="entity")
        if self.connector:
            if not hasattr(self.connector, "metadata"):
                raise ValueError(
                    f"It does not contain metadata attribute: {self.connector}"
                )
            if self.connector.metadata.name != "device":
                raise ValueError(
                    f"It is not a valid connector object: {self.connector}"
                )

    def to_dict(self):
        return asdict(self, dict_factory=HidePrivateAttrs)
