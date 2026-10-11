# SPDX-License-Identifier: LGPL-2.1-or-later
# FORK: Construction workbench (design doc §5). Python only.

set(Construction_SRCS
    Init.py
    InitGui.py
    Build.py
    Cabinet.py
    Checks.py
    ConstructionCommands.py
    ConstructionObjects.py
    ConstructionPanels.py
    CutList.py
    Framing.py
    Joinery.py
    Library.py
    Member.py
    Parts.py
    Room.py
    Sheathing.py
    Shed.py
    TestConstruction.py
    TestConstructionApp.py
    TestConstructionGui.py
)
file(GLOB_RECURSE Construction_DATA RELATIVE ${CMAKE_CURRENT_SOURCE_DIR} Resources/libraries/*.json)
# Tutorials (docs/tutorials/construction) ship with the workbench, opened from its menu.
file(GLOB Construction_TUTORIALS ${CMAKE_SOURCE_DIR}/docs/tutorials/construction/*.md)

add_custom_target(Construction ALL SOURCES ${Construction_SRCS} ${Construction_DATA})

fc_copy_sources(Construction "${CMAKE_BINARY_DIR}/Mod/Construction"
    ${Construction_SRCS} ${Construction_DATA})

install(FILES ${Construction_SRCS} DESTINATION Mod/Construction)
install(FILES ${Construction_TUTORIALS} DESTINATION Mod/Construction/Tutorials)
file(COPY ${Construction_TUTORIALS} DESTINATION "${CMAKE_BINARY_DIR}/Mod/Construction/Tutorials")
foreach(_file ${Construction_DATA})
    get_filename_component(_dir ${_file} DIRECTORY)
    install(FILES ${_file} DESTINATION Mod/Construction/${_dir})
endforeach()
