# SPDX-License-Identifier: LGPL-2.1-or-later
"""Runs in stock FreeCAD: FreeCADCmd -t TestTemplate (from the add-on's folder on the path)."""

import unittest

import FreeCAD


class TestTemplate(unittest.TestCase):
    def test_document_roundtrip(self):
        doc = FreeCAD.newDocument("Template")
        try:
            box = doc.addObject("Part::Box", "Box")
            doc.recompute()
            self.assertTrue(box.Shape.isValid())
        finally:
            FreeCAD.closeDocument(doc.Name)
