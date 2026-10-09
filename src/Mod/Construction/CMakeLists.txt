# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: Construction workbench (design doc §5). Python only.

set(Construction_SRCS
    Init.py
    InitGui.py
    Cabinet.py
    Checks.py
    ConstructionCommands.py
    ConstructionObjects.py
    CutList.py
    Framing.py
    Library.py
    Member.py
    TestConstruction.py
)
file(GLOB_RECURSE Construction_DATA RELATIVE ${CMAKE_CURRENT_SOURCE_DIR} Resources/libraries/*.json)

add_custom_target(Construction ALL SOURCES ${Construction_SRCS} ${Construction_DATA})

fc_copy_sources(Construction "${CMAKE_BINARY_DIR}/Mod/Construction"
    ${Construction_SRCS} ${Construction_DATA})

install(FILES ${Construction_SRCS} DESTINATION Mod/Construction)
foreach(_file ${Construction_DATA})
    get_filename_component(_dir ${_file} DIRECTORY)
    install(FILES ${_file} DESTINATION Mod/Construction/${_dir})
endforeach()
