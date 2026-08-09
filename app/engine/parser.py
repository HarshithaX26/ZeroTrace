"""pcap parsing: stream capture files into normalized, aggregated flows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scapy.all import IP, TCP, UDP, PcapReader

_PROTO_NAMES = {1: "icmp", 6: "tcp", 17: "udp"}
# TCP header flag-offset 1 bits: SYN = 0x02, ACK = 0x10.
_SYN_MASK = 0x02
_ACK_MASK = 0x10


@dataclass(frozen=True, order=True)
class FlowKey:
    """Protocol-level key, used before IP addresses are resolved to services."""

    src_ip: str
    dst_ip: str
    proto: str
    dport: int


@dataclass
class Flow:
    """Aggregated counters for one :class:`FlowKey`."""

    key: FlowKey
    packets: int = 0
    bytes: int = 0
    syn: int = 0
    first_ts: float = 0.0
    last_ts: float = 0.0


def extract(pkt) -> tuple[FlowKey, bool] | None:
    """Return ``(FlowKey, is_syn)`` for one scapy packet, or ``None``.

    ``is_syn`` marks TCP connection-open packets; the destination port of a
    SYN is the listening port, which the graph builder uses to fold the
    matching ACK return-traffic back into the one canonical edge.
    """
    if IP not in pkt:
        return None
    ip: IP = pkt[IP]
    proto_num = int(ip.proto)
    proto = _PROTO_NAMES.get(proto_num, str(proto_num))

    dport = 0
    syn = False
    if proto == "tcp" and TCP in pkt:
        tcp: TCP = pkt[TCP]
        flags = int(tcp.flags)
        dport = int(tcp.dport)
        # A connection-open is SYN *without* ACK; SYN-ACK (S+A) is a reply.
        syn = bool(flags & _SYN_MASK) and not bool(flags & _ACK_MASK)
    elif proto == "udp" and UDP in pkt:
        dport = int(pkt[UDP].dport)

    return FlowKey(src_ip=ip.src, dst_ip=ip.dst, proto=proto, dport=dport), syn


def parse_pcap(path: Path) -> dict[FlowKey, Flow]:
    """Stream ``path`` with scapy and aggregate per-key counters.

    Operates on the raw IP addresses; services are resolved later by the
    graph builder. Packet size uses the IP header length, skipping
    link-layer padding so counters stay consistent across capture points.
    """
    flows: dict[FlowKey, Flow] = {}
    with PcapReader(str(path)) as reader:
        for pkt in reader:
            parsed = extract(pkt)
            if parsed is None:
                continue
            key, syn = parsed
            flow = flows.get(key)
            if flow is None:
                flow = flows[key] = Flow(key=key, first_ts=float(pkt.time))
            flow.packets += 1
            flow.bytes += len(pkt[IP])
            flow.syn += 1 if syn else 0
            flow.last_ts = float(pkt.time)
    return flows
