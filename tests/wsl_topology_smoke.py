"""Linux-only topology-construction check; run under WSL after bootstrap."""

from sdn_ddos.topology import SWITCH_NODE_NAMES, build_topology, controller_switch_id


def main() -> None:
    topology = build_topology()
    expected_switches = set(SWITCH_NODE_NAMES.values())
    expected_hosts = {"c1", "b1", "a1", "web", "api", "dns"}
    actual_switches = set(topology.switches())
    actual_hosts = set(topology.hosts())
    assert actual_switches == expected_switches, actual_switches
    assert expected_hosts.issubset(actual_hosts), actual_hosts
    assert controller_switch_id("leaf-red") == "3"
    print(f"topology ready: {len(actual_switches)} OVS switches, {len(actual_hosts)} hosts")


if __name__ == "__main__":
    main()
