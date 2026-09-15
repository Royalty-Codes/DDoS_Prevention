"""Basic five-device network connected through one Linux router."""

from mininet.node import Node
from mininet.topo import Topo


class LinuxRouter(Node):
    """Mininet node that forwards packets between its interfaces."""

    def config(self, **params):
        super().config(**params)
        self.cmd("sysctl -w net.ipv4.ip_forward=1")

    def terminate(self):
        self.cmd("sysctl -w net.ipv4.ip_forward=0")
        super().terminate()


class FiveDeviceRouterTopology(Topo):
    """Five devices, each on its own LAN segment, attached to router r1."""

    def build(self):
        router = self.addNode("r1", cls=LinuxRouter, ip=None)

        for device_number in range(1, 6):
            device_ip = f"10.0.{device_number}.2/24"
            router_ip = f"10.0.{device_number}.1/24"

            device = self.addHost(
                f"d{device_number}",
                ip=device_ip,
                defaultRoute=f"via {router_ip.split('/')[0]}",
            )
            self.addLink(device, router, params2={"ip": router_ip})


# Future topologies can be added as separate classes and selected by the
# Mininet launcher without changing this basic network.
topos = {"five_device_router": FiveDeviceRouterTopology}


if __name__ == "__main__":
    from mininet.net import Mininet

    network = Mininet(topo=FiveDeviceRouterTopology(), controller=None)
    network.start()
    network.pingAll()
    network.stop()
