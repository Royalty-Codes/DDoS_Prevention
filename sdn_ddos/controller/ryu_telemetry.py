"""Ryu OpenFlow 1.3 learning switch with an auditable telemetry journal.

Run only through a Python environment that has the optional `controller`
dependencies installed. The capture process consumes this JSONL journal rather
than inventing controller-side counters.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil
from ryu.base import app_manager
from ryu.controller import dpset, ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, DEAD_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.lib import hub
from ryu.lib.packet import ethernet, packet
from ryu.ofproto import ofproto_v1_3


class MeasuredTelemetryController(app_manager.RyuApp):
    """Installs ordinary learning flows and writes only controller observations."""

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    _CONTEXTS = {"dpset": dpset.DPSet}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.datapaths: dict[int, Any] = {}
        self.mac_to_port: dict[int, dict[str, int]] = {}
        self.packet_in_total: dict[int, int] = {}
        self.telemetry_path = Path(os.environ.get("SDN_DDOS_CONTROLLER_TELEMETRY", "runs/controller_telemetry.jsonl"))
        self.telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        self.process = psutil.Process()
        self.process.cpu_percent(interval=None)  # Prime psutil's interval measurement.
        self.monitor_thread = hub.spawn(self._monitor)

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _write_event(self, event_type: str, switch_id: str, **fields: Any) -> None:
        event = {"event_type": event_type, "timestamp_utc": self._utc_now(), "switch_id": switch_id, **fields}
        with self.telemetry_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True))
            handle.write("\n")

    def _add_flow(self, datapath: Any, priority: int, match: Any, actions: list[Any], idle_timeout: int = 30) -> None:
        parser = datapath.ofproto_parser
        instructions = [parser.OFPInstructionActions(datapath.ofproto.OFPIT_APPLY_ACTIONS, actions)]
        datapath.send_msg(
            parser.OFPFlowMod(
                datapath=datapath,
                priority=priority,
                match=match,
                instructions=instructions,
                idle_timeout=idle_timeout,
            )
        )

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, event: Any) -> None:
        datapath = event.msg.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        self.datapaths[datapath.id] = datapath
        self.mac_to_port.setdefault(datapath.id, {})
        self.packet_in_total.setdefault(datapath.id, 0)
        self._add_flow(
            datapath,
            priority=0,
            match=parser.OFPMatch(),
            actions=[parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)],
            idle_timeout=0,
        )
        self._write_event("switch_connected", str(datapath.id), datapath_id=datapath.id)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, event: Any) -> None:
        datapath = event.datapath
        if event.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
        elif event.state == DEAD_DISPATCHER:
            self.datapaths.pop(datapath.id, None)
            self._write_event("switch_disconnected", str(datapath.id), datapath_id=datapath.id)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, event: Any) -> None:
        message = event.msg
        datapath = message.datapath
        parser = datapath.ofproto_parser
        ofproto = datapath.ofproto
        dpid = datapath.id
        self.packet_in_total[dpid] = self.packet_in_total.get(dpid, 0) + 1
        ingress_port = message.match["in_port"]
        eth = packet.Packet(message.data).get_protocol(ethernet.ethernet)
        if eth is None:
            return
        destination, source = eth.dst, eth.src
        table = self.mac_to_port.setdefault(dpid, {})
        table[source] = ingress_port
        egress_port = table.get(destination, ofproto.OFPP_FLOOD)
        actions = [parser.OFPActionOutput(egress_port)]
        if egress_port != ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=ingress_port, eth_src=source, eth_dst=destination)
            self._add_flow(datapath, priority=10, match=match, actions=actions, idle_timeout=20)
        data = None if message.buffer_id != ofproto.OFP_NO_BUFFER else message.data
        datapath.send_msg(
            parser.OFPPacketOut(
                datapath=datapath,
                buffer_id=message.buffer_id,
                in_port=ingress_port,
                actions=actions,
                data=data,
            )
        )

    def _monitor(self) -> None:
        while True:
            for datapath in list(self.datapaths.values()):
                parser = datapath.ofproto_parser
                datapath.send_msg(parser.OFPFlowStatsRequest(datapath))
                datapath.send_msg(parser.OFPPortStatsRequest(datapath, 0))
            hub.sleep(1.0)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, event: Any) -> None:
        datapath = event.msg.datapath
        rows = list(event.msg.body)
        self._write_event(
            "flow_snapshot",
            str(datapath.id),
            datapath_id=datapath.id,
            flow_table_size=len(rows),
            packet_in_total=self.packet_in_total.get(datapath.id, 0),
            controller_cpu_pct=self.process.cpu_percent(interval=None),
            flow_packet_total=sum(int(item.packet_count) for item in rows),
            flow_byte_total=sum(int(item.byte_count) for item in rows),
        )

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply_handler(self, event: Any) -> None:
        datapath = event.msg.datapath
        ports = list(event.msg.body)
        self._write_event(
            "port_snapshot",
            str(datapath.id),
            datapath_id=datapath.id,
            rx_packets=sum(int(port.rx_packets) for port in ports),
            tx_packets=sum(int(port.tx_packets) for port in ports),
            rx_bytes=sum(int(port.rx_bytes) for port in ports),
            tx_bytes=sum(int(port.tx_bytes) for port in ports),
        )
