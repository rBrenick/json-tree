import json
import os
from collections import OrderedDict
from functools import partial, wraps

from . import data_tree_model
from . import ui_utils
from .ui_utils import QtCore, QtWidgets


class LocalConstants:
    row_key = 0
    row_value = 1
    row_type = 2

    add_types = (str, int, float, bool, dict, list)
    default_add_values = {
        str: "STRING",
        dict: {"key": "value"},
        list: ["list_item"],
    }

    default_key_name = "KEY"

    list_types = (list, tuple)
    dict_types = (dict, OrderedDict)
    list_type_names = (list.__name__, tuple.__name__)
    dict_type_names = (dict.__name__, OrderedDict.__name__)
    supports_children_types = list_types + dict_types
    supports_children_type_names = list_type_names + dict_type_names
    none_type_name = str(type(None).__name__)


lk = LocalConstants


class DataTreeWidget(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super(DataTreeWidget, self).__init__(*args, **kwargs)

        self.default_expand_depth = 1
        self._root_type = None

        self.tree_view = QtWidgets.QTreeView()
        self.tree_view.setAlternatingRowColors(True)
        self.tree_view.setSelectionMode(QtWidgets.QTreeView.ExtendedSelection)
        self.tree_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.build_tree_context_menu)

        self.tree_model = data_tree_model.DataModel(self.tree_view)

        self.filter_model = data_tree_model.DataSortFilterProxyModel(self.tree_view, self.tree_model)
        self.filter_model.setRecursiveFilteringEnabled(True)
        self.tree_view.setModel(self.tree_model)

        self.main_layout = QtWidgets.QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.tree_view)
        self.setLayout(self.main_layout)

        # self.test_set_and_get()

    ########################################################
    # Base Functions
    def set_tree_data(self, data):
        self.tree_model.set_data(data)
        self.set_tree_view_settings()

    def get_tree_data(self):
        return self.tree_model.get_data()

    ###########################################################

    def refresh_view(self):
        self.tree_model.refresh_model()
        self.set_tree_view_settings()

    def build_tree_context_menu(self):
        action_list = list()

        action_list.extend([
            {"Cut": self.action_cut_selected_items},
            {"Copy": self.action_copy_selected_items},
            {"Paste": self.action_paste_selected_items},
            {"Duplicate": self.action_duplicate_selected_item},
            {"Delete": self.action_delete_selected_items},
            "-",
            {"Move Up": self.action_move_selected_items_up},
            {"Move Down": self.action_move_selected_items_down},
            "-",
        ])

        for add_type in lk.add_types:
            action_list.append({
                "Add - {}".format(add_type.__name__): partial(self.add_item_of_type, add_type)
            })

        ui_utils.build_menu_from_action_list(action_list)

    def keep_tree_view_state(func):
        @wraps(func)
        def inner(self, *args, **kwargs):

            persistent_indices = self.tree_model.get_all_indices(persistent=True)
            are_expanded = {}
            for persistent_index in persistent_indices:
                if self.tree_view.isExpanded(persistent_index):
                    are_expanded[persistent_index] = True

            self.tree_model.beginInsertRows(QtCore.QModelIndex(), 0, 0)  # this seems to work?

            try:
                return func(self, *args, **kwargs)
            finally:

                self.tree_model.endInsertRows()

                self.tree_view.setExpanded(self.tree_model.index(0, 0, QtCore.QModelIndex()), True)
                for index, is_expanded in are_expanded.items():
                    if index.isValid():
                        self.tree_view.setExpanded(index, True)

        return inner

    def add_item_of_type(self, add_type=str):
        data_to_add = lk.default_add_values.get(add_type, add_type())
        self.add_data_to_selected(data_to_add, merge=False)

    def action_cut_selected_items(self):
        self.action_copy_selected_items()
        self.action_delete_selected_items()

    def action_copy_selected_items(self):
        selected_data = self.get_selected_data()
        json_string = json.dumps(selected_data)
        cb = QtWidgets.QApplication.clipboard()
        cb.setText(json_string)

    def action_paste_selected_items(self):
        cb = QtWidgets.QApplication.clipboard()
        cb_text = cb.text()

        try:
            clipboard_data = json.loads(cb_text, object_pairs_hook=OrderedDict)
        except json.JSONDecodeError as e:
            clipboard_data = None

        if not clipboard_data:
            print("Failed to parse json data from clipboard")
            return

        self.add_data_to_selected(clipboard_data)

    def action_delete_selected_items(self):
        indices_to_remove = self.get_selected_indexes(persistent=True)
        index_parents = [idx.parent() for idx in indices_to_remove if idx.parent() not in indices_to_remove]

        for key_index in indices_to_remove:  # type: QtCore.QModelIndex
            self.tree_model.removeRow(key_index.row(), key_index.parent())

        # since we can't select the item we just deleted, select the parent
        for parent_index in index_parents:
            self.tree_view.setCurrentIndex(parent_index)

    @keep_tree_view_state
    def action_duplicate_selected_item(self, return_new_items=False, key_safety=True):
        pre_indices = list(self.tree_model.get_all_indices(persistent=True))

        for key_index, data in self.get_selected_data(as_raw_data=False).items():
            parent_item = key_index.internalPointer().parent
            self.tree_model.add_data_to_model(
                data_value=data,
                parent_item=parent_item,
                merge=True,
                key_safety=key_safety
            )

        if return_new_items:
            new_items = []
            for index in self.tree_model.get_all_indices():
                if index not in pre_indices:
                    new_items.append(index.internalPointer())
            return new_items

    def set_filter(self, filter_text):
        self.filter_model.setFilterRegExp(
            QtCore.QRegExp(filter_text, QtCore.Qt.CaseInsensitive, QtCore.QRegExp.FixedString)
        )
        if filter_text == "":
            self.tree_view.expandToDepth(self.default_expand_depth)

    @keep_tree_view_state
    def add_data_to_selected(self, data, merge=True):
        for item in self.get_selected_items():  # type: data_tree_model.DataModelItem
            if item.data_type not in lk.supports_children_type_names:
                # print('Item "{}" of type "{}" does not support adding children'.format(item.data_key, item.data_type))
                continue

            # when pasting to a list, make sure it's actually a list being pasted
            data_to_apply = data
            if merge:
                if item.data_type in lk.list_type_names and isinstance(data, lk.dict_types):
                    data_to_apply = list(data.values())

            self.tree_model.add_data_to_model(data_value=data_to_apply, parent_item=item, merge=merge, key_safety=True)

    @keep_tree_view_state
    def action_move_selected_items_up(self):
        for index in self.get_selected_indexes():  # type: QtCore.QModelIndex
            if index.row() == 0:
                continue
            self.tree_model.moveRow(
                index.parent(),
                index.row(),
                index.parent(),
                index.row() - 1
            )

    @keep_tree_view_state
    def action_move_selected_items_down(self):
        for index in reversed(self.get_selected_indexes()):  # type: QtCore.QModelIndex
            parent_max = index.internalPointer().parent.child_count()
            if index.row() + 1 == parent_max:
                continue

            self.tree_model.moveRow(
                index.parent(),
                index.row() + 1,
                index.parent(),
                index.row()
            )

    def get_selected_indexes(self, persistent=False):
        selected_indexes = self.tree_view.selectionModel().selectedRows(data_tree_model.lk.col_key)
        # selected_indexes = [self.filter_model.mapToSource(i) for i in selected_indexes]
        if persistent:
            selected_indexes = [QtCore.QPersistentModelIndex(i) for i in selected_indexes]
        return selected_indexes

    def get_selected_items(self):
        return [idx.internalPointer() for idx in self.get_selected_indexes()]

    def get_selected_data(self, as_raw_data=True, persistent=False):
        selected_indices = self.tree_view.selectionModel().selectedRows(data_tree_model.lk.col_key)

        output_map = {}
        for key_index in selected_indices:
            item = key_index.internalPointer()  # type: data_tree_model.DataModelItem
            selected_key = item.data_key

            output_obj = item.parent.raw_data_type()
            self.tree_model.recursive_fill_data(output_obj, item.parent)

            if as_raw_data:
                if isinstance(output_obj, lk.dict_types):
                    output_map[selected_key] = output_obj.get(selected_key)

                elif isinstance(output_obj, lk.list_types):
                    list_index = int(selected_key[1:-1])
                    output_map[list_index] = output_obj[list_index]
                else:
                    output_map[selected_key] = output_obj
            else:
                if isinstance(output_obj, lk.dict_types):
                    output_map[key_index] = {selected_key: output_obj.get(selected_key)}

                elif isinstance(output_obj, lk.list_types):
                    list_index = int(selected_key[1:-1])
                    output_map[key_index] = output_obj[list_index]
                else:
                    output_map[key_index] = output_obj

        return output_map

    def set_tree_view_settings(self):
        tree_header = self.tree_view.header()
        tree_header.setStretchLastSection(False)
        tree_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tree_view.expandToDepth(self.default_expand_depth)
        self.tree_view.resizeColumnToContents(lk.row_key)

    def test_set_and_get(self):
        example_json_path = os.path.join(os.path.dirname(__file__), "resources", "example_json_data.json")
        with open(example_json_path, "r") as fp:
            test_data = json.load(fp, object_pairs_hook=OrderedDict)
        self.set_tree_data(test_data)
        ui_data = self.get_tree_data()
        assert (ui_data == test_data)

    # End Base Functions
    ####################################################################################
