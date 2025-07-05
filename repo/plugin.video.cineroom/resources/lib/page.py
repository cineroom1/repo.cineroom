from xbmcaddon import Addon

addon = Addon()
ITEMS_PER_PAGE = int(addon.getSetting("items_per_page") or 100)
