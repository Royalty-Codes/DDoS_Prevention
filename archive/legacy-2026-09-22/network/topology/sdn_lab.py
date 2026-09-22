"""Practical multi-switch SDN laboratory topology for DDoS experiments."""

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.net import Mininet
from mininet.node import Host, OVSSwitch, RemoteController
from mininet.topo import Topo


class SdnDdosLabTopology(Topo):
    """Two access switches, two core switches, and three service segments."""

    def build(self):
        switches = {
            name: self.addSwitch(name, protocols="OpenFlow13")
            for name in ("s1", "s2", "s3", "s4")
        }

        # Two parallel core paths provide path diversity and failover tests.
        self.addLink(switches["s1"], switches["s3"], cls=TCLink, bw=100)
        self.addLink(switches["s1"], switches["s4"], cls=TCLink, bw=100)
        self.addLink(switches["s2"], switches["s3"], cls=TCLink, bw=100)
        self.addLink(switches["s2"], switches["s4"], cls=TCLink, bw=100)
        self.addLink(switches["s3"], switches["s4"], cls=TCLink, bw=100)

        # One /16 campus segment keeps this fabric L2-only; OVS does not route.
        clients = {
            "c1": ("s1", "10.0.0.11/16"),
            "c2": ("s1", "10.0.0.12/16"),
            "c3": ("s2", "10.0.0.21/16"),
            "c4": ("s2", "10.0.0.22/16"),
        }
        attackers = {
            "a1": ("s1", "10.0.0.101/16"),
            "a2": ("s2", "10.0.0.102/16"),
            "a3": ("s1", "10.0.0.103/16"),
            "a4": ("s2", "10.0.0.104/16"),
        }
        services = {
            "web": ("s3", "10.0.0.10/16"),
            "dns": ("s3", "10.0.0.53/16"),
            "ntp": ("s4", "10.0.0.123/16"),
            "ssdp": ("s4", "10.0.0.190/16"),
        }

        for host_name, (switch_name, address) in {
            **clients,
            **attackers,
            **services,
        }.items():
            host = self.addHost(host_name, cls=Host, ip=address)
            self.addLink(host, switches[switch_name], cls=TCLink, bw=100)


def start_lab():
    """Start the lab with one remote Ryu controller and an interactive CLI."""
    network = Mininet(
        topo=SdnDdosLabTopology(),
        switch=OVSSwitch,
        controller=None,
        link=TCLink,
        autoSetMacs=True,
    )
    network.addController(
        "c0",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6653,
    )
    network.start()
    try:
        CLI(network)
    finally:
        network.stop()


if __name__ == "__main__":
    start_lab()