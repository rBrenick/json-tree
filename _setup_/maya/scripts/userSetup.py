import sys
import site
import inspect
import os

def _json_tree_site_dir_setup():
    dirname = os.path.dirname
    
    # Add site-packages to sys.path
    package_dir = dirname(dirname(dirname(dirname(inspect.getfile(inspect.currentframe())))))
    
    if package_dir not in sys.path:
        site.addsitedir(package_dir)

_json_tree_site_dir_setup()


try:
    import json_tree
    json_tree.startup()
except Exception as e:
    print(e)




