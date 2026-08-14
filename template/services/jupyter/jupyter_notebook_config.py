# Jupyter Lab configuration for H100 RealEval Template
c.ServerApp.ip = "0.0.0.0"
c.ServerApp.port = 8888
c.ServerApp.open_browser = False
c.ServerApp.allow_root = True
c.ServerApp.root_dir = "/workspace"
# Fail closed: require a strong token from the environment. The previous empty token
# ('' = no auth) on a 0.0.0.0 bind left the notebook server fully open.
import os as _os
_jupyter_token = _os.environ.get("JUPYTER_TOKEN")
if not _jupyter_token:
    raise RuntimeError("JUPYTER_TOKEN must be set to a strong value before launching Jupyter.")
c.ServerApp.token = _jupyter_token
c.ServerApp.password = ""
# Restrict CORS to an explicit origin (default: none) instead of the wildcard "*".
c.ServerApp.allow_origin = _os.environ.get("JUPYTER_ALLOW_ORIGIN", "")
c.ServerApp.allow_remote_access = True

# Increase buffer for large model files
c.ServerApp.max_body_size = 2 * 1024 * 1024 * 1024  # 2GB
c.ServerApp.max_buffer_size = 2 * 1024 * 1024 * 1024  # 2GB

# Kernel settings
c.KernelManager.shutdown_wait_time = 30.0
c.MappingKernelManager.cull_idle_timeout = 3600
c.MappingKernelManager.cull_interval = 300
c.MappingKernelManager.cull_connected = False

# Notebook settings
c.NotebookApp.allow_password_change = False
