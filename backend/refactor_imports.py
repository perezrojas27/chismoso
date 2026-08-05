import os

REPLACEMENTS = {
    "from app.config": "from shared.config",
    "import app.config": "import shared.config",
    "from app.security": "from shared.security",
    "from app.models": "from shared.models",
    "from app.services.exceptions": "from shared.services.exceptions",
    "from app.services.name_format": "from shared.services.name_format",
    "from app.services.event_cleaner": "from shared.services.event_cleaner",
    
    "from app.edge": "from edge_app.edge",
    "from app.api.routes_edge": "from edge_app.api.routes_edge",
    "from app.api.routes_devices": "from edge_app.api.routes_devices",
    "from app.services.hikvision_connector": "from edge_app.services.hikvision_connector",
    "from app.services.device_discovery": "from edge_app.services.device_discovery",
    "from app.services.device_registry": "from edge_app.services.device_registry",
    "from app.services.hikcentral_pdf_loader": "from edge_app.services.hikcentral_pdf_loader",
    
    "from app.api.routes_reports": "from cloud_app.api.routes_reports",
    "from app.api.routes_cloud_mock": "from cloud_app.api.routes_cloud_mock",
    "from app.api.routes_exceptions": "from cloud_app.api.routes_exceptions",
    "from app.services.report_generator": "from cloud_app.services.report_generator",
    "from app.services.pdf_exporter": "from cloud_app.services.pdf_exporter",
    "from app.services.cafeteria_exceptions": "from cloud_app.services.cafeteria_exceptions",
}

for root, _, files in os.walk("."):
    for file in files:
        if file.endswith(".py") and file != "refactor_imports.py":
            path = os.path.join(root, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
                
            original = content
            for old, new in REPLACEMENTS.items():
                content = content.replace(old, new)
            
            # Special case for routes_health
            if "edge_app" in path:
                content = content.replace("from app.api.routes_health", "from edge_app.api.routes_health")
            elif "cloud_app" in path:
                content = content.replace("from app.api.routes_health", "from cloud_app.api.routes_health")

            if content != original:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"Updated {path}")
