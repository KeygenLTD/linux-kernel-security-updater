"""Real service and HTTP health checks."""
import ssl
import urllib.error
import urllib.request

from .core import LKSUError, run


def check_all(config):
    results = {}
    for service in config.get("services", []):
        results[f"service:{service}"] = run("systemctl", "is-active", "--quiet", service, check=False).returncode == 0
    context = ssl.create_default_context()
    for item in config.get("health_urls", []):
        url = item["url"] if isinstance(item, dict) else item
        expected = int(item.get("status", 200)) if isinstance(item, dict) else 200
        if not url.startswith(("http://", "https://")):
            raise LKSUError("Health URL must use HTTP or HTTPS")
        try:
            request = urllib.request.Request(url, method="GET", headers={"User-Agent": "LKSU/0.2"})
            with urllib.request.urlopen(request, timeout=10, context=context) as response:
                results[f"url:{url}"] = response.status == expected
        except (urllib.error.URLError, TimeoutError, ValueError):
            results[f"url:{url}"] = False
    return results
