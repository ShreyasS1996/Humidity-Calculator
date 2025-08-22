
import math
import streamlit as st

st.set_page_config(page_title="Humidity Calculator", page_icon="💧", layout="centered")

# ---------- Helper functions ----------
def saturation_vapor_pressure_kpa(t_c: float) -> float:
    """
    Buck (1981) equation for saturation vapor pressure over liquid water.
    T in °C, returns kPa.
    Valid for roughly -40°C to +50°C with good accuracy.
    """
    return 0.61121 * math.exp((18.678 - (t_c / 234.5)) * (t_c / (257.14 + t_c)))

def psychrometric_constant_kpa_per_c(t_wb_c: float, p_kpa: float) -> float:
    """
    Approximate psychrometric coefficient A*P for a well-ventilated sling psychrometer.
    A = 0.00066 * (1 + 0.00115 * T_wb)  [kPa/°C per kPa of pressure]
    gamma = A * P
    """
    A = 0.00066 * (1 + 0.00115 * t_wb_c)
    return A * p_kpa

def actual_vapor_pressure_kpa(t_db_c: float, t_wb_c: float, p_kpa: float) -> float:
    """
    Compute actual vapor pressure from DBT, WBT, pressure.
    e = e_ws(Twb) - gamma * (Tdb - Twb)
    Clamped to [0, e_s(Tdb)].
    """
    e_ws_wb = saturation_vapor_pressure_kpa(t_wb_c)
    gamma = psychrometric_constant_kpa_per_c(t_wb_c, p_kpa)
    e = e_ws_wb - gamma * (t_db_c - t_wb_c)
    # Clamp to physical limits
    e = max(0.0, e)
    e = min(e, saturation_vapor_pressure_kpa(t_db_c))
    return e

def humidity_ratio_kg_per_kg_dry_air(e_kpa: float, p_kpa: float) -> float:
    """
    Humidity ratio (omega) in kg water/kg dry air.
    """
    return 0.62198 * e_kpa / max(1e-9, (p_kpa - e_kpa))

def specific_humidity_kg_per_kg_moist_air(omega: float) -> float:
    """
    Specific humidity q = omega / (1 + omega)
    """
    return omega / (1.0 + omega)

def dew_point_from_vapor_pressure(e_kpa: float) -> float:
    """
    Invert the Buck equation via Newton iteration for dew point (°C) from vapor pressure (kPa).
    Provides a useful cross-check.
    """
    # Initial guess using a common approximation
    # Magnus-type inversion
    if e_kpa <= 0:
        return float("nan")
    ln_ratio = math.log(e_kpa / 0.61121)
    # Rough initial guess
    t = (257.14 * 18.678 - 257.14 * ln_ratio) / (ln_ratio + 18.678) - 5.0
    # Newton refine
    for _ in range(8):
        f = saturation_vapor_pressure_kpa(t) - e_kpa
        # derivative of Buck w.r.t temperature (numerical)
        dt = 0.01
        df = saturation_vapor_pressure_kpa(t + dt) - saturation_vapor_pressure_kpa(t - dt)
        df /= (2 * dt)
        if abs(df) < 1e-8:
            break
        t -= f / df
    return t

# ---------- UI ----------
st.title("💧 Humidity Calculator (DBT + WBT + Pressure)")
st.caption("Enter dry-bulb and wet-bulb temperatures and barometric pressure to compute relative and specific humidity.")

with st.sidebar:
    st.header("Inputs")
    t_db = st.slider("Dry-bulb temperature (°C)", min_value=-30.0, max_value=60.0, value=30.0, step=0.1)
    t_wb = st.slider("Wet-bulb temperature (°C)", min_value=-30.0, max_value=60.0, value=24.0, step=0.1)
    p_kpa = st.number_input("Barometric pressure (kPa)", min_value=60.0, max_value=110.0, value=101.325, step=0.1, help="Sea level ≈ 101.325 kPa.")

    st.markdown("---")
    st.write("**Notes**")
    st.write("- Wet-bulb should be ≤ dry-bulb under normal conditions.")
    st.write("- Pressure range covers typical elevations from high altitude to sea level.")

invalid = False
if t_wb > t_db:
    st.error("Wet-bulb temperature must be less than or equal to dry-bulb temperature.")
    invalid = True

if not invalid:
    e = actual_vapor_pressure_kpa(t_db, t_wb, p_kpa)
    es_db = saturation_vapor_pressure_kpa(t_db)
    rh = (e / es_db) * 100.0 if es_db > 0 else float("nan")
    omega = humidity_ratio_kg_per_kg_dry_air(e, p_kpa)
    q = specific_humidity_kg_per_kg_moist_air(omega)
    t_dp = dew_point_from_vapor_pressure(e)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Results")
        st.metric("Relative Humidity (RH)", f"{rh:0.1f} %")
        st.metric("Humidity Ratio (ω)", f"{omega:.5f} kg/kg dry air")
        st.metric("Specific Humidity (q)", f"{q:.5f} kg/kg moist air")
    with col2:
        st.subheader("Intermediate")
        st.write(f"Saturation pressure at DBT (eₛ)", f"{es_db:0.3f} kPa")
        st.write(f"Actual vapor pressure (e)", f"{e:0.3f} kPa")
        st.write(f"Dew point (approx.)", f"{t_dp:0.1f} °C")

    st.markdown("---")
    with st.expander("Equations & Method"):
        st.markdown(r"""
**Saturation vapor pressure (Buck 1981):**
\[
e_s(T) = 0.61121 \exp\!\left[\left(18.678 - \frac{T}{234.5}\right)\frac{T}{257.14 + T}\right] \quad \text{kPa}
\]

**Psychrometric relation (well-ventilated sling psychrometer):**
\[
e = e_s(T_{wb}) - \underbrace{0.00066\,(1+0.00115\,T_{wb})}_{A}\;P\,(T_{db}-T_{wb})
\]

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
st.caption("Tip: Save this app with your inputs as a permalink by using the Share menu in Streamlit Cloud.")
