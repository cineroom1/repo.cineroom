import xbmcgui
import xbmcaddon

ADDON_ID = xbmcaddon.Addon().getAddonInfo('id')
ADDON_PATH = xbmcaddon.Addon(id=ADDON_ID).getAddonInfo('path')
DONATION_IMAGE = f"{ADDON_PATH}/resources/medias/icons/donate.jpg"

BUTTON_CLOSE = 200

class DonationDialog(xbmcgui.WindowXMLDialog):
    def onInit(self):
        self.getControl(100).setImage(DONATION_IMAGE)

    def onAction(self, action):
        if action in [xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_SELECT_ITEM]:
            self.close()

    def onClick(self, control_id):
        if control_id == BUTTON_CLOSE:
            self.close()