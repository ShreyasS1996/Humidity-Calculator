import math
import streamlit as st

st.set_page_config(page_title="Humidity Calculator", page_icon="💧", layout="centered")

# ---------- Unit conversion constants ----------
MMHG_PER_KPA = 7.50061683        # 1 kPa = 7.50061683 mmHg
KPA_PER_MMHG = 1.0 / MMHG_PER_KPA # 0.133322368 kPa per mmHg

# ---------- Helper functions (work in kPa internally) ----------
def saturation_vapor_pressure_kpa(t_c: float) -> float:
    """Buck (1981) equation for saturation vapor pressure over liquid water. T in °C, returns kPa."""
    return 0.61121 * math.exp((18.678 - (t_c / 234.5)) * (t_c / (257.14 + t_c)))

def psychrometric_constant_kpa_per_c(t_wb_c: float, p_kpa: float) -> float:
    """Psychrometric coefficient gamma = A * P, where A = 0.00066 * (1 + 0.00115 * T_wb)."""
    A = 0.00066 * (1 + 0.00115 * t_wb_c)
    return A * p_kpa

def actual_vapor_pressure_kpa(t_db_c: float, t_wb_c: float, p_kpa: float) -> float:
    """e = e_ws(Twb) - gamma * (Tdb - Twb), clamped to [0, e_s(Tdb)]."""
    e_ws_wb = saturation_vapor_pressure_kpa(t_wb_c)
    gamma = psychrometric_constant_kpa_per_c(t_wb_c, p_kpa)
    e = e_ws_wb - gamma * (t_db_c - t_wb_c)
    e = max(0.0, e)
    e = min(e, saturation_vapor_pressure_kpa(t_db_c))
    return e

def humidity_ratio_kg_per_kg_dry_air(e_kpa: float, p_kpa: float) -> float:
    """Humidity ratio (omega) in kg water/kg dry air."""
    return 0.62198 * e_kpa / max(1e-9, (p_kpa - e_kpa))

def specific_humidity_kg_per_kg_moist_air(omega: float) -> float:
    """Specific humidity q = omega / (1 + omega)."""
    return omega / (1.0 + omega)

def dew_point_from_vapor_pressure(e_kpa: float) -> float:
    """Invert Buck via Newton iteration for dew point (°C) given vapor pressure (kPa)."""
    if e_kpa <= 0:
        return float("nan")
    ln_ratio = math.log(e_kpa / 0.61121)
    t = (257.14 * 18.678 - 257.14 * ln_ratio) / (ln_ratio + 18.678) - 5.0
    for _ in range(8):
        f = saturation_vapor_pressure_kpa(t) - e_kpa
        dt = 0.01
        df = saturation_vapor_pressure_kpa(t + dt) - saturation_vapor_pressure_kpa(t - dt)
        df /= (2 * dt)
        if abs(df) < 1e-8:
            break
        t -= f / df
    return t

# ---------- Small helpers for UI display ----------
def to_display_pressure(p_kpa: float, unit: str) -> float:
    return p_kpa * MMHG_PER_KPA if unit == "mmHg" else p_kpa

def fmt_pressure(p_kpa: float, unit: str) -> str:
    return f"{p_kpa*MMHG_PER_KPA:0.1f} mmHg" if unit == "mmHg" else f"{p_kpa:0.3f} kPa"

# ---------- UI ----------
st.title("💧 Humidity Calculator (DBT + WBT + Pressure)")
st.caption("Enter dry-bulb and wet-bulb temperatures and barometric pressure to compute relative and specific humidity.")

with st.sidebar:
    st.header("Inputs")

    # Unit toggle
    unit = st.radio("Pressure unit", ["mmHg", "kPa"], index=0, horizontal=True)

    t_db = st.slider("Dry-bulb temperature (°C)", min_value=-30.0, max_value=60.0, value=30.0, step=0.1)
    t_wb = st.slider("Wet-bulb temperature (°C)", min_value=-30.0, max_value=60.0, value=24.0, step=0.1)

    # Pressure input based on selected unit, convert to kPa for internal calcs
    if unit == "mmHg":
        p_in = st.number_input(
            "Barometric pressure (mmHg)",
            min_value=450.0, max_value=850.0, value=760.0, step=0.5,
            help="Sea level ≈ 760 mmHg (≈ 101.3 kPa). 1 kPa = 7.5006 mmHg."
        )
        p_kpa = p_in * KPA_PER_MMHG
    else:
        p_in = st.number_input(
            "Barometric pressure (kPa)",
            min_value=60.0, max_value=110.0, value=101.325, step=0.1,
            help="Sea level ≈ 101.325 kPa (≈ 760 mmHg). 1 mmHg = 0.133322 kPa."
        )
        p_kpa = p_in  # already kPa

    st.markdown("---")
    st.write("**Notes**")
    st.write("- Wet-bulb should be ≤ dry-bulb under normal conditions.")
    st.write("- Pressure range covers typical elevations from high altitude to sea level.")

invalid = False
if t_wb > t_db:
    st.error("Wet-bulb temperature must be less than or equal to dry-bulb temperature.")
    invalid = True

if not invalid:
    # Core psychrometric calculations (kPa internally)
    e_kpa = actual_vapor_pressure_kpa(t_db, t_wb, p_kpa)
    es_db_kpa = saturation_vapor_pressure_kpa(t_db)
    rh = (e_kpa / es_db_kpa) * 100.0 if es_db_kpa > 0 else float("nan")
    omega = humidity_ratio_kg_per_kg_dry_air(e_kpa, p_kpa)
    q = specific_humidity_kg_per_kg_moist_air(omega)
    t_dp = dew_point_from_vapor_pressure(e_kpa)

    # Convert pressures for display according to selected unit
    e_disp = to_display_pressure(e_kpa, unit)
    es_db_disp = to_display_pressure(es_db_kpa, unit)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Results")
        st.metric("Relative Humidity (RH)", f"{rh:0.1f} %")
        st.metric("Humidity Ratio (ω)", f"{omega:.5f} kg/kg dry air")
        st.metric("Specific Humidity (q)", f"{q:.5f} kg/kg moist air")
    with col2:
        st.subheader(f"Intermediate (pressures in {unit})")
        st.write("Saturation pressure at DBT (eₛ)", f"{es_db_disp:0.1f} {unit}")
        st.write("Actual vapor pressure (e)", f"{e_disp:0.1f} {unit}")
        st.write("Dew point (approx.)", f"{t_dp:0.1f} °C")

    st.markdown("---")
    with st.expander("Equations & Method"):
        st.markdown(r"""
**Units & Conversions:**
- Calculations use kPa internally for standard psychrometric formulas; inputs/outputs can be displayed in kPa or mmHg.
- 1 kPa = 7.50062 mmHg, 1 mmHg = 0.133322 kPa.

**Saturation vapor pressure (Buck 1981):**
\[
e_s(T) = 0.61121 \exp\!\left[\left(18.678 - \frac{T}{234.5}\right)\frac{T}{257.14 + T}\right] \quad [\text{kPa}]
\]

**Psychrometric relation (well-ventilated sling psychrometer):**
\[
e = e_s(T_{wb}) - \underbrace{0.00066\,(1+0.00115\,T_{wb})}_{A}\;P\,(T_{db}-T_{wb})
\]
(where \(P\) is total pressure in kPa for computation; the UI displays your selected unit)

**Relative Humidity:**
\[
RH = \frac{e}{e_s(T_{db})}\times 100\%
\]

**Humidity Ratio (mass basis):**
\[
\omega = 0.62198 \frac{e}{P-e} \quad \left[\frac{\text{kg water}}{\text{kg dry air}}\right]
\]

**Specific Humidity (moist-air basis):**
\[
q = \frac{\omega}{1+\omega}
\]
""")

st.markdown("---")
st.caption("Tip: Use the unit toggle to enter and view pressure in kPa or mmHg. All computations use kPa internally for accuracy.")
