"""Four-host isolated OpenFlow 1.3 topology for the local lab."""
try:
    from mininet.topo import Topo
except ImportError:
    Topo = object
class SdnDdosTopology(Topo):
    def build(self):
        s1 = self.addSwitch('s1', protocols='OpenFlow13')
        for host in ('h1','h2','h3','h4'):
            self.addLink(self.addHost(host), s1)
