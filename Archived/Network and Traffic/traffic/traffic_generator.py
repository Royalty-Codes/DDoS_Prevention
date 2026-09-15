"""Safe local-only traffic driver. It refuses non-Mininet targets."""
import ipaddress
def assert_local_mininet_target(host):
    address = ipaddress.ip_address(host)
    if address not in ipaddress.ip_network('10.0.0.0/8'):
        raise ValueError('Only Mininet 10.0.0.0/8 targets are allowed')
def describe_schedule(scenario):
    return f"{scenario['label']}: bounded {scenario['pps'][1]} packets/s maximum inside Mininet only"
