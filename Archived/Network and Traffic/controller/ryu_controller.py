"""Observation-only Ryu OpenFlow 1.3 statistics app."""
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3
class FlowStatsController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, event):
        event.msg.datapath.send_msg(event.msg.datapath.ofproto_parser.OFPFlowMod(datapath=event.msg.datapath, priority=0, match=event.msg.datapath.ofproto_parser.OFPMatch(), instructions=[]))
    @set_ev_cls(ofp_event.EventOFPStateChange, MAIN_DISPATCHER)
    def state_change_handler(self, event):
        self.logger.info('Switch connected: %s', event.datapath.id)
