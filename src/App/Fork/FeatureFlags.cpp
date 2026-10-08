// SPDX-License-Identifier: LGPL-2.1-or-later
// FORK: feature flags for inherited features with risk-register exposure.

#include "FeatureFlags.h"

#include <stdexcept>

#include <App/Application.h>
#include <Fork/FeatureConfig.h>

namespace App::Fork
{

const std::vector<FeatureInfo>& features()
{
    static const std::vector<FeatureInfo> list {
        {Feature::NaviCube, "NaviCube", "R1", CADAPP_FEATURE_NAVICUBE != 0},
        {Feature::CamAdaptive, "CAMAdaptive", "R3", CADAPP_FEATURE_CAM_ADAPTIVE != 0},
    };
    return list;
}

const FeatureInfo& info(Feature feature)
{
    for (const auto& item : features()) {
        if (item.feature == feature) {
            return item;
        }
    }
    throw std::out_of_range("unknown fork feature");
}

bool isCompiled(Feature feature)
{
    return info(feature).compiled;
}

bool isEnabled(Feature feature)
{
    const auto& item = info(feature);
    if (!item.compiled) {
        return false;
    }
    auto group = App::GetApplication().GetParameterGroupByPath(FeatureParameterPath);
    return group->GetBool(item.key, true);
}

void publishToConfig(std::map<std::string, std::string>& config)
{
    for (const auto& item : features()) {
        config[std::string("Fork.Feature.") + item.key + ".Compiled"] = item.compiled ? "1" : "0";
    }
}

}  // namespace App::Fork
