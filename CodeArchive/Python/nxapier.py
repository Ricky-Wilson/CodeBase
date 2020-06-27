import re
import pendulum
from netapi.probe import ping

PATTERNS = {
    "ping": re.compile(
        r"(?P<tx>\d+) packets transmitted, (?P<rx>\d+) packets received, "
        r"(?P<loss>\d+\.\d+)% packet loss\nround-trip min/avg/max = "
        r"(?P<min>\d+(\.\d+)?)/(?P<avg>\d+(\.\d+)?)/(?P<max>\d+(\.\d+)?).*",
        re.MULTILINE,
    )
}

TIMEOUT_PATTERNS = {
    "ping": re.compile(
        r"(?P<tx>\d+) packets transmitted, (?P<rx>\d+) packets received, "
        r"(?P<loss>\d+\.\d+)% packet loss"
    )
}


class Ping(ping.PingBase):
    def __post_init__(self, **_ignore):
        super().__post_init__()
        self.metadata.implementation = "NXOS-NXAPI"

    def _ping_parameters(self):
        "Ping Parameters for nxos"
        params = []
        if self.size:
            params.append(f"packet-size {self.size}")
        if self.count:
            params.append(f"count {self.count}")
        if self.timeout:
            params.append(f"timeout {self.timeout}")
        if self.source:
            # NOTE: On older versions of NXOS is parent-interface...
            params.append(f"source-interface {self.source}")
        if self.source_ip:
            params.append(f"source {self.source_ip}")
        if self.df_bit:
            params.append(f"df-bit")
        if self.interval:
            params.append(f"interval {self.interval}")
        return params

    def _ping_base_cmd(self):
        "Ping base command for nxos"
        # If resolve_target was selected it will use the target IP for the ping
        if self.resolve_target:
            target = str(self.target_ip)
        else:
            target = self.target
        ping_base_cmd = ["ping", target]
        if self.instance is not None:
            ping_base_cmd.append(f"vrf {self.instance}")

        return ping_base_cmd

    def generate_ping_cmd(self, **_ignore):
        self.ping_cmd = " ".join(self._ping_base_cmd() + self._ping_parameters())

    def execute(self, warning_thld=None, critical_thld=None):
        """
        Automatic execution of entity to retrieve results. Also applies warning/critical
        thresholds for the analysis if given.

        - `warning_thld`: Packet loss above this value is flagged as `warning`
        - `critical_thld`: Packet loss above this value is flagged as `critical`

        NOTE: If `warning_thld` was set and paket loss is below the percentage value,
        it is then flagged as `ok`

        By default it uses the built-in analysis:
        `packet_loss` >= 100 -> `critical`
        `packet_loss` == 0   -> `ok`
        `packet_loss` != 0   -> `warning`
        """
        if self.connector is None:
            raise NotImplementedError("Need to have the connector defined")

        # Generate exec command
        if not self.ping_cmd:
            self.generate_ping_cmd()

        result = PingParser().parse(
            self.connector.run(self.ping_cmd),
            self,
            warning_thld=warning_thld,
            critical_thld=critical_thld,
        )
        self.metadata.updated_at = pendulum.now()
        self.metadata.collection_count += 1
        return result


class PingParser:
    "Ping darta parser for the returned NXOS implementation"

    def ping_match_data(self, match_obj):
        return dict(
            probes_sent=int(match_obj.group("tx")),
            probes_received=int(match_obj.group("rx")),
            packet_loss=float("{:.4f}".format(float(match_obj.group("loss")) / 100)),
            rtt_min=float(match_obj.group("min")),
            rtt_avg=float(match_obj.group("avg")),
            rtt_max=float(match_obj.group("max")),
        )

    def ping_match_timeout_data(self, match_obj):
        return dict(
            probes_sent=int(match_obj.group("tx")),
            probes_received=int(match_obj.group("rx")),
            packet_loss=float("{:.4f}".format(float(match_obj.group("loss")) / 100)),
        )

    def _data_parser_logic(self, result, ping_match_obj, timeout_match_obj):
        if ping_match_obj:
            result.update(self.ping_match_data(ping_match_obj))
        elif timeout_match_obj:
            result.update(self.ping_match_timeout_data(timeout_match_obj))

        if not result:
            raise ValueError("[ERROR] Not able to parse ping output")

    def data_parser(self, data):
        """
        Accepts the raw input of the remote ping and returns its parsed output.

        Args:

        - `data`: Raw string of ping output

        Returns:
        - Dict: Parsed result of the raw data
        """
        result = dict()
        _ping_match = re.search(PATTERNS["ping"], data)
        _ping_timeout_match = re.search(TIMEOUT_PATTERNS["ping"], data)

        # Execute parser logic
        self._data_parser_logic(result, _ping_match, _ping_timeout_match)

        return result

    def parse(self, raw_data, ping_obj, **kwargs):
        "Parses the Ping output"
        # data = list(raw_data.values())[0].get("messages")[0]
        data = raw_data  # TODO: Needs to be developed
        if not data:
            raise ValueError(f"No data returned from device")

        # When network is unreachable
        if "Network is unreachable" in data:
            ping_obj.result = ping.PingResult(
                probes_sent=0,
                probes_received=0,
                packet_loss=0.0,
                status="no-route",
                status_code=3,
                status_up=False,
            )
            return False

        result = self.data_parser(data)

        # Add analysis data
        result.update(
            warning_thld=kwargs.get("warning_thld"),
            critical_thld=kwargs.get("critical_thld"),
            apply_analysis=True,
        )

        ping_obj.result = ping.PingResult(**result)

        return True

    def collector_parse(self, raw_data, ping_objs, **kwargs):
        """
        It takes the ouput from multiple pings executions and parses them.
        NOTE: This can only be used if targets are not the same, even if they are on
        a diffent VRF.
        """
        for _command in raw_data:
            for _ping in ping_objs.values():
                if _ping.command() == _command:
                    _ping.result = self.data_parser(raw_data[_command])
        return ping_objs
