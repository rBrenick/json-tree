import collections
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
        self.batch_modify_widget.prefix_line_edit.setText("SOME_")

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

    def modify_rename(self):
        modify_keys = "keys" in self.modify_type_chooser.currentText().lower()
        modify_values = "value" in self.modify_type_chooser.currentText().lower()

        for item in self.json_tree.get_selected_items(keys=modify_keys, values=modify_values):

            safe_to_modify = True

            # check we're not trying to modify unsupported types
            if modify_values and item.column() == data_tree.lk.row_value:
                item_type = self.json_tree.get_type_from_item(item)
                if item_type != "str":
                    safe_to_modify = False

            if safe_to_modify:
                current_data = item.index().data()
                modified_data = self.batch_modify_widget.modify_string(current_data)
                item.setText(modified_data)

            if self.modify_hierarchy.isChecked():
                self._recursive_item_modify(item, modify_keys=modify_keys, modify_values=modify_values)

    def _recursive_item_modify(self, root_item, modify_keys=True, modify_values=True):
        for i in range(root_item.rowCount()):
            key_child_item = root_item.child(i, data_tree.lk.row_key)
            item_type = self.json_tree.get_type_from_item(key_child_item)

            if modify_keys:
                current_text = key_child_item.index().data()
                new_text = self.batch_modify_widget.modify_string(current_text)
                key_child_item.setText(new_text)

            if modify_values:
                value_item = root_item.child(i, data_tree.lk.row_value)

                if item_type == "str":
                    current_text = value_item.index().data()
                    new_text = self.batch_modify_widget.modify_string(current_text)
                    value_item.setText(new_text)

            self._recursive_item_modify(key_child_item, modify_keys=modify_keys, modify_values=modify_values)

    def modify_duplicate(self):
        self.json_tree.action_duplicate_selected_item(select_new_items=True)
        self.modify_rename()

    def test_ui_save_load(self):
        self.path_widget.set_path(EXAMPLE_JSON_PATH)
        self.save_json()


def recursive_modify(data, modify_string_func, mod_key, mod_values):
    if isinstance(data, (dict, collections.OrderedDict)):
        new_data = collections.OrderedDict()
        for key, val in data.items():
            if mod_key:
                key = modify_string_func(key)

            new_data[key] = recursive_modify(val, modify_string_func, mod_key, mod_values)

    elif isinstance(data, (list, tuple)):
        new_data = []
        for val in data:
            new_val = recursive_modify(val, modify_string_func, mod_key, mod_values)
            new_data.append(new_val)
    else:
        new_data = data
        if mod_values and type(data) == str:
            new_data = modify_string_func(data)

    return new_data


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
