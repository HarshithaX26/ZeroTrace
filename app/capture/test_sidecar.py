"""Unit tests for compose capture-override injection."""

from __future__ import annotations

from pathlib import Path

from app.capture import sidecar

PROJECT = Path(__file__).resolve().parents[2] / "env"


def test_override_renders_one_sidecar_per_service() -> None:
    files = sidecar.compose_files(PROJECT)
    override = sidecar.build_override(files)

    services = set(override["services"])
    assert services == {
        "zt-frontend-cap",
        "zt-auth-cap",
        "zt-orders-cap",
        "zt-db-cap",
        "zt-rogue-cap",
    }


def test_sidecar_shares_service_network_namespace() -> None:
    files = sidecar.compose_files(PROJECT)
    override = sidecar.build_override(files)

    sidecars = override["services"]
    for svc, cap in sidecars.items():
        target = svc.removeprefix("zt-").removesuffix("-cap")
        assert cap["network_mode"] == f"service:{target}"
        assert cap["image"] == sidecar.CAPTURE_IMAGE
        assert set(cap["cap_add"]) == {"NET_RAW", "NET_ADMIN"}
        assert cap["command"][0] == "-U"
        assert cap["command"][-1] == "/capture/eth0.pcap"
        mount = cap["volumes"][0]
        assert mount["target"] == "/capture"
        assert mount["source"].endswith(f"/capture/{target}")


def test_override_writes_mergable_yaml(tmp_path: Path) -> None:
    import yaml

    files = sidecar.compose_files(PROJECT)
    out = sidecar.write_override(sidecar.build_override(files))
    rendered = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert "services" in rendered
    assert len(rendered["services"]) == 5
