#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
chaos_monkey.py – модуль хаос-тестирования.
"""

import docker
import time
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("chaos_monkey")

DOCKER_CLIENT = docker.from_env()
RECOVERY_TIMEOUT = int(os.getenv("RECOVERY_TIMEOUT", "120"))

def _check_tool(container, tool):
    try:
        exec_result = container.exec_run(f"which {tool}", user="root")
        return exec_result.exit_code == 0
    except Exception:
        return False

def stop_container(container_name, timeout=30):
    """Останавливает контейнер, убивая его основной процесс."""
    try:
        container = DOCKER_CLIENT.containers.get(container_name)
    except docker.errors.NotFound:
        return {"error": f"Container {container_name} not found"}

    logger.info(f"Killing main process in container {container_name}")
    start = time.time()
    # Убиваем процесс uvicorn (или другой основной процесс)
    try:
        container.exec_run("pkill -9 uvicorn", privileged=True)
    except Exception as e:
        return {"error": f"Failed to kill process: {e}"}

    recovered = False
    while time.time() - start < RECOVERY_TIMEOUT:
        time.sleep(2)
        try:
            container.reload()
            if container.status == "running":
                recovered = True
                break
        except Exception:
            pass
    recovery_time = int((time.time() - start) * 1000)
    result = {
        "recovered": recovered,
        "recovery_time_ms": recovery_time,
        "error": None
    }
    logger.info(f"Container {container_name} recovered={recovered}")
    return result

def remove_container(container_name):
    try:
        container = DOCKER_CLIENT.containers.get(container_name)
    except docker.errors.NotFound:
        return {"error": f"Container {container_name} not found"}

    logger.info(f"Removing container {container_name}")
    container.remove(force=True)
    start = time.time()
    recovered = False
    while time.time(o)n n-ec tsitnargt  {<c oRnEtCaOiVnEeRrY__nTaImMeE}O UfTr:o
m   f a c ttotroyt-rnoeytt"-)r
n o e y tttr"y-:)
r 
 n   o   e   yn etttwtorr"ky -=: )D
OrC K
E Rn_ C L IoE N T .en e t wyonr kest.tgtewtt(o"rfra"cktyo r-y=-:n e)tD"
)O
r C   K 
 E   R nn_e C L IoE N T .en e t wyonr kest.tgtewtt(o"rfra"cktyo r-y=-:n e)tDe"
s=)1O)
:r 
C      K  t
r yE : 
  R    n n  _ ceo nCt aiLn eIroE  =N  DDODCOKDECRO_KCDLEICERNOT_.KcCoDnLtEaICiEneRrsN.gOeTt(_co.nKtcaCioneDr_nnLatmEaeIC)i
E ne Rr sN .geOxecTet(p_cto. ndKotcckaeCr.ieorrnoresD.Nrot_FnounnLda:t
m Ea eI C) i 
 E   nree tRurr ns N{ ".egrerOoxrec"Te:t (fp"_cCtoo.sn =nt1d)a:K
i o t n ctrcye:k
 a r e     C rco{n.tcaiineor e=o DnOCrKEtRr_nCLaIoEiNrTe.ncsoenD.traN_irnoentras_.Fgmente(ocuo}nntna inLerd_nnaamoe:)t
t   
 f meox cueEpnta dd o"ckee}r.Ie r
rCo)r
s .iN  o 
t F o uEnid :f
       n  n r errerteurrtne u{r"retnrer uo{rr"":r eft"Cnonrtaeirn euro {{rrc"o"n:tra ineefr_tn"amCen}o nnort tfaoeuinrdn" }e
u
ro   {{ rr ci"fo" nn:torat i ne_ecfhre_ctkn_"taomoCle(nc}oo nnntoarti tnfearo,e u"istnrredsns"- n}ge"
)u:

r o     {{   r r   cri"efto"u nrnn: t{"error": "stress-onrg anott in sit alnleed i_n coentcaifnherr"e}
_
 c   cmdt = kf"ns_t"rests-ang o--vm m{woorkCersl} e--(vmn-bytces 80% --timeout {dura}tioono_ sec}ns"n
  n  tlogogear.rintfo(if" Exetcuntinfg eianr {coont,aiene r_nua"mei}s: {tcmdn}"r)
 r   etrdy:
s n  s "  - n}ge"
)u:

r o     {{   r r   cri"efto"u nrnn: t{"error": "stress-onrg anott in sit alnleed i_n coentcaifnherr"e}
_
 c     container.exec_run(cmd, detach=True)
        time.sleep(duration_sec + 2)
    except Exception as e:
        return {"error": str(e)}
    return {"recovered": True, "duration_sec": duration_sec}

def network_latency(container_name, latency_ms=500, duration_sec=30):
    try:
        container = DOCKER_CLIENT.containers.get(container_name)
    except docker.errors.NotFound:
        return {"error": f"Container {container_name} not found"}

    if not _check_tool(container, "tc"):
        return {"error": "tc (iproute2) not installed in container"}

    add_cmd = f"tc qdisc add dev eth0 root netem delay {latency_ms}ms"
    try:
        container.exec_run(add_cmd, privileged=True)
    except Exception as e:
        return {"error": f"Failed to add delay: {e}"}

    time.sleep(duration_sec)

    del_cmd = "tc qdisc del dev eth0 root"
    try:
        container.exec_run(del_cmd, privileged=True)
    except Exception as e:
        return {"error": f"Failed to remove delay: {e}"}

    return {"recovered": True, "duration_sec": duration_sec}

def run_experiment(container_name, experiment_type, params=None):
    if params is None:
        params = {}
    if experiment_type == "container_stop":
        return stop_container(container_name, params.get("timeout", 30))
    elif experiment_type == "container_rm":
        return remove_container(container_name)
    elif experiment_type == "network_loss":
        return network_loss(container_name, params.get("duration_sec", 30))
    elif experiment_type == "cpu_stress":
        return cpu_stress(container_name, params.get("duration_sec", 30), params.get("cores", 1))
    elif experiment_type == "memory_stress":
        return memory_stress(container_name, params.get("duration_sec", 30), params.get("workers", 1))
    elif experiment_type == "network_latency":
        return network_latency(container_name, params.get("latency_ms", 500), params.get("duration_sec", 30))
    else:
        return {"error": f"Unknown experiment type: {experiment_type}"}
