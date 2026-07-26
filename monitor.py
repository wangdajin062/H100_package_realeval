import subprocess  
import time  
import os  
import sys  
import datetime  
  
def get_gpu():  
    try:  
        out = subprocess.check_output('nvidia-smi --query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,fan.speed --format=csv,noheader,nounits', shell=True, text=True, timeout=5)  
        gpus = []  
        for line in out.strip().splitlines():  
            if not line.strip(): continue  
            p = [x.strip() for x in line.split(',')]  
            if len(p)  
                mu = float(p[3].replace(' MiB','').replace(' MB',''))  
                mt = float(p[4].replace(' MiB','').replace(' MB',''))  
                gpus.append({'index':p[0],'name':p[1],'util':int(float(p[2].replace(' %',''))),'mem_used':round(mu/1024,1),'mem_total':round(mt/1024,1),'mem_pct':round(mu/mt*100,1) if mt else 0,'temp':int(p[5]),'power':float(p[6]),'fan':p[7]})  
        return gpus  
    except: return []  
  
def render(gpus):  
    os.system('cls' if os.name=='nt' else 'clear')  
    print('='*60)  
    print('  H100 GPU Monitor')  
    print('='*60)  
    for g in gpus:  
        util = g['util']  
        n = g['mem_pct']  
        uf = '#' * int(util/100*30)  
        mf = '#' * int(n/100*30)  
        print(f'  GPU {g[\"index\"]}  {g[\"name\"]}')  
