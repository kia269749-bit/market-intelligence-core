#!/usr/bin/env python3
from __future__ import annotations
import argparse, subprocess, sys, time

def main():
    p=argparse.ArgumentParser(description="Lightweight live research signal runner.")
    p.add_argument("--project60-file",default="")
    p.add_argument("--interval",type=int,default=60)
    p.add_argument("--cycles",type=int,default=0)
    p.add_argument("--fomo-chain",default="solana")
    p.add_argument("--fomo-limit",type=int,default=5)
    p.add_argument("--fomo-fills-file",default="")
    p.add_argument("--fomo-leader-scores",default="")
    a=p.parse_args()
    if a.interval<30: raise SystemExit("interval must be >= 30s")
    n=0
    while True:
        cmd=[sys.executable,"-m","mi_core.cli","live-all","--interval","30","--cycles","1","--fomo-chain",a.fomo_chain,"--fomo-limit",str(a.fomo_limit)]
        if a.project60_file: cmd += ["--project60-file",a.project60_file]
        if a.fomo_fills_file: cmd += ["--fomo-fills-file",a.fomo_fills_file]
        if a.fomo_leader_scores: cmd += ["--fomo-leader-scores",a.fomo_leader_scores]
        subprocess.run(cmd,check=False)
        n+=1
        if a.cycles and n>=a.cycles: break
        time.sleep(a.interval)

if __name__=="__main__": main()
