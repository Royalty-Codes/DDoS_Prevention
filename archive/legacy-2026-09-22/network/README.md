# Network Design

The active SDN lab is a switched campus fabric:

```text
d1 --- 10.0.1.0/24 ---\\
d2 --- 10.0.2.0/24 ----\\
d3 --- 10.0.3.0/24 ----- r1
d4 --- 10.0.4.0/24 ----/
d5 --- 10.0.5.0/24 ---/
```

All hosts use the shared `10.0.0.0/16` laboratory segment. This is deliberate:
OVS is operating as a Layer-2 data plane here, so inter-subnet routing would
require a separate router or L3 switch. Hosts remain distributed across access
switches, making their switch and path identity visible to the controller.

The active topology is `FiveDeviceRouterTopology` in
`network/topology/basic_router.py`. Future networks should be added as
separate topology classes and selected by name, so this baseline can be
disabled without deleting its definition.

Run it from the project root on a machine with Mininet installed:

```bash
sudo python3 network/topology/basic_router.py
```

The script starts the network, runs `pingAll()`, and then stops the network.