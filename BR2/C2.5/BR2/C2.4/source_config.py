#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
source_config.py – управление конфигурацией внешних источников.
"""

import os
import json
import sys
import logging
from pathlib import Path

CONFIG_DIR = Path("00_КАНОН/Внешние_источники")
CONFIG_FILE = CONFIG_DIR / "sources.json"
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/source_config.log")

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filena_me=DLOG_IFIRLE., mlkevdel=iloggrin(g.pINaFO,
r e  n          t       sfo=rmTatr=u'e, exist_ok=Tru%e)(
 a s c tiimef)s  n-o t% (ClOeNvFeIlGn_aFmIeL)E.sex i-st s%(():(
 )  :  ( 
   s)av e_ c:on fi g((D E
F A U LsT)_aCvON FIeG)_
  c : o n   f i  pgr((iDn tE
(F fA "UC rLseT)a_atCevdON  FdIeeGf)a_u
l t  cc o: no fn i g f  ia  tp g{rC(O(NiFDInG _tFIEL
E(}F" )fA
  " U C  erlLsseeT):a
_a tC e vd O N   print(f"Confi g  alFreaddyI eeeGf)a_xu
il s
tt  s      c  a icft r epoo[ ":u{ rClno"O]  N=fF=n Iu rGll:l
: l 
 :    l     
   :p ri nt ( "lR e p o s 
i t  :p ri nt ( "olRr ye  apl roe asd y
 ii nt  l i:spt. "r)i
    n  t   (   " o l Rrre tyuer n 
a p l   rcooen faisg[d"r epyo
si tiorii enst" ] .la pip:esnpdt(.n e"wr_)rie
p o ) 
   n    sta v e _(c  o n" foi gl( cRroren ftyiuge)r
   n   p
rai npt (lf " A drdceodo e{nu rfla}i"s)g
[
dd"erf  erpeymoo
vse_ire ptioo(ruiril) :e
n s  t c"on f]i g .=l lao adp_icpon:feigs()n
p d  t (i.fn c onef"iwgr _i)sr iNoen
ep:
  o    )   
    p rni n t ( "sCtao nv fei g_ (cn  oo tn"  ffoouin dg.l"() 
c R r o r e n   ftryeiutgeu)rr
n 
   n      ipn
irtaiial _npt (lf " A drdceodo e{nu rfla}i"s)g
[
dd"erf  erpeymoo
vse_ire ptioo(ruiril) :e
n s  t c"on f]i g .=l lao adp_icpon:feigs()n
p d  t (i.fn c onef"iwgr _i)sr iNoen
ep:
  o    )   
    p rnlen = len(config["repositories"])
    config["repositories"] = [r for r in config["repositories"] if r["url"] != url]
    if len(config["repositories"]) < initial_len:
        save_config(config)
        print(f"Removed {url}")
    else:
        print("URL not found.")

def list_repos():
    config = load_config()
    if config is None:
        print("Config not found.")
        return
    for i, repo in enumerate(config["repositories"], 1):
        print(f"{i}. {repo['url']} (branch: {repo.get('branch','main')})")

def interactive():
    while True:
        print("\nCommands: init, add, remove, list, quit")
        cmd = input("> ").strip().lower()
        if cmd == "init":
            init()
        elif cmd == "add":
            url = input("URL: ").strip()
            branch = input("Branch [main]: ").strip() or "main"
            min_stars = int(input("Min stars [1000]: ").strip() or "1000")
            print("Allowed licenses (comma-separated) [MIT,Apache-2.0,BSD-3-Clause]:")
            lic_input = input().strip()
            license_allow = [x.strip() for x in lic_input.split(",")] if lic_input else None
            add_repo(url, branch, min_stars, license_allow)
        elif cmd == "remove":
            url = input("URL: ").strip()
            remove_repo(url)
        elif cmd == "list":
            list_repos()
        elif cmd == "quit":
            break
        else:
            print("Unknown command.")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        interactive()
    elif sys.argv[1] == "init":
        init()
    elif sys.argv[1] == "add" and len(sys.argv) >= 3:
        add_repo(sys.argv[2])
    elif sys.argv[1] == "remove" and len(sys.argv) >= 3:
        remove_repo(sys.argv[2])
    elif sys.argv[1] == "list":
        list_repos()
    else:
        print("Usage: source_config.py [init|add <url>|remove <url>|list]")
