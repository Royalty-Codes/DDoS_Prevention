"""Bounded local traffic profiles; never target addresses outside Mininet."""
BASE = {'window_seconds': 10, 'attacker_count': 3}
def scenario(label, family, protocol, application, pps, packet_size, flows, ack_ratio, intensity, cpu):
    return {**BASE, 'label':label, 'attack_family':family, 'protocol':protocol, 'application':application, 'pps':pps, 'packet_size':packet_size, 'flows':flows, 'ack_ratio':ack_ratio, 'attack_intensity':intensity, 'controller_proxy':cpu}
SCENARIOS = [
 scenario('BENIGN','BENIGN','TCP','HTTP',(20,180),(400,1200),(1,8),(.6,.99),0,(5,25)),
 scenario('UDP_FLOOD','VOLUMETRIC','UDP','UDP',(800,2500),(256,900),(20,100),(0,0),.6,(25,60)),
 scenario('ICMP_FLOOD','VOLUMETRIC','ICMP','ICMP',(600,2200),(64,1200),(10,70),(0,0),.6,(20,60)),
 scenario('UDP_AMPLIFICATION_STYLE','VOLUMETRIC','UDP','DNS',(900,2800),(700,1400),(20,100),(0,0),.7,(30,70)),
 scenario('SYN_FLOOD','PROTOCOL','TCP','TCP',(500,2000),(40,100),(80,300),(.01,.2),.7,(35,80)),
 scenario('PING_OF_DEATH_STYLE','PROTOCOL','ICMP','ICMP',(80,500),(1400,9000),(5,30),(0,0),.5,(15,50)),
 scenario('SMURF_STYLE','PROTOCOL','ICMP','ICMP',(700,2300),(800,1500),(20,100),(0,0),.7,(30,75)),
 scenario('HTTP_FLOOD','APPLICATION','TCP','HTTP',(300,1500),(300,1400),(40,200),(.4,.9),.6,(25,70)),
 scenario('SLOWLORIS_STYLE','APPLICATION','TCP','HTTP',(10,100),(50,400),(60,250),(.01,.25),.5,(20,65)),
 scenario('LAND_STYLE','PROTOCOL','TCP','TCP',(100,800),(40,800),(10,80),(.05,.4),.5,(20,65)),
 scenario('PACKET_IN_FLOOD_STYLE','SDN_CONTROL','UDP','UNKNOWN',(400,1800),(60,600),(200,800),(0,0),.8,(60,95)),
]
