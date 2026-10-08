# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: single branding configuration for the CADApp fork (design doc §2, §4.2).
#
# Every product-name string set by the build comes from this file. Values are
# written to <build>/src/Fork/BrandingConfig.h by cMake/CADApp/CADAppFork.cmake.
# "CADApp" is a placeholder; the final name requires trademark clearance (§11, §12 R17).

# Application name. Also names the per-user data/config directory, which must
# differ from upstream ("FreeCAD") so both can be installed side by side.
set(CADAPP_EXE_NAME "CADApp")

# Vendor name. Not used in the data directory path (AppDataSkipVendor=true).
set(CADAPP_EXE_VENDOR "CADApp")

# Reverse-DNS application id: desktop file name, macOS bundle id, Wayland app id.
set(CADAPP_APP_ID "io.github.dboshardy.CADApp")

# Project page shown in Help > About. Not contacted by the application.
set(CADAPP_MAINTAINER_URL "https://github.com/dboshardy/MyCAD")

# Factual attribution and non-affiliation statement (§2, §12 R16, R17).
set(CADAPP_ATTRIBUTION "Based on FreeCAD (https://www.freecad.org), licensed under LGPL-2.1-or-later.")
set(CADAPP_NON_AFFILIATION "CADApp is not affiliated with, endorsed by, or sponsored by the FreeCAD project or the FreeCAD Project Association.")
