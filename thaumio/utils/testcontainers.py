import logging
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_container_ready

logger = logging.getLogger("TestcontainersThaumio")

class ThaumioContainer(DockerContainer):
    """
    Testcontainers wrapper to spin up a Thaumio simulation engine container in Python tests.
    
    Example:
        with ThaumioContainer(image="thaumio:latest") as thaumio:
            api_url = thaumio.get_api_url()
            # Query the dynamic topology endpoint
            response = requests.get(f"{api_url}/api/topology/status")
            print(response.json())
    """
    def __init__(self, image: str = "thaumio/thaumio:latest", port: int = 8081, config_path: str = None, **kwargs):
        super().__init__(image=image, **kwargs)
        self.port = port
        self.with_exposed_ports(self.port)
        
        # If a custom configuration file is provided, map it into the container's standard configuration path
        if config_path:
            self.with_volume_mapping(config_path, "/app/config/topology_config.json")

    def get_api_url(self) -> str:
        """Returns the HTTP API base URL to query the control plane."""
        host = self.get_container_host_ip()
        port = self.get_exposed_port(self.port)
        return f"http://{host}:{port}"

    @wait_container_ready(ValueError)
    def _wait_ready(self):
        """Custom check to wait until the FastAPI REST API is fully responsive."""
        import urllib.request
        import json
        url = f"{self.get_api_url()}/api/topology/status"
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return True
        except Exception:
            raise ValueError("Thaumio API Server not ready yet.")

    def start(self):
        super().start()
        self._wait_ready()
        logger.info(f"Thaumio container started. Control plane available at: {self.get_api_url()}")
        return self
