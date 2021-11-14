import os.path
import sys

from . import batch_widget
from . import data_tree
from . import json_tree_system as system
from . import ui_utils
from .ui_utils import QtWidgets, QtGui

# if running in standalone, create app
EXISTING_QAPP = QtWidgets.QApplication.instance()
STANDALONE_QAPP = None if EXISTING_QAPP else QtWidgets.QApplication(sys.argv)

EXAMPLE_JSON_PATH = os.path.join(os.path.dirname(__file__), "resources", "example_json_data.json")


class JsonTreeWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(JsonTreeWidget, self).__init__(*args, **kwargs)
        self.main_layout = QtWidgets.QVBoxLayout()

        self.path_widget = ui_utils.QtPathWidget(
            settings_name="JsonTree",
            file_filter="JSON (*.json)",
            recent_paths_amount=100,
        )

        self.filter_widget = QtWidgets.QLineEdit()
        self.filter_widget.setPlaceholderText("filter")
        self.filter_widget.setClearButtonEnabled(True)
        self.filter_widget.textEdited.connect(self.filter_data)

        self.json_tree = data_tree.DataTreeWidget()

        self.batch_modify_widget = batch_widget.BatchModifyWidget()

        ###########################################################
        # JSON tree specific ui
        self.modify_hierarchy = QtWidgets.QCheckBox("Modify Hierarchy")
        self.modify_hierarchy.setChecked(True)
        self.modify_type_chooser = QtWidgets.QComboBox()
        self.modify_type_chooser.addItems(["Keys & Values", "Keys", "Values"])
        self.modify_rename_button = QtWidgets.QPushButton("Rename")
        self.modify_duplicate_button = QtWidgets.QPushButton("Duplicate")

        # connect signals
        self.modify_rename_button.clicked.connect(self.modify_rename)
        self.modify_duplicate_button.clicked.connect(self.modify_duplicate)

        modify_layout = QtWidgets.QHBoxLayout()
        modify_layout.setContentsMargins(0, 0, 0, 0)
        modify_layout.addWidget(self.modify_hierarchy)
        modify_layout.addWidget(self.modify_type_chooser)
        modify_layout.addWidget(self.modify_rename_button)
        modify_layout.addWidget(self.modify_duplicate_button)
        ###########################################################

        self.main_layout.addWidget(self.path_widget)
        self.main_layout.addWidget(self.filter_widget)
        self.main_layout.addWidget(self.json_tree)
        self.main_layout.addWidget(self.batch_modify_widget)
        self.main_layout.addLayout(modify_layout)
        self.setLayout(self.main_layout)

        # connect signals
        self.path_widget.path_changed.connect(self.load_json)
        self.test_ui_save_load()

    def filter_data(self):
        filter_text = self.filter_widget.text()
        self.json_tree.set_filter(filter_text)

    def load_json(self, new_path):
        json_data = system.load_json(new_path)
        if json_data is None:
            return
        self.json_tree.set_tree_data(json_data)

    def save_json(self):
        json_path = self.path_widget.path()
        data_from_ui = self.json_tree.get_tree_data()
        json_path = json_path.replace(".json", "_TEST.json")
        system.save_json(data_from_ui, json_path)
        print("Saved Json to: {}".format(json_path))

    def save_json_as(self):
        if self.path_widget.open_dialog_and_set_path():
            self.save_json()

    def modify_rename(self, items=None, recursive=None):
        if items is None:
            items = self.json_tree.get_selected_items()
        if recursive is None:
            recursive = self.modify_hierarchy.isChecked()

        modify_keys = "keys" in self.modify_type_chooser.currentText().lower()
        modify_values = "value" in self.modify_type_chooser.currentText().lower()

        for item in items:  # type: data_tree.data_tree_model.DataModelItem
            rename_item(
                item=item,
                modify_string_func=self.batch_modify_widget.modify_string,
                mod_key=modify_keys,
                mod_values=modify_values,
                recursive=recursive,
            )

    def modify_duplicate(self):
        new_items = self.json_tree.action_duplicate_selected_item(return_new_items=True, key_safety=False)
        self.modify_rename(new_items, recursive=False)

    def test_ui_save_load(self):
        self.path_widget.set_path(EXAMPLE_JSON_PATH)
        self.save_json()


def rename_item(item, modify_string_func, mod_key, mod_values, recursive=False):
    if mod_key:
        item.data_key = modify_string_func(item.data_key)

    if mod_values:
        if item.data_type == "str":
            item.set_value(modify_string_func(item.data_value))

    if recursive:
        for child in item.children:  # type: data_tree.data_tree_model.DataModelItem
            rename_item(child, modify_string_func, mod_key, mod_values, recursive=recursive)


class JsonTreeWindow(ui_utils.ToolWindow):
    def __init__(self):
        super(JsonTreeWindow, self).__init__()
        self.ui = JsonTreeWidget()
        self.setCentralWidget(self.ui)
        self.resize(1000, 1000)

        menu_bar = QtWidgets.QMenuBar()
        file_menu = menu_bar.addMenu("File")
        file_menu.setTearOffEnabled(True)
        file_menu.addAction("Open", self.ui.path_widget.open_dialog_and_set_path, QtGui.QKeySequence("Ctrl+O"))
        file_menu.addAction("Save", self.ui.save_json, QtGui.QKeySequence("Ctrl+S"))
        file_menu.addAction("Save As...", self.ui.save_json_as, QtGui.QKeySequence("Ctrl+Shift+S"))

        edit_menu = menu_bar.addMenu("Edit")
        edit_menu.setTearOffEnabled(True)
        edit_menu.addAction("Cut",
                            self.ui.json_tree.action_cut_selected_items,
                            QtGui.QKeySequence("Ctrl+X"),
                            )

        edit_menu.addAction("Copy",
                            self.ui.json_tree.action_copy_selected_items,
                            QtGui.QKeySequence("Ctrl+C"),
                            )

        edit_menu.addAction("Paste",
                            self.ui.json_tree.action_paste_selected_items,
                            QtGui.QKeySequence("Ctrl+V"),
                            )

        edit_menu.addAction("Duplicate",
                            self.ui.json_tree.action_duplicate_selected_item,
                            QtGui.QKeySequence("Ctrl+D"),
                            )

        edit_menu.addAction("Delete",
                            self.ui.json_tree.action_delete_selected_items,
                            QtGui.QKeySequence("DEL"),
                            )

        edit_menu.addSeparator()

        edit_menu.addAction("Move Up",
                            self.ui.json_tree.action_move_selected_items_up,
                            QtGui.QKeySequence("Alt+Up"),
                            )

        edit_menu.addAction("Move Down",
                            self.ui.json_tree.action_move_selected_items_down,
                            QtGui.QKeySequence("Alt+Down"),
                            )

        self.setMenuBar(menu_bar)


def main(refresh=False):
    win = JsonTreeWindow()
    win.main(refresh=refresh)

    if STANDALONE_QAPP:
        sys.exit(STANDALONE_QAPP.exec_())

    return win


if __name__ == "__main__":
    main()
