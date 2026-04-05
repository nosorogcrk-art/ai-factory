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
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛ?? / s o u rjcseo_nc.oduumupm(ucpomn(fuicgp,om nf(,f uiincdgepn,to=m2 ,n fe(n,sfu ruei_iansccdigi=eFpanl,steo)=
m 2   , nl ofgeg(inn,gs.fiun frou(e"iC_oinafnisgcurcadtiigoin= esFapvaendl.,"s)t
e
od)e=f
 mi n2i t ( ),: 
n l   o fCgOeNgF(IiGn_nD,IgRs..mfkiduinr (fpraorue(net"si=CT_rouien,a fenxiissgtc_uork=cTardutei)i
g o i n =i fe snFoatpvaendl .C,O"NsF)ItG
_eF
IoLdE).ee=xfi
s tmsi( )n:2
i 
   t      f o r  fr eop or  i nf rc oenofpi gor[  "i rnefp orsci tooenrofipie sg"o]r:[
   " i  r ne fp   o risfc ire pto[oo"eunrrlo"f]i p=i= eur l:s
g "  o  ] r  : [ 
    p r" iin   tr( "n Ree pf o      print(f"Removed {ur l} " ) 
  p r  i   neeltilf( scfmed" :=R=
 e" amd do" :v
  e   d       {   u p r ru rill n=} ti n(p"u"t (U")URR LL:
  " )n. spt rri pi netl(sfe":R
e m oot  vf oeu ndd . " ){
 
udperf list_repos():
    cron fiilgn }=t  l(o"a"d _Uc)oRn fLi
g ( )n
  p   r  iif  nceotnlf(isgf ei"s: RN
oen em: 
o o t     v f   operiun tn(d"dC o.n f"i g) {n
o t
 ufdopuenrdf. "l)is
t _ r e  p o s (r)e:t
u r n 
  c r o nf ofri iil,g nr e}p=ot  i nl (eon"uam"edr a_tUec()cooRnn ffiLgi[
"gr e(p o)sni
t o rpi e s "r] ,  i1i)f: 
  n c e o t n l fp(riisngt(ff "e{ii"}s.:  {RrNe
pooe[n'u relm':] }
 o( ob rta n c h :  v{ rfe p o .ogpeetr(i'ubnr atnnc(hd'",d'Cm aoi.nn' )f}")i" )g
)
 d{enf
 oi ntt
e ruafcdtoipvuee(n)r:df
.   " l )wihsi
lte  _T rru ee: 
  p   o   s   ( rp)rei:ntt
(u" \rn Cno m
m a ncd sr :o  innfi to,f raid di,i lre,mgo vner,  el}ips=to,t   qiu intl" )(
e o n "  u a m"   " i  r ne fp   o risfc i()
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
