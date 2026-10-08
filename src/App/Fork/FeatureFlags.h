// SPDX-License-Identifier: LGPL-2.1-or-later
// FORK: feature flags for inherited features with risk-register exposure
// (design doc §12.4 item 4, docs/inherited-conflicts.md).

#pragma once

#include <map>
#include <string>
#include <vector>

#include <FCGlobal.h>

namespace App::Fork
{

/// Inherited features isolated behind a compile-time and a runtime flag.
enum class Feature
{
    NaviCube,     ///< Clickable navigation cube (risk R1)
    CamAdaptive,  ///< CAM Adaptive clearing operation (risk R3)
};

struct FeatureInfo
{
    Feature feature;
    /// Key used for the runtime parameter and the Config() entry.
    const char* key;
    /// Risk register id in docs/DESIGN.md §12.
    const char* riskId;
    /// true when the feature is compiled in (CMake option, default ON).
    bool compiled;
};

/// Parameter group holding the runtime flags. Each flag is a bool named by
/// FeatureInfo::key and defaults to true.
constexpr const char* FeatureParameterPath = "User parameter:BaseApp/Preferences/Fork/Features";

AppExport const std::vector<FeatureInfo>& features();
AppExport const FeatureInfo& info(Feature feature);

/// true when the feature is compiled into this build.
AppExport bool isCompiled(Feature feature);

/// true when the feature is compiled in and the runtime flag is not set to false.
AppExport bool isEnabled(Feature feature);

/// Writes "Fork.Feature.<key>.Compiled" = "1"/"0" for every feature, so Python
/// code can read the compile-time state with FreeCAD.ConfigGet().
AppExport void publishToConfig(std::map<std::string, std::string>& config);

}  // namespace App::Fork
