"""Dual-spine, multi-zone Mininet topology for isolated SDN measurements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LabAddresses:
    campus_network: str = "10.77.10.0/24"
    branch_network: str = "10.77.11.0/24"
    attacker_network: str = "10.77.12.0/24"
    service_network: str = "10.77.20.0/24"
    spine_a_network: str = "172.31.1.0/24"
    spine_b_network: str = "172.31.2.0/24"


ADDRESSES = LabAddresses()
SWITCH_DPIDS = {
    "leaf-campus": "0000000000000001",
    "leaf-branch": "0000000000000002",
    "leaf-red": "0000000000000003",
    "leaf-service": "0000000000000004",
    "spine-a": "0000000000000011",
    "spine-b": "0000000000000012",
}
# Linux network-interface names are capped at 15 bytes.  Mininet derives link
# interfaces as ``<node>-eth<n>``, so descriptive dataset names cannot be used
# as its kernel node names.  This mapping keeps the data contract readable and
# the kernel-facing names safely short.
SWITCH_NODE_NAMES = {
    "leaf-campus": "lc",
    "leaf-branch": "lb",
    "leaf-red": "lr",
    "leaf-service": "ls",
    "spine-a": "sa",
    "spine-b": "sb",
}


def controller_switch_id(switch_name: str) -> str:
    """Return the decimal DPID string emitted by Ryu for an OVS switch name."""

    return str(int(SWITCH_DPIDS[switch_name], 16))


def mininet_switch_name(switch_id: str) -> str:
    """Return the short kernel-facing Mininet name for a dataset switch ID."""

    return SWITCH_NODE_NAMES[switch_id]


def build_topology() -> Any:
    """Return a Topo with four OVS access switches, two spines, and four routers.

    Imports are intentionally local: ordinary contract tests do not need a
    Linux kernel, Mininet, or Open vSwitch installation.
    """

    from mininet.link import TCLink
    from mininet.node import Node
    from mininet.topo import Topo

    class LinuxRouter(Node):
        def config(self, **params: Any) -> Any:
            result = super().config(**params)
            self.cmd("sysctl -w net.ipv4.ip_forward=1")
            self.cmd("sysctl -w net.ipv4.conf.all.rp_filter=0")
            return result

        def terminate(self) -> Any:
            self.cmd("sysctl -w net.ipv4.ip_forward=0")
            return super().terminate()

    class MultiZoneDualSpineTopo(Topo):
        def build(self) -> None:
            leaves = ("leaf-campus", "leaf-branch", "leaf-red", "leaf-service")
            spines = ("spine-a", "spine-b")
            for switch in (*leaves, *spines):
                self.addSwitch(
                    mininet_switch_name(switch),
                    dpid=SWITCH_DPIDS[switch],
                    protocols="OpenFlow13",
                    failMode="secure",
                )

            routers = {
                "r-campus": ("leaf-campus", "10.77.10.1/24", "172.31.1.2/24", "172.31.2.2/24"),
                "r-branch": ("leaf-branch", "10.77.11.1/24", "172.31.1.3/24", "172.31.2.3/24"),
                "r-red": ("leaf-red", "10.77.12.1/24", "172.31.1.4/24", "172.31.2.4/24"),
                "r-service": ("leaf-service", "10.77.20.1/24", "172.31.1.1/24", "172.31.2.1/24"),
            }
            for router_name, (leaf, lan_ip, spine_a_ip, spine_b_ip) in routers.items():
                self.addNode(router_name, cls=LinuxRouter, ip=None)
                self.addLink(router_name, mininet_switch_name(leaf), cls=TCLink, bw=100, delay="1ms", params1={"ip": lan_ip})
                self.addLink(router_name, mininet_switch_name("spine-a"), cls=TCLink, bw=100, delay="2ms", params1={"ip": spine_a_ip})
                self.addLink(router_name, mininet_switch_name("spine-b"), cls=TCLink, bw=100, delay="4ms", params1={"ip": spine_b_ip})

            for index in range(1, 5):
                self.addHost(
                    f"c{index}",
                    ip=f"10.77.10.{10 + index}/24",
                    defaultRoute="via 10.77.10.1",
                )
                self.addLink(f"c{index}", mininet_switch_name("leaf-campus"), cls=TCLink, bw=25, delay="2ms")
                self.addHost(
                    f"b{index}",
                    ip=f"10.77.11.{10 + index}/24",
                    defaultRoute="via 10.77.11.1",
                )
                self.addLink(f"b{index}", mininet_switch_name("leaf-branch"), cls=TCLink, bw=25, delay="4ms")

            for index in range(1, 9):
                self.addHost(
                    f"a{index}",
                    ip=f"10.77.12.{10 + index}/24",
                    defaultRoute="via 10.77.12.1",
                )
                self.addLink(f"a{index}", mininet_switch_name("leaf-red"), cls=TCLink, bw=20, delay="2ms")

            services = {"web": "10.77.20.10/24", "api": "10.77.20.20/24", "dns": "10.77.20.53/24"}
            for name, address in services.items():
                self.addHost(name, ip=address, defaultRoute="via 10.77.20.1")
                self.addLink(name, mininet_switch_name("leaf-service"), cls=TCLink, bw=100, delay="1ms")

    return MultiZoneDualSpineTopo()


def configure_routes(network: Any) -> None:
    """Install deterministic primary and backup routes after Mininet starts."""

    primary = {"r-campus": "172.31.1.2", "r-branch": "172.31.1.3", "r-red": "172.31.1.4", "r-service": "172.31.1.1"}
    backup = {"r-campus": "172.31.2.2", "r-branch": "172.31.2.3", "r-red": "172.31.2.4", "r-service": "172.31.2.1"}
    zone_networks = {
        "r-campus": ADDRESSES.campus_network,
        "r-branch": ADDRESSES.branch_network,
        "r-red": ADDRESSES.attacker_network,
        "r-service": ADDRESSES.service_network,
    }
    for router_name, router in ((name, network.get(name)) for name in primary):
        for destination_router, destination_network in zone_networks.items():
            if destination_router == router_name:
                continue
            router.cmd(f"ip route replace {destination_network} via {primary[destination_router]} metric 100")
            router.cmd(f"ip route add {destination_network} via {backup[destination_router]} metric 200 2>/dev/null || true")


def start_lab(controller_ip: str = "127.0.0.1", controller_port: int = 6653) -> Any:
    """Start the full Mininet fabric attached to the external Ryu controller."""

    from mininet.link import TCLink
    from mininet.net import Mininet
    from mininet.node import OVSSwitch, RemoteController

    network = Mininet(topo=build_topology(), controller=None, switch=OVSSwitch, link=TCLink, autoSetMacs=True)
    network.addController("c0", controller=RemoteController, ip=controller_ip, port=controller_port)
    network.start()
    configure_routes(network)
    return network
