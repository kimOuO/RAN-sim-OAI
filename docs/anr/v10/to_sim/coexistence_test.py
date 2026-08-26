#!/usr/bin/env python3
"""驗證「執行期編譯的 KPM」與「預編譯的 RC 模組」能否共存於同一個 pycrate GLOBAL。

背景:sim 端以 compile_text 在執行期把 e2ap + kpm + rc 合編;RIC 端給的
E2SM_RC_for_sim.py 是預編譯 runtime 模組且自帶一份 E2SM-COMMON-IEs。
兩份同名 COMMON 共存是否會讓 KPM 解不開 —— 本腳本用實測回答。

用法:改下面三個路徑,然後 python3 coexistence_test.py
判讀:三次 KPM 往返的位元組必須完全相同,且 RC Format 3 仍可編碼。
"""
import sys, os

ASN_DIR = "/home/mitlab/xapps/mobiflow-auditor/src/asn1/asn1"
ASN_FILES = ["e2ap_v2.asn1", "e2sm_v3.00.asn", "e2sm_kpm_v2.0.03.asn"]
RC_MODULE_DIR = "/home/mitlab/xapps/rc-probe/src"     # 內含 asn1/E2SM_RC.py
GEN_DIR = "/tmp/pycrate_gen"

from pycrate_asn1c.asnproc import compile_text, generate_modules, PycrateGenerator

txt = "".join(open(os.path.join(ASN_DIR, f), encoding="utf-8").read() + "\n"
              for f in ASN_FILES)
compile_text(txt)
os.makedirs(GEN_DIR, exist_ok=True)
generate_modules(PycrateGenerator, os.path.join(GEN_DIR, "RT.py"))
sys.path.insert(0, GEN_DIR)
import RT


def kpm_roundtrip(tag):
    M = RT.E2SM_KPM_IEs.E2SM_KPM_IndicationHeader
    M.set_val({'indicationHeader-formats':
               ('indicationHeader-Format1', {'colletStartTime': b'\x00\x00\x00\x01'})})
    enc = M.to_aper()
    M.from_aper(enc)
    print("  [%s] KPM 往返 OK, %d bytes" % (tag, len(enc)))
    return enc


e1 = kpm_roundtrip("匯入 RC 之前")

sys.path.insert(0, RC_MODULE_DIR)
from asn1.E2SM_RC import E2SM_RC_IEs, E2SM_COMMON_IEs
print("  已匯入 RC。其 E2SM-COMMON-IEs OID:", E2SM_COMMON_IEs._oid_)

e2 = kpm_roundtrip("匯入 RC 之後")

H = E2SM_RC_IEs.E2SM_RC_ControlHeader
H.set_val({'ric-controlHeader-formats': ('controlHeader-Format3', {
    'ue-Group-ID': 17,
    'ue-Group-Definition': {'ueGroupDefinitionIdentifier-LIST': [
        {'ranParameter-ID': 10001,
         'ranParameter-valueType': ('ranP-Choice-ElementTrue',
                                    {'ranParameter-value': ('valueOctS', b's19_c0')}),
         'logicalOR': 'false'}]},
    'ric-Style-Type': 3, 'ric-ControlAction-ID': 1})})
print("  RC Format 3 編碼 OK:", len(H.to_aper()), "bytes")

e3 = kpm_roundtrip("RC 編碼之後")
print("\n結果:KPM 三次位元組一致 =", e1 == e2 == e3)
sys.exit(0 if e1 == e2 == e3 else 1)
