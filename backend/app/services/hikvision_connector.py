"""
Conector a eventos de acceso Hikvision.

AccessEventSource: contrato común.
MockHikvisionConnector: datos de demostración (sin hardware).
HikvisionConnector: ISAPI real — POST /ISAPI/AccessControl/AcsEvent?format=json
  con autenticación Digest y paginación.
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from pathlib import Path

import httpx

from app.config import HikvisionDevice, Settings
from app.models.events import RawAccessEvent
from app.services.exceptions import (
    AuthenticationErrorBiometric,
    ConnectionErrorBiometric,
    DeviceProtocolError,
    EmptyResponseError,
)
from app.services.name_format import format_employee_name

logger = logging.getLogger(__name__)

# Catálogo oficial de departamentos HikCentral (UI Personas).
# Quien no esté en un depto específico figura en "All Departments".
HIKCENTRAL_DEPARTMENTS: frozenset[str] = frozenset(
    {
        "ADMON Y FINANZAS",
        "AEROPUERTO",
        "ALBATROS CARGO",
        "ASUNTOS LEGALES",
        "AUDITORIA INTERNA",
        "CENTRO DE INSTRUCCION A.",
        "COMERCIAL",
        "COMPRAS",
        "CONECCTION TOUR",
        "CONTROL CONTABLE",
        "CTROL Y ASEG DE CALIDAD",
        "ESTACION MAIQUETIA",
        "ESTACION LAS PIEDRAS",
        "ESTACION MARACAY",
        "ESTACION PORLAMAR",
        "GESTION DE TALENTO HUMANO",
        "ING Y MTTO AERO",
        "JUNTA DIRECTIVA",
        "MANTENIMIENTO AERONAUTICO",
        "MERCADEO Y PUBLICIDAD",
        "OMAC- N569",
        "OPERACIONES AEREAS",
        "P.C.P.",
        "PASANTES",
        "PROMOTORES COMUNITARIOS",
        "RENDIMIENTO CORPORATIVO",
        "S.M.S",
        "SEGURIDAD AVSEC",
        "SERVICIOS GENERALES",
        "TECNOLOGIA",
        "TRIP. DE MANDO",
        "TRIPULACION DE CABINA",
    }
)

# Depto por nombre completo (export HikCentral / UI Personas).
# El DS-K1T8003MF no expone departamento en UserInfo ISAPI.
_DEPARTMENT_BY_NAME: dict[str, str] = {
    "DAHIL DEL VALLE PALMA NAVAS": "SERVICIOS GENERALES",
    "NANCY RUTH PEREZ NAVA": "SERVICIOS GENERALES",
    "JULIO JEISON VALOR POMPA": "TECNOLOGIA",
    "FRANK JAVIER SALCEDO LOPEZ": "OPERACIONES AEREAS",
    "HERIMAR DE LOS ANGELES GARCIA RODRIGUEZ": "SERVICIOS GENERALES",
    "MARIA TERESA YANNONE DI LISO": "SEGURIDAD AVSEC",
    "DANIELA ANDREA CARRASQUEL MENDOZA": "PASANTES",
    "EMELYJOSMAR CASTRO ROJAS": "SERVICIOS GENERALES",
    "MARIA EUGENIA PEREZ PINO": "CONTROL CONTABLE",
    "KRHIS AXEL MUDAEL BELISARIO": "PASANTES",
    "ANGEL ANTONIO CONTRERAS NATERA": "CENTRO DE INSTRUCCION A.",
    "LORELIS GINETTE MONSALVE QUERALES": "CONTROL CONTABLE",
    "CARLOS DAVID RIVERO GONZALEZ": "CONTROL CONTABLE",
    "LEIXANDER GABRIEL TOVAR RODRIGUEZ": "PASANTES",
    "FRANKJELY ALEJANDRA ABREU BARRETO": "GESTION DE TALENTO HUMANO",
    "MARIA ALEJANDRA PEREZ BELLO": "AUDITORIA INTERNA",
    "KIVER JOSE GARCIA GUTIERREZ": "SERVICIOS GENERALES",
    "GERALDINE VICTORIA BLANCO GUAIMARE": "ADMON Y FINANZAS",
    "OMAR ENRIQUE CONTRERAS MEDINA": "COMERCIAL",
    "FRANKLIN ENRIQUE SALAZAR GONZALEZ": "OPERACIONES AEREAS",
    "JENIFFER ALCIMAR BENITEZ PEÑA": "ADMON Y FINANZAS",
    "AMILCAR JOSE MUCHACA VARGAS": "OPERACIONES AEREAS",
    "BRAYAM LEONEL ARRIETA VILLALOBOS": "SERVICIOS GENERALES",
    "JESUS LEONARDO CASTILLO CONTRERA": "AEROPUERTO",
    "GUSTAVO DE LA CRUZ MARQUEZ": "TECNOLOGIA",
    "PAULO ANTONIO PEREZ ROJAS": "TECNOLOGIA",
    "MANUEL VICENTE RAMIREZ CEDEÑO": "TRIP. DE MANDO",
    "CARMEN GABRIELA BARRERA BANDRES": "CONTROL CONTABLE",
    "AYMARA GABRIELA RODRIGUEZ VALERO": "OPERACIONES AEREAS",
    "DUBREYKIS MARIELIS ZERPA HENRIQUEZ": "ADMON Y FINANZAS",
    "GABRIELA JOSE NOGUERA DOMINGUEZ": "AEROPUERTO",
    "YOSIL ISABEL MARTINEZ SILVA": "S.M.S",
    "GUSTAVO ADOLFO SOTO CASTILLO": "COMERCIAL",
    "NEREIDA DEL CARMEN PICON UZCATEGUI": "GESTION DE TALENTO HUMANO",
    "ANTHONY BRYAN MORE COLMENARES": "ADMON Y FINANZAS",
    "ABRAHAM ALEXANDER OVIEDO YANNONE": "TECNOLOGIA",
    "JESUS ARMANDO GARCIA ESCALONA": "MERCADEO Y PUBLICIDAD",
    "GLADYS GIOVANNA PEREZ BLANCO": "S.M.S",
    "ENDRICK OMAR DELGADO HERNANDEZ": "SERVICIOS GENERALES",
    "JOSE GREGORIO ROJO ALVAREZ": "ING Y MTTO AERO",
    "JUAN MELO": "JUNTA DIRECTIVA",
    "ELEAZAR ALEXANDER ACEVEDO MORILLO": "ADMON Y FINANZAS",
    # HikCentral Personas — verificados 2026-08-05 (terminal no expone depto ISAPI)
    "ALEXANDER ANTONIO MENDEZ LUCENA": "SERVICIOS GENERALES",
    "NEIL QUINTERO": "ASUNTOS LEGALES",
    "ALEJANDRA DE LOS ANGELES ARTALEJO PIÑA": "SERVICIOS GENERALES",
    "LUZHANA HENRIQUEZ": "ASUNTOS LEGALES",
    "RUBEN JOSE PIÑA MORALES": "ASUNTOS LEGALES",
    "EDUARDO JOSE ROJO": "SERVICIOS GENERALES",
    "LUIS ENRIQUE LUCERO MEDINA": "SERVICIOS GENERALES",
    "JOHAN ARTURO ZAPATA CASTILLO": "SERVICIOS GENERALES",
    "ALEXIS GREGORIO SEGOVIA HERNANDEZ": "SERVICIOS GENERALES",
    "KELLA NAHOMI MARACARA GONZALEZ": "PASANTES",
    "AURELIO C MEDINA C": "TECNOLOGIA",
    "RAMON TRUJILLO": "JUNTA DIRECTIVA",
}

# Depto por employeeNo del terminal (más estable que el nombre)
_DEPARTMENT_BY_EMPLOYEE_NO: dict[str, str] = {
    "0000000044": "ADMON Y FINANZAS",  # ELEAZAR ALEXANDER ACEVEDO MORILLO
    "000000000208": "SERVICIOS GENERALES",  # ALEXANDER ANTONIO MENDEZ LUCENA
    "0000000000000184": "ASUNTOS LEGALES",  # NEIL QUINTERO
    "0000000003": "SERVICIOS GENERALES",  # ALEJANDRA DE LOS ANGELES ARTALEJO PIÑA
    "6126098442": "ASUNTOS LEGALES",  # LUZHANA HENRIQUEZ
    "0000000145": "ASUNTOS LEGALES",  # RUBEN JOSE PIÑA MORALES
    "000000000190": "SERVICIOS GENERALES",  # EDUARDO JOSE ROJO
    "0000000096": "SERVICIOS GENERALES",  # LUIS ENRIQUE LUCERO MEDINA
    "0000000076": "SERVICIOS GENERALES",  # JOHAN ARTURO ZAPATA CASTILLO
    "0000000008": "SERVICIOS GENERALES",  # ALEXIS GREGORIO SEGOVIA HERNANDEZ
    "000000000210": "SERVICIOS GENERALES",  # ENDRICK OMAR DELGADO HERNANDEZ
    "000000000197": "PASANTES",  # KELLA NAHOMI MARACARA GONZALEZ
    "00000000194": "TECNOLOGIA",  # AURELIO C MEDINA C
    "0000000000000187": "JUNTA DIRECTIVA",  # RAMON TRUJILLO
}


def _department_lookup(employee_id: str, employee_name: str) -> str:
    """Resuelve depto por ID, nombre completo o nombre corto formateado."""
    emp = (employee_id or "").strip()
    if emp and emp in _DEPARTMENT_BY_EMPLOYEE_NO:
        return _DEPARTMENT_BY_EMPLOYEE_NO[emp]

    name = (employee_name or "").strip().upper()
    if not name:
        return ""
    if name in _DEPARTMENT_BY_NAME:
        return _DEPARTMENT_BY_NAME[name]

    # Índice por nombre corto (p. ej. ELEAZAR A. ACEVEDO M.)
    short = format_employee_name(name)
    if short in _DEPARTMENT_BY_NAME:
        return _DEPARTMENT_BY_NAME[short]
    for full, dept in _DEPARTMENT_BY_NAME.items():
        if format_employee_name(full) == short or format_employee_name(full) == name:
            return dept
    return ""


def resolve_department(employee_id: str, employee_name: str) -> str:
    """Resuelve depto por ID o nombre (mapa HikCentral; el terminal ISAPI no lo expone)."""
    return _department_lookup(employee_id, employee_name)


class AccessEventSource(ABC):
    @abstractmethod
    async def fetch_events(self, from_date: date, to_date: date) -> list[RawAccessEvent]:
        """Obtiene eventos crudos en el rango [from_date, to_date] inclusive."""


class JsonFileEventSource(AccessEventSource):
    """Eventos desde JSON generado a partir del PDF HikCentral (prueba local)."""

    def __init__(self, json_path: Path, device_id: str = "HIKCENTRAL-PDF") -> None:
        from app.services.hikcentral_pdf_loader import load_events_from_json

        self.device_id = device_id
        self._events = load_events_from_json(Path(json_path))
        logger.info(
            "JsonFileEventSource: %s eventos desde %s",
            len(self._events),
            json_path,
        )

    async def fetch_events(self, from_date: date, to_date: date) -> list[RawAccessEvent]:
        events = [
            e
            for e in self._events
            if e.timestamp is not None and from_date <= e.timestamp.date() <= to_date
        ]
        if not events:
            raise EmptyResponseError(
                f"JSON sin eventos entre {from_date.isoformat()} y {to_date.isoformat()}"
            )
        return events


class MockHikvisionConnector(AccessEventSource):
    """
    Fuente mock con el export Hikvision Transacciones A4 del 2026-07-22.
    Conserva duplicados del PDF; event_cleaner deduplica por minuto.
    Comedor (≤ 09:00): 35 personas. Fuera de corte: 09:06, 09:35, 09:45 y tarde.
    """

    # (id, nombre, departamento) — IDs estables inventados (el PDF no trae badge).
    _PEOPLE: dict[str, tuple[str, str]] = {
        "2001": ("DAHIL DEL VALLE PALMA NAVAS", "SERVICIOS GENERALES"),
        "2002": ("NANCY RUTH PEREZ NAVA", "SERVICIOS GENERALES"),
        "2003": ("JULIO JEISON VALOR POMPA", "TECNOLOGIA"),
        "2004": ("FRANK JAVIER SALCEDO LOPEZ", "OPERACIONES AEREAS"),
        "2005": ("HERIMAR DE LOS ANGELES GARCIA RODRIGUEZ", "SERVICIOS GENERALES"),
        "2006": ("MARIA TERESA YANNONE DI LISO", "SEGURIDAD AVSEC"),
        "2007": ("DANIELA ANDREA CARRASQUEL MENDOZA", "PASANTES"),
        "2008": ("EMELYJOSMAR CASTRO ROJAS", "SERVICIOS GENERALES"),
        "2009": ("MARIA EUGENIA PEREZ PINO", "CONTROL CONTABLE"),
        "2010": ("KRHIS AXEL MUDAEL BELISARIO", "PASANTES"),
        "2011": ("ANGEL ANTONIO CONTRERAS NATERA", "CENTRO DE INSTRUCCION A."),
        "2012": ("LORELIS GINETTE MONSALVE QUERALES", "CONTROL CONTABLE"),
        "2013": ("CARLOS DAVID RIVERO GONZALEZ", "CONTROL CONTABLE"),
        "2014": ("LEIXANDER GABRIEL TOVAR RODRIGUEZ", "PASANTES"),
        "2015": ("FRANKJELY ALEJANDRA ABREU BARRETO", "GESTION DE TALENTO HUMANO"),
        "2016": ("MARIA ALEJANDRA PEREZ BELLO", "AUDITORIA INTERNA"),
        "2017": ("KIVER JOSE GARCIA GUTIERREZ", "SERVICIOS GENERALES"),
        "2018": ("GERALDINE VICTORIA BLANCO GUAIMARE", "ADMON Y FINANZAS"),
        "2019": ("OMAR ENRIQUE CONTRERAS MEDINA", "COMERCIAL"),
        "2020": ("FRANKLIN ENRIQUE SALAZAR GONZALEZ", "OPERACIONES AEREAS"),
        "2021": ("JENIFFER ALCIMAR BENITEZ PEÑA", "ADMON Y FINANZAS"),
        "2022": ("AMILCAR JOSE MUCHACA VARGAS", "OPERACIONES AEREAS"),
        "2023": ("BRAYAM LEONEL ARRIETA VILLALOBOS", "SERVICIOS GENERALES"),
        "2024": ("JESUS LEONARDO CASTILLO CONTRERA", "AEROPUERTO"),
        "2025": ("GUSTAVO DE LA CRUZ MARQUEZ", "TECNOLOGIA"),
        "2026": ("PAULO ANTONIO PEREZ ROJAS", "TECNOLOGIA"),
        "2027": ("MANUEL VICENTE RAMIREZ CEDEÑO", "TRIP. DE MANDO"),
        "2028": ("CARMEN GABRIELA BARRERA BANDRES", "CONTROL CONTABLE"),
        "2029": ("AYMARA GABRIELA RODRIGUEZ VALERO", "OPERACIONES AEREAS"),
        "2030": ("DUBREYKIS MARIELIS ZERPA HENRIQUEZ", "ADMON Y FINANZAS"),
        "2031": ("GABRIELA JOSE NOGUERA DOMINGUEZ", "AEROPUERTO"),
        "2032": ("YOSIL ISABEL MARTINEZ SILVA", "S.M.S"),
        "2033": ("GUSTAVO ADOLFO SOTO CASTILLO", "COMERCIAL"),
        "2034": ("NEREIDA DEL CARMEN PICON UZCATEGUI", "GESTION DE TALENTO HUMANO"),
        "2035": ("ANTHONY BRYAN MORE COLMENARES", "ADMON Y FINANZAS"),
        "2036": ("ABRAHAM ALEXANDER OVIEDO YANNONE", "TECNOLOGIA"),
        "2037": ("JESUS ARMANDO GARCIA ESCALONA", "MERCADEO Y PUBLICIDAD"),
        "2038": ("GLADYS GIOVANNA PEREZ BLANCO", "S.M.S"),
        "2039": ("ENDRICK OMAR DELGADO HERNANDEZ", "SERVICIOS GENERALES"),
        "2040": ("JOSE GREGORIO ROJO ALVAREZ", "ING Y MTTO AERO"),
        "2041": ("JUAN MELO", "JUNTA DIRECTIVA"),
    }

    # Marcas exactas del PDF Transacciones_A4_2026-07-22 (hora, minuto, employee_id).
    # Incluye duplicados del export (mismo minuto / segunda marca del día).
    _MARKS: list[tuple[int, int, str]] = [
        (6, 28, "2001"),
        (6, 28, "2002"),
        (6, 30, "2001"),
        (6, 44, "2003"),
        (6, 59, "2004"),
        (7, 1, "2005"),
        (7, 4, "2006"),
        (7, 4, "2006"),
        (7, 30, "2007"),
        (7, 32, "2008"),
        (7, 48, "2009"),
        (7, 59, "2010"),
        (8, 6, "2011"),
        (8, 8, "2012"),
        (8, 9, "2013"),
        (8, 12, "2014"),
        (8, 14, "2015"),
        (8, 17, "2016"),
        (8, 18, "2017"),
        (8, 20, "2018"),
        (8, 20, "2019"),
        (8, 20, "2020"),
        (8, 23, "2021"),
        (8, 25, "2022"),
        (8, 25, "2023"),
        (8, 27, "2024"),
        (8, 27, "2025"),
        (8, 31, "2026"),
        (8, 32, "2027"),
        (8, 36, "2028"),
        (8, 37, "2029"),
        (8, 38, "2030"),
        (8, 43, "2031"),
        (8, 43, "2031"),
        (8, 43, "2031"),
        (8, 44, "2032"),
        (8, 45, "2033"),
        (8, 51, "2034"),
        (8, 54, "2035"),
        (9, 6, "2036"),
        (9, 35, "2037"),
        (9, 45, "2038"),
        (9, 45, "2038"),
        (12, 1, "2023"),
        (12, 4, "2004"),
        (12, 10, "2039"),
        (12, 25, "2040"),
        (12, 26, "2041"),
        (12, 46, "2009"),
    ]

    def __init__(self, device_id: str = "BIO-01") -> None:
        self.device_id = device_id

    async def fetch_events(self, from_date: date, to_date: date) -> list[RawAccessEvent]:
        events: list[RawAccessEvent] = []
        day = from_date

        while day <= to_date:
            for hour, minute, emp_id in self._MARKS:
                name, department = self._PEOPLE[emp_id]
                events.append(
                    RawAccessEvent(
                        employee_id=emp_id,
                        employee_name=name,
                        department=department,
                        timestamp=datetime(day.year, day.month, day.day, hour, minute, 0),
                        device_id=self.device_id,
                        success=True,
                        major=5,
                        minor=75,
                    )
                )
            day += timedelta(days=1)

        if not events:
            raise EmptyResponseError(
                f"Mock sin eventos entre {from_date.isoformat()} y {to_date.isoformat()}"
            )
        return events


class HikvisionConnector(AccessEventSource):
    """
    Cliente ISAPI real (un dispositivo).

    Endpoint preferido (DS-K1T8003MF V1.4):
      POST /ISAPI/AccessControl/AcsEvent?format=json
    Auth: HTTP Digest
    Paginación: searchResultPosition + maxResults (máx. 10 en este firmware).
    """

    SEARCH_PATH_JSON = "/ISAPI/AccessControl/AcsEvent?format=json"
    SEARCH_PATH_XML = "/ISAPI/AccessControl/AcsEvent/Search"
    DEVICE_INFO_PATH = "/ISAPI/System/deviceInfo"
    # Capacidades del DS-K1T8003MF: maxResults <= 10, searchID <= 20 chars
    MAX_PAGE_SIZE = 10

    def __init__(
        self,
        settings: Settings,
        *,
        device_id: str | None = None,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        self.settings = settings
        if host is not None:
            device = HikvisionDevice(
                device_id=device_id or settings.device_id,
                host=host,
                port=port if port is not None else settings.hikvision_port,
            )
        else:
            device = settings.parsed_hikvision_devices()[0]
            if device_id:
                device = HikvisionDevice(
                    device_id=device_id, host=device.host, port=device.port
                )
        self.device = device
        self.device_id = device.device_id
        self.base_url = settings.hikvision_url_for(device)
        self.page_size = settings.hikvision_page_size
        self.timeout = settings.hikvision_timeout

    async def probe(self) -> dict:
        """
        Prueba real: Digest + deviceInfo + búsqueda AcsEvent del día.
        Devuelve muestras visibles para demostrar conexión establecida.
        """
        auth = httpx.DigestAuth(self.settings.hikvision_user, self.settings.hikvision_password)
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                auth=auth,
                timeout=min(self.timeout, 12.0),
                verify=False,
            ) as client:
                info = await client.get(self.DEVICE_INFO_PATH)
                if info.status_code in (401, 403):
                    return {
                        "device_id": self.device_id,
                        "host": self.device.host,
                        "reachable": True,
                        "auth_ok": False,
                        "connection_established": False,
                        "error": "Credenciales ISAPI inválidas (usuario/clave del terminal)",
                        "search": None,
                    }
                if info.status_code >= 400:
                    return {
                        "device_id": self.device_id,
                        "host": self.device.host,
                        "reachable": True,
                        "auth_ok": False,
                        "connection_established": False,
                        "error": f"deviceInfo HTTP {info.status_code}",
                        "search": None,
                    }

                device_label = self._parse_device_label(info.text)
                today = date.today()
                sample_size = min(5, self.MAX_PAGE_SIZE)
                body = self._build_search_json(today, today, 0, sample_size)
                response = await client.post(
                    self.SEARCH_PATH_JSON,
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )
                if response.status_code >= 400:
                    return {
                        "device_id": self.device_id,
                        "host": self.device.host,
                        "reachable": True,
                        "auth_ok": True,
                        "connection_established": False,
                        "error": f"AcsEvent HTTP {response.status_code}: {response.text[:120]}",
                        "search": None,
                        "device_label": device_label,
                    }

                try:
                    events, total_matches, num_matches = self._parse_acs_event_json(
                        response.text
                    )
                except DeviceProtocolError as exc:
                    return {
                        "device_id": self.device_id,
                        "host": self.device.host,
                        "reachable": True,
                        "auth_ok": True,
                        "connection_established": False,
                        "error": str(exc),
                        "search": None,
                        "device_label": device_label,
                    }

                total = total_matches if total_matches is not None else num_matches
                try:
                    events = await self._enrich_events_with_userinfo(client, events)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Probe: no se pudieron enriquecer nombres en %s: %s",
                        self.device_id,
                        exc,
                    )

                samples = [
                    {
                        "employee_id": e.employee_id,
                        "employee_name": (e.employee_name or e.employee_id).strip(),
                        "timestamp": e.timestamp.isoformat(timespec="seconds"),
                    }
                    for e in events[:sample_size]
                ]
                search_msg = (
                    f"Conexión establecida · {total} evento(s) hoy"
                    if total
                    else "Conexión establecida · sin eventos registrados hoy"
                )
                return {
                    "device_id": self.device_id,
                    "host": self.device.host,
                    "reachable": True,
                    "auth_ok": True,
                    "connection_established": True,
                    "error": None,
                    "device_label": device_label,
                    "search": {
                        "date": today.isoformat(),
                        "total_matches": total,
                        "sample_count": len(samples),
                        "samples": samples,
                        "message": search_msg,
                    },
                }
        except httpx.RequestError as exc:
            return {
                "device_id": self.device_id,
                "host": self.device.host,
                "reachable": False,
                "auth_ok": False,
                "connection_established": False,
                "error": str(exc),
                "search": None,
            }

    @staticmethod
    def _parse_device_label(raw: str) -> str | None:
        text = (raw or "").strip()
        if not text:
            return None
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                for key in ("deviceName", "model", "deviceID", "serialNumber"):
                    val = data.get(key)
                    if val:
                        return str(val).strip()
        except json.JSONDecodeError:
            pass
        for tag in ("deviceName", "model", "deviceID", "serialNumber"):
            open_t, close_t = f"<{tag}>", f"</{tag}>"
            if open_t in text and close_t in text:
                start = text.index(open_t) + len(open_t)
                end = text.index(close_t, start)
                value = text[start:end].strip()
                if value:
                    return value
        return None

    async def fetch_events(
        self,
        from_date: date,
        to_date: date,
        *,
        allow_empty: bool = False,
    ) -> list[RawAccessEvent]:
        all_events: list[RawAccessEvent] = []
        position = 0
        total_matches: int | None = None
        page_size = min(max(1, self.page_size), self.MAX_PAGE_SIZE)

        auth = httpx.DigestAuth(self.settings.hikvision_user, self.settings.hikvision_password)

        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                auth=auth,
                timeout=self.timeout,
                verify=False,
            ) as client:
                while True:
                    body = self._build_search_json(from_date, to_date, position, page_size)
                    try:
                        response = await client.post(
                            self.SEARCH_PATH_JSON,
                            content=body,
                            headers={
                                "Content-Type": "application/json",
                                "Accept": "application/json",
                            },
                        )
                    except httpx.RequestError as exc:
                        raise ConnectionErrorBiometric(
                            f"No se pudo conectar a {self.base_url} ({self.device_id}): {exc}"
                        ) from exc

                    if response.status_code in (401, 403):
                        raise AuthenticationErrorBiometric(
                            f"Credenciales inválidas en {self.device_id} ({self.device.host})"
                        )
                    if response.status_code >= 400:
                        raise DeviceProtocolError(
                            f"{self.device_id} ISAPI HTTP {response.status_code}: "
                            f"{response.text[:300]}"
                        )

                    page_events, total_matches, num_matches = self._parse_acs_event_json(
                        response.text
                    )
                    all_events.extend(page_events)

                    if num_matches == 0:
                        break
                    position += num_matches
                    if total_matches is not None and position >= total_matches:
                        break
                    if num_matches < page_size:
                        break

                all_events = await self._enrich_events_with_userinfo(client, all_events)
        except (ConnectionErrorBiometric, AuthenticationErrorBiometric, DeviceProtocolError):
            raise
        except Exception as exc:  # noqa: BLE001
            raise ConnectionErrorBiometric(
                f"Error inesperado ISAPI {self.device_id}: {exc}"
            ) from exc

        if not all_events and not allow_empty:
            raise EmptyResponseError(
                f"{self.device_id} no devolvió eventos entre {from_date} y {to_date}"
            )
        return all_events

    async def _enrich_events_with_userinfo(
        self,
        client: httpx.AsyncClient,
        events: list[RawAccessEvent],
    ) -> list[RawAccessEvent]:
        """Completa nombre (y depto si existe) vía UserInfo/Search del terminal."""
        missing_ids = sorted(
            {
                e.employee_id.strip()
                for e in events
                if e.employee_id.strip()
                and (not (e.employee_name or "").strip() or e.employee_name.strip() == e.employee_id.strip())
            }
        )
        if not missing_ids:
            # Aun así completar departamentos por nombre si faltan
            return [self._apply_department_fallback(e) for e in events]

        directory = await self._fetch_user_directory(client, missing_ids)
        enriched: list[RawAccessEvent] = []
        for event in events:
            emp = (event.employee_id or "").strip()
            info = directory.get(emp)
            name = (event.employee_name or "").strip()
            department = (event.department or "").strip()
            if info:
                if info.get("name"):
                    name = info["name"]
                if info.get("department"):
                    department = info["department"]
            if not name:
                name = emp
            updated = event.model_copy(
                update={
                    "employee_name": name,
                    "department": department,
                }
            )
            enriched.append(self._apply_department_fallback(updated))
        return enriched

    async def _fetch_user_directory(
        self,
        client: httpx.AsyncClient,
        employee_nos: list[str],
    ) -> dict[str, dict[str, str]]:
        """Busca usuarios por employeeNo (lotes de hasta 10; firmware maxResults=10)."""
        directory: dict[str, dict[str, str]] = {}
        batch_size = 10
        for i in range(0, len(employee_nos), batch_size):
            batch = employee_nos[i : i + batch_size]
            payload = {
                "UserInfoSearchCond": {
                    "searchID": f"u{i // batch_size}",
                    "searchResultPosition": 0,
                    "maxResults": batch_size,
                    "EmployeeNoList": [{"employeeNo": emp} for emp in batch],
                }
            }
            try:
                response = await client.post(
                    "/ISAPI/AccessControl/UserInfo/Search?format=json",
                    content=json.dumps(payload),
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )
            except httpx.RequestError as exc:
                logger.warning("UserInfo Search falló en %s: %s", self.device_id, exc)
                continue
            if response.status_code >= 400:
                logger.warning(
                    "UserInfo Search HTTP %s en %s: %s",
                    response.status_code,
                    self.device_id,
                    response.text[:160],
                )
                continue
            try:
                data = response.json()
            except json.JSONDecodeError:
                continue
            users = ((data.get("UserInfoSearch") or {}).get("UserInfo")) or []
            for user in users:
                if not isinstance(user, dict):
                    continue
                emp = str(user.get("employeeNo") or "").strip()
                if not emp:
                    continue
                name = str(user.get("name") or "").strip()
                department = str(
                    user.get("departmentName")
                    or user.get("deptName")
                    or user.get("department")
                    or user.get("orgName")
                    or ""
                ).strip()
                directory[emp] = {"name": name, "department": department}
        return directory

    @staticmethod
    def _apply_department_fallback(event: RawAccessEvent) -> RawAccessEvent:
        """Si el terminal no trae depto, intenta mapa por ID / nombre (export HikCentral)."""
        if (event.department or "").strip():
            return event
        dept = _department_lookup(event.employee_id, event.employee_name)
        if not dept:
            return event
        return event.model_copy(update={"department": dept})

    def _build_search_json(
        self,
        from_date: date,
        to_date: date,
        position: int,
        max_results: int,
    ) -> str:
        start = datetime.combine(from_date, datetime.min.time()).strftime("%Y-%m-%dT%H:%M:%S")
        end = datetime.combine(to_date, datetime.max.time().replace(microsecond=0)).strftime(
            "%Y-%m-%dT%H:%M:%S"
        )
        # searchID corto (firmware exige 1..20). Evitar UUID de 36 chars.
        search_id = f"{self.device_id[:8]}{position % 10000:04d}"[:20]
        payload = {
            "AcsEventCond": {
                "searchID": search_id,
                "searchResultPosition": position,
                "maxResults": min(max(1, max_results), self.MAX_PAGE_SIZE),
                "major": 0,
                "minor": 0,
                "startTime": start,
                "endTime": end,
            }
        }
        return json.dumps(payload)

    def _parse_acs_event_json(
        self, text: str
    ) -> tuple[list[RawAccessEvent], int | None, int]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise DeviceProtocolError(
                f"JSON ISAPI inválido ({self.device_id}): {exc}"
            ) from exc

        acs = data.get("AcsEvent") or data
        if not isinstance(acs, dict):
            raise DeviceProtocolError(f"Respuesta AcsEvent inesperada ({self.device_id})")

        total_matches = acs.get("totalMatches")
        num_matches = int(acs.get("numOfMatches") or 0)
        if isinstance(total_matches, str) and total_matches.isdigit():
            total_matches = int(total_matches)
        elif not isinstance(total_matches, int):
            total_matches = None

        events: list[RawAccessEvent] = []
        for item in acs.get("InfoList") or []:
            if not isinstance(item, dict):
                continue
            emp_id = str(item.get("employeeNoString") or item.get("employeeNo") or "").strip()
            raw_name = item.get("name")
            name = str(raw_name).strip() if raw_name else ""
            department = str(
                item.get("departmentName")
                or item.get("deptName")
                or item.get("department")
                or ""
            ).strip()
            time_str = item.get("time")
            if not time_str:
                continue
            ts = self._parse_hikvision_time(str(time_str))
            if ts is None:
                continue
            major = item.get("major")
            minor = item.get("minor")
            major_i = int(major) if isinstance(major, int) or str(major).isdigit() else None
            minor_i = int(minor) if isinstance(minor, int) or str(minor).isdigit() else None
            success = True if major_i is None else major_i == 5
            events.append(
                RawAccessEvent(
                    employee_id=emp_id,
                    employee_name=name,
                    department=department,
                    timestamp=ts,
                    device_id=self.device_id,
                    major=major_i,
                    minor=minor_i,
                    success=success,
                )
            )

        if num_matches == 0 and events:
            num_matches = len(events)
        return events, total_matches, num_matches

    @staticmethod
    def _parse_hikvision_time(value: str) -> datetime | None:
        cleaned = value.strip()
        for fmt in (
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                if "." in cleaned and "+" not in cleaned[10:] and "Z" not in cleaned:
                    base = cleaned.split(".", 1)[0]
                    return datetime.strptime(base, "%Y-%m-%dT%H:%M:%S")
                if cleaned.endswith("Z"):
                    cleaned_z = cleaned[:-1] + "+0000"
                    return datetime.strptime(
                        cleaned_z[:19] + cleaned_z[-5:], "%Y-%m-%dT%H:%M:%S%z"
                    ).replace(tzinfo=None)
                return datetime.strptime(cleaned[:19], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                continue
        logger.warning("No se pudo parsear timestamp Hikvision: %s", value)
        return None


class MultiDeviceHikvisionSource(AccessEventSource):
    """Consulta varios biométricos y fusiona eventos; mismas reglas de negocio después."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.connectors = [
            HikvisionConnector(
                settings,
                device_id=device.device_id,
                host=device.host,
                port=device.port,
            )
            for device in settings.parsed_hikvision_devices()
        ]

    async def fetch_events(self, from_date: date, to_date: date) -> list[RawAccessEvent]:
        async def _one(connector: HikvisionConnector) -> list[RawAccessEvent]:
            try:
                return await connector.fetch_events(from_date, to_date, allow_empty=True)
            except EmptyResponseError:
                return []

        results = await asyncio.gather(
            *[_one(c) for c in self.connectors],
            return_exceptions=True,
        )

        merged: list[RawAccessEvent] = []
        hard_errors: list[str] = []

        for connector, result in zip(self.connectors, results):
            if isinstance(result, Exception):
                msg = getattr(result, "message", None) or str(result)
                hard_errors.append(f"{connector.device_id}: {msg}")
                logger.warning("Fallo biométrico %s: %s", connector.device_id, msg)
                continue
            merged.extend(result)

        if not merged:
            if hard_errors:
                raise ConnectionErrorBiometric(
                    "Ningún biométrico devolvió eventos. " + " | ".join(hard_errors)
                )
            raise EmptyResponseError(
                f"Ningún biométrico devolvió eventos entre {from_date} y {to_date}"
            )
        return merged


async def probe_hikvision_devices(settings: Settings) -> list[dict]:
    connectors = [
        HikvisionConnector(
            settings,
            device_id=device.device_id,
            host=device.host,
            port=device.port,
        )
        for device in settings.parsed_hikvision_devices()
    ]
    return list(await asyncio.gather(*[c.probe() for c in connectors]))


def create_event_source(settings: Settings) -> AccessEventSource:
    source = (settings.source or "mock").strip().lower()
    if source == "hikvision":
        devices = settings.parsed_hikvision_devices()
        if len(devices) > 1:
            return MultiDeviceHikvisionSource(settings)
        device = devices[0]
        return HikvisionConnector(
            settings,
            device_id=device.device_id,
            host=device.host,
            port=device.port,
        )
    if source in {"hikcentral_pdf", "pdf", "json"}:
        path = Path(settings.mock_events_json or "").expanduser()
        if not path.is_file():
            raise FileNotFoundError(
                "SOURCE=hikcentral_pdf requiere MOCK_EVENTS_JSON con un JSON válido "
                f"(recibido: {settings.mock_events_json!r})"
            )
        return JsonFileEventSource(path, device_id=settings.device_id or "HIKCENTRAL-PDF")
    # mock: si hay JSON de HikCentral, úsalo; si no, demo de un día
    mock_path = Path(settings.mock_events_json or "").expanduser()
    if mock_path.is_file():
        return JsonFileEventSource(mock_path, device_id=settings.device_id or "HIKCENTRAL-PDF")
    return MockHikvisionConnector(device_id=settings.device_id)
