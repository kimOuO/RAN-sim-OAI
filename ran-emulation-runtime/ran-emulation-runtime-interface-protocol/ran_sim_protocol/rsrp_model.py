"""Shared RSRP / SINR conversion utilities — single source of truth.

Why this module exists
----------------------
Before this module, Coverage heatmap (Physics) and RU realtime KPM (RANsim-RU)
each had their own RSRP formula:

  Coverage:  RSRP = 10*log10(path_gain) + gnb.power_dbm
  RU:        RSRP = path_gain_db + RU_TX_POWER_DBM(env=43) + RU_ANTENNA_GAIN_DBI(env=14)
                                - RU_SCENE_CALIBRATION_LOSS_DB(env=50)

Two problems with the RU version:
  (a) per-gNB power_dbm was completely ignored — RU always used the env constant
  (b) +14 dBi antenna gain was double-counted (Sionna PlanarArray already
      applies the antenna pattern inside path_gain), and the magic -50 dB
      calibration just happened to cancel out the double-count + add a
      conceptual "scene loss" — but the value was tuned only for TX=43 dBm.

When the user dropped power to 23 dBm, the Coverage heatmap shrank correctly
but RU's KPM showed no change (because it still used 43 internally), making
the two views diverge — a recipe for confused debugging.

This module **forces** every layer to call the same function, so any future
change to RSRP semantics propagates everywhere atomically.

Conventions
-----------
- `path_gain_linear` is what Sionna PathSolver / RadioMapSolver returns:
  a dimensionless ratio (Pr/Pt) that **already includes** the TX & RX antenna
  array patterns (gain + directivity). DO NOT add antenna_gain_dbi on top.
- `tx_power_dbm` is the per-cell transmit power (read from Cell.power_dbm
  on the RU side or scene_config gnb.power_dbm on the Physics side).
- `scene_loss_db` represents losses Sionna does NOT model (building
  penetration, body loss, shadowing, foliage). For the Brownstone outdoor
  scene this is ~36 dB (was 50 dB historically when antenna gain was
  double-counted; new default 36 = 50 - 14 keeps numerical equivalence
  at TX=43 dBm while removing the conceptual error).
- Sentinel value `-200.0 dBm` represents "no signal at all" (path_gain<=0).
"""
from __future__ import annotations

import math

# Default scene loss for Brownstone-like urban simulations.
# Tuned so that at TX=43 dBm, this module produces RSRP equivalent to the
# legacy RU pipeline (which used env=43 + 14 gain - 50 calibration = 7 dBm
# net adder, equivalent to using 43 - 36 = 7 dBm net with no double-counted
# gain). When you change to a more realistic scene with full building/body
# loss already modeled, drop this value (e.g. 10 dB or 0 dB).
DEFAULT_SCENE_LOSS_DB: float = 36.0

# Sentinel returned when path_gain is non-positive (no LoS, full block, etc.).
# Below the 3GPP RSRP min of -156 dBm, picked so downstream A3 / KPM filters
# obviously drop it.
NO_SIGNAL_DBM: float = -200.0


def compute_rsrp_dbm(
    path_gain_linear: float,
    *,
    tx_power_dbm: float,
    scene_loss_db: float = DEFAULT_SCENE_LOSS_DB,
) -> float:
    """Convert Sionna path_gain → RSRP (dBm), the ONE canonical formula.

    RSRP_dBm = TX_power_dBm + 10*log10(path_gain_linear) - scene_loss_db

    Note that path_gain_linear is assumed to already include the antenna
    pattern (Sionna's PlanarArray bakes the antenna response into the
    channel coefficients), so antenna_gain_dbi is NOT added here. If your
    Sionna setup uses an isotropic radiator (`pattern="iso"`) then the
    caller may need to add gain externally before calling this.

    Args:
        path_gain_linear: Pr/Pt ratio from Sionna PathSolver / RadioMapSolver.
            Must be > 0. Returns NO_SIGNAL_DBM if not.
        tx_power_dbm: Cell/gNB transmit power. On RU side this comes from
            Cell.power_dbm; on Physics side from scene_config gnb.power_dbm.
        scene_loss_db: Additional propagation loss not modeled by Sionna.
            Defaults to DEFAULT_SCENE_LOSS_DB (36 dB for Brownstone scene).
            Pass 0 if the underlying scene is fully modeled.

    Returns:
        RSRP in dBm, or NO_SIGNAL_DBM if path_gain_linear <= 0.
    """
    if path_gain_linear is None or path_gain_linear <= 0:
        return NO_SIGNAL_DBM
    path_gain_db = 10.0 * math.log10(float(path_gain_linear))
    return float(tx_power_dbm) + path_gain_db - float(scene_loss_db)
