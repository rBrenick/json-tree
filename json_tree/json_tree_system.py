import collections
import json
import os


def load_json(json_path):
    if not os.path.exists(json_path):
        return

    with open(json_path, "r") as fp:
        json_data = json.load(fp, object_pairs_hook=collections.OrderedDict)
    return json_data


def save_json(json_data, json_path):
    with open(json_path, "w+") as fp:
        json.dump(json_data, fp, indent=2)
