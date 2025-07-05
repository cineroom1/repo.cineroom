import xbmcgui
import xbmcaddon

ADDON_ID = 'plugin.video.cineroom'
ADDON_PATH = xbmcaddon.Addon(id=ADDON_ID).getAddonInfo('path')
DONATION_IMAGE = f"{ADDON_PATH}/resources/images/donation.jpg"

class DonationDialog(xbmcgui.WindowXMLDialog):
    def onInit(self):
        self.getControl(100).setImage(DONATION_IMAGE)
        self.getControl(101).setLabel('[COLOR yellow]Muito obrigado pelo seu apoio![/COLOR]')

    def onAction(self, action):
        if action in [xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK]:
            self.close()
