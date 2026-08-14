import os
c.ServerApp.ip = '0.0.0.0'
c.ServerApp.port = 8888
c.ServerApp.allow_root = True
c.ServerApp.open_browser = False
# Fail closed: require a strong token from the environment rather than shipping the
# well-known default "realeval" (Jupyter binds 0.0.0.0, so a default token = open shell).
_jupyter_token = os.environ.get("JUPYTER_TOKEN")
if not _jupyter_token:
    raise RuntimeError("JUPYTER_TOKEN must be set to a strong value before launching Jupyter "
                       "(no weak default token is provided).")
c.ServerApp.token = _jupyter_token
c.ServerApp.password = ''
c.ServerApp.notebook_dir = '/workspace'
c.ServerApp.allow_origin = os.environ.get("JUPYTER_ALLOW_ORIGIN", "")
