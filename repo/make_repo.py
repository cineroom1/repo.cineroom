# make_repo.py
import os
import hashlib

def generate_addons_file(path='repo'):
    addons = []
    for addon in os.listdir(path):
        addon_path = os.path.join(path, addon)
        if os.path.isdir(addon_path):
            addon_xml_path = os.path.join(addon_path, 'addon.xml')
            with open(addon_xml_path, 'r', encoding='utf-8') as f:
                addons.append(f.read().strip())

    addons_xml = u"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<addons>\n" + "\n".join(addons) + "\n</addons>\n"
    with open("addons.xml", "w", encoding="utf-8") as f:
        f.write(addons_xml)

    md5_hash = hashlib.md5(addons_xml.encode('utf-8')).hexdigest()
    with open("addons.xml.md5", "w") as f:
        f.write(md5_hash)

    print("addons.xml e addons.xml.md5 gerados com sucesso.")

generate_addons_file()
