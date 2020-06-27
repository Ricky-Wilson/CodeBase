from netapi.probe.linux import subprocesser


class Pings(subprocesser.Pings):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metadata.implementation = "LINUX-PARAMIKO"


class Ping(subprocesser.Ping):
    def __post_init__(self, **_ignore):
        super().__post_init__()
        self.metadata.implementation = "LINUX-PARAMIKO"


class PingParser(subprocesser.PingParser):
    pass
