import streamlit as st
import time
import psutil
import pandas as pd
import numpy as np

# 尝试初始化 NVIDIA 驱动接口
try:
    import pynvml
    pynvml.nvmlInit()
    GPU_AVAILABLE = True
    device_count = pynvml.nvmlDeviceGetCount()
except Exception:
    GPU_AVAILABLE = False
    device_count = 0

st.set_page_config(page_title="RunPod 多维系统监控", layout="wide", page_icon="📊")

# 标题
st.title("📊 RunPod 实时多维系统监控看板")
st.markdown("---")

# 初始化历史数据缓存（用于画折线图）
if "history" not in st.session_state:
    st.session_state.history = {
        "cpu": [0.0] * 30,
        "ram": [0.0] * 30,
        "gpu_util": [0.0] * 30,
        "vram_util": [0.0] * 30,
    }

# 更新历史数据的函数
def update_history(cpu, ram, gpu, vram):
    st.session_state.history["cpu"].append(cpu)
    st.session_state.history["ram"].append(ram)
    st.session_state.history["gpu_util"].append(gpu)
    st.session_state.history["vram_util"].append(vram)
    # 只保留最近30秒的数据
    for key in st.session_state.history:
        st.session_state.history[key] = st.session_state.history[key][-30:]

# 占位符用于实时刷新
placeholder = st.empty()

# 实时循环刷新
while True:
    # 1. 采集 CPU 与 内存数据
    cpu_percent = psutil.cpu_percent()
    ram = psutil.virtual_memory()
    ram_percent = ram.percent
    
    # 2. 采集 GPU 数据
    gpu_name = "未检测到 NVIDIA 显卡 (模拟模式)"
    gpu_util = 0.0
    vram_used_gb = 0.0
    vram_total_gb = 0.0
    vram_percent = 0.0
    
    if GPU_AVAILABLE and device_count > 0:
        # 默认获取第一张显卡 (Device 0)
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        gpu_name = pynvml.nvmlDeviceGetName(handle)
        if isinstance(gpu_name, bytes):
            gpu_name = gpu_name.decode("utf-8")
            
        # 获取利用率
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        gpu_util = float(util.gpu)
        
        # 获取显存信息
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        vram_used_gb = mem.used / (1024 ** 3)
        vram_total_gb = mem.total / (1024 ** 3)
        vram_percent = (mem.used / mem.total) * 100
    else:
        # 模拟数据，防止无GPU环境报错
        gpu_name = "模拟 GPU 设备 (未检测到硬件)"
        gpu_util = np.random.uniform(10, 30)
        vram_used_gb = 4.2
        vram_total_gb = 24.0
        vram_percent = (vram_used_gb / vram_total_gb) * 100

    update_history(cpu_percent, ram_percent, gpu_util, vram_percent)
    
    # 3. 渲染看板界面
    with placeholder.container():
        # 第一排：设备基本信息
        st.info(f"🖥️ **当前 GPU 设备**: {gpu_name}")
        
        # 第二排：核心指标卡片
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("🔥 GPU 利用率", f"{gpu_util:.1f} %")
        with col2:
            st.metric("💾 显存占用 (VRAM)", f"{vram_used_gb:.2f} GB / {vram_total_gb:.1f} GB", f"{vram_percent:.1f}%")
        with col3:
            st.metric("⚙️ CPU 利用率", f"{cpu_percent:.1f} %")
        with col4:
            st.metric("🧠 系统内存 (RAM)", f"{ram.used / (1024**3):.1f} GB / {ram.total / (1024**3):.1f} GB", f"{ram_percent:.1f}%")
            
        st.markdown("### 📈 实时趋势折线图 (最近 30 秒)")
        
        # 第三排：历史折线图
        chart_col1, chart_col2 = st.columns(2)
        
        with chart_col1:
            st.write("**GPU 与 显存 趋势**")
            gpu_df = pd.DataFrame({
                "GPU 利用率 (%)": st.session_state.history["gpu_util"],
                "显存 占用率 (%)": st.session_state.history["vram_util"]
            })
            st.line_chart(gpu_df)
            
        with chart_col2:
            st.write("**CPU 与 内存 趋势**")
            cpu_df = pd.DataFrame({
                "CPU 利用率 (%)": st.session_state.history["cpu"],
                "内存 占用率 (%)": st.session_state.history["ram"]
            })
            st.line_chart(cpu_df)
            
        # 第四排：诊断建议
        st.markdown("### 🔍 运行诊断")
        if cpu_percent > 85 and gpu_util < 40:
            st.warning("⚠️ **诊断报告**：检测到 **CPU 瓶颈**。CPU 利用率极高，但 GPU 利用率较低。建议在训练脚本中增加 `num_workers` 或优化数据预处理流程。")
        elif vram_percent > 90:
            st.error("🚨 **诊断报告**：**显存接近爆满**！容易触发 OOM (Out Of Memory) 错误。建议适当调小 Batch Size。")
        else:
            st.success("✅ **诊断报告**：系统运行状态良好，未检测到明显硬件瓶颈。")
            
    time.sleep(1) # 每秒刷新一次