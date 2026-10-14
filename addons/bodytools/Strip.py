# SPDX-License-Identifier: LGPL-2.1-or-later
"""History strip: a horizontal list of a Body's features. Click sets the marker (Tip),
drag reorders (refused when a dependency would break)."""

from PySide import QtCore, QtWidgets

import History


class HistoryStrip(QtWidgets.QListWidget):
    # shortcut: notify defaults to a message box; tests replace it
    def __init__(self, body, notify=None, parent=None):
        super().__init__(parent)
        self.body = body
        self.notify = notify or (lambda text: QtWidgets.QMessageBox.warning(self, "History", text))
        self.setFlow(QtWidgets.QListView.LeftToRight)
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)
        self.setFixedHeight(56)
        self.itemClicked.connect(self._marker)
        self.refresh()

    def refresh(self):
        self.clear()
        for f in History.features(self.body):
            item = QtWidgets.QListWidgetItem(f.Label)
            item.setData(QtCore.Qt.UserRole, f.Name)
            self.addItem(item)
            if f is self.body.Tip:
                font = item.font()
                font.setBold(True)
                item.setFont(font)

    def _feature(self, name):
        return self.body.Document.getObject(name)

    def _marker(self, item):
        History.set_marker(self.body, self._feature(item.data(QtCore.Qt.UserRole)))
        self.refresh()

    def dropEvent(self, event):
        item = self.currentItem()
        if item is None:
            event.ignore()
            return
        target = self.indexAt(event.position().toPoint() if hasattr(event, "position") else event.pos())
        row = target.row() if target.isValid() else self.count() - 1
        feature = self._feature(item.data(QtCore.Qt.UserRole))
        order = History.features(self.body)
        # index among the Body's group (the Origin comes first)
        dest = self.body.Group.index(order[row]) if row < len(order) else len(self.body.Group) - 1
        event.ignore()  # the view is rebuilt from the Body, not by Qt's own move
        try:
            History.move(self.body, feature, dest)
        except ValueError as e:
            self.notify(str(e))
        self.refresh()
