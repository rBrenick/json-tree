import builtins
import json
import os
import sys
from collections import OrderedDict

from json_tree.ui_utils import QtCore, QtWidgets

Qt = QtCore.Qt  # create shortcut to Qt


class LocalConstants:
    col_key = 0
    col_value = 1
    col_type = 2

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


class DataModelItem(object):
    def __init__(self, data_key=None, data_value=None, parent=None, key_safety=False):
        self.data_key = data_key
        self.data_value = data_value
        self.raw_data_type = type(data_value)
        self.data_type = self.raw_data_type.__name__

        self.parent = parent  # type: DataModelItem
        if parent:
            parent.add_child(self)

        if key_safety:
            self.data_key = self.get_unique_key(data_key)

        self.row = 0
        self.children = []

    def get_unique_key(self, target_name=""):
        if self.parent.raw_data_type in lk.list_types:
            return "[{}]".format(self.parent.children.index(self))

        # make sure this value isn't blank
        if target_name == "":
            target_name = lk.default_key_name

        output_name = target_name
        key_names = self.parent.get_child_keys()

        while output_name in key_names:
            output_name = "{}_1".format(output_name)

        return output_name

    def child_count(self):
        return len(self.children)

    def add_child(self, child_item, index=None):
        child_item.parent = self
        if index is None:
            child_item.row = self.child_count()
            self.children.append(child_item)
        else:
            self.children.insert(index, child_item)
            for i, item in enumerate(self.children):
                item.row = i  # update row mapping

    def remove_child(self, item):
        self.children.remove(item)

    def get_child_keys(self):
        return [child.data_key for child in self.children]

    def set_value(self, new_value):
        try:
            type_cls = builtins.__dict__.get(self.data_type)

            if type_cls == bool:
                # I let you be really sloppy with typing here
                if new_value.lower().startswith("t"):
                    data_value = True
                elif new_value.lower() in ["1", "y"]:
                    data_value = True
                elif new_value.lower().startswith("f"):
                    data_value = False
                else:
                    data_value = False

                data_value = data_value
            else:
                data_value = type_cls(new_value)

            self.data_value = data_value

        except Exception as e:
            print('Failed to convert "{}" to type "{}"'.format(new_value, self.data_type))


class DataModel(QtCore.QAbstractItemModel):
    def __init__(self, *args, **kwargs):
        super(DataModel, self).__init__(*args, **kwargs)

        self.root_item = DataModelItem()

    ##########################################################################################
    # Overloads

    def flags(self, index):
        if index.column() < 3:
            return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            if section == lk.col_key:
                return "Key"
            elif section == lk.col_value:
                return "Value"
            elif section == lk.col_type:
                return "Type"

        return None

    def parent(self, child):
        if not child.isValid():
            return QtCore.QModelIndex()
        child_item = child.internalPointer()
        dir(child_item)  # run this to make sure child_item has a parent property
        parent_item = child_item.parent
        if parent_item == self.root_item:
            return QtCore.QModelIndex()
        return self.createIndex(parent_item.row, 0, parent_item)

    def rowCount(self, parent):
        if parent.isValid():
            return parent.internalPointer().child_count()
        else:
            return self.root_item.child_count()

    def columnCount(self, *args):
        return 3

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        if parent.isValid():
            parent_item = parent.internalPointer()
        else:
            parent_item = self.root_item

        child = parent_item.children[row]
        if not child:
            return QtCore.QModelIndex()
        return self.createIndex(row, column, child)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return

        item = index.internalPointer()  # type: DataModelItem
        if role == Qt.DisplayRole or role == Qt.EditRole:
            column = index.column()
            if column == lk.col_key:
                if item.parent.raw_data_type in lk.list_types:
                    return "[{}]".format(item.parent.children.index(item))

                return item.data_key

            if column == lk.col_value:
                if item.data_value is None:
                    return "None"
                elif item.raw_data_type == bool:
                    return str(item.data_value).title()
                elif item.raw_data_type in lk.supports_children_types:
                    return "-------- {} items --------".format(item.child_count())
                return str(item.data_value)

            if column == lk.col_type:
                return item.data_type

        return None

    def setData(self, index, value, role):
        if not index.isValid():
            return False

        if not value:
            return False

        if role == Qt.EditRole:
            item = index.internalPointer()  # type: DataModelItem

            column = index.column()
            if column == lk.col_key:
                item.data_key = value
            if column == lk.col_value:
                if not item.set_value(value):
                    return False
            if column == lk.col_type:
                item.data_type = value

            return True

    def removeRow(self, row, parent):
        self.beginRemoveRows(parent, 0, 0)
        index = self.index(row, lk.col_key, parent)
        if not index.isValid():
            self.endRemoveRows()
            return False
        item = index.internalPointer()  # type: DataModelItem
        item.parent.remove_child(item)
        self.endRemoveRows()
        return True

    def moveRow(self, sourceParent, sourceRow, destinationParent, destinationChild):
        self.beginMoveRows(sourceParent, sourceRow, sourceRow, destinationParent, destinationChild)
        index = self.index(sourceRow, lk.col_key, sourceParent)

        if not index.isValid():
            self.endMoveRows()
            return False

        item = index.internalPointer()  # type: DataModelItem

        item.parent.remove_child(item)
        item.parent.add_child(item, index=destinationChild)

        self.endMoveRows()
        return True

    ##########################################################################################

    def get_all_indices(self, index=None, persistent=False):
        if not index:
            index = QtCore.QModelIndex()

        for i in range(self.rowCount(index)):
            child = self.index(i, 0, index)
            if persistent:
                child = QtCore.QPersistentModelIndex(child)
            yield child
            for grand_child in self.get_all_indices(child, persistent=persistent):
                yield grand_child

    def set_data(self, data):
        self.beginResetModel()
        self.root_item = DataModelItem(data_value=type(data)())
        if data is None:
            return
        self.add_data_to_model(data_value=data, parent_item=self.root_item)
        self.endResetModel()

    def get_index_from_item(self, item):
        # TODO: improve this with UUIDs or something
        for index in self.get_all_indices():
            if index.internalPointer() is item:
                return index
        return QtCore.QModelIndex()

    def add_data_to_indices(self, index_data_map, merge=True):
        for index_data in index_data_map:
            index = index_data[0]
            data = index_data[1]

            item = index.internalPointer()

            data_length = get_data_length(data)
            start = item.child_count()
            end = start + data_length - 1

            self.beginInsertRows(index, start, end)

            self.add_data_to_model(data_value=data, parent_item=item, merge=merge, key_safety=True)

            self.endInsertRows()

    def add_data_to_model(self, data_key="", data_value=None, parent_item=None, merge=False, key_safety=False):
        if isinstance(data_value, lk.dict_types):
            if not merge:
                parent_item = DataModelItem(data_key=data_key, data_value={}, parent=parent_item, key_safety=key_safety)

            for k, v in data_value.items():
                self.add_data_to_model(
                    data_key=k,
                    data_value=v,
                    parent_item=parent_item,
                    key_safety=key_safety,
                )

        elif isinstance(data_value, lk.list_types):
            if not merge:
                parent_item = DataModelItem(data_key=data_key, data_value=[], parent=parent_item, key_safety=key_safety)

            for i, v in enumerate(data_value):
                self.add_data_to_model(
                    data_key="[{}]".format(i),
                    data_value=v,
                    parent_item=parent_item,
                    key_safety=key_safety,
                )
        else:
            DataModelItem(data_key, data_value, parent=parent_item, key_safety=key_safety)

    def get_data(self):
        output_obj = self.root_item.raw_data_type()  # create instance of root type
        for child in self.root_item.children:
            self.recursive_fill_data(output_obj, item=child)
        return output_obj

    def recursive_fill_data(self, output_obj, item):
        for child in item.children:  # type:DataModelItem

            if child.data_type in lk.dict_type_names:
                data_value = self.recursive_fill_data(OrderedDict(), child)

            elif child.data_type in lk.list_type_names:
                data_value = self.recursive_fill_data([], child)
            else:
                data_value = child.data_value

            if isinstance(output_obj, lk.list_types):
                output_obj.append(data_value)
            else:
                output_obj[child.data_key] = data_value

        return output_obj

    def refresh_model(self):
        self.beginResetModel()
        self.endResetModel()


class DataSortFilterProxyModel(QtCore.QSortFilterProxyModel):
    def __init__(self, parent=None, source_model=None):
        super(DataSortFilterProxyModel, self).__init__(parent)
        self.setSourceModel(source_model)
        self.setSortCaseSensitivity(Qt.CaseInsensitive)
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)

    def get_all_indices(self, index=None, persistent=False):
        if not index:
            index = QtCore.QModelIndex()

        for i in range(self.rowCount(index)):
            child = self.index(i, 0, index)
            if persistent:
                child = QtCore.QPersistentModelIndex(child)
            yield child
            for grand_child in self.get_all_indices(child, persistent=persistent):
                yield grand_child

    def get_index_from_item(self, item):
        for index in self.get_all_indices():
            if index.internalPointer() is item:
                return index
        return QtCore.QModelIndex()


def get_data_length(data):
    if isinstance(data, lk.dict_types):
        return len(data.keys())
    elif isinstance(data, lk.list_types):
        return len(data)
    return 1


def recursive_get_data_length(data, merge=False):
    data_length = 0
    if isinstance(data, lk.dict_types):
        if not merge:
            data_length += 1

        for k, v in data.items():
            data_length += recursive_get_data_length(v, merge)

    elif isinstance(data, lk.list_types):
        if not merge:
            data_length += 1

        for v in data:
            data_length += recursive_get_data_length(v, merge)

    else:
        data_length += 1

    return data_length


def test_data_model_view():
    app = QtWidgets.QApplication(sys.argv)
    win = QtWidgets.QMainWindow()

    tree = QtWidgets.QTreeView()
    tree.setAlternatingRowColors(True)
    tree.setSelectionMode(QtWidgets.QTreeView.ExtendedSelection)
    model = DataModel(tree)

    filter_model = DataSortFilterProxyModel(tree, model)
    tree.setModel(filter_model)

    ######################################
    # Test Data
    example_json_path = os.path.join(os.path.dirname(__file__), "resources", "example_json_data.json")
    with open(example_json_path, "r") as fp:
        test_data = json.load(fp, object_pairs_hook=OrderedDict)
    model.set_data(test_data)
    ui_data = model.get_data()

    print("TEST_DATA", test_data)
    print("UI_DATA", ui_data)
    assert (ui_data == test_data)
    ######################################

    tree_header = tree.header()
    tree_header.setStretchLastSection(False)
    tree_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
    tree.expandToDepth(2)
    tree.resizeColumnToContents(lk.col_key)

    win.setCentralWidget(tree)
    win.show()
    win.resize(1000, 1000)
    sys.exit(app.exec_())


if __name__ == '__main__':
    test_data_model_view()
