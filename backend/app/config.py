from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ → raíz del repo
REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class HikvisionDevice:
    device_id: str
    host: str
    port: int = 80


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    source: str = "mock"  # mock | hikvision | hikcentral_pdf

    # Reportes: store = lee SQLite (recomendado guía); live = ISAPI en cada request
    report_data_mode: str = "store"
    # Si store vacío / auto: sync ISAPI antes de generar (solo edge local)
    auto_sync_on_report: bool = True

    # Sede actual del agente (una sede por proceso edge)
    site_code: str = "oficina_central"
    site_name: str = "Torre Sindoni (oficina central)"
    site_id: str = ""  # UUID; si vacío se resuelve por site_code

    # Cliente edge → INTEGRADO (vacío = mock local en :8003)
    integrado_base_url: str = ""
    enrollment_token: str = ""
    agent_credential: str = ""
    integrado_timeout: float = 20.0

    # JSON generado desde PDF HikCentral (Tarjeta de registro de tiempo)
    mock_events_json: str = ""

    # Un solo host (compat) o lista: BIO-01@192.168.10.200:80,BIO-02@192.168.10.201:80
    hikvision_devices: str = ""
    hikvision_host: str = "192.168.1.64"
    hikvision_port: int = 80
    hikvision_user: str = "admin"
    hikvision_password: str = ""
    hikvision_use_https: bool = False
    device_id: str = "BIO-01"

    cafeteria_cutoff: str = "09:00:00"
    # Candidatos GTH: primera marca después del corte y antes de este límite
    cafeteria_late_end: str = "11:00:00"
    hikvision_timeout: float = 15.0
    hikvision_page_size: int = 30

    letterhead_pdf: str = str(REPO_ROOT / "assets" / "hoja-membretada.pdf")

    # Integración Albatros INTEGRADO
    auth_disabled: bool = True  # true = desarrollo local sin JWT
    jwt_secret_key: str = ""
    app_client_id: str = "biometrico"

    @property
    def cafeteria_cutoff_time(self):
        from datetime import time

        parts = self.cafeteria_cutoff.split(":")
        return time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)

    @property
    def cafeteria_late_end_time(self):
        from datetime import time

        parts = self.cafeteria_late_end.split(":")
        return time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)

    @property
    def hikvision_base_url(self) -> str:
        scheme = "https" if self.hikvision_use_https else "http"
        return f"{scheme}://{self.hikvision_host}:{self.hikvision_port}"

    def _parse_env_hikvision_devices(self) -> list[HikvisionDevice]:
        """Solo dispositivos definidos en variables de entorno."""
        raw = (self.hikvision_devices or "").strip()
        if not raw:
            return [
                HikvisionDevice(
                    device_id=self.device_id,
                    host=self.hikvision_host,
                    port=self.hikvision_port,
                )
            ]

        devices: list[HikvisionDevice] = []
        for chunk in raw.split(","):
            part = chunk.strip()
            if not part:
                continue
            device_id = self.device_id
            host_port = part
            if "@" in part:
                device_id, host_port = part.split("@", 1)
                device_id = device_id.strip() or self.device_id
            host = host_port
            port = self.hikvision_port
            if ":" in host_port:
                host, port_s = host_port.rsplit(":", 1)
                host = host.strip()
                if port_s.strip().isdigit():
                    port = int(port_s.strip())
            if host:
                devices.append(HikvisionDevice(device_id=device_id, host=host, port=port))
        return devices or [
            HikvisionDevice(
                device_id=self.device_id,
                host=self.hikvision_host,
                port=self.hikvision_port,
            )
        ]

    def parsed_hikvision_devices(self) -> list[HikvisionDevice]:
        """
        Env (.env) + dispositivos agregados desde la UI (data/hikvision_devices.json).
        Si el mismo ID está en ambos, gana el de la UI.
        """
        from app.services.device_registry import get_device_registry

        by_id: dict[str, HikvisionDevice] = {
            d.device_id: d for d in self._parse_env_hikvision_devices()
        }
        for managed in get_device_registry().list_devices():
            by_id[managed.device_id] = managed.to_hikvision()
        return list(by_id.values())

    def hikvision_url_for(self, device: HikvisionDevice) -> str:
        scheme = "https" if self.hikvision_use_https else "http"
        return f"{scheme}://{device.host}:{device.port}"

    @property
    def letterhead_path(self) -> Path:
        path = Path(self.letterhead_pdf)
        if not path.is_absolute():
            candidates = [
                (Path(__file__).resolve().parent.parent / path).resolve(),
                (REPO_ROOT / path).resolve(),
                (REPO_ROOT / "assets" / "hoja-membretada.pdf").resolve(),
            ]
            for candidate in candidates:
                if candidate.exists():
                    return candidate
            return candidates[0]
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
