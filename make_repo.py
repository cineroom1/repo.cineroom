import os
import hashlib

REPO_DIR = 'repo'
OUTPUT_XML = 'addons.xml'
OUTPUT_MD5 = 'addons.xml.md5'

def generate_addons_file():
    addons = []
    for addon in sorted(os.listdir(REPO_DIR)):
        addon_path = os.path.join(REPO_DIR, addon)
        addon_xml = os.path.join(addon_path, 'addon.xml')
        if os.path.isdir(addon_path) and os.path.isfile(addon_xml):
            with open(addon_xml, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content.startswith('<?xml'):
                    content = content[content.find('?>')+2:].strip()
                addons.append(content)
    with open(OUTPUT_XML, 'w', encoding='utf-8') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<addons>\n')
        for addon in addons:
            f.write(addon + '\n')
        f.write('</addons>\n')

def generate_md5():
    with open(OUTPUT_XML, 'rb') as f:
        data = f.read()
    md5_hash = hashlib.md5(data).hexdigest()
    with open(OUTPUT_MD5, 'w') as f:
        f.write(md5_hash)

if __name__ == '__main__':
    generate_addons_file()
    generate_md5()
