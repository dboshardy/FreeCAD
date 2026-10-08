# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: Python access to the fork feature flags (src/App/Fork/FeatureFlags.h).
"""Feature flags for inherited features with risk-register exposure.

A feature is enabled when it is compiled in (CMake option, default ON) and the
runtime parameter BaseApp/Preferences/Fork/Features/<key> is not set to false.
Keys: "NaviCube" (risk R1), "CAMAdaptive" (risk R3).
"""

PARAM_PATH = "User parameter:BaseApp/Preferences/Fork/Features"


def is_compiled(key):
    import FreeCAD

    # Builds without the fork configuration have no entry: treat as compiled in.
    return FreeCAD.ConfigGet("Fork.Feature." + key + ".Compiled") != "0"


def is_enabled(key):
    import FreeCAD

    return is_compiled(key) and FreeCAD.ParamGet(PARAM_PATH).GetBool(key, True)
