# labs/metrics.py
import docker, json
client = docker.from_env()

def container_metrics(container_name):
    c = client.containers.get(container_name)
    # use docker API stats (non-blocking single snapshot)
    stats = c.stats(stream=False)
    # stats is a dict-like
    mem_usage = stats['memory_stats'].get('usage', 0)
    mem_limit = stats['memory_stats'].get('limit', 1)
    mem_pct = round((mem_usage / mem_limit) * 100, 2)
    return {"mem_usage": mem_usage, "mem_limit": mem_limit, "mem_pct": mem_pct}
