"""Auto-detect mobile vs desktop layout for Streamlit UI."""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

MOBILE_BREAKPOINT = 768


def _ua_hints_mobile() -> bool:
    """First-paint hint from User-Agent before viewport sync runs."""
    try:
        headers = st.context.headers  # type: ignore[attr-defined]
        ua = (headers.get("User-Agent") or headers.get("user-agent") or "").lower()
    except Exception:
        ua = ""
    if "iphone" in ua or "ipod" in ua:
        return True
    if "android" in ua and "mobile" in ua:
        return True
    return False


def _query_param_vw() -> str | None:
    raw = st.query_params.get("vw")
    if isinstance(raw, list):
        return raw[0] if raw else None
    return raw


def ensure_viewport_detected(*, breakpoint: int = MOBILE_BREAKPOINT) -> None:
    """
    Inject a tiny browser script that syncs ?vw=m|d to actual viewport width.
    One lightweight redirect may occur on first load if UA guess differs from width.
    """
    components.html(
        f"""
<script>
(function() {{
  const bp = {breakpoint};
  const root = window.parent.document;
  const w = window.parent.innerWidth || window.innerWidth;
  const mobile = w < bp;
  const want = mobile ? "m" : "d";
  root.body.setAttribute("data-crm-layout", mobile ? "mobile" : "desktop");
  const url = new URL(window.parent.location.href);
  if (url.searchParams.get("vw") !== want) {{
    url.searchParams.set("vw", want);
    window.parent.location.replace(url.toString());
  }}
}})();
</script>
        """,
        height=0,
    )


def is_mobile_ui(*, breakpoint: int = MOBILE_BREAKPOINT) -> bool:
    """
    True when the client should use phone-first card layouts.

    Uses synced viewport query param (?vw=m|d), then session cache, then UA hint.
    Optional: streamlit-js-eval if installed for width without URL sync.
    """
    try:
        from streamlit_js_eval import streamlit_js_eval

        raw = streamlit_js_eval(js_expressions="window.innerWidth", key="crm_viewport_width")
        if raw is not None:
            width = int(float(raw))
            mobile = width < breakpoint
            st.session_state["_crm_device_mobile"] = mobile
            st.session_state["_crm_viewport_width"] = width
            return mobile
    except Exception:
        pass

    vw = _query_param_vw()
    if vw == "m":
        st.session_state["_crm_device_mobile"] = True
        return True
    if vw == "d":
        st.session_state["_crm_device_mobile"] = False
        return False

    if "_crm_device_mobile" in st.session_state:
        return bool(st.session_state["_crm_device_mobile"])

    mobile = _ua_hints_mobile()
    st.session_state["_crm_device_mobile"] = mobile
    return mobile


def device_layout_label(*, mobile: bool | None = None) -> str:
    if mobile is None:
        mobile = bool(st.session_state.get("_crm_device_mobile", False))
    return "Mobile" if mobile else "Desktop"
