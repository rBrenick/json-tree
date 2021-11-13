import builtins
import json
import os
from collections import OrderedDict
from functools import partial

from . import ui_utils
from .ui_utils import QtCore, QtWidgets, QtGui


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
        self.tree_view.setSelectionMode(QtWidgets.QTreeView.ExtendedSelection)
        self.tree_view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self.build_tree_context_menu)

        self.tree_model = QtGui.QStandardItemModel()

        self.filter_model = QtCore.QSortFilterProxyModel()
        self.filter_model.setSourceModel(self.tree_model)
        self.filter_model.setRecursiveFilteringEnabled(True)
        self.tree_view.setModel(self.filter_model)

        self.main_layout = QtWidgets.QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.tree_view)
        self.setLayout(self.main_layout)

        self.test_set_and_get()

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
        for key_index in self.get_selected_indexes(persistent=True):  # type: QtCore.QModelIndex
            self.tree_model.removeRow(key_index.row(), key_index.parent())

    def action_duplicate_selected_item(self, select_new_items=False):
        all_new_items = []
        for key_index, data in self.get_selected_data(as_raw_data=False).items():
            parent_item = self.tree_model.itemFromIndex(key_index.parent())
            new_items = self.add_data_to_tree(data_value=data, parent_item=parent_item, merge=True, key_safety=True)
            all_new_items.extend(new_items)

        if select_new_items:
            full_sel = QtCore.QItemSelection()
            for item in all_new_items:
                sel = QtCore.QItemSelection(item.index(), item.index())
                full_sel.append(sel)

            # TODO: select new items
            # self.tree_view.selectionModel().select(full_sel, QtCore.QItemSelectionModel.ClearAndSelect)
            # for index in all_new_items:
            #     print(index.data())

    def set_filter(self, filter_text):
        self.filter_model.setFilterRegExp(
            QtCore.QRegExp(filter_text, QtCore.Qt.CaseInsensitive, QtCore.QRegExp.FixedString)
        )
        if filter_text == "":
            self.tree_view.expandToDepth(self.default_expand_depth)

    def add_data_to_selected(self, data, merge=True):
        selected_keys = self.get_selected_indexes(column=lk.row_key)
        selected_types = self.get_selected_indexes(column=lk.row_type)

        for key_index, type_index in zip(selected_keys, selected_types):
            target_type = type_index.data()

            if target_type not in lk.supports_children_type_names:
                print('Item "{}" of type "{}" does not support adding children'.format(key_index.data(), target_type))
                continue

            # when pasting to a list, make sure it's actually a list being pasted
            data_to_apply = data
            if merge:
                if target_type in lk.list_type_names and isinstance(data, lk.dict_types):
                    data_to_apply = list(data.values())

            sel_item = self.tree_model.itemFromIndex(key_index)
            self.add_data_to_tree(data_value=data_to_apply, parent_item=sel_item, merge=merge, key_safety=True)

    def action_move_selected_items_up(self):
        # TODO: implement this
        # for index in self.get_selected_indexes():
        #     print(index.row())
        #     print(self.tree_model.takeRow(index.row()))
        pass

    def action_move_selected_items_down(self):
        # TODO: implement this
        pass

    ########################################################
    # Base Functions

    def set_tree_data(self, data):
        self.tree_model.clear()
        self.add_data_to_tree(data_value=data)
        self.set_tree_view_settings()

    def get_tree_data(self):
        output_obj = self._root_type()
        for i in range(self.tree_model.rowCount()):
            data_key_item = self.tree_model.index(i, lk.row_key)
            self._recursive_model_to_data(output_obj, parent_index=data_key_item)
        return output_obj

    def get_selected_indexes(self, persistent=False, column=lk.row_key):
        selected_indexes = self.tree_view.selectionModel().selectedRows(column)
        selected_indexes = [self.filter_model.mapToSource(i) for i in selected_indexes]
        if persistent:
            selected_indexes = [QtCore.QPersistentModelIndex(i) for i in selected_indexes]
        return selected_indexes

    def get_selected_items(self, keys=True, values=False):
        columns = []
        columns.append(lk.row_key) if keys else None
        columns.append(lk.row_value) if values else None

        items = []
        for column in columns:
            items.extend([self.tree_model.itemFromIndex(idx) for idx in self.get_selected_indexes(column=column)])

        return items

    def get_selected_data(self, as_raw_data=True, persistent=False):
        selected_indices = self.get_selected_indexes(persistent)
        output_map = {}
        for key_index in selected_indices:
            selected_key = key_index.data(lk.row_key)
            parent_index = key_index.parent()
            if parent_index == self.tree_view.rootIndex():
                continue

            parent_type_index = self.tree_model.index(
                parent_index.row(),
                lk.row_type,
                parent=parent_index.parent(),
            )

            row_type = parent_type_index.data()
            output_obj_type = builtins.__dict__.get(row_type)
            if row_type == OrderedDict.__name__:
                output_obj = OrderedDict()
            else:
                output_obj = output_obj_type()

            # fill output object
            self._recursive_model_to_data(output_obj, parent_index)

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
        self.tree_model.setHorizontalHeaderLabels(["Key", "Value", "Type"])
        tree_header = self.tree_view.header()
        tree_header.setStretchLastSection(False)
        tree_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tree_view.expandToDepth(self.default_expand_depth)
        self.tree_view.resizeColumnToContents(lk.row_key)

    def add_data_to_tree(self, data_key="", data_value=None, parent_item=None, merge=False, key_safety=False):
        if parent_item is None:
            parent_item = self.tree_model.invisibleRootItem()
            self._root_type = type(data_value)

        new_key_items = []
        if isinstance(data_value, (dict, OrderedDict)):
            if not merge:
                if key_safety:
                    data_key = self.get_unique_key(parent_item, target_name=data_key)

                dict_parent = QtGui.QStandardItem(data_key)
                dict_parent_data = QtGui.QStandardItem()
                dict_parent_type = QtGui.QStandardItem(type(data_value).__name__)
                parent_item.appendRow([dict_parent, dict_parent_data, dict_parent_type])
                new_key_items.append(dict_parent)
                parent_item = dict_parent

            for k, v in data_value.items():
                if key_safety:
                    k = self.get_unique_key(parent_item, target_name=k, check_type=False)  # skip type check for speed

                new_key_items.extend(self.add_data_to_tree(
                    data_key=k,
                    data_value=v,
                    parent_item=parent_item,
                ))

        elif isinstance(data_value, (list, tuple)):
            if not merge:
                if key_safety:
                    data_key = self.get_unique_key(parent_item, target_name=data_key)  # skip type check for speed

                list_parent = QtGui.QStandardItem(data_key)
                list_parent_data = QtGui.QStandardItem()
                list_parent_type = QtGui.QStandardItem(type(data_value).__name__)
                parent_item.appendRow([list_parent, list_parent_data, list_parent_type])
                new_key_items.append(list_parent)
                parent_item = list_parent

            for i, list_item in enumerate(data_value):
                list_index_key = "[{}]".format(i)
                if key_safety:
                    list_index_key = "[{}]".format(parent_item.rowCount())

                new_key_items.extend(self.add_data_to_tree(
                    data_key=list_index_key,
                    data_value=list_item,
                    parent_item=parent_item,
                ))

        else:
            if key_safety:
                data_key = self.get_unique_key(parent_item, target_name=data_key)

            data_item_key = QtGui.QStandardItem(data_key)
            data_value_item = QtGui.QStandardItem(str(data_value))
            data_type_item = QtGui.QStandardItem(type(data_value).__name__)
            parent_item.appendRow([data_item_key, data_value_item, data_type_item])
            new_key_items.append(data_item_key)

        return new_key_items

    def get_type_from_item(self, key_item):
        if key_item.parent() is None:
            return self._root_type.__name__
        return self.tree_model.index(key_item.row(), lk.row_type, key_item.parent().index()).data()

    def get_unique_key(self, parent_item, target_name="", check_type=True):
        if check_type:
            parent_type = self.get_type_from_item(parent_item)

            # parent type is list, key will be the next available list index
            if parent_type in lk.list_type_names:
                return "[{}]".format(parent_item.rowCount())

        # make sure this value isn't blank
        if target_name == "":
            target_name = lk.default_key_name

        output_name = target_name
        key_names = self.get_key_names(parent_item)

        while output_name in key_names:
            output_name = "{}_1".format(output_name)

        return output_name

    @staticmethod
    def get_key_names(item):
        key_names = []
        for i in range(item.rowCount()):
            key_names.append(item.index().child(i, lk.row_key).data())
        return key_names

    def _recursive_model_to_data(self, output_obj, parent_index):
        for i in range(self.tree_model.rowCount(parent_index)):
            data_key_index = self.tree_model.index(i, lk.row_key, parent_index)
            data_value_index = self.tree_model.index(i, lk.row_value, parent_index)
            data_type_index = self.tree_model.index(i, lk.row_type, parent_index)
            data_type = data_type_index.data()

            if data_type in lk.dict_type_names:
                data_value = self._recursive_model_to_data(OrderedDict(), parent_index=data_key_index)
            elif data_type in lk.list_type_names:
                data_value = self._recursive_model_to_data([], parent_index=data_key_index)
            else:
                data_value = data_value_index.data()
                type_cls = builtins.__dict__.get(data_type)

                if data_type == lk.none_type_name:
                    data_value = None

                elif type_cls == bool:
                    data_value = data_value == "True"

                elif type_cls is not None:
                    data_value = type_cls(data_value)

            if isinstance(output_obj, lk.list_types):
                output_obj.append(data_value)
            else:
                output_obj[data_key_index.data()] = data_value

        return output_obj

    def test_set_and_get(self):
        example_json_path = os.path.join(os.path.dirname(__file__), "resources", "example_json_data.json")
        with open(example_json_path, "r") as fp:
            test_data = json.load(fp, object_pairs_hook=OrderedDict)
        self.set_tree_data(test_data)
        ui_data = self.get_tree_data()
        assert (ui_data == test_data)

    # End Base Functions
    ####################################################################################
