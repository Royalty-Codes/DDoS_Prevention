"""Ryu OpenFlow 1.3 controller for forwarding and laboratory telemetry."""

import json
import os
import time
from pathlib import Path

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER, set_ev_cls
from ryu.lib import hub
from ryu.lib.packet import ethernet, packet
from ryu.ofproto import ofproto_v1_3
from ryu.topology import event
from ryu.topology.api import get_all_link, get_all_switch


class SdnDdosController(app_manager.RyuApp):
    """Learning switch with topology inventory and periodic stats snapshots."""

    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}
        self.links = {}
        self.telemetry_path = Path(os.environ.get(
            "SDN_TELEMETRY_PATH", "data/raw/openflow_telemetry.jsonl"
        ))
        self.telemetry_path.parent.mkdir(parents=True, exist_ok=True)
        self.monitor_thread = hub.spawn(self._monitor)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, event_message):
        datapath = event_message.msg.datapath
        self.datapaths[datapath.id] = datapath
        self._install_table_miss(datapath)
        self.logger.info("switch_ready dpid=%s", datapath.id)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change_handler(self, event_message):
        datapath = event_message.datapath
        if event_message.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
        elif event_message.state == DEAD_DISPATCHER:
            self.datapaths.pop(datapath.id, None)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, event_message):
        message = event_message.msg
        datapath = message.datapath
        parser = datapath.ofproto_parser
        in_port = message.match["in_port"]
        parsed_packet = packet.Packet(message.data)
        ethernet_frame = parsed_packet.get_protocol(ethernet.ethernet)
        if ethernet_frame is None:
            return
        src = ethernet_frame.src
        dst = ethernet_frame.dst
        self.mac_to_port.setdefault(datapath.id, {})[src] = in_port
        out_port = self.mac_to_port[datapath.id].get(dst, datapath.ofproto.OFPP_FLOOD)
        actions = [parser.OFPActionOutput(out_port)]
        if out_port != datapath.ofproto.OFPP_FLOOD:
            match = parser.OFPMatch(in_port=in_port, eth_src=src, eth_dst=dst)
            self._add_flow(datapath, 10, match, actions, idle_timeout=60)
        datapath.send_msg(parser.OFPPacketOut(
            datapath=datapath, buffer_id=message.buffer_id,
            in_port=in_port, actions=actions,
            data=message.data if message.buffer_id == datapath.ofproto.OFP_NO_BUFFER else None,
        ))

    @set_ev_cls(event.EventSwitchEnter)
    def switch_enter_handler(self, event_message):
        self._refresh_topology()

    @set_ev_cls(event.EventLinkAdd)
    @set_ev_cls(event.EventLinkDelete)
    def link_change_handler(self, event_message):
        self._refresh_topology()

    def _install_table_miss(self, datapath):
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(datapath.ofproto.OFPP_CONTROLLER,
                                          datapath.ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(datapath, 0, match, actions)

    def _add_flow(self, datapath, priority, match, actions, idle_timeout=0):
        parser = datapath.ofproto_parser
        instructions = [parser.OFPInstructionActions(
            datapath.ofproto.OFPIT_APPLY_ACTIONS, actions
        )]
        datapath.send_msg(parser.OFPFlowMod(
            datapath=datapath, priority=priority, match=match,
            instructions=instructions, idle_timeout=idle_timeout,
        ))

    def _monitor(self):
        while True:
            for datapath in list(self.datapaths.values()):
                parser = datapath.ofproto_parser
                datapath.send_msg(parser.OFPFlowStatsRequest(datapath))
                datapath.send_msg(parser.OFPPortStatsRequest(datapath, 0))
            hub.sleep(10)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats_reply_handler(self, event_message):
        datapath = event_message.msg.datapath
        flows = []
        for stat in event_message.msg.body:
            flows.append({
                "table_id": stat.table_id,
                "priority": stat.priority,
                "packet_count": stat.packet_count,
                "byte_count": stat.byte_count,
                "duration_seconds": stat.duration_sec,
                "idle_timeout": stat.idle_timeout,
                "match": {key: str(value) for key, value in stat.match.items()},
            })
        self._write_record("flow_stats", datapath.id, {"flows": flows})

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats_reply_handler(self, event_message):
        datapath = event_message.msg.datapath
        ports = [{
            "port_no": stat.port_no,
            "rx_packets": stat.rx_packets,
            "tx_packets": stat.tx_packets,
            "rx_bytes": stat.rx_bytes,
            "tx_bytes": stat.tx_bytes,
            "rx_dropped": stat.rx_dropped,
            "tx_dropped": stat.tx_dropped,
            "rx_errors": stat.rx_errors,
            "tx_errors": stat.tx_errors,
        } for stat in event_message.msg.body]
        self._write_record("port_stats", datapath.id, {"ports": ports})

    def _refresh_topology(self):
        self.links = {
            link.src.dpid: {
                "src_port": link.src.port_no,
                "dst_dpid": link.dst.dpid,
                "dst_port": link.dst.port_no,
            }
            for link in get_all_link(self)
        }
        self.logger.info("topology switches=%s links=%s",
                         [switch.dp.id for switch in get_all_switch(self)],
                         len(get_all_link(self)))

    def _write_record(self, record_type, switch_id, payload):
        record = {
            "timestamp_utc": time.time(),
            "record_type": record_type,
            "switch_id": str(switch_id),
            "topology": self.links,
            **payload,
        }
        with self.telemetry_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")