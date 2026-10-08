# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: build configuration for the CADApp fork: branding and feature flags.
# Included once from the top-level CMakeLists.txt.

include(${CMAKE_SOURCE_DIR}/branding/branding.cmake)

# Inherited features with risk-register exposure (design doc §12, docs/inherited-conflicts.md).
# Default ON per the inherited-feature rule. OFF removes the feature from the build.
option(CADAPP_FEATURE_NAVICUBE "Build the clickable navigation cube (risk R1)" ON)
option(CADAPP_FEATURE_CAM_ADAPTIVE "Build the CAM Adaptive operation (risk R3)" ON)

foreach(_flag NAVICUBE CAM_ADAPTIVE)
    if(CADAPP_FEATURE_${_flag})
        set(CADAPP_FEATURE_${_flag}_VALUE 1)
    else()
        set(CADAPP_FEATURE_${_flag}_VALUE 0)
    endif()
endforeach()

configure_file(${CMAKE_SOURCE_DIR}/cMake/CADApp/BrandingConfig.h.in
               ${CMAKE_BINARY_DIR}/src/Fork/BrandingConfig.h)
configure_file(${CMAKE_SOURCE_DIR}/cMake/CADApp/FeatureConfig.h.in
               ${CMAKE_BINARY_DIR}/src/Fork/FeatureConfig.h)

message(STATUS "CADApp: product name ${CADAPP_EXE_NAME}, app id ${CADAPP_APP_ID}")
message(STATUS "CADApp: NaviCube ${CADAPP_FEATURE_NAVICUBE}, CAM Adaptive ${CADAPP_FEATURE_CAM_ADAPTIVE}")
