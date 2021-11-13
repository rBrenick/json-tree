def main(*args, **kwargs):
    from . import json_tree_ui
    return json_tree_ui.main(*args, **kwargs)


def reload_modules():
    import sys
    if sys.version_info.major >= 3:
        from importlib import reload
    else:
        from imp import reload
    
    from . import data_tree
    from . import json_tree_system
    from . import json_tree_ui
    reload(data_tree)
    reload(json_tree_system)
    reload(json_tree_ui)
    

def startup():
    # from maya import cmds
    # cmds.optionVar(query="") # example of finding a maya optionvar
    pass




