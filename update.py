import platform
import os
import shutil
import json

CONFIG_DIR = "configs/"
DEFAULT_CONFIG = os.path.join(CONFIG_DIR, "DEFAULT_CONFIG.json")
backup_folder = "configs_backup/"

# Check if new key is in the old dict
# if no, then add the new key and its value pair to the old dict
# if yes, check if the new key is a dict 
# if yes, get all the keys of the new key's dict and all the key's of the old key's dict and compare those
# if no, return

def compare_dict_and_update(dict_new, dict_old):
    keys = dict_new.keys()
    for key in keys:
        if key in dict_old:
            if isinstance(dict_new[key], dict) and isinstance(dict_old[key], dict):
                compare_dict_and_update(dict_new[key], dict_old[key])
            elif isinstance(dict_new[key], dict) and not isinstance(dict_old[key], dict):
                dict_old[key] = dict_new[key]
            elif not isinstance(dict_new[key], dict) and isinstance(dict_old[key], dict):
                dict_old[key] = dict_new[key]
        else:
            dict_old[key] = dict_new[key]

def test_cases():
    new = {0: 1, 1: 1, 2: 2}
    old = {0: 2, 1: 2, 2: 3}
    compare_dict_and_update(new, old)
    print(f"New: {new}, old: {old}")
    assert(old[0] == 2)
    assert(old[1] == 2)
    assert(old[2] == 3)

    new = {0: 1, 1: 10}
    old = {0: 15}
    compare_dict_and_update(new, old)
    print(f"New: {new}, old: {old}")
    assert(old[0] == 15)
    assert(old[1] == 10)

    new = {0: {0: 10, 1: 10}, 1: 10}
    old = {0: 1, 1: 15}
    compare_dict_and_update(new, old)
    print(f"New: {new}, old: {old}")
    assert(list(old[0].keys()) == [0, 1])
    assert(old[1] == 15)

    new = {0: 1, 1: 1}
    old = {0: {1: 1}, 2: 2, 1: 3}
    compare_dict_and_update(new, old)
    assert(isinstance(old[0], int))
    assert(old[2] == 2)
    assert(old[1] == 3)

def backup_and_update():
    # 1. Make a backup of the configs/ folder
    try:
        shutil.copytree(CONFIG_DIR, backup_folder)
    except Exception as e:
        print(f"Errored while creating a backup of the `configs/` folder. Aborting and exiting. \nError: \n{e}")
        quit()

    # 2. git checkout .
    os.system("git checkout .")

    # 3. git pull
    os.system("git pull")

    # 4. Get new default json from the newly pulled configs/
    with open(DEFAULT_CONFIG) as json_file:
        new_default_config = json.load(json_file)

    # 5. Go through 
    for filepath in os.listdir(backup_folder):
        if ".json" in filepath:
            new_path = os.path.join(CONFIG_DIR, filepath)
            filepath = os.path.join(backup_folder, filepath)
            with open(filepath) as json_file:
                old_template = json.load(json_file)
            compare_dict_and_update(new_default_config, old_template)
            with open(new_path, 'w') as outfile:
                json.dump(old_template, outfile, indent=4)

    # Remove the backup folder
    # windows
    os.system(f"rd /s /q {backup_folder}")

if __name__ == "__main__":
    # test_cases()
    backup_and_update()