# H100 RealEval Template — CUDA 12.4 + PyTorch + Multi-Service
# Base: nvidia/cuda 12.4.1 DEVEL with Ubuntu 22.04.
# devel (not runtime) so nvcc is present — flash-attn compiles from source below
# (--no-build-isolation); the runtime image has no nvcc and the build fails.
FROM nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Asia/Shanghai \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# ─── System packages ───
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget git git-lfs build-essential \
    openssh-server \
    libsndfile1 libsndfile1-dev \
    python3.11 python3.11-dev python3.11-venv python3-pip \
    htop nvtop tmux vim nano jq net-tools \
    && ln -sf /usr/bin/python3.11 /usr/bin/python \
    && ln -sf /usr/bin/python3.11 /usr/bin/python3 \
    && rm -rf /var/lib/apt/lists/*

# ─── SSH setup ───
# Key-only root login by default. RunPod (and most cloud GPU hosts) inject the
# user's SSH public key at launch, so no password is needed — and baking one in
# ('root:realeval') gave anyone who could reach port 22 instant root over all of
# /workspace (data, models, S3 creds). Password auth stays DISABLED in the image.
# To enable it for a private deployment, do it at RUNTIME from a secret, e.g. in
# the entrypoint:  [ -n "$ROOT_PASSWORD" ] && echo "root:$ROOT_PASSWORD" | chpasswd
#                  && sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication yes/' /etc/ssh/sshd_config
RUN mkdir -p /var/run/sshd \
    && sed -i 's/#\?PermitRootLogin .*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config \
    && sed -i 's/#\?PasswordAuthentication .*/PasswordAuthentication no/' /etc/ssh/sshd_config

# ─── Working directory ───
WORKDIR /workspace

# ─── Python environment ───
RUN python -m pip install --upgrade pip setuptools wheel

# PyTorch 2.5.1 with CUDA 12.4
RUN pip install --no-cache-dir \
    torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 \
    --index-url https://download.pytorch.org/whl/cu124

# Core ML/Audio dependencies
RUN pip install --no-cache-dir \
    numpy>=1.24 \
    scipy>=1.10 \
    scikit-learn>=1.3 \
    pandas>=2.0 \
    matplotlib>=3.7 \
    seaborn>=0.12 \
    transformers>=4.36 \
    datasets>=2.14 \
    accelerate>=0.25 \
    peft>=0.7 \
    bitsandbytes>=0.43 \
    "flash-attn>=2.0" --no-build-isolation \
    pyyaml>=6.0 \
    tqdm>=4.66 \
    librosa>=0.10 \
    soundfile>=0.12 \
    jiwer>=3.0 \
    evaluate>=0.4 \
    openai-whisper

# Jupyter + VSCode server
RUN pip install --no-cache-dir \
    jupyterlab>=4.0 \
    jupyterlab-code-formatter \
    ipywidgets \
    ipykernel

# code-server (VSCode in browser)
RUN curl -fsSL https://code-server.dev/install.sh | sh

# FastAPI + Uvicorn
RUN pip install --no-cache-dir \
    fastapi>=0.110 \
    "uvicorn[standard]>=0.27" \
    pydantic>=2.0 \
    python-multipart

# ─── Model cache directories ───
RUN mkdir -p /workspace/models /workspace/hf_cache /workspace/outputs /workspace/logs \
    && mkdir -p /workspace/.ollama /workspace/.cache

ENV HF_HOME=/workspace/hf_cache \
    TRANSFORMERS_CACHE=/workspace/hf_cache \
    TORCH_HOME=/workspace/hf_cache/torch \
    REALEVAL_MODELS_ROOT=/workspace/models \
    REALEVAL_DATA_ROOT=/workspace/data \
    REALEVAL_OUTPUT_ROOT=/workspace/outputs \
    OLLAMA_MODELS=/workspace/.ollama

# ─── Copy configs & scripts ───
COPY services/jupyter/jupyter_notebook_config.py /etc/jupyter/
COPY services/vscode/config.yaml /root/.config/code-server/
COPY services/api/ /workspace/api/
COPY scripts/ /scripts/

RUN chmod +x /scripts/*.sh

# ─── Expose ports ───
EXPOSE 22 8888 3000 8000 11434

# ─── Health check ───
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD /scripts/healthcheck.sh

ENTRYPOINT ["/scripts/entrypoint.sh"]
