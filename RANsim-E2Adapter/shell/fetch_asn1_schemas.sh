#!/usr/bin/env bash
# Fetch O-RAN ASN.1 schemas from FlexRIC repo.
# 對應 P2.7b — RIC team 已確認 sim 走 standard schema (Path A)。
#
# 使用：在 RANsim-E2Adapter/ 根目錄跑（會把檔案放進 ./asn1/）
set -euo pipefail

cd "$(dirname "$0")/.."
ASN1_DIR="$(pwd)/asn1"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "${TMP_DIR}"' EXIT

echo "[fetch] cloning FlexRIC into ${TMP_DIR}"
git clone --depth 1 https://gitlab.eurecom.fr/mosaic5g/flexric.git "${TMP_DIR}"

# (src_path_in_flexric, dest_filename)
declare -A SCHEMAS=(
  ["src/lib/e2ap/v2_03/ie/e2ap_v2_03.asn"]="e2ap_v2.asn1"
  ["src/sm/kpm_sm/kpm_sm_v02.03/ie/e2sm_kpm_v02.03_standard.asn1"]="e2sm_kpm_v2.0.03.asn"
  ["src/sm/rc_sm/ie/e2sm_rc_v1_03_standard.asn"]="e2sm_rc_v01.03.asn"
)

mkdir -p "${ASN1_DIR}"
for src in "${!SCHEMAS[@]}"; do
  dest="${SCHEMAS[$src]}"
  src_full="${TMP_DIR}/${src}"
  if [[ ! -f "${src_full}" ]]; then
    echo "[fetch] WARN: ${src} not found in FlexRIC tree" >&2
    continue
  fi
  cp "${src_full}" "${ASN1_DIR}/${dest}"
  echo "[fetch] copied ${dest} ← ${src}"
done

echo "[fetch] done. files in ${ASN1_DIR}:"
ls -la "${ASN1_DIR}"
